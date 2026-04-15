data "aws_iam_policy_document" "sagemaker_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "sagemaker_processing_silver" {
  name               = "${var.project_prefix}-sagemaker-processing-silver"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume_role.json
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_silver_s3_read_raw" {
  role       = aws_iam_role.sagemaker_processing_silver.name
  policy_arn = aws_iam_policy.s3_read_raw.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_silver_s3_write_processed" {
  role       = aws_iam_role.sagemaker_processing_silver.name
  policy_arn = aws_iam_policy.s3_write_processed.arn
}