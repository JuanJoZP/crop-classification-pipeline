output "parameter_names" {
  value = concat(
    [aws_ssm_parameter.copernicus_s3_endpoint.name],
    [aws_ssm_parameter.copernicus_s3_access_key.name],
    [aws_ssm_parameter.copernicus_s3_secret_key.name],
    [aws_ssm_parameter.bronze_catalog_url.name],
    [aws_ssm_parameter.bronze_max_cloud_cover.name],
    [aws_ssm_parameter.bronze_s2_processing_baseline_min.name],
    [aws_ssm_parameter.bronze_bands.name],
    [aws_ssm_parameter.bronze_resolution.name],
    [aws_ssm_parameter.bronze_crs.name],
    [aws_ssm_parameter.bronze_dtype.name],
    [aws_ssm_parameter.bronze_workers_per_core.name],
  )
}