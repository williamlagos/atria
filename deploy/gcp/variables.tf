variable "project_id" {
  description = "The Google Cloud Project ID where resources will be provisioned."
  type        = string
}

variable "region" {
  description = "The GCP region to deploy to. Defaults to us-central1 (eligible for Always Free Tier for Cloud Run and GCS)."
  type        = string
  default     = "us-central1"
}

variable "site_domain" {
  description = "Domain name for the site or service."
  type        = string
  default     = "atria.internal"
}

variable "db_tier" {
  description = "The Cloud SQL machine tier. Default db-f1-micro is lowest cost; for enterprise workloads, use db-custom-1-3840 (covered by Pro credits)."
  type        = string
  default     = "db-f1-micro"
}

variable "db_password" {
  description = "Database user password (leave empty to generate a random password)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "db_deletion_protection" {
  description = "Prevent accidental deletion of Cloud SQL instance."
  type        = bool
  default     = false
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances to scale up to."
  type        = number
  default     = 5
}

variable "django_secret_key" {
  description = "Django secret key (leave empty to generate a random 50-char key)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "gemini_api_key" {
  description = "Google Gemini API key for AI Discovery and embeddings."
  type        = string
  default     = ""
  sensitive   = true
}

variable "web3_provider_url" {
  description = "Web3 RPC provider endpoint (defaults to public Ethereum RPC)."
  type        = string
  default     = "https://eth.llamarpc.com"
}
