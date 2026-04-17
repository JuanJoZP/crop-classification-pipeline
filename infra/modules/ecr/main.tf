resource "aws_ecr_repository" "this" {
  name                 = var.repository_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# NOTE: ECR lifecycle policy exists (created via AWS CLI) but is not managed by
# Terraform due to a bug in the AWS provider v5.100.0 that crashes on
# aws_ecr_lifecycle_policy resources with nil pointer dereference in
# lifecyclePolicyRuleSelection.reduce(). To re-create:
#   aws ecr put-lifecycle-policy \
#     --repository-name crop-classification-processing \
#     --lifecycle-policy-text '{"rules":[{"rulePriority":1,"description":"Keep only 3 images","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":3},"action":{"type":"expire"}}]}'