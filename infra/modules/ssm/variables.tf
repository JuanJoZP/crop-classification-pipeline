variable "project_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "crop-classification"
}

variable "copernicus_s3_endpoint" {
  description = "S3 endpoint URL for Copernicus data access"
  type        = string
  default     = "eodata.dataspace.copernicus.eu"
}

variable "bronze_catalog_url" {
  description = "STAC catalog URL for Sentinel-2 data"
  type        = string
  default     = "https://earth-search.aws.element84.com/v1"
}

variable "bronze_max_cloud_cover" {
  description = "Max cloud cover percentage for Sentinel-2 item filtering"
  type        = number
  default     = 70
}

variable "bronze_s2_processing_baseline_min" {
  description = "Minimum Sentinel-2 processing baseline version"
  type        = string
  default     = "05.00"
}

variable "bronze_bands" {
  description = "Sentinel-2 bands to download"
  type        = list(string)
  default     = ["coastal", "blue", "green", "red", "rededge1", "rededge2", "rededge3", "nir", "nir08", "nir09", "swir16", "swir22", "aot", "scl"]
}

variable "bronze_resolution" {
  description = "Resolution in degrees for Sentinel-2 data"
  type        = string
  default     = "0.00009009"
}

variable "bronze_crs" {
  description = "Target CRS for Sentinel-2 data"
  type        = string
  default     = "EPSG:4326"
}

variable "bronze_dtype" {
  description = "NumPy dtype for Sentinel-2 data"
  type        = string
  default     = "uint16"
}

variable "bronze_workers_per_core" {
  description = "ThreadPoolExecutor workers per CPU core"
  type        = number
  default     = 20
}