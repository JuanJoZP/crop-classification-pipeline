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