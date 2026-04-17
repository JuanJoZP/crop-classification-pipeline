data "external" "source_hash" {
  program = ["bash", "-c", "find ${var.source_path} -name '*.py' -o -name 'requirements.txt' | sort | xargs md5sum | md5sum | awk '{print $1}' | jq -R -s '{hash: .}' | tr -d '\\n'"]
}

resource "terraform_data" "install_dependencies" {
  triggers_replace = {
    source_hash = data.external.source_hash.result.hash
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

  depends_on = [terraform_data.install_dependencies]
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
  publish       = false

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

  depends_on = [terraform_data.install_dependencies]
}