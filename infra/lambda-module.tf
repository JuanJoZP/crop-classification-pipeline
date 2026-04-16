locals {
  python_version = trimspace(file("${path.module}/../.python-version"))
  python_runtime = "python${regex("^[0-9]+\\.[0-9]+", local.python_version)}"
}

module "lambda_crawl_polygons" {
  source               = "./modules/lambda"
  function_name        = "${var.project_prefix}-crawl-polygons"
  function_description = "Crawlea los polígonos, label y metadatos del dataset del UPRA"
  handler              = "lambda_handler.handler"
  python_runtime       = local.python_runtime
  lambda_role_arn      = module.iam.lambda_polygon_crawl_role_arn
  source_path          = "${path.module}/../src/lambdas/crawl_polygons"

  environment_variables = {
    UPRA_GEOSERVICIOS_URL = "https://geoservicios.upra.gov.co/arcgis/rest/services"
    S3_BUCKET             = var.bucket_name
    S3_PREFIX             = "polygons"
  }
}