output "sagemaker_processing_config" {
  value = local.sagemaker_processing
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "s3_bucket_name" {
  value = var.bucket_name
}

output "github_actions_role_arn" {
  value = module.github_oidc.role_arn
}

output "silver_task_definition_arn" {
  value = aws_ecs_task_definition.silver.arn
}