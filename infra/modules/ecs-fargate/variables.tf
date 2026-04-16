variable "cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "crop-classification"
}

variable "container_image" {
  description = "Docker image URL for the processing container (e.g. ECR URL with tag)"
  type        = string
}

variable "cpu" {
  description = "CPU units for the Fargate task (valid: 256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 1024
}

variable "memory" {
  description = "Memory (MiB) for the Fargate task (must be valid for the CPU value)"
  type        = number
  default     = 2048
}

variable "task_role_arn" {
  description = "ARN of the IAM role for the Fargate task (application permissions)"
  type        = string
}

variable "execution_role_arn" {
  description = "ARN of the IAM role for the ECS task execution (image pull, logs)"
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket name passed as S3_BUCKET env var"
  type        = string
}

variable "stac_catalog_url" {
  description = "STAC catalog URL passed as STAC_CATALOG_URL env var"
  type        = string
  default     = "https://earth-search.aws.element84.com/v1"
}

variable "processing_step" {
  description = "Default processing step (bronze, silver, gold) - can be overridden via containerOverrides at runtime"
  type        = string
  default     = "bronze"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}