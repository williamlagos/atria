output "cloud_run_url" {
  description = "The public URL of the deployed Atria web service on Cloud Run."
  value       = google_cloud_run_v2_service.atria_web.uri
}

output "api_docs_url" {
  description = "Interactive OpenAPI Swagger documentation endpoint."
  value       = "${google_cloud_run_v2_service.atria_web.uri}/api/docs"
}

output "cloud_storage_bucket" {
  description = "GCS bucket name for Django media and static files (Always Free tier)."
  value       = google_storage_bucket.atria_media.name
}

output "artifact_registry_repo" {
  description = "Docker repository URI in Google Artifact Registry."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.atria_repo.repository_id}/atria"
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name used by Cloud Run unix socket."
  value       = google_sql_database_instance.atria_db.connection_name
}

output "migration_job_name" {
  description = "Name of the Cloud Run migration job."
  value       = google_cloud_run_v2_job.atria_migrate.name
}
