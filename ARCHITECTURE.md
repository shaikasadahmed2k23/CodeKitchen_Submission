# Architecture

## Data flow

```
Developer pushes commit / opens PR
        │
        ▼
GitHub sends "pull_request" webhook (opened / synchronize / reopened)
        │
        ▼
Cloud Run: POST /webhook/github
  - verifies X-Hub-Signature-256 (HMAC-SHA256) against GITHUB_WEBHOOK_SECRET
  - parses the event, extracts repo/pr_number/author
  - enqueues a review job (Cloud Tasks in prod, in-process asyncio locally)
  - returns 200 immediately -- webhook delivery isn't blocked on the review
        │
        ▼ (async, via Cloud Tasks → POST /internal/run-review, OIDC-authenticated)
Review pipeline:
  1. Fetch PR diff + changed file list from GitHub REST API
  2. Redact likely secrets/PII from the diff (app/security.py) BEFORE it
     ever reaches Gemini -- API keys, AWS keys, private key blocks, emails, JWTs
  3. Truncate diff to MAX_DIFF_CHARS if it exceeds the review size limit
  4. Send to Gemini 1.5 Pro with a system prompt requiring strict JSON output
     (quality_score, summary, per-file/line comments with severity+category)
  5. Persist ReviewResult to Firestore (review_history collection)
  6. Post the formatted review as a PR comment via GitHub REST API
        │
        ▼
GET /dashboard renders recent reviews + per-developer trend from Firestore
```

## Why each GCP product

- **Cloud Run** — the webhook receiver and review worker are the same
  stateless FastAPI service, scales to zero between PRs, scales out under
  burst load (e.g. a mass rebase across a monorepo).
- **Gemini 1.5 Pro (Vertex AI / Generative AI SDK)** — multi-language
  understanding for the actual review reasoning; large context window
  handles realistic diff sizes.
- **Firestore** — review history is sparse, per-document, per-developer/
  per-repo metadata that's read far more by "give me the last N reviews for
  developer X" than by relational joins. Schemaless documents + native
  composite indexes on (repo, author, reviewed_at) fit that access pattern
  better than Cloud SQL, with no schema migrations as the review shape
  evolves (e.g. adding a new comment category later).
- **Cloud Tasks** — decouples "webhook received" from "review executed" so
  a burst of PRs doesn't block the Cloud Run request thread or hammer the
  Gemini API synchronously; built-in retry/backoff on failed review jobs.
- **Cloud Build** — CI trigger on push to `main`; builds the container,
  pushes to Artifact/Container Registry, deploys the new revision to Cloud
  Run.
- **Secret Manager** — `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`, and
  `GEMINI_API_KEY` are injected into Cloud Run as secret env vars
  (`--set-secrets`), never baked into the image or committed to the repo.

## Edge cases handled

- **Auth**: every inbound webhook is HMAC-verified against
  `GITHUB_WEBHOOK_SECRET` (`app/webhook_handler.py::verify_signature`) using
  constant-time comparison (`hmac.compare_digest`) to avoid timing attacks.
  The internal `/internal/run-review` callback is only reachable via
  Cloud Tasks' OIDC-authenticated request (enforced at the Cloud Run IAM
  layer with `--no-allow-unauthenticated`).
- **Privacy**: diffs are redacted (`app/security.py::redact`) for API keys,
  AWS credentials, private key blocks, emails, and JWTs before they're sent
  to Gemini — irrespective of whether the repo owner opted into any
  training-data sharing.
- **Scale**: large diffs are truncated to `MAX_DIFF_CHARS` rather than
  failing outright; bursty PR volume is absorbed by Cloud Tasks queueing
  instead of blocking webhook responses (GitHub retries/times out webhooks
  that don't ACK within 10s).
- **Resilience**: the review pipeline fails closed per-PR (logs and moves
  on) rather than crashing the whole service if Gemini or GitHub returns an
  error for a single PR.
