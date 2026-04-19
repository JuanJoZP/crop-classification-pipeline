data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "silver_fargate_task" {
  name               = "${var.project_prefix}-silver-fargate-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
}

resource "aws_iam_role_policy_attachment" "silver_fargate_s3_read_raw" {
  role       = aws_iam_role.silver_fargate_task.name
  policy_arn = aws_iam_policy.s3_read_raw.arn
}

resource "aws_iam_role_policy_attachment" "silver_fargate_s3_read_processed" {
  role       = aws_iam_role.silver_fargate_task.name
  policy_arn = aws_iam_policy.s3_read_processed.arn
}

resource "aws_iam_role_policy_attachment" "silver_fargate_s3_write_processed" {
  role       = aws_iam_role.silver_fargate_task.name
  policy_arn = aws_iam_policy.s3_write_processed.arn
}

resource "aws_iam_role_policy_attachment" "silver_fargate_ssm_read" {
  role       = aws_iam_role.silver_fargate_task.name
  policy_arn = aws_iam_policy.ssm_read_processor.arn
}