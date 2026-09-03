import hashlib
import hmac
from dataclasses import dataclass


class InvalidSignatureError(Exception):
    pass


def verify_signature(payload_body: bytes, signature_header: str | None, secret: str) -> None:
    """
    Verifies the X-Hub-Signature-256 header GitHub sends on every webhook
    delivery. Raises InvalidSignatureError on any mismatch. This is what
    stops a random actor from POSTing fake PR events at the reviewer.
    """
    if not signature_header:
        raise InvalidSignatureError("Missing X-Hub-Signature-256 header")
    if not signature_header.startswith("sha256="):
        raise InvalidSignatureError("Unsupported signature scheme")

    expected = hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]

    if not hmac.compare_digest(expected, provided):
        raise InvalidSignatureError("Signature mismatch")


@dataclass
class PullRequestEvent:
    action: str
    repo_full_name: str
    pr_number: int
    author: str
    diff_url: str
    installation_needed: bool = False


def parse_pull_request_event(payload: dict) -> PullRequestEvent | None:
    """
    Only react to opened/synchronize (new commits pushed) so the reviewer
    re-runs on every push, not just PR creation.
    """
    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return None

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    if not pr or not repo:
        return None

    return PullRequestEvent(
        action=action,
        repo_full_name=repo.get("full_name", ""),
        pr_number=pr.get("number", 0),
        author=pr.get("user", {}).get("login", "unknown"),
        diff_url=pr.get("diff_url", ""),
    )
