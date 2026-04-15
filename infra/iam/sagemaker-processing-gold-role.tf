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