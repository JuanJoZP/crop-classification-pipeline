resource "aws_ecr_repository" "this" {
  name                 = var.repository_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [{
      rulePriority  = 1
      description   = "Keep last ${var.max_image_count} images"
      selectionType = "imageCountMoreThan"
      countNumber   = var.max_image_count
      action = {
        type = "expire"
      }
    }]
  })
}