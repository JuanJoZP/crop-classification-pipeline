variable "bucket_name" {
  description = "Name of the S3 bucket for the data lake"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "crop-classification"
}

variable "raw_expiration_days" {
  description = "Days before expiring objects in the raw/ prefix"
  type        = number
  default     = 7
}

variable "polygons_expiration_days" {
  description = "Days before expiring objects in the polygons/ prefix"
  type        = number
  default     = 1
}