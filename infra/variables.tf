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
  default     = "juanzpjose136@gmail.com"
}

variable "silver_area_threshold_ha" {
  description = "Area threshold in hectares above which polygons are split into grid cells"
  type        = number
  default     = 10.0
}

variable "silver_cell_size_m" {
  description = "Grid cell size in meters for splitting large polygons"
  type        = number
  default     = 223.0
}