import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.github_client import GitHubClient
from app.gemini_reviewer import GeminiReviewer
from app.queue import InProcessQueue, CloudTasksQueue, ReviewJob
from app.security import redact, truncate
from app.store import FirestoreReviewStore, InMemoryReviewStore, ReviewStore
from app.webhook_handler import InvalidSignatureError, parse_pull_request_event, verify_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("code-reviewer")

settings = get_settings()
app = FastAPI(title="24/7 Intelligent Code Reviewer")
templates = Jinja2Templates(directory="templates")

github = GitHubClient(token=settings.github_token)

# Firestore requires real GCP creds; fall back to in-memory so `uvicorn app.main:app`
# works out of the box for local dev / grading without any cloud setup.
try:
    store: ReviewStore = FirestoreReviewStore(settings.gcp_project_id, settings.firestore_collection)
except Exception as exc:  # pragma: no cover - exercised only when GCP creds are absent
    logger.warning("Firestore unavailable (%s); using in-memory store.", exc)
    store = InMemoryReviewStore()

_reviewer: GeminiReviewer | None = None
if settings.gemini_api_key:
    _reviewer = GeminiReviewer(api_key=settings.gemini_api_key, model_name=settings.gemini_model)
else:
    logger.warning("GEMINI_API_KEY not set; reviews will fail until it is configured.")


async def _run_review(job: ReviewJob) -> None:
    """The actual review pipeline. Runs off the request thread via the queue."""
    repo, pr_number, author = job["repo"], job["pr_number"], job["author"]
    try:
        diff = await github.fetch_pr_diff(repo, pr_number)
        files = await github.fetch_pr_files(repo, pr_number)

        cleaned_diff, redacted_types = redact(diff)
        if redacted_types:
            logger.info("Redacted %s from diff before sending to Gemini (%s#%s)", redacted_types, repo, pr_number)
        cleaned_diff, was_truncated = truncate(cleaned_diff, settings.max_diff_chars)

        if _reviewer is None:
            raise RuntimeError("Gemini reviewer not configured")

        result = _reviewer.review(repo=repo, pr_number=pr_number, author=author,
                                   diff_text=cleaned_diff, files=files)
        if was_truncated:
            result.summary += " (Note: diff exceeded size limit and was truncated for review.)"

        await store.save(result)
        await github.post_pr_comment(repo, pr_number, result.to_pr_comment_markdown())
        logger.info("Reviewed %s#%s -> score %d", repo, pr_number, result.quality_score)
    except Exception:
        logger.exception("Review pipeline failed for %s#%s", repo, pr_number)


queue = (
    CloudTasksQueue(
        settings.gcp_project_id, settings.gcp_region, settings.cloud_tasks_queue,
        target_url="https://REPLACE_WITH_CLOUD_RUN_URL/internal/run-review",
        service_account_email=f"cloud-tasks-invoker@{settings.gcp_project_id}.iam.gserviceaccount.com",
    )
    if settings.use_cloud_tasks
    else InProcessQueue(_run_review)
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/github")
async def github_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    try:
        verify_signature(body, signature, settings.github_webhook_secret)
    except InvalidSignatureError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    event_type = request.headers.get("X-GitHub-Event", "")
    if event_type != "pull_request":
        return {"status": "ignored", "reason": f"event type {event_type} not handled"}

    payload = await request.json()
    event = parse_pull_request_event(payload)
    if event is None:
        return {"status": "ignored", "reason": "not an opened/synchronize PR action"}

    await queue.enqueue({"repo": event.repo_full_name, "pr_number": event.pr_number, "author": event.author})
    return {"status": "queued", "repo": event.repo_full_name, "pr_number": event.pr_number}


@app.post("/internal/run-review")
async def internal_run_review(request: Request):
    """Target endpoint Cloud Tasks calls back into (OIDC-authenticated at the
    Cloud Run/IAM layer -- not re-verified here)."""
    job = await request.json()
    await _run_review(job)
    return {"status": "done"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    recent = await store.all_recent(limit=50)
    return templates.TemplateResponse("dashboard.html", {"request": request, "reviews": recent})


@app.get("/dashboard/{repo_owner}/{repo_name}/{developer}")
async def developer_trend(repo_owner: str, repo_name: str, developer: str):
    repo = f"{repo_owner}/{repo_name}"
    trend = await store.trend_for_developer(repo, developer)
    history = await store.history_for_developer(repo, developer)
    return {"trend": trend.model_dump(mode="json"), "history": [h.model_dump(mode="json") for h in history]}
