# Atria Google Cloud Platform Deployment Guide

This guide details how to deploy **Atria** to Google Cloud Platform (GCP) while maximizing **Google Cloud Free Tier** allowances and leveraging **Google Cloud Pro Credits**.

---

## 1. Architecture & Cost Strategy

The deployment leverages a **modern serverless n-tier architecture** with automated scale-to-zero:

```
[ Internet / Clients ]
         │ (HTTPS)
         ▼
[ Google Cloud Run: atria-web ] ── (Scale to 0 when idle = $0 idle cost)
   │                  │
   │ (Unix Socket)    │ (Cloud Storage SDK)
   ▼                  ▼
[ Cloud SQL: atria-db ]     [ Google Cloud Storage: atria-media ]
(PostgreSQL 16 Enterprise)   (5 GB/month Always Free in us-central1)
   │
[ Secret Manager ]
(Secret storage: keys, database credentials)
```

### Cost Optimization Matrix (Free Tier + Pro Credits)

| Component | GCP Resource | Free Tier Coverage | Pro Credits Usage |
| :--- | :--- | :--- | :--- |
| **Compute / API** | **Cloud Run (v2)** | **2 million requests/month FREE**, 360,000 GB-sec RAM, 180,000 vCPU-sec. Scales to zero when idle. | $0 (covered by Free Tier under normal usage) |
| **Static & Media** | **Cloud Storage** | **5 GB-months Regional Storage FREE** in `us-central1`, `us-east1`, or `us-west1`. 5,000 Class A ops, 50,000 Class B ops. | $0 (covered by Free Tier) |
| **Container Images** | **Artifact Registry** | **0.5 GB/month storage FREE**. | $0 (covered by Free Tier) |
| **CI/CD** | **Cloud Build** | **120 build-minutes/day FREE** on standard machines. | $0 (covered by Free Tier) |
| **Database** | **Cloud SQL (PostgreSQL 16)** | N/A (Standard relational database service). | **Covered by Pro Credits** (`db-f1-micro` or `db-custom-1-3840`). |
| **Secrets** | **Secret Manager** | **6 active secret versions FREE**, 10,000 access operations/month. | $0 (covered by Free Tier) |
| **AI Embeddings** | **Gemini API** | Free tier rate limits via Google AI Studio / Vertex AI credits. | $0 / Pro credits |

---

## 2. Prerequisites

1. Install Google Cloud SDK (`gcloud` CLI):
   ```bash
   brew install --cask google-cloud-sdk
   ```
2. Authenticate and select your GCP Project:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project <YOUR_PROJECT_ID>
   ```
3. Install Terraform (>= 1.5):
   ```bash
   brew install terraform
   ```

---

## 3. Provision Infrastructure with Terraform

1. Navigate to the terraform configuration directory:
   ```bash
   cd deploy/gcp
   ```

2. Initialize Terraform providers:
   ```bash
   terraform init
   ```

3. Review the execution plan:
   ```bash
   terraform plan -var="project_id=<YOUR_PROJECT_ID>"
   ```

4. Apply the configuration:
   ```bash
   terraform apply -var="project_id=<YOUR_PROJECT_ID>" -auto-approve
   ```

Terraform outputs the:
* Cloud Run URL (`https://atria-web-*.a.run.app`)
* Interactive API Documentation URL (`https://atria-web-*.a.run.app/api/docs`)
* Cloud Storage Media Bucket name
* Cloud SQL instance connection string

---

## 4. Automated CI/CD Deployment

### Option A: Using the `deploy.sh` script
From the root of the Atria repository:
```bash
export GCP_PROJECT_ID="<YOUR_PROJECT_ID>"
./deploy/gcp/deploy.sh
```

### Option B: Using Google Cloud Build
Submit a build directly to Google Cloud Build (runs building, migrations, and service deployment):
```bash
gcloud builds submit --config=deploy/gcp/cloudbuild.yaml .
```

---

## 5. Verifying the Deployment

1. **Check Service Health & OpenAPI Docs**:
   Open `<SERVICE_URL>/api/docs` in your browser.
2. **Verify Database Connectivity**:
   ```bash
   curl -s <SERVICE_URL>/api/qa/reputation/leaderboard
   ```
3. **Verify Scale-to-Zero & Cloud Metrics**:
   Open the Google Cloud Console &rarr; Cloud Run &rarr; `atria-web` &rarr; Metrics to observe traffic and CPU utilization dropping to 0 when idle.
