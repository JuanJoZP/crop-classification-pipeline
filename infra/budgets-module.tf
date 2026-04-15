module "budgets" {
  source             = "./budgets"
  budget_alert_email = var.budget_alert_email
}