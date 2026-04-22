data "aws_region" "current" {}

resource "aws_ecs_task_definition" "silver" {
  family                   = "${var.project_prefix}-silver-processing"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = module.iam.ecs_task_execution_role_arn
  task_role_arn            = module.iam.silver_fargate_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "processing"
      image     = "${module.ecr.repository_url}:latest"
      essential = true

      environment = [
        { name = "S3_BUCKET", value = var.bucket_name },
        { name = "PROCESSING_STEP", value = "silver" },
        { name = "GIT_SHA", value = data.external.git_commit.result.commit },
        { name = "AREA_THRESHOLD_HA", value = tostring(var.silver_area_threshold_ha) },
        { name = "CELL_SIZE_M", value = tostring(var.silver_cell_size_m) },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = module.ecs.log_group_name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "silver"
        }
      }
    }
  ])
}