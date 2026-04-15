module "iam" {
  source      = "./iam"
  bucket_name = var.bucket_name
}