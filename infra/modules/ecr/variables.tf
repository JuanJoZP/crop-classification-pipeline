variable "repository_name" {
  description = "Name of the ECR repository"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "crop-classification"
}

variable "max_image_count" {
  description = "Maximum number of images to retain in ECR"
  type        = number
  default     = 3
}