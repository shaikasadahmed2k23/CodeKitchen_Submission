#!/usr/bin/env bash
# One-time GCP project setup for the 24/7 Intelligent Code Reviewer.
# Run once with an authenticated `gcloud` CLI (gcloud auth login && gcloud config set project <id>).
set -euo pipefail

PROJECT_ID="${1:?Usage: setup_gcp.sh <project-id>}"
REGION="asia-south1"

echo "==> Enabling required APIs"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  cloudtasks.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  --project "$PROJECT_ID"

echo "==> Creating Firestore database (Native mode) in $REGION"
gcloud firestore databases create --project="$PROJECT_ID" --location="$REGION" || true

echo "==> Creating Cloud Tasks queue"
gcloud tasks queues create review-jobs --project="$PROJECT_ID" --location="$REGION" || true

echo "==> Creating secrets (values must be set manually via 'gcloud secrets versions add')"
for secret in github-token github-webhook-secret gemini-api-key; do
  gcloud secrets create "$secret" --project="$PROJECT_ID" --replication-policy="automatic" || true
done

echo "==> Creating Cloud Build trigger (fill in your repo owner/name)"
echo "    gcloud builds triggers create github \\"
echo "      --repo-name=<REPO_NAME> --repo-owner=<REPO_OWNER> \\"
echo "      --branch-pattern='^main$' --build-config=cloudbuild.yaml --project=$PROJECT_ID"

echo "==> Done. Push a secret value with:"
echo "    echo -n 'VALUE' | gcloud secrets versions add github-token --data-file=- --project=$PROJECT_ID"
