module "iam" {
  source             = "./iam"
  bucket_name        = var.bucket_name
  ecr_repository_arn = module.ecr.repository_arn
}