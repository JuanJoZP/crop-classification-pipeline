module "github_oidc" {
  source             = "./modules/github-oidc"
  repository_name    = "JuanJoZP/crop-classification-pipeline"
  ecr_repository_arn = module.ecr.repository_arn
}