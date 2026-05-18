
variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "The Google Cloud Region"
  type        = string
  default     = "us-central1"
}

variable "vt_api_key" {
  description = "Google Threat Intelligence / VirusTotal API Key"
  type        = string
  sensitive   = true
}

variable "authorized_member" {
  description = "The IAM member allowed to access the Web UI (e.g., user:your-email@domain.com, domain:altostrat.com)"
  type        = string
  default     = "domain:altostrat.com"
}
