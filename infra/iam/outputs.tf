output "gold_fargate_task_role_arn" {
  value = aws_iam_role.gold_fargate_task.arn
}

output "gold_fargate_task_role_name" {
  value = aws_iam_role.gold_fargate_task.name
}

output "ecs_task_execution_role_arn" {
  value = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_execution_role_name" {
  value = aws_iam_role.ecs_task_execution.name
}

output "fargate_image_copy_role_arn" {
  value = aws_iam_role.fargate_image_copy.arn
}

output "silver_fargate_task_role_arn" {
  value = aws_iam_role.silver_fargate_task.arn
}

output "silver_fargate_task_role_name" {
  value = aws_iam_role.silver_fargate_task.name
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

output "lambda_polygon_crawl_role_arn" {
  value = aws_iam_role.lambda_polygon_crawl.arn
}

output "lambda_polygon_crawl_role_name" {
  value = aws_iam_role.lambda_polygon_crawl.name
}