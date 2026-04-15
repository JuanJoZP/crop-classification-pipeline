variable "bucket_name" {
  description = "Name of the project S3 bucket"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for all IAM resource names"
  type        = string
  default     = "crop-classification"
}

variable "feature_group_names" {
  description = "SageMaker Feature Group names to allow in IAM policies"
  type        = list(string)
  default     = ["crop_features"]
}