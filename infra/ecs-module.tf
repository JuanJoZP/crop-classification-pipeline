module "ecs" {
  source = "./modules/ecs-fargate"

  cluster_name       = var.project_prefix
  container_image    = "${module.ecr.repository_url}:latest"
  task_role_arn      = module.iam.fargate_image_copy_role_arn
  execution_role_arn = module.iam.ecs_task_execution_role_arn
  bucket_name        = var.bucket_name
  stac_catalog_url   = "https://earth-search.aws.element84.com/v1"
}