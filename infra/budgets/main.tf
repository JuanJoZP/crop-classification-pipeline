resource "aws_budgets_budget" "monthly" {
  name              = "${var.project_prefix}-monthly"
  budget_type       = "COST"
  limit_amount      = var.budget_limit_amount
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2026-01-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    threshold                  = 100
    subscriber_sns_topic_arns  = []
    subscriber_email_addresses = [var.budget_alert_email]
  }
}