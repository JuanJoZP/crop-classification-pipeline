module "ssm" {
  source = "./modules/ssm"

  project_prefix = var.project_prefix
}