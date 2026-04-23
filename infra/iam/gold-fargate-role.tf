data "aws_iam_policy_document" "gold_fargate_assume_role" {
  statement {
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "gold_fargate_task" {
  name               = "${var.project_prefix}-gold-fargate-task"
  assume_role_policy = data.aws_iam_policy_document.gold_fargate_assume_role.json
}

resource "aws_iam_role_policy_attachment" "gold_fargate_s3_read_processed" {
  role       = aws_iam_role.gold_fargate_task.name
  policy_arn = aws_iam_policy.s3_read_processed.arn
}

resource "aws_iam_role_policy_attachment" "gold_fargate_s3_write_feature_store" {
  role       = aws_iam_role.gold_fargate_task.name
  policy_arn = aws_iam_policy.s3_write_feature_store.arn
}

resource "aws_iam_role_policy_attachment" "gold_fargate_s3_read_polygons" {
  role       = aws_iam_role.gold_fargate_task.name
  policy_arn = aws_iam_policy.s3_read_polygons.arn
}

resource "aws_iam_role_policy_attachment" "gold_fargate_featurestore_ingest" {
  role       = aws_iam_role.gold_fargate_task.name
  policy_arn = aws_iam_policy.sagemaker_featurestore_ingest.arn
}

resource "aws_iam_role_policy_attachment" "gold_fargate_glue_feature_store" {
  role       = aws_iam_role.gold_fargate_task.name
  policy_arn = aws_iam_policy.glue_feature_store.arn
}

resource "aws_iam_role_policy_attachment" "gold_fargate_cloudwatch" {
  role       = aws_iam_role.gold_fargate_task.name
  policy_arn = aws_iam_policy.cloudwatch_feature_store.arn
}

resource "aws_iam_role_policy_attachment" "gold_fargate_athena" {
  role       = aws_iam_role.gold_fargate_task.name
  policy_arn = aws_iam_policy.sagemaker_gold_athena.arn
}

resource "aws_iam_role_policy_attachment" "gold_fargate_ssm_read" {
  role       = aws_iam_role.gold_fargate_task.name
  policy_arn = aws_iam_policy.ssm_read_processor.arn
}