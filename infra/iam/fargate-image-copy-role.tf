resource "aws_iam_role" "fargate_image_copy" {
  name = "${var.project_prefix}-fargate-image-copy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "fargate_image_copy_s3_write_raw" {
  role       = aws_iam_role.fargate_image_copy.name
  policy_arn = aws_iam_policy.s3_write_raw.arn
}

resource "aws_iam_role_policy_attachment" "fargate_image_copy_s3_read_public" {
  role       = aws_iam_role.fargate_image_copy.name
  policy_arn = aws_iam_policy.s3_read_public.arn
}

resource "aws_iam_role_policy_attachment" "fargate_image_copy_s3_read_polygons" {
  role       = aws_iam_role.fargate_image_copy.name
  policy_arn = aws_iam_policy.s3_read_polygons.arn
}