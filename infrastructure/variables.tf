# General
variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "hub"
}

variable "environment" {
  description = "Environment name (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3" # Paris
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

variable "aws_profile" {
  description = "AWS CLI profile name"
  type = string
}

# Network
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (need 2 for ALB)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (need 2 for RDS)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "availability_zones" {
  description = "Availability zones to use"
  type        = list(string)
  default     = ["eu-west-3a", "eu-west-3b"]
}

# EC2
variable "ec2_instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.small"
}

# RDS
variable "rds_instance_class" {
  description = "RDS instance class (db.t3.micro is free tier eligible)"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "rds_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16"
}

variable "rds_backup_retention" {
  description = "RDS backup retention period in days"
  type        = number
  default     = 7
}

# Domain
variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "hub.vizzuality.com"
}

# GitHub OIDC
variable "github_org" {
  description = "GitHub organization name"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
}

# Monitoring
variable "alarm_email" {
  description = "Email address for CloudWatch alarms (optional)"
  type        = string
  default     = ""
}

# =============================================================================
# Secrets (stored in Secrets Manager, values from tfvars)
# =============================================================================

# Google OAuth
variable "google_client_id" {
  description = "Google OAuth client ID"
  type        = string
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth client secret"
  type        = string
  sensitive   = true
}

# Jira OAuth
variable "jira_client_id" {
  description = "Jira OAuth client ID"
  type        = string
  sensitive   = true
}

variable "jira_client_secret" {
  description = "Jira OAuth client secret"
  type        = string
  sensitive   = true
}

# GitHub
variable "github_token" {
  description = "GitHub personal access token for API access"
  type        = string
  sensitive   = true
}

# Slack (optional)
variable "slack_bot_token" {
  description = "Slack bot token (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

# Grafana Cloud
variable "grafana_cloud_api_token" {
  description = "Grafana Cloud API token for metrics and logs"
  type        = string
  sensitive   = true
  default     = ""
}

variable "grafana_cloud_prometheus_username" {
  description = "Grafana Cloud Prometheus remote_write username"
  type        = string
  default     = ""
}

variable "grafana_cloud_loki_username" {
  description = "Grafana Cloud Loki push username"
  type        = string
  default     = ""
}
