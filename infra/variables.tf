variable "bucket_name" {
  description = "Name of the project S3 bucket (to be created later)"
  type        = string
  default     = "crop-classification-data"
}

variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "crop-classification"
}

variable "budget_alert_email" {
  description = "Email address for budget alerts"
  type        = string
}