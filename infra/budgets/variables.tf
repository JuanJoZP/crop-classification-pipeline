variable "budget_alert_email" {
  description = "Email address for budget alerts"
  type        = string
}

variable "budget_limit_amount" {
  description = "Monthly budget limit in USD"
  type        = number
  default     = 1
}

variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "crop-classification"
}