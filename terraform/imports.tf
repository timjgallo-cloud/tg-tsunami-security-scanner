import {
  to = google_storage_bucket.scan_results
  id = "threat-vulnerability-analyzer-tsunami-results"
}

import {
  to = google_artifact_registry_repository.tsunami_repo
  id = "projects/threat-vulnerability-analyzer/locations/us-central1/repositories/tsunami-repo"
}

import {
  to = google_service_account.scanner_sa
  id = "projects/threat-vulnerability-analyzer/serviceAccounts/tsunami-scanner-sa@threat-vulnerability-analyzer.iam.gserviceaccount.com"
}

import {
  to = google_service_account.web_ui_sa
  id = "projects/threat-vulnerability-analyzer/serviceAccounts/tsunami-web-ui-sa@threat-vulnerability-analyzer.iam.gserviceaccount.com"
}

import {
  to = google_service_account.pubsub_sa
  id = "projects/threat-vulnerability-analyzer/serviceAccounts/tsunami-pubsub-sa@threat-vulnerability-analyzer.iam.gserviceaccount.com"
}

import {
  to = google_pubsub_topic.scan_completed
  id = "projects/threat-vulnerability-analyzer/topics/tsunami-scan-completed"
}

import {
  to = google_cloud_run_v2_job.tsunami_scanner_job
  id = "projects/threat-vulnerability-analyzer/locations/us-central1/jobs/tsunami-scanner"
}

import {
  to = google_cloud_run_service.web_ui_service
  id = "us-central1/threat-vulnerability-analyzer/tsunami-web-ui"
}
