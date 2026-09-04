# 24/7 Intelligent Code Reviewer

**Code Kitchen S01 — Track 01 submission.**

An always-on code reviewer for teams without a senior reviewer available
round the clock. Opens/updates on a PR trigger an automated multi-language
review (bugs, security, performance, style, maintainability), a 0–100
quality score, **and a developer trust profile that learns from review
history** — all built on GCP.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full data flow and the
reasoning behind each GCP product choice.

## Stack

FastAPI · Gemini 3.5 Flash · Firestore · Cloud Tasks · Cloud Run · Cloud Build · Secret Manager

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY at minimum to test reviews

uvicorn app.main:app --reload --port 8080
```

Without GCP credentials configured, the app **automatically falls back to
an in-memory review store** so you can run and test it fully locally —
no GCP project needed just to boot it up.

Visit `http://localhost:8080/dashboard` once a few reviews have run.

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

35 tests covering: webhook signature verification, PR event parsing,
secret/PII redaction, diff truncation, the Gemini JSON-response parser
(mocked), the GitHub API client (mocked httpx), the review store, and the
developer trust profile / historical-learning adjustment rules.

## Deploying to GCP

```bash
bash scripts/setup_gcp.sh <your-project-id>   # one-time: enables APIs, creates Firestore/Cloud Tasks/secrets
# then set real secret values:
echo -n '<value>' | gcloud secrets versions add github-token --data-file=- --project=<your-project-id>
echo -n '<value>' | gcloud secrets versions add github-webhook-secret --data-file=- --project=<your-project-id>
echo -n '<value>' | gcloud secrets versions add gemini-api-key --data-file=- --project=<your-project-id>

gcloud builds submit --config=cloudbuild.yaml   # build + deploy to Cloud Run
```

Then point a GitHub webhook (repo → Settings → Webhooks) at
`https://<cloud-run-url>/webhook/github`, content type `application/json`,
secret matching `GITHUB_WEBHOOK_SECRET`, event: **Pull requests**.

## Project layout

```
app/
  main.py             FastAPI app: webhook receiver, internal review runner, dashboard
  config.py           Settings (env-var driven)
  models.py           ReviewResult / ReviewComment / DeveloperTrend
  webhook_handler.py  HMAC signature verification + PR event parsing
  github_client.py    GitHub REST API (fetch diff/files, post PR comment)
  gemini_reviewer.py  Gemini prompt + structured JSON review parsing
  security.py         Secret/PII redaction + diff truncation
  store.py            Firestore store (prod) / in-memory store (local, tests)
  trust.py            Developer trust profile -- historical learning, bounded score adjustment
  queue.py            Cloud Tasks queue (prod) / in-process queue (local)
templates/dashboard.html
tests/                35 unit tests, all mocked -- no live GCP/GitHub/Gemini calls needed
Dockerfile, cloudbuild.yaml, scripts/setup_gcp.sh
```
