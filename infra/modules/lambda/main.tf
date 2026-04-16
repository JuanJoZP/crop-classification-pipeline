resource "null_resource" "install_dependencies" {
  triggers = {
    dependencies_hash = filemd5("${var.source_path}/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      rm -rf ${path.module}/deps
      pip install -r ${var.source_path}/requirements.txt -t ${path.module}/deps
      rsync -a --include='*.py' --include='*/' --exclude='*' ${var.source_path}/ ${path.module}/deps/
    EOT
  }

  provisioner "local-exec" {
    when       = destroy
    command    = "rm -rf ${path.module}/deps"
    on_failure = continue
  }
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/deps"
  output_path = "${path.module}/${var.function_name}.zip"
  excludes    = ["__pycache__", "*.pyc"]

  depends_on = [null_resource.install_dependencies]
}

data "external" "git_commit" {
  program = ["${path.module}/../../scripts/git_commit.sh"]
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