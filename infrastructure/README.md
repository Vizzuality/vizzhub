# Hub Infrastructure

OpenTofu/Terraform configuration for deploying Hub (Project Scorecard) to AWS.

## Architecture

```
Internet → ALB (HTTPS/ACM) → EC2 (Docker Compose)
              ↓ path routing       ├── backend:8000
              ├── /api/*  ────────→│
              └── /*      ────────→├── frontend:5173
                                   ├── worker (arq)
                                   └── redis
```

**Components:**

| Service | Type | Purpose |
|---------|------|---------|
| ALB | - | HTTPS termination (ACM), path-based routing |
| EC2 | t3.micro | Docker host (frontend, backend, worker, redis) |
| RDS | db.t3.micro | PostgreSQL 16 with automated backups |
| ECR | - | Container registry |
| Secrets Manager | - | All credentials (from tfvars) |
| SSM | - | Secure shell access (no SSH) |

## Quick Start

**For step-by-step deployment, see [DEPLOYMENT.md](./DEPLOYMENT.md)**

### TL;DR

```bash
cd infrastructure

# 1. Configure
cp environments/prod.tfvars.example environments/prod.tfvars
# Edit prod.tfvars with ALL values including secrets

# 2. Deploy
terraform init
terraform apply -var-file=environments/prod.tfvars

# 3. Add DNS records (from outputs)
terraform output acm_validation_record  # Add to DNS, wait 5 min
terraform apply -var-file=environments/prod.tfvars
terraform output alb_dns_name  # Add hub.vizzuality.com CNAME

# 4. Configure GitHub Actions (from outputs)
terraform output github_actions_variables

# 5. Push to main
```

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

Deploy a specific version:

```bash
# SSH into EC2 first
cd /opt/hub
export TAG="<git-sha>"
export ECR_URI="<account-id>.dkr.ecr.eu-west-1.amazonaws.com"

aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $ECR_URI
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Rollback

```bash
# SSH into EC2 first
cd /opt/hub
export TAG="<previous-sha>"
export ECR_URI="<account-id>.dkr.ecr.eu-west-1.amazonaws.com"
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Refresh Secrets

If you update secrets in AWS Secrets Manager, re-run the deploy workflow or manually recreate .env:

```bash
# SSH into EC2 via SSM, then re-deploy to fetch new secrets
# Or trigger the GitHub Actions deploy workflow
docker compose -f /opt/hub/docker-compose.prod.yml restart backend worker
```

## File Structure

```
infrastructure/
├── main.tf              # Provider and backend
├── state.tf             # S3/DynamoDB for state storage
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── network.tf           # VPC, subnets, routing
├── security_groups.tf   # Firewall rules
├── alb.tf               # ALB, ACM, target groups, listeners
├── ec2.tf               # EC2 instance + IAM
├── rds.tf               # PostgreSQL database
├── ecr.tf               # Container registry
├── secrets.tf           # Secrets Manager
├── iam.tf               # IAM policies
├── github.tf            # GitHub OIDC provider and role
├── cloudwatch.tf        # Logs and alarms
│
├── docker-compose.prod.yml  # Production compose (deployed via SSM)
│
├── environments/
│   └── prod.tfvars.example  # Production config template
│
└── README.md
```

## Deployment Flow

```
Push to main
  → CI tests (pytest, vitest)
  → Build images + push to ECR
  → SSM send-command to EC2:
      - Write docker-compose.prod.yml
      - ECR login
      - docker compose pull && up -d
      - Health check
```

No deploy.sh, no S3. Compose file is written directly via SSM.

## Troubleshooting

### ACM Certificate Not Validating

1. Check CNAME is correctly added: `dig _xxx.hub.vizzuality.com CNAME`
2. Ensure no typos in record name/value
3. Wait up to 30 minutes for propagation

### Deploy Failed

Check SSM command output in GitHub Actions logs, or:

```bash
# SSH into EC2
docker compose -f /opt/hub/docker-compose.prod.yml logs backend
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
docker compose -f /opt/hub/docker-compose.prod.yml ps
docker compose -f /opt/hub/docker-compose.prod.yml logs backend
docker compose -f /opt/hub/docker-compose.prod.yml logs frontend
```

## Security

- No SSH access (port 22 closed) - use SSM Session Manager
- RDS not publicly accessible - only reachable from EC2
- All secrets in AWS Secrets Manager
- HTTPS via ALB with ACM certificate (auto-renewal)
- EC2 only accepts traffic from ALB (no public ports)
- IMDSv2 required (no IMDSv1)
- Root volume encrypted

### SonarQube-Compliant Security

**S3 Buckets:**

- HTTPS-only access enforced via bucket policy
- Access logging enabled on state bucket
- Server-side encryption with AES256
- Public access blocked

**SNS Topics:**

- KMS encryption enabled (`alias/aws/sns`)

**EC2 Instance:**

- No public ingress (ALB only)
- Non-root user in containers
- Read-only file permissions

**Docker Images:**

- Multi-stage builds
- Non-root user (`appuser`)
- `.dockerignore` excludes sensitive files

**GitHub Actions:**

- Job-level permissions
- SHA-pinned action versions
- OIDC authentication (no long-lived credentials)

## Costs

**Default (Free Tier Eligible - first 12 months):**

| Resource          | Monthly Cost |
| ----------------- | ------------ |
| EC2 t3.micro      | $0 (free)    |
| RDS db.t3.micro   | $0 (free)    |
| ALB               | ~$16         |
| Secrets Manager   | ~$2          |
| **Total**         | **~$18**     |

**After Free Tier (or with larger instances):**

| Resource          | t3.micro/db.t3.micro | t3.medium/db.t4g.small |
| ----------------- | -------------------- | ---------------------- |
| EC2               | ~$8                  | ~$30                   |
| RDS               | ~$13                 | ~$25                   |
| ALB               | ~$16                 | ~$16                   |
| Secrets Manager   | ~$2                  | ~$2                    |
| **Total**         | **~$39**             | **~$73**               |

Note: ALB (~$16/month) is not free tier eligible but eliminates SSL management complexity.
