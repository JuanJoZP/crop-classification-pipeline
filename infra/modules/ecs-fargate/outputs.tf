output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.this.arn
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.this.arn
}

output "subnet_ids" {
  value = data.aws_subnets.default.ids
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "container_name" {
  value = "processing"
}