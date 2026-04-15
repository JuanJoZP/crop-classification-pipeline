variable "bucket_name" {
  description = "Name of the S3 bucket for the data lake"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "crop-classification"
}

variable "feature_store_role_arn" {
  description = "ARN of the IAM role for SageMaker Feature Store"
  type        = string
}

variable "feature_group_name" {
  description = "Name of the SageMaker Feature Group"
  type        = string
  default     = "crop-polygon-features"
}