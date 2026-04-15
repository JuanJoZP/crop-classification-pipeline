data "aws_iam_policy_document" "step_functions_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "step_functions" {
  name               = "${var.project_prefix}-step-functions"
  assume_role_policy = data.aws_iam_policy_document.step_functions_assume_role.json
}

resource "aws_iam_role_policy_attachment" "step_functions_lambda_invoke" {
  role       = aws_iam_role.step_functions.name
  policy_arn = aws_iam_policy.step_functions_invoke_lambda.arn
}

resource "aws_iam_role_policy_attachment" "step_functions_ecs_run_task" {
  role       = aws_iam_role.step_functions.name
  policy_arn = aws_iam_policy.step_functions_run_ecs.arn
}

resource "aws_iam_role_policy_attachment" "step_functions_sagemaker_processing" {
  role       = aws_iam_role.step_functions.name
  policy_arn = aws_iam_policy.step_functions_run_sagemaker.arn
}