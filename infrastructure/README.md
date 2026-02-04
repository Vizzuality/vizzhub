# Hub Infrastructure

OpenTofu/Terraform configuration for deploying Hub (Project Scorecard) to AWS.

## Architecture

- **EC2 t3.medium**: Docker Compose with frontend, backend, worker, nginx, redis
- **RDS db.t4g.small**: PostgreSQL 16 with automated backups
- **ECR**: Container registry for Docker images
- **Secrets Manager**: Secure storage for credentials
- **SSM Session Manager**: Secure shell access (no SSH)

Estimated monthly cost: ~$58 (on-demand) / ~$39 (reserved instances)

## Prerequisites

- [OpenTofu](https://opentofu.org/) or Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- GitHub repository for CI/CD

## Quick Start

### 1. Bootstrap (First Time Only)

Create S3 bucket and DynamoDB table for state storage:

```bash
cd bootstrap
tofu init
tofu apply
```

Save the outputs - you'll need the bucket name and table name.

### 2. Configure Backend

Edit `main.tf` and uncomment the backend configuration:

```hcl
backend "s3" {
  bucket         = "hub-vizzuality-tfstate"  # from bootstrap output
  key            = "hub/prod/terraform.tfstate"
  region         = "eu-west-1"
  dynamodb_table = "hub-vizzuality-tflock"   # from bootstrap output
  encrypt        = true
}
```

### 3. Configure Variables

Copy and edit the production variables:

```bash
cp environments/prod.tfvars.example environments/prod.tfvars
# Edit prod.tfvars with your values
```

Required variables:
- `github_org`: Your GitHub organization name
- `github_repo`: Your GitHub repository name
- `admin_email`: Email for Let's Encrypt certificates

### 4. Deploy Infrastructure

```bash
tofu init
tofu plan -var-file=environments/prod.tfvars
tofu apply -var-file=environments/prod.tfvars
```

### 5. Configure DNS

Point your domain to the Elastic IP from the outputs:

```
hub.vizzuality.com → [elastic_ip_from_output]
```

**IMPORTANT**: DNS must be configured BEFORE the EC2 instance can obtain SSL certificates.

### 6. Fill Manual Secrets

In AWS Console → Secrets Manager, fill these secrets:

| Secret | Required Fields |
|--------|-----------------|
| `/hub/prod/google-oauth` | `client_id`, `client_secret` |
| `/hub/prod/jira-oauth` | `client_id`, `client_secret` |
| `/hub/prod/github` | `token`, `org` |
| `/hub/prod/slack` | `bot_token` (optional) |

Auto-generated secrets (DO NOT EDIT):
- `/hub/prod/db-password`
- `/hub/prod/jwt-secrets`

### 7. Configure GitHub Actions

In GitHub → Settings → Secrets and variables → Actions → Variables:

| Variable | Value |
|----------|-------|
| `AWS_ACCOUNT_ID` | Your AWS account ID |
| `AWS_REGION` | `eu-west-1` |
| `EC2_INSTANCE_ID` | From tofu output |

No secrets needed - authentication uses OIDC.

### 8. First Deploy

Push to `main` branch or trigger workflow manually.

## Operations

### Connect to EC2

```bash
aws ssm start-session --target $(tofu output -raw ec2_instance_id)
```

### View Logs

```bash
# SSH into EC2 first, then:
docker compose -f /opt/hub/docker-compose.prod.yml logs -f
```

### Manual Deploy

```bash
# SSH into EC2 first, then:
/opt/hub/deploy.sh <git-sha>
```

### Manual Rollback

```bash
# SSH into EC2 first, then:
source /opt/hub/.env.infra
export TAG="<previous-sha>"
docker compose -f /opt/hub/docker-compose.prod.yml pull
docker compose -f /opt/hub/docker-compose.prod.yml up -d
```

### Renew SSL Certificate (if needed)

```bash
# SSH into EC2 first, then:
docker compose -f /opt/hub/docker-compose.prod.yml stop nginx
certbot certonly --standalone \
  -d hub.vizzuality.com \
  --config-dir /opt/hub/certbot/config \
  --work-dir /opt/hub/certbot/work \
  --logs-dir /opt/hub/certbot/logs
docker compose -f /opt/hub/docker-compose.prod.yml start nginx
```

## File Structure

```
infrastructure/
├── bootstrap/           # State storage (run first)
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── main.tf              # Provider and backend
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── network.tf           # VPC, subnets, routing
├── security_groups.tf   # Firewall rules
├── ec2.tf               # EC2 instance + IAM
├── rds.tf               # PostgreSQL database
├── ecr.tf               # Container registry
├── secrets.tf           # Secrets Manager
├── iam.tf               # GitHub OIDC
├── cloudwatch.tf        # Logs and alarms
│
├── templates/
│   └── user_data.sh     # EC2 bootstrap script
│
├── environments/
│   └── prod.tfvars.example  # Production config template
│
└── README.md
```

## Troubleshooting

### SSL Certificate Failed

If certbot fails during initial setup:

1. Verify DNS is pointing to the Elastic IP: `dig hub.vizzuality.com`
2. SSH into EC2 and run certbot manually (see above)

### Deploy Failed

Check SSM command output in GitHub Actions logs, or:

```bash
# SSH into EC2
cat /var/log/hub/deploy-*.log | tail -100
```

### Database Connection Failed

```bash
# SSH into EC2
docker exec hub-backend python -c "
from sqlalchemy import text
from app.database import engine
with engine.connect() as conn:
    print(conn.execute(text('SELECT 1')).fetchone())
"
```

### Container Won't Start

```bash
# SSH into EC2
docker compose -f /opt/hub/docker-compose.prod.yml logs backend
docker compose -f /opt/hub/docker-compose.prod.yml logs frontend
```

## Security

- No SSH access (port 22 closed) - use SSM Session Manager
- RDS not publicly accessible - only reachable from EC2
- All secrets in AWS Secrets Manager
- HTTPS only with automatic certificate renewal
- IMDSv2 required (no IMDSv1)
- Root volume encrypted

## Costs

| Resource | Monthly Cost |
|----------|-------------|
| EC2 t3.medium | ~$30 |
| RDS db.t4g.small | ~$23 |
| RDS Storage 20GB | ~$2.30 |
| Secrets Manager | ~$2 |
| Elastic IP | $0 (when attached) |
| **Total** | **~$58** |

With 1-year Reserved Instances: ~$39/month
