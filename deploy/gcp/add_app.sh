#!/usr/bin/env bash
# ==============================================================================
# Multi-App Provisioner for Shared GCP Infrastructure
# Adds an isolated PostgreSQL database, user, secrets, and Cloud Run setup
# for any new personal project (e.g. Python API + Angular frontend).
# ==============================================================================

set -euo pipefail

APP_NAME="${1:-}"

if [[ -z "${APP_NAME}" ]]; then
  echo "Usage: ./add_app.sh <app-name>"
  echo "Example: ./add_app.sh family-recipes"
  exit 1
fi

# Sanitize app name (lowercase alphanumeric and hyphens only)
APP_NAME=$(echo "${APP_NAME}" | tr '[:upper:]' '[:lower:]' | tr '_' '-' | tr -cd 'a-z0-9-')
DB_NAME=$(echo "${APP_NAME}" | tr '-' '_')_db
DB_USER=$(echo "${APP_NAME}" | tr '-' '_')_user

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo "")}"
REGION="${GCP_REGION:-us-central1}"

echo "=============================================================================="
echo " Provisioning Shared GCP Resources for: ${APP_NAME}"
echo " GCP Project: ${PROJECT_ID}"
echo " Region:      ${REGION}"
echo " Database:    ${DB_NAME}"
echo " DB User:     ${DB_USER}"
echo "=============================================================================="

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: No GCP project configured. Run: gcloud config set project <PROJECT_ID>"
  exit 1
fi

# 1. Discover Cloud SQL Instance
echo "[1/4] Discovering active Cloud SQL PostgreSQL instance..."
INSTANCE_NAME=$(gcloud sql instances list --project="${PROJECT_ID}" --format="value(name)" --filter="databaseVersion:POSTGRES*" | head -n 1)

if [[ -z "${INSTANCE_NAME}" ]]; then
  echo "Error: No active Cloud SQL PostgreSQL instance found in project ${PROJECT_ID}."
  echo "Please provision the shared infrastructure via Terraform in deploy/gcp first."
  exit 1
fi

CONNECTION_NAME=$(gcloud sql instances describe "${INSTANCE_NAME}" --project="${PROJECT_ID}" --format="value(connectionName)")
echo "Found Cloud SQL instance: ${INSTANCE_NAME} (${CONNECTION_NAME})"

# 2. Create Isolated PostgreSQL Database & User
echo "[2/4] Creating PostgreSQL database '${DB_NAME}' and user '${DB_USER}'..."
if ! gcloud sql databases describe "${DB_NAME}" --instance="${INSTANCE_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud sql databases create "${DB_NAME}" --instance="${INSTANCE_NAME}" --project="${PROJECT_ID}" --quiet
  echo "Database '${DB_NAME}' created."
else
  echo "Database '${DB_NAME}' already exists."
fi

# Generate strong random password
DB_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || true)

if ! gcloud sql users list --instance="${INSTANCE_NAME}" --project="${PROJECT_ID}" --format="value(name)" | grep -qw "${DB_USER}"; then
  gcloud sql users create "${DB_USER}" \
    --instance="${INSTANCE_NAME}" \
    --password="${DB_PASSWORD}" \
    --project="${PROJECT_ID}" \
    --quiet
  echo "User '${DB_USER}' created."
else
  echo "User '${DB_USER}' already exists. Updating password..."
  gcloud sql users set-password "${DB_USER}" \
    --instance="${INSTANCE_NAME}" \
    --password="${DB_PASSWORD}" \
    --project="${PROJECT_ID}" \
    --quiet
fi

# 3. Store Database Connection URL in Secret Manager
echo "[3/4] Registering connection string in Secret Manager..."
DB_URL="postgres://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"
SECRET_ID="${APP_NAME}-database-url"

if ! gcloud secrets describe "${SECRET_ID}" --project="${PROJECT_ID}" &>/dev/null; then
  echo -n "${DB_URL}" | gcloud secrets create "${SECRET_ID}" \
    --data-file=- \
    --replication-policy="automatic" \
    --project="${PROJECT_ID}" \
    --quiet
else
  echo -n "${DB_URL}" | gcloud secrets versions add "${SECRET_ID}" \
    --data-file=- \
    --project="${PROJECT_ID}" \
    --quiet
fi

# 4. Create App Service Account with Cloud SQL & Secret Access
echo "[4/4] Creating dedicated Service Account for ${APP_NAME}..."
SA_NAME="${APP_NAME}-runner"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="${APP_NAME} Cloud Run Runner" \
    --project="${PROJECT_ID}" \
    --quiet
fi

# Grant Cloud SQL client and Secret Accessor
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudsql.client" \
  --condition=None --quiet >/dev/null

gcloud secrets add-iam-policy-binding "${SECRET_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --project="${PROJECT_ID}" \
  --quiet >/dev/null

echo "=============================================================================="
echo " Setup Complete for '${APP_NAME}'!"
echo "=============================================================================="
echo " Database:           ${DB_NAME}"
echo " Database User:      ${DB_USER}"
echo " Database Password:  ${DB_PASSWORD}"
echo " Cloud SQL Instance: ${CONNECTION_NAME}"
echo " Secret ID:          ${SECRET_ID}"
echo " Service Account:    ${SA_EMAIL}"
echo ""
echo " Connection String (Cloud Run / Unix socket):"
echo "   ${DB_URL}"
echo ""
echo " Deploying Backend to Cloud Run (Example):"
echo "   gcloud run deploy ${APP_NAME}-api \\"
echo "     --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/atria/${APP_NAME}:latest \\"
echo "     --region=${REGION} \\"
echo "     --service-account=${SA_EMAIL} \\"
echo "     --add-cloudsql-instances=${CONNECTION_NAME} \\"
echo "     --set-secrets=DATABASE_URL=${SECRET_ID}:latest \\"
echo "     --min-instances=0 \\"
echo "     --max-instances=3 \\"
echo "     --allow-unauthenticated"
echo "=============================================================================="
