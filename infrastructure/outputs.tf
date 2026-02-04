output "ec2_instance_id" {
  description = "EC2 instance ID (for SSM and GitHub Actions)"
  value       = aws_instance.main.id
}

output "ec2_elastic_ip" {
  description = "Elastic IP address (point DNS here)"
  value       = aws_eip.main.public_ip
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "ECR frontend repository URL"
  value       = aws_ecr_repository.frontend.repository_url
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions"
  value       = aws_iam_role.github_actions.arn
}

output "secrets_arns" {
  description = "Secrets Manager ARNs"
  value = {
    db_password  = aws_secretsmanager_secret.db_password.arn
    jwt_secrets  = aws_secretsmanager_secret.jwt_secrets.arn
    google_oauth = aws_secretsmanager_secret.google_oauth.arn
    jira_oauth   = aws_secretsmanager_secret.jira_oauth.arn
    github       = aws_secretsmanager_secret.github.arn
    slack        = aws_secretsmanager_secret.slack.arn
  }
}

output "ssm_connect_command" {
  description = "Command to connect to EC2 via SSM"
  value       = "aws ssm start-session --target ${aws_instance.main.id}"
}

output "github_actions_variables" {
  description = "Variables to configure in GitHub Actions"
  value = {
    AWS_ACCOUNT_ID    = data.aws_caller_identity.current.account_id
    AWS_REGION        = var.aws_region
    EC2_INSTANCE_ID   = aws_instance.main.id
    ECR_BACKEND_URI   = aws_ecr_repository.backend.repository_url
    ECR_FRONTEND_URI  = aws_ecr_repository.frontend.repository_url
  }
}
