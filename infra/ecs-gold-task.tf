variable "feature_group_name" {
  description = "SageMaker Feature Group name"
  type        = string
}

resource "aws_ecs_task_definition" "gold" {
  family                   = "${var.project_prefix}-gold-processing"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = module.iam.ecs_task_execution_role_arn
  task_role_arn            = module.iam.gold_fargate_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "processing"
      image     = "${module.ecr.repository_url}:latest"
      essential = true

      environment = [
        { name = "S3_BUCKET", value = var.bucket_name },
        { name = "PROCESSING_STEP", value = "gold" },
        { name = "GIT_SHA", value = data.external.git_commit.result.commit },
        { name = "FEATURE_GROUP_NAME", value = var.feature_group_name },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = module.ecs.log_group_name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "gold"
        }
      }
    }
  ])
}