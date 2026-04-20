resource "aws_iam_policy" "step_functions_logging" {
  name        = "${var.project_prefix}-step-functions-logging"
  description = "Allow Step Functions to manage CloudWatch Logs, EventBridge rules, and service-linked roles"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "events:PutTargets",
          "events:PutRule",
          "events:DescribeRule"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreateServiceLinkedRole"
        ]
        Resource = "arn:aws:iam::*:role/aws-service-role/states.amazonaws.com/AWSServiceRoleForStates"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "step_functions_logging" {
  role       = module.iam.step_functions_role_name
  policy_arn = aws_iam_policy.step_functions_logging.arn
}

resource "aws_sfn_state_machine" "data_pipeline" {
  name     = "${var.project_prefix}-data-pipeline"
  role_arn = module.iam.step_functions_role_arn
  type     = "STANDARD"

  definition = templatefile(
    "${path.module}/../workflows/data-pipeline.asl.json",
    {
      lambda_crawl_polygons_arn = module.lambda_crawl_polygons.lambda_function_arn
      ecs_cluster_arn           = module.ecs.cluster_arn
      bronze_task_family         = "${var.project_prefix}-processing"
      silver_task_family         = "${var.project_prefix}-silver-processing"
      subnet_ids_json            = jsonencode(module.ecs.subnet_ids)
      security_group_id          = module.ecs.security_group_id
      s3_bucket                  = var.bucket_name
      git_sha                    = data.external.git_commit.result.commit
      ecr_image_uri              = "${module.ecr.repository_url}:latest"
      sagemaker_gold_role_arn    = module.iam.sagemaker_processing_gold_role_arn
      gold_instance_type         = local.sagemaker_processing.gold.instance_type
      gold_instance_count        = local.sagemaker_processing.gold.instance_count
      gold_volume_size           = local.sagemaker_processing.gold.volume_size_in_gb
      gold_job_name               = "${var.project_prefix}-gold-processing"
      feature_group_name          = module.feature_store.feature_group_name
    }
  )

  logging_configuration {
    level = "OFF"
  }

  depends_on = [aws_iam_role_policy_attachment.step_functions_logging]
}