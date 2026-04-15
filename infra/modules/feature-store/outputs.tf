output "feature_group_arn" {
  value = aws_sagemaker_feature_group.this.arn
}

output "feature_group_name" {
  value = aws_sagemaker_feature_group.this.feature_group_name
}