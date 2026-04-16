data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  bucket_arn = "arn:aws:s3:::${var.bucket_name}"
  feature_group_arns = [for fg in var.feature_group_names :
    "arn:aws:sagemaker:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:feature-group/${fg}"
  ]
}

resource "aws_iam_policy" "s3_write_raw" {
  name        = "s3-write-raw-${var.bucket_name}"
  description = "Write access to raw/ prefix in the project bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${local.bucket_arn}/raw/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = local.bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["raw/*"]
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "s3_read_raw" {
  name        = "s3-read-raw-${var.bucket_name}"
  description = "Read access to raw/ prefix in the project bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${local.bucket_arn}/raw/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = local.bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["raw/*"]
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "s3_write_processed" {
  name        = "s3-write-processed-${var.bucket_name}"
  description = "Write access to processed/ prefix in the project bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${local.bucket_arn}/processed/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = local.bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["processed/*"]
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "s3_read_processed" {
  name        = "s3-read-processed-${var.bucket_name}"
  description = "Read access to processed/ prefix in the project bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${local.bucket_arn}/processed/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = local.bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["processed/*"]
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "sagemaker_featurestore_ingest" {
  name        = "sagemaker-featurestore-ingest"
  description = "Write records to SageMaker Feature Store"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:PutRecord",
          "sagemaker:BatchGetRecord",
          "sagemaker:GetRecord"
        ]
        Resource = local.feature_group_arns
      }
    ]
  })
}

resource "aws_iam_policy" "s3_write_feature_store" {
  name        = "s3-write-feature-store-${var.bucket_name}"
  description = "Write access to feature-store/ prefix in the project bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = "${local.bucket_arn}/feature-store/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = local.bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["feature-store/*"]
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "glue_feature_store" {
  name        = "glue-feature-store"
  description = "Glue permissions for SageMaker Feature Store offline catalog"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:GetTable",
          "glue:GetTableVersions",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:BatchGetPartition",
          "glue:GetDatabase"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_policy" "cloudwatch_feature_store" {
  name        = "cloudwatch-feature-store"
  description = "CloudWatch Logs permissions for SageMaker Feature Store"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
      }
    ]
  })
}

resource "aws_iam_policy" "s3_read_public" {
  name        = "s3-read-public"
  description = "Read access to public S3 buckets for image ingestion"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_policy" "s3_write_polygons" {
  name        = "s3-write-polygons-${var.bucket_name}"
  description = "Write access to polygons/ prefix for Lambda crawl-polygons"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${local.bucket_arn}/polygons/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = local.bucket_arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["polygons/*"]
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "step_functions_invoke_lambda" {
  name        = "${var.project_prefix}-step-functions-invoke-lambda"
  description = "Allow Step Functions to invoke Lambda functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_policy" "step_functions_run_ecs" {
  name        = "${var.project_prefix}-step-functions-run-ecs"
  description = "Allow Step Functions to run ECS/Fargate tasks"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:StopTask",
          "ecs:DescribeTasks"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.fargate_image_copy.arn
        ]
      }
    ]
  })
}

resource "aws_iam_policy" "step_functions_run_sagemaker" {
  name        = "${var.project_prefix}-step-functions-run-sagemaker"
  description = "Allow Step Functions to run SageMaker processing jobs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:CreateProcessingJob",
          "sagemaker:DescribeProcessingJob",
          "sagemaker:StopProcessingJob"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.sagemaker_processing_silver.arn,
          aws_iam_role.sagemaker_processing_gold.arn
        ]
      }
    ]
  })
}