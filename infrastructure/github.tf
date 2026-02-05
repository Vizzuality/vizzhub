# GitHub Provider Configuration
provider "github" {
  owner = var.github_org
  token = var.github_token
}

# GitHub Actions Secrets
resource "github_actions_secret" "aws_account_id" {
  repository      = var.github_repo
  secret_name     = "AWS_ACCOUNT_ID"
  plaintext_value = var.aws_account_id
}

resource "github_actions_secret" "aws_region" {
  repository      = var.github_repo
  secret_name     = "AWS_REGION"
  plaintext_value = var.aws_region
}

resource "github_actions_secret" "ec2_instance_id" {
  repository      = var.github_repo
  secret_name     = "EC2_INSTANCE_ID"
  plaintext_value = aws_instance.main.id
}
