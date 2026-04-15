resource "null_resource" "install_dependencies" {
  triggers = {
    dependencies_hash = filemd5("${var.source_path}/requirements.txt")
  }

  provisioner "local-exec" {
    command = "pip install -r ${var.source_path}/requirements.txt -t ${var.source_path}/"
  }
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = var.source_path
  output_path = "${path.module}/${var.function_name}.zip"
  excludes    = ["__pycache__", "*.pyc"]

  depends_on = [null_resource.install_dependencies]
}

data "external" "git_commit" {
  program = ["git", "rev-parse", "--short", "HEAD"]
}

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  role          = var.lambda_role_arn
  handler       = var.handler
  runtime       = var.python_runtime
  timeout       = var.timeout
  memory_size   = var.memory_size
  description   = "Commit: ${data.external.git_commit.result.commit} - ${var.function_description}"
  publish       = true

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

  depends_on = [null_resource.install_dependencies]
}