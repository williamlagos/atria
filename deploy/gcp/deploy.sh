#!/usr/bin/env bash
# ==============================================================================
# Atria Google Cloud Platform Deployment Script
# Leverages:
#   - Google Cloud Free Tier (Cloud Run scale-to-zero, Cloud Storage 5GB, Cloud Build)
#   - Google Cloud Pro Credits (Cloud SQL PostgreSQL, Secret Manager)
# ==============================================================================

set -euo pipefail

# Configuration defaults
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo "")}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="atria-web"
JOB_NAME="atria-migrate"
REPO_NAME="atria"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/atria:latest"

echo "=============================================================================="
echo " Starting Atria GCP Deployment"
echo " Project: ${PROJECT_ID}"
echo " Region:  ${REGION} (Free Tier Eligible)"
echo "=============================================================================="

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: No GCP project selected. Set GCP_PROJECT_ID or run: gcloud config set project <PROJECT_ID>"
  exit 1
fi

# 1. Enable Required Google Cloud APIs
echo "[1/5] Enabling necessary Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project="${PROJECT_ID}" --quiet

# 2. Ensure Artifact Registry Repository Exists
echo "[2/5] Checking Artifact Registry repository..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Creating Artifact Registry repository '${REPO_NAME}'..."
  gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Atria Docker container repository" \
    --project="${PROJECT_ID}" --quiet
fi

# 3. Build & Push Image using Google Cloud Build (Free Tier: 120 mins/day)
echo "[3/5] Building and pushing Docker container image via Cloud Build..."
gcloud builds submit \
  --tag="${IMAGE_NAME}" \
  --project="${PROJECT_ID}" \
  .

# 4. Run Database Migrations via Cloud Run Job
echo "[4/5] Executing database migrations..."
if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud run jobs update "${JOB_NAME}" \
    --image="${IMAGE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" --quiet
  gcloud run jobs execute "${JOB_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --wait
else
  echo "Notice: Cloud Run migration job '${JOB_NAME}' not yet provisioned via Terraform. Skipping job execution."
fi

# 5. Update Cloud Run Web Service
echo "[5/5] Deploying updated container to Cloud Run..."
if gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --quiet
  SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
  echo "=============================================================================="
  echo " Deployment Succeeded!"
  echo " Service URL:   ${SERVICE_URL}"
  echo " API Docs:      ${SERVICE_URL}/api/docs"
  echo "=============================================================================="
else
  echo "Notice: Cloud Run service '${SERVICE_NAME}' not yet provisioned. Apply Terraform in deploy/gcp first:"
  echo "  cd deploy/gcp && terraform init && terraform apply"
fi
