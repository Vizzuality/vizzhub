# ALB
output "alb_dns_name" {
  description = "ALB DNS name (add CNAME: hub.vizzuality.com → this value)"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "ALB zone ID (for Route53 alias records if needed)"
  value       = aws_lb.main.zone_id
}

# ACM Certificate Validation
output "acm_validation_record" {
  description = "ACM certificate validation CNAME record (add to DNS)"
  value = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}

output "acm_certificate_status" {
  description = "ACM certificate status"
  value       = aws_acm_certificate.main.status
}

# EC2
output "ec2_instance_id" {
  description = "EC2 instance ID (for SSM and GitHub Actions)"
  value       = aws_instance.main.id
}

# RDS
output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

# ECR
output "ecr_backend_url" {
  description = "ECR backend repository URL"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "ECR frontend repository URL"
  value       = aws_ecr_repository.frontend.repository_url
}

# IAM
output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions"
  value       = aws_iam_role.github_actions.arn
}

# Secrets
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

# S3
output "assets_bucket_name" {
  description = "S3 assets bucket name"
  value       = aws_s3_bucket.assets.bucket
}

output "assets_bucket_url" {
  description = "S3 assets bucket regional URL (for image references)"
  value       = "https://${aws_s3_bucket.assets.bucket}.s3.${var.aws_region}.amazonaws.com"
}

# CloudFront (Playbook)
output "playbook_cloudfront_domain" {
  description = "CloudFront domain for playbook (add CNAME: playbook.vizzuality.com → this value)"
  value       = aws_cloudfront_distribution.playbook.domain_name
}

output "playbook_cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.playbook.id
}

output "playbook_acm_validation_record" {
  description = "ACM certificate validation CNAME for playbook.vizzuality.com (add to DNS)"
  value = {
    for dvo in aws_acm_certificate.playbook.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}

# Commands
output "ssm_connect_command" {
  description = "Command to connect to EC2 via SSM"
  value       = "aws ssm start-session --target ${aws_instance.main.id}"
}

# GitHub Actions Variables
output "github_actions_variables" {
  description = "Variables to configure in GitHub Actions"
  value = {
    AWS_ACCOUNT_ID   = var.aws_account_id
    AWS_REGION       = var.aws_region
    EC2_INSTANCE_ID  = aws_instance.main.id
    ECR_BACKEND_URI  = aws_ecr_repository.backend.repository_url
    ECR_FRONTEND_URI = aws_ecr_repository.frontend.repository_url
  }
}

# DNS Setup Instructions
output "dns_setup_instructions" {
  description = "DNS configuration steps"
  value       = <<-EOT
    DNS Configuration Steps:

    1. Add ACM validation CNAMEs (see acm_validation_record + playbook_acm_validation_record):
       - hub.vizzuality.com validation CNAME
       - playbook.vizzuality.com validation CNAME

    2. Wait ~5 minutes for certificate validation

    3. Add application CNAMEs:
       Name:  hub.vizzuality.com      → ${aws_lb.main.dns_name}
       Name:  playbook.vizzuality.com → ${aws_cloudfront_distribution.playbook.domain_name}

    4. Run 'tofu apply' again after DNS is configured
  EOT
}
