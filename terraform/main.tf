
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
    "securitycenter.googleapis.com", # For optional SCC integration
    "pubsub.googleapis.com",
    "cloudresourcemanager.googleapis.com"
  ])
  service = each.key
  disable_on_destroy = false
}

# Dynamic lookup of Project details
data "google_project" "project" {}

# Artifact Registry for Container Images
resource "google_artifact_registry_repository" "tsunami_repo" {
  location      = var.region
  repository_id = "tsunami-repo"
  description   = "Docker repository for Tsunami Scanner and Web UI"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}

# Grant Cloud Build SA writer permissions to Artifact Registry
resource "google_artifact_registry_repository_iam_member" "cloud_build_ar_writer" {
  location   = google_artifact_registry_repository.tsunami_repo.location
  repository = google_artifact_registry_repository.tsunami_repo.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}

# Grant Compute Engine SA writer permissions to Artifact Registry
resource "google_artifact_registry_repository_iam_member" "compute_sa_ar_writer" {
  location   = google_artifact_registry_repository.tsunami_repo.location
  repository = google_artifact_registry_repository.tsunami_repo.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
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

# Grant Web UI SA permission to read/write to GCS (needs write for saving enriched results)
resource "google_storage_bucket_iam_member" "web_ui_gcs_admin" {
  bucket = google_storage_bucket.scan_results.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.web_ui_sa.email}"
}

# Grant Web UI SA permission to invoke Cloud Run Jobs
resource "google_project_iam_member" "web_ui_run_invoker" {
  project = var.project_id
  role    = "roles/run.developer" # Needs permission to run jobs
  member  = "serviceAccount:${google_service_account.web_ui_sa.email}"
}

# Grant Web UI SA permission to create signed URLs
resource "google_project_iam_member" "web_ui_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.web_ui_sa.email}"
}

# Cloud Run Job for Tsunami Scanner
resource "google_cloud_run_v2_job" "tsunami_scanner_job" {
  name     = "tsunami-scanner"
  location = var.region
  deletion_protection = false

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
        env {
          name  = "PUBSUB_TOPIC"
          value = google_pubsub_topic.scan_completed.name
        }
        env {
          name  = "SERVICE_ACCOUNT_EMAIL"
          value = google_service_account.web_ui_sa.email
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
  member   = var.authorized_member
}

# Pub/Sub Topic for Scan Completion
resource "google_pubsub_topic" "scan_completed" {
  name = "tsunami-scan-completed"
  depends_on = [google_project_service.enabled_apis]
}

# Grant Scanner SA permission to publish to Pub/Sub
resource "google_pubsub_topic_iam_member" "scanner_pubsub_publisher" {
  topic  = google_pubsub_topic.scan_completed.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.scanner_sa.email}"
}

# Service Account for Pub/Sub Push Subscription
resource "google_service_account" "pubsub_sa" {
  account_id   = "tsunami-pubsub-sa"
  display_name = "Tsunami PubSub Push Service Account"
}

# Grant PubSub SA permission to invoke Web UI Service
resource "google_cloud_run_service_iam_member" "pubsub_invoker" {
  service  = google_cloud_run_service.web_ui_service.name
  location = google_cloud_run_service.web_ui_service.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_sa.email}"
}

# Pub/Sub Push Subscription
resource "google_pubsub_subscription" "scan_enrichment_sub" {
  name  = "tsunami-scan-enrichment-sub"
  topic = google_pubsub_topic.scan_completed.name

  push_config {
    push_endpoint = "${google_cloud_run_service.web_ui_service.status[0].url}/api/v1/worker/enrich"
    oidc_token {
      service_account_email = google_service_account.pubsub_sa.email
    }
  }

  depends_on = [google_cloud_run_service.web_ui_service]
}
