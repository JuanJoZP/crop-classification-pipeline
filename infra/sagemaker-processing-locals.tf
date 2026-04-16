locals {
  sagemaker_processing = {
    silver = {
      processing_step   = "silver"
      instance_type     = "ml.t3.medium"
      instance_count    = 1
      volume_size_in_gb = 4
      role_arn          = module.iam.sagemaker_processing_silver_role_arn
      container_image   = "${module.ecr.repository_url}:latest"
      environment = {
        S3_BUCKET       = var.bucket_name
        PROCESSING_STEP = "silver"
      }
    }
    gold = {
      processing_step   = "gold"
      instance_type     = "ml.t3.medium"
      instance_count    = 1
      volume_size_in_gb = 4
      role_arn          = module.iam.sagemaker_processing_gold_role_arn
      container_image   = "${module.ecr.repository_url}:latest"
      environment = {
        S3_BUCKET          = var.bucket_name
        PROCESSING_STEP    = "gold"
        FEATURE_GROUP_NAME = module.feature_store.feature_group_name
      }
    }
  }
}