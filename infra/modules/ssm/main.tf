# ── Copernicus S3 credentials ──

resource "aws_ssm_parameter" "copernicus_s3_endpoint" {
  name        = "/${var.project_prefix}/copernicus/s3_endpoint"
  description = "S3 endpoint URL for Copernicus data access"
  type        = "String"
  value       = var.copernicus_s3_endpoint
}

resource "aws_ssm_parameter" "copernicus_s3_access_key" {
  name        = "/${var.project_prefix}/copernicus/s3_access_key"
  description = "Access key for Copernicus S3 data access"
  type        = "SecureString"
  value       = "CHANGE_ME"
}

resource "aws_ssm_parameter" "copernicus_s3_secret_key" {
  name        = "/${var.project_prefix}/copernicus/s3_secret_key"
  description = "Secret key for Copernicus S3 data access"
  type        = "SecureString"
  value       = "CHANGE_ME"
}

# ── Bronze processor config ──

resource "aws_ssm_parameter" "bronze_catalog_url" {
  name        = "/${var.project_prefix}/bronze/catalog_url"
  description = "STAC catalog URL for Sentinel-2 data"
  type        = "String"
  value       = var.bronze_catalog_url
}

resource "aws_ssm_parameter" "bronze_max_cloud_cover" {
  name        = "/${var.project_prefix}/bronze/max_cloud_cover"
  description = "Max cloud cover percentage for Sentinel-2 item filtering"
  type        = "String"
  value       = tostring(var.bronze_max_cloud_cover)
}

resource "aws_ssm_parameter" "bronze_s2_processing_baseline_min" {
  name        = "/${var.project_prefix}/bronze/s2_processing_baseline_min"
  description = "Minimum Sentinel-2 processing baseline version"
  type        = "String"
  value       = var.bronze_s2_processing_baseline_min
}

resource "aws_ssm_parameter" "bronze_bands" {
  name        = "/${var.project_prefix}/bronze/bands"
  description = "Comma-separated Sentinel-2 bands to download"
  type        = "String"
  value       = join(",", var.bronze_bands)
}

resource "aws_ssm_parameter" "bronze_resolution" {
  name        = "/${var.project_prefix}/bronze/resolution"
  description = "Resolution in degrees for Sentinel-2 data"
  type        = "String"
  value       = var.bronze_resolution
}

resource "aws_ssm_parameter" "bronze_crs" {
  name        = "/${var.project_prefix}/bronze/crs"
  description = "Target CRS for Sentinel-2 data"
  type        = "String"
  value       = var.bronze_crs
}

resource "aws_ssm_parameter" "bronze_dtype" {
  name        = "/${var.project_prefix}/bronze/dtype"
  description = "NumPy dtype for Sentinel-2 data"
  type        = "String"
  value       = var.bronze_dtype
}

resource "aws_ssm_parameter" "bronze_workers" {
  name        = "/${var.project_prefix}/bronze/workers"
  description = "Number of ThreadPoolExecutor workers for bronze processing"
  type        = "String"
  value       = tostring(var.bronze_workers)
}

# ── Silver processor config ──

resource "aws_ssm_parameter" "silver_aoi_padding" {
  name        = "/${var.project_prefix}/silver/aoi_padding"
  description = "Erosion iterations for AOI mask"
  type        = "String"
  value       = tostring(var.silver_aoi_padding)
}

resource "aws_ssm_parameter" "silver_clouds_padding" {
  name        = "/${var.project_prefix}/silver/clouds_padding"
  description = "Erosion iterations for clear pixels mask"
  type        = "String"
  value       = tostring(var.silver_clouds_padding)
}

resource "aws_ssm_parameter" "silver_cloud_mask_scl_keep_classes" {
  name        = "/${var.project_prefix}/silver/cloud_mask_scl_keep_classes"
  description = "SCL classes to keep in clear pixels mask (comma-separated)"
  type        = "String"
  value       = join(",", var.silver_cloud_mask_scl_keep_classes)
}

resource "aws_ssm_parameter" "silver_calc_phenometrics" {
  name        = "/${var.project_prefix}/silver/calc_phenometrics"
  description = "Whether to calculate phenological variables"
  type        = "String"
  value       = tostring(var.silver_calc_phenometrics)
}

resource "aws_ssm_parameter" "silver_indexes" {
  name        = "/${var.project_prefix}/silver/indexes"
  description = "Spectral indexes to calculate (comma-separated)"
  type        = "String"
  value       = var.silver_indexes
}

# ── Gold processor config ──

resource "aws_ssm_parameter" "gold_normalization_method" {
  name        = "/${var.project_prefix}/gold/normalization_method"
  description = "Normalization method: minmax or zscore"
  type        = "String"
  value       = var.gold_normalization_method
}

resource "aws_ssm_parameter" "gold_target_column" {
  name        = "/${var.project_prefix}/gold/target_column"
  description = "Column name for the crop label"
  type        = "String"
  value       = var.gold_target_column
}