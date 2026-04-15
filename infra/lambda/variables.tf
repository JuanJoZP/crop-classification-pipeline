variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "handler" {
  description = "Lambda function handler entry point"
  type        = string
}

variable "python_runtime" {
  description = "Lambda runtime identifier (e.g. python3.10)"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of the IAM role for the Lambda function"
  type        = string
}

variable "source_path" {
  description = "Absolute path to the Lambda source code directory"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 128
}

variable "function_description" {
  description = "Description of the Lambda function"
  type        = string
  default     = ""
}