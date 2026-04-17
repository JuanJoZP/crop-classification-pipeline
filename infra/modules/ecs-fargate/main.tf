data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_region" "current" {}

data "external" "git_commit" {
  program = ["${path.module}/../../scripts/git_commit.sh"]
}

resource "aws_ecs_cluster" "this" {
  name = var.cluster_name
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name = aws_ecs_cluster.this.name

  capacity_providers = ["FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 1
    capacity_provider = "FARGATE_SPOT"
  }
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.project_prefix}-processing"
  retention_in_days = var.log_retention_days
}

resource "aws_security_group" "this" {
  name        = "${var.project_prefix}-fargate-processing"
  description = "Security group for Fargate processing tasks (outbound only)"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "this" {
  family                   = "${var.project_prefix}-processing"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "processing"
      image     = var.container_image
      essential = true

      environment = [
        { name = "S3_BUCKET", value = var.bucket_name },
        { name = "PROCESSING_STEP", value = var.processing_step },
        { name = "GIT_SHA", value = data.external.git_commit.result.commit },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "processing"
        }
      }
    }
  ])
}