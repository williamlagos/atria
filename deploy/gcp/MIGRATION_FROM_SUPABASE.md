# Migrating from Supabase + GitHub Pages to Google Cloud (Cloud SQL + Cloud Run + Firebase)

This guide walks through migrating an **Angular + Python + PostgreSQL** application from **Supabase + GitHub Pages** into your shared **Google Cloud Platform (GCP)** infrastructure.

---

## 1. Why This Is an Upgrade

| Feature | Supabase Free + GitHub Pages | Google Cloud Shared Infrastructure |
| :--- | :--- | :--- |
| **Database Uptime** | ⚠️ **Pauses after 7 days of inactivity**; requires manual unpause. | ✅ **Never pauses**; persistent 24/7 Cloud SQL backed by Google Cloud Pro credits. |
| **Backend Compute** | ⚠️ Complex setup or third-party servers required for custom Python. | ✅ **Native Cloud Run**: custom Python (FastAPI/Flask/Django) with scale-to-zero ($0 idle). |
| **SPA Routing** | ⚠️ GitHub Pages returns 404 on page refresh unless using URL hack scripts. | ✅ **Native SPA rewrites**: clean URLs (`/dashboard`, `/profile`) handled automatically. |
| **CORS & APIs** | ⚠️ Requires configuring CORS headers across domains. | ✅ **Direct `/api/**` proxy**: Frontend and backend share the same origin URL! |
| **AI Capabilities** | Extra billing / third-party API keys. | ✅ **Google AI Pro**: Gemini 2.5 Flash embeddings and text generation built-in. |
| **Monthly Cost** | Free tier (with pausing / limitations). | **$0.00 Out-of-Pocket** (covered by Free Tier + Pro credits). |

---

## 2. Step 1: Provision the App in 30 Seconds

Run the helper script from `deploy/gcp`:

```bash
cd deploy/gcp
./add_app.sh <app-name>
# Example: ./add_app.sh recipe-book
```

This automatically:
1. Creates `recipe_book_db` on the Cloud SQL PostgreSQL instance.
2. Creates user `recipe_book_user` with a strong password.
3. Generates the Cloud Run connection string and registers it in Secret Manager.
4. Creates a dedicated service account with least privilege.

---

## 3. Step 2: Migrate Database Data from Supabase

If she has existing tables and data in Supabase:

### 1. Export Data from Supabase
Get the Supabase connection string from the Supabase Dashboard &rarr; Project Settings &rarr; Database:
```bash
# Dump tables and data
pg_dump "postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres" \
  --no-owner \
  --no-privileges \
  --clean \
  --if-exists \
  > supabase_dump.sql
```

### 2. Import Data into Cloud SQL
Connect via the Cloud SQL Auth Proxy or `gcloud`:
```bash
# Start Cloud SQL proxy locally (or connect via gcloud sql connect)
gcloud sql connect <INSTANCE_NAME> --user=recipe_book_user --database=recipe_book_db < supabase_dump.sql
```
All tables, sequences, and records are now restored into the Cloud SQL database!

---

## 4. Step 3: Deploy the Python Backend to Cloud Run

1. Copy the starter template from [`deploy/gcp/templates/python-backend/`](templates/python-backend/) into her backend repository.
2. Build and deploy to Cloud Run:
   ```bash
   gcloud run deploy recipe-book-api \
     --source . \
     --region us-central1 \
     --add-cloudsql-instances <CONNECTION_NAME> \
     --set-secrets DATABASE_URL=recipe-book-database-url:latest \
     --set-secrets GEMINI_API_KEY=atria-gemini-api-key:latest \
     --min-instances 0 \
     --max-instances 3 \
     --allow-unauthenticated
   ```

---

## 5. Step 4: Deploy the Angular Frontend to Firebase Hosting

1. In her Angular project directory, install Firebase CLI:
   ```bash
   npm install -g firebase-tools
   firebase login
   ```
2. Initialize Firebase Hosting using your existing GCP Project ID:
   ```bash
   firebase use --add <YOUR_GCP_PROJECT_ID>
   ```
3. Copy [`deploy/gcp/templates/angular-frontend/firebase.json`](templates/angular-frontend/firebase.json) into her Angular repository root.
4. Replace the placeholders in `firebase.json`:
   * `"site"`: name of her site (e.g. `recipe-book-web`)
   * `"run.serviceId"`: name of her Cloud Run API (e.g. `recipe-book-api`)
5. Build and deploy:
   ```bash
   ng build --configuration production
   firebase deploy --only hosting
   ```

Firebase gives her an instant live HTTPS URL (e.g., `https://recipe-book-web.web.app`) with automatic SSL, zero 404 routing errors on page refresh, and automatic `/api/**` proxying to her Python backend!
