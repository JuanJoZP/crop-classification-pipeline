module "feature_store" {
  source                 = "./feature-store"
  bucket_name            = var.bucket_name
  feature_store_role_arn = module.iam.sagemaker_processing_gold_role_arn
  feature_group_name     = "crop-polygon-features"
}