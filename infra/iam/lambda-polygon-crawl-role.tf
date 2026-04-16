data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda_polygon_crawl" {
  name               = "${var.project_prefix}-lambda-polygon-crawl"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "lambda_polygon_crawl_logs" {
  role       = aws_iam_role.lambda_polygon_crawl.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_polygon_crawl_s3_write" {
  role       = aws_iam_role.lambda_polygon_crawl.name
  policy_arn = aws_iam_policy.s3_write_polygons.arn
}