terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ------------------------------------------------------------------------------
# Random Suffix for Unique Cloud Storage & Resource Naming
# ------------------------------------------------------------------------------
resource "random_id" "suffix" {
  byte_length = 4
}

# ------------------------------------------------------------------------------
# Service Account for Cloud Run (Least-Privilege Execution)
# ------------------------------------------------------------------------------
resource "google_service_account" "atria_runner" {
  account_id   = "atria-runner"
  display_name = "Atria Cloud Run Runner Service Account"
  description  = "Dedicated runtime service account for Atria serverless services"
}

# ------------------------------------------------------------------------------
# Google Artifact Registry (Container Registry for Atria Docker images)
# ------------------------------------------------------------------------------
resource "google_artifact_registry_repository" "atria_repo" {
  location      = var.region
  repository_id = "atria"
  description   = "Docker repository for Atria production images"
  format        = "DOCKER"
}

# ------------------------------------------------------------------------------
# Google Cloud Storage (5 GB Always Free Tier in us-central1 / us-east1 / us-west1)
# ------------------------------------------------------------------------------
resource "google_storage_bucket" "atria_media" {
  name                        = "atria-media-${var.project_id}-${random_id.suffix.hex}"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = false

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Public read access for uploaded media in Cloud Storage
resource "google_storage_bucket_iam_member" "public_media_read" {
  bucket = google_storage_bucket.atria_media.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Runner SA access to manage media and static assets in Cloud Storage
resource "google_storage_bucket_iam_member" "runner_storage_admin" {
  bucket = google_storage_bucket.atria_media.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.atria_runner.email}"
}

# ------------------------------------------------------------------------------
# Cloud SQL for PostgreSQL 16 (Leverages Google Cloud Pro Credits)
# ------------------------------------------------------------------------------
resource "random_password" "db_password" {
  length  = 24
  special = false
}

resource "google_sql_database_instance" "atria_db" {
  name             = "atria-db-${random_id.suffix.hex}"
  database_version = "POSTGRES_16"
  region           = var.region
  deletion_protection = var.db_deletion_protection

  settings {
    tier              = var.db_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL" # Zonal to optimize cost against credits
    disk_size         = 10      # Minimal 10GB auto-increasing SSD
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = false
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
    }
  }
}

resource "google_sql_database" "atria" {
  name     = "atria"
  instance = google_sql_database_instance.atria_db.name
}

resource "google_sql_user" "atria" {
  name     = "atria"
  instance = google_sql_database_instance.atria_db.name
  password = var.db_password != "" ? var.db_password : random_password.db_password.result
}

# Grant Cloud SQL Client role to runner SA
resource "google_project_iam_member" "runner_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.atria_runner.email}"
}

# ------------------------------------------------------------------------------
# Secret Manager (Secure Credentials Storage)
# ------------------------------------------------------------------------------
resource "random_password" "django_secret_key" {
  length  = 50
  special = true
}

resource "google_secret_manager_secret" "secret_key" {
  secret_id = "atria-django-secret-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "secret_key_val" {
  secret      = google_secret_manager_secret.secret_key.id
  secret_data = var.django_secret_key != "" ? var.django_secret_key : random_password.django_secret_key.result
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "atria-database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url_val" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgres://${google_sql_user.atria.name}:${var.db_password != "" ? var.db_password : random_password.db_password.result}@localhost:5432/${google_sql_database.atria.name}?host=/cloudsql/${google_sql_database_instance.atria_db.connection_name}"
}

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "atria-gemini-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "gemini_api_key_val" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key != "" ? var.gemini_api_key : "none"
}

# Secret Accessor permission for Cloud Run Service Account
resource "google_secret_manager_secret_iam_member" "secret_key_access" {
  secret_id = google_secret_manager_secret.secret_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.atria_runner.email}"
}

resource "google_secret_manager_secret_iam_member" "db_url_access" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.atria_runner.email}"
}

resource "google_secret_manager_secret_iam_member" "gemini_api_key_access" {
  secret_id = google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.atria_runner.email}"
}

# ------------------------------------------------------------------------------
# Cloud Run v2 Database Migration Job (Serverless Schema Updates)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_job" "atria_migrate" {
  name     = "atria-migrate"
  location = var.region

  template {
    template {
      service_account = google_service_account.atria_runner.email

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.atria_db.connection_name]
        }
      }

      containers {
        image   = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.atria_repo.repository_id}/atria:latest"
        command = ["python", "manage.py", "migrate", "--noinput"]

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }

        env {
          name  = "DJANGO_SETTINGS_MODULE"
          value = "atria.settings"
        }
        env {
          name  = "DEBUG"
          value = "0"
        }
        env {
          name  = "GS_BUCKET_NAME"
          value = google_storage_bucket.atria_media.name
        }
        env {
          name = "SECRET_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secret_key.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
}

# ------------------------------------------------------------------------------
# Cloud Run v2 Web Service (Scale-to-Zero, 100% Free Tier Compliant)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "atria_web" {
  name     = "atria-web"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.atria_runner.email

    scaling {
      min_instance_count = 0                 # Scale to ZERO when idle = $0 server cost!
      max_instance_count = var.max_instances # Cap instances to prevent runaway spend
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.atria_db.connection_name]
      }
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.atria_repo.repository_id}/atria:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi" # Fits cleanly inside Cloud Run Always-Free allowance
        }
        cpu_idle = true # CPU only allocated during request processing
      }

      ports {
        container_port = 8000
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name  = "DJANGO_SETTINGS_MODULE"
        value = "atria.settings"
      }
      env {
        name  = "DEBUG"
        value = "0"
      }
      env {
        name  = "PORT"
        value = "8000"
      }
      env {
        name  = "ALLOWED_HOSTS"
        value = "*"
      }
      env {
        name  = "SITE_DOMAIN"
        value = var.site_domain
      }
      env {
        name  = "GS_BUCKET_NAME"
        value = google_storage_bucket.atria_media.name
      }
      env {
        name  = "WEB3_PROVIDER_URL"
        value = var.web3_provider_url
      }
      env {
        name  = "CELERY_BROKER_URL"
        value = "memory://"
      }
      env {
        name  = "CELERY_RESULT_BACKEND"
        value = "cache+memory://"
      }

      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/api/docs"
          port = 8000
        }
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/api/docs"
          port = 8000
        }
        timeout_seconds   = 3
        period_seconds    = 30
        failure_threshold = 3
      }
    }
  }

  depends_on = [
    google_project_iam_member.runner_cloudsql_client,
    google_secret_manager_secret_iam_member.secret_key_access,
    google_secret_manager_secret_iam_member.db_url_access,
    google_secret_manager_secret_iam_member.gemini_api_key_access,
  ]
}

# ------------------------------------------------------------------------------
# Public Invoker Binding (Allows Public Internet Access to Atria API)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.atria_web.location
  name     = google_cloud_run_v2_service.atria_web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
