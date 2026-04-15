output "ecs_task_execution_role_arn" {
  value = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_execution_role_name" {
  value = aws_iam_role.ecs_task_execution.name
}

output "fargate_image_copy_role_arn" {
  value = aws_iam_role.fargate_image_copy.arn
}

output "sagemaker_processing_silver_role_arn" {
  value = aws_iam_role.sagemaker_processing_silver.arn
}

output "sagemaker_processing_silver_role_name" {
  value = aws_iam_role.sagemaker_processing_silver.name
}

output "sagemaker_processing_gold_role_arn" {
  value = aws_iam_role.sagemaker_processing_gold.arn
}

output "sagemaker_processing_gold_role_name" {
  value = aws_iam_role.sagemaker_processing_gold.name
}

output "step_functions_role_arn" {
  value = aws_iam_role.step_functions.arn
}

output "step_functions_role_name" {
  value = aws_iam_role.step_functions.name
}