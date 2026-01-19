
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
