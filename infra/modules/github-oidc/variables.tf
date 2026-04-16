variable "repository_name" {
  description = "GitHub repository in the format owner/repo (e.g. JuanJoZP/crop-classification-pipeline)"
  type        = string
}

variable "branch_name" {
  description = "GitHub branch allowed to assume the role"
  type        = string
  default     = "main"
}

variable "ecr_repository_arn" {
  description = "ARN of the ECR repository to allow push access"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "crop-classification"
}