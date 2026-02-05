# Hub Infrastructure Deployment Guide

Step-by-step guide to deploy Hub infrastructure from scratch.

## Prerequisites

- [ ] Terraform >= 1.0 installed
- [ ] AWS CLI configured with credentials
- [ ] Access to DNS for `vizzuality.com`
- [ ] Secrets ready (see below)

### Required Secrets

| Secret | Source |
|--------|--------|
| `github_token` | GitHub → Settings → Developer settings → Personal access tokens |
| `google_client_id` | Google Cloud Console → APIs & Services → Credentials |
| `google_client_secret` | Google Cloud Console → APIs & Services → Credentials |
| `jira_client_id` | Atlassian Developer Console → OAuth 2.0 apps |
| `jira_client_secret` | Atlassian Developer Console → OAuth 2.0 apps |
| `slack_bot_token` | Slack API → Your Apps → OAuth & Permissions (optional) |

---

## Phase 1: Prepare Configuration

```bash
cd infrastructure

# Copy and edit tfvars with your secrets
cp environments/prod.tfvars.example environments/prod.tfvars
# Edit prod.tfvars and fill ALL values including secrets
```

---

## Phase 2: Create State Backend (S3 + DynamoDB)

```bash
# Initialize Terraform (local state initially)
terraform init

# Create ONLY state resources first
terraform apply -var-file=environments/prod.tfvars \
  -target=aws_s3_bucket.state \
  -target=aws_s3_bucket.state_logs \
  -target=aws_s3_bucket_versioning.state \
  -target=aws_s3_bucket_server_side_encryption_configuration.state \
  -target=aws_s3_bucket_server_side_encryption_configuration.state_logs \
  -target=aws_s3_bucket_public_access_block.state \
  -target=aws_s3_bucket_public_access_block.state_logs \
  -target=aws_s3_bucket_logging.state \
  -target=aws_s3_bucket_lifecycle_configuration.state_logs \
  -target=aws_s3_bucket_policy.state_https_only \
  -target=aws_s3_bucket_policy.state_logs_https_only \
  -target=aws_dynamodb_table.state_lock
```

---

## Phase 3: Migrate to Remote State

Edit `main.tf` and uncomment the backend block:

```hcl
backend "s3" {
  bucket         = "hub-vizzuality-tfstate"
  key            = "hub/prod/terraform.tfstate"
  region         = "eu-west-3"
  dynamodb_table = "hub-vizzuality-tflock"
  encrypt        = true
}
```

```bash
# Migrate local state to S3
terraform init -migrate-state

# Confirm: yes
```

---

## Phase 4: Create Core Infrastructure (VPC, RDS, ECR, Secrets)

```bash
# Create network, database, ECR, and secrets
terraform apply -var-file=environments/prod.tfvars \
  -target=aws_vpc.main \
  -target=aws_internet_gateway.main \
  -target=aws_subnet.public \
  -target=aws_subnet.private \
  -target=aws_route_table.public \
  -target=aws_route_table.private \
  -target=aws_route_table_association.public \
  -target=aws_route_table_association.private \
  -target=aws_db_subnet_group.main \
  -target=aws_security_group.rds \
  -target=aws_security_group.ec2 \
  -target=aws_security_group.alb \
  -target=random_password.db_password \
  -target=random_password.jwt_secret \
  -target=random_password.session_secret \
  -target=aws_db_instance.main \
  -target=aws_ecr_repository.backend \
  -target=aws_ecr_repository.frontend \
  -target=aws_ecr_lifecycle_policy.backend \
  -target=aws_ecr_lifecycle_policy.frontend \
  -target=aws_secretsmanager_secret.db_password \
  -target=aws_secretsmanager_secret.jwt_secrets \
  -target=aws_secretsmanager_secret.google_oauth \
  -target=aws_secretsmanager_secret.jira_oauth \
  -target=aws_secretsmanager_secret.github \
  -target=aws_secretsmanager_secret.slack \
  -target=aws_secretsmanager_secret_version.db_password \
  -target=aws_secretsmanager_secret_version.jwt_secrets \
  -target=aws_secretsmanager_secret_version.google_oauth \
  -target=aws_secretsmanager_secret_version.jira_oauth \
  -target=aws_secretsmanager_secret_version.github \
  -target=aws_secretsmanager_secret_version.slack
```

---

## Phase 5: Create ACM Certificate

```bash
# Create ACM certificate (will be pending validation)
terraform apply -var-file=environments/prod.tfvars \
  -target=aws_acm_certificate.main
```

Get the validation CNAME:

```bash
terraform output acm_validation_record
```

**Add this CNAME record to DNS** (in the external AWS account managing vizzuality.com).

Wait for validation (~5 minutes), then verify:

```bash
terraform output acm_certificate_status
# Should show: ISSUED
```

---

## Phase 6: Create EC2 and ALB

```bash
# Create remaining infrastructure
terraform apply -var-file=environments/prod.tfvars
```

This creates:
- EC2 instance with IAM roles
- ALB with target groups and listeners
- ACM certificate validation
- CloudWatch alarms (if alarm_email set)
- GitHub OIDC provider

---

## Phase 7: Configure DNS

Get ALB DNS name:

```bash
terraform output alb_dns_name
```

**Add CNAME record to DNS:**

```
hub.vizzuality.com → [alb_dns_name from output]
```

---

## Phase 8: Configure GitHub Actions

Get the values:

```bash
terraform output github_actions_variables
terraform output ec2_instance_id
```

In GitHub → Settings → Secrets and variables → Actions → Variables, add:

| Variable | Value |
|----------|-------|
| `AWS_ACCOUNT_ID` | (from output) |
| `AWS_REGION` | `eu-west-3` |
| `EC2_INSTANCE_ID` | (from output) |

---

## Phase 9: First Deploy

Option A - Push to main:
```bash
git checkout main
git merge chore/infra
git push origin main
```

Option B - Manual trigger:
Go to GitHub → Actions → Deploy → Run workflow

---

## Verification

```bash
# Check ALB health
curl -I https://hub.vizzuality.com/health

# Connect to EC2 via SSM
aws ssm start-session --target $(terraform output -raw ec2_instance_id)

# On EC2, check containers
docker compose -f /opt/hub/docker-compose.prod.yml ps
docker compose -f /opt/hub/docker-compose.prod.yml logs backend
```

---

## Outputs Reference

```bash
# All outputs
terraform output

# Specific outputs
terraform output alb_dns_name
terraform output ec2_instance_id
terraform output rds_endpoint
terraform output ssm_connect_command
terraform output acm_validation_record
terraform output github_actions_variables
```

---

## Rollback

If something goes wrong:

```bash
# Connect to EC2
aws ssm start-session --target <instance-id>

# On EC2, rollback to previous version
cd /opt/hub
export TAG="<previous-git-sha>"
export ECR_URI="<account-id>.dkr.ecr.eu-west-3.amazonaws.com"
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

---

## Destroy (Caution!)

```bash
# This will destroy ALL infrastructure
terraform destroy -var-file=environments/prod.tfvars
```

Note: RDS has `deletion_protection = true`. Disable it first in AWS Console or via terraform before destroy.
