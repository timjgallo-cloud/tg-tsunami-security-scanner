
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.0.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "enabled_apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "storage.googleapis.com",
    "securitycenter.googleapis.com" # For optional SCC integration
  ])
  service = each.key
  disable_on_destroy = false
}

# Artifact Registry for Container Images
resource "google_artifact_registry_repository" "tsunami_repo" {
  location      = var.region
  repository_id = "tsunami-repo"
  description   = "Docker repository for Tsunami Scanner and Web UI"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}

# GCS Bucket for Scan Results
resource "google_storage_bucket" "scan_results" {
  name          = "${var.project_id}-tsunami-results"
  location      = var.region
  force_destroy = true
  uniform_bucket_level_access = true
  depends_on    = [google_project_service.enabled_apis]
}

# Service Account for Tsunami Scanner Job
resource "google_service_account" "scanner_sa" {
  account_id   = "tsunami-scanner-sa"
  display_name = "Tsunami Scanner Service Account"
}

# Service Account for Web UI
resource "google_service_account" "web_ui_sa" {
  account_id   = "tsunami-web-ui-sa"
  display_name = "Tsunami Web UI Service Account"
}

# Grant Scanner SA permission to write to GCS
resource "google_storage_bucket_iam_member" "scanner_gcs_write" {
  bucket = google_storage_bucket.scan_results.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.scanner_sa.email}"
}

# Grant Web UI SA permission to read from GCS
resource "google_storage_bucket_iam_member" "web_ui_gcs_read" {
  bucket = google_storage_bucket.scan_results.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.web_ui_sa.email}"
}

# Grant Web UI SA permission to invoke Cloud Run Jobs
resource "google_project_iam_member" "web_ui_run_invoker" {
  project = var.project_id
  role    = "roles/run.developer" # Needs permission to run jobs
  member  = "serviceAccount:${google_service_account.web_ui_sa.email}"
}

# Cloud Run Job for Tsunami Scanner
resource "google_cloud_run_v2_job" "tsunami_scanner_job" {
  name     = "tsunami-scanner"
  location = var.region

  template {
    template {
      service_account = google_service_account.scanner_sa.email
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.tsunami_repo.name}/tsunami-scanner:latest"
        
        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }

        # Environment variables will be overridden by the Web UI when triggering the job
        env {
          name  = "TARGET"
          value = "127.0.0.1" 
        }
        env {
          name  = "GCS_BUCKET"
          value = google_storage_bucket.scan_results.name
        }
      }
    }
  }

  depends_on = [google_project_service.enabled_apis]
}

# Cloud Run Service for Web UI
resource "google_cloud_run_service" "web_ui_service" {
  name     = "tsunami-web-ui"
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.web_ui_sa.email
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.tsunami_repo.name}/tsunami-web-ui:latest"
        
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "REGION"
          value = var.region
        }
        env {
          name  = "SCANNER_JOB_NAME"
          value = google_cloud_run_v2_job.tsunami_scanner_job.name
        }
        env {
          name  = "GCS_BUCKET"
          value = google_storage_bucket.scan_results.name
        }
        env {
          name  = "VT_API_KEY"
          value = var.vt_api_key
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.enabled_apis]
}

# Allow public access to Web UI (for demo purposes - secure this in production!)
resource "google_cloud_run_service_iam_member" "public_access" {
  service  = google_cloud_run_service.web_ui_service.name
  location = google_cloud_run_service.web_ui_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
