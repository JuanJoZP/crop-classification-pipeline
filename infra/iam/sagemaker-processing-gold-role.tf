data "aws_iam_policy_document" "sagemaker_assume_role" {
  statement {
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "sagemaker_processing_gold" {
  name               = "${var.project_prefix}-sagemaker-processing-gold"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume_role.json
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_gold_s3_read_processed" {
  role       = aws_iam_role.sagemaker_processing_gold.name
  policy_arn = aws_iam_policy.s3_read_processed.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_gold_featurestore_ingest" {
  role       = aws_iam_role.sagemaker_processing_gold.name
  policy_arn = aws_iam_policy.sagemaker_featurestore_ingest.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_gold_s3_write_feature_store" {
  role       = aws_iam_role.sagemaker_processing_gold.name
  policy_arn = aws_iam_policy.s3_write_feature_store.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_gold_glue" {
  role       = aws_iam_role.sagemaker_processing_gold.name
  policy_arn = aws_iam_policy.glue_feature_store.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_gold_cloudwatch" {
  role       = aws_iam_role.sagemaker_processing_gold.name
  policy_arn = aws_iam_policy.cloudwatch_feature_store.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_gold_ssm_read" {
  role       = aws_iam_role.sagemaker_processing_gold.name
  policy_arn = aws_iam_policy.ssm_read_processor.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_gold_ecr_pull" {
  role       = aws_iam_role.sagemaker_processing_gold.name
  policy_arn = aws_iam_policy.ecr_pull.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_processing_gold_athena" {
  role       = aws_iam_role.sagemaker_processing_gold.name
  policy_arn = aws_iam_policy.sagemaker_gold_athena.arn
}