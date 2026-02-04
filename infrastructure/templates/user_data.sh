#!/bin/bash
set -euo pipefail

# Logging
exec > >(tee /var/log/user-data.log) 2>&1
echo "=== User data script started at $(date) ==="

# Variables from OpenTofu
AWS_REGION="${aws_region}"
ACCOUNT_ID="${account_id}"
DOMAIN_NAME="${domain_name}"
ADMIN_EMAIL="${admin_email}"
PROJECT_NAME="${project_name}"
RDS_ENDPOINT="${rds_endpoint}"
RDS_DB_NAME="${rds_db_name}"

ECR_URI="$${ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com"
DEPLOY_DIR="/opt/hub"

# Update system
dnf update -y

# Install Docker
dnf install -y docker
systemctl enable docker
systemctl start docker

# Install Docker Compose plugin
DOCKER_CONFIG=/usr/local/lib/docker/cli-plugins
mkdir -p $DOCKER_CONFIG
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o $DOCKER_CONFIG/docker-compose
chmod +x $DOCKER_CONFIG/docker-compose

# Install certbot
dnf install -y certbot

# Install AWS CLI (should be pre-installed on AL2023, but ensure)
dnf install -y aws-cli

# Install jq for JSON parsing
dnf install -y jq

# Create deployment directory
mkdir -p "$${DEPLOY_DIR}/certbot/config"
mkdir -p "$${DEPLOY_DIR}/certbot/work"
mkdir -p "$${DEPLOY_DIR}/certbot/logs"
mkdir -p /var/log/hub

# Create infrastructure environment file
cat > "$${DEPLOY_DIR}/.env.infra" << EOF
AWS_REGION=$${AWS_REGION}
ACCOUNT_ID=$${ACCOUNT_ID}
ECR_URI=$${ECR_URI}
PROJECT_NAME=$${PROJECT_NAME}
RDS_ENDPOINT=$${RDS_ENDPOINT}
RDS_DB_NAME=$${RDS_DB_NAME}
EOF
chmod 600 "$${DEPLOY_DIR}/.env.infra"

# Create script to fetch secrets and generate .env.prod
cat > "$${DEPLOY_DIR}/fetch-secrets.sh" << 'FETCH_SCRIPT'
#!/bin/bash
set -euo pipefail

source /opt/hub/.env.infra

# Fetch secrets from Secrets Manager
DB_SECRET=$(aws secretsmanager get-secret-value --secret-id "/$${PROJECT_NAME}/prod/db-password" --query SecretString --output text --region $${AWS_REGION})
JWT_SECRET=$(aws secretsmanager get-secret-value --secret-id "/$${PROJECT_NAME}/prod/jwt-secrets" --query SecretString --output text --region $${AWS_REGION})
GOOGLE_SECRET=$(aws secretsmanager get-secret-value --secret-id "/$${PROJECT_NAME}/prod/google-oauth" --query SecretString --output text --region $${AWS_REGION})
JIRA_SECRET=$(aws secretsmanager get-secret-value --secret-id "/$${PROJECT_NAME}/prod/jira-oauth" --query SecretString --output text --region $${AWS_REGION})
GITHUB_SECRET=$(aws secretsmanager get-secret-value --secret-id "/$${PROJECT_NAME}/prod/github" --query SecretString --output text --region $${AWS_REGION})
SLACK_SECRET=$(aws secretsmanager get-secret-value --secret-id "/$${PROJECT_NAME}/prod/slack" --query SecretString --output text --region $${AWS_REGION} 2>/dev/null || echo '{"bot_token":""}')

# Parse JSON secrets
DB_PASSWORD=$(echo "$DB_SECRET" | jq -r '.password')
DB_USER=$(echo "$DB_SECRET" | jq -r '.username')
DB_HOST=$(echo "$DB_SECRET" | jq -r '.host')
DB_NAME=$(echo "$DB_SECRET" | jq -r '.dbname')

JWT_SECRET_KEY=$(echo "$JWT_SECRET" | jq -r '.jwt_secret_key')
SESSION_SECRET_KEY=$(echo "$JWT_SECRET" | jq -r '.session_secret_key')

GOOGLE_CLIENT_ID=$(echo "$GOOGLE_SECRET" | jq -r '.client_id')
GOOGLE_CLIENT_SECRET=$(echo "$GOOGLE_SECRET" | jq -r '.client_secret')

JIRA_CLIENT_ID=$(echo "$JIRA_SECRET" | jq -r '.client_id')
JIRA_CLIENT_SECRET=$(echo "$JIRA_SECRET" | jq -r '.client_secret')

GITHUB_TOKEN=$(echo "$GITHUB_SECRET" | jq -r '.token')
GITHUB_ORG=$(echo "$GITHUB_SECRET" | jq -r '.org')

SLACK_BOT_TOKEN=$(echo "$SLACK_SECRET" | jq -r '.bot_token')

# Generate .env.prod
cat > /opt/hub/.env.prod << EOF
# Database
DATABASE_URL=postgresql+asyncpg://$${DB_USER}:$${DB_PASSWORD}@$${DB_HOST}:5432/$${DB_NAME}

# Security
JWT_SECRET_KEY=$${JWT_SECRET_KEY}
SESSION_SECRET_KEY=$${SESSION_SECRET_KEY}
JWT_EXPIRE_HOURS=24

# Google OAuth
GOOGLE_CLIENT_ID=$${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=$${GOOGLE_CLIENT_SECRET}
ALLOWED_GOOGLE_DOMAIN=vizzuality.com

# Jira OAuth
JIRA_OAUTH_CLIENT_ID=$${JIRA_CLIENT_ID}
JIRA_OAUTH_CLIENT_SECRET=$${JIRA_CLIENT_SECRET}
JIRA_OAUTH_REDIRECT_URI=https://${domain_name}/api/oauth/jira/callback
JIRA_OAUTH_SCOPES=read:jira-work read:jira-user read:issue-details:jira read:user:jira read:project:jira read:board-scope:jira-software read:sprint:jira-software offline_access

# GitHub
GITHUB_TOKEN=$${GITHUB_TOKEN}
GITHUB_ORG=$${GITHUB_ORG}

# Slack (optional)
SLACK_BOT_TOKEN=$${SLACK_BOT_TOKEN}

# Application
DEBUG=false
CORS_ORIGINS=["https://${domain_name}"]

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
EOF

chmod 600 /opt/hub/.env.prod
echo "Secrets fetched and .env.prod generated"
FETCH_SCRIPT
chmod +x "$${DEPLOY_DIR}/fetch-secrets.sh"

# Create deploy script
cat > "$${DEPLOY_DIR}/deploy.sh" << 'DEPLOY_SCRIPT'
#!/bin/bash
set -euo pipefail

TAG=$${1:-latest}
DEPLOY_DIR="/opt/hub"
LOG_DIR="/var/log/hub"
TAG_FILE="$${DEPLOY_DIR}/.current-tag"
COMPOSE_FILE="docker-compose.prod.yml"

if [[ ! -f "$${DEPLOY_DIR}/.env.infra" ]]; then
  echo "ERROR: $${DEPLOY_DIR}/.env.infra not found"
  exit 1
fi

source "$${DEPLOY_DIR}/.env.infra"

mkdir -p "$LOG_DIR"
LOG_FILE="$${LOG_DIR}/deploy-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Deploy started: TAG=$TAG ==="

# Fetch latest secrets
"$${DEPLOY_DIR}/fetch-secrets.sh"

PREVIOUS_TAG=""
if [[ -f "$TAG_FILE" ]]; then
  PREVIOUS_TAG=$(cat "$TAG_FILE")
  echo "Previous tag: $PREVIOUS_TAG"
fi

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_URI"

export TAG ECR_URI
cd "$DEPLOY_DIR"

docker compose -f "$COMPOSE_FILE" pull
docker compose -f "$COMPOSE_FILE" up -d

echo "=== Waiting for services (15s) ==="
sleep 15

rollback() {
  if [[ -n "$PREVIOUS_TAG" && "$PREVIOUS_TAG" != "$TAG" ]]; then
    echo "=== ROLLBACK to $PREVIOUS_TAG ==="
    export TAG="$PREVIOUS_TAG"
    docker compose -f "$COMPOSE_FILE" pull
    docker compose -f "$COMPOSE_FILE" up -d
    sleep 10
  fi
  exit 1
}

echo "Checking backend..."
if ! curl -sf http://localhost:8000/health > /dev/null; then
  echo "ERROR: Backend healthcheck failed"
  docker compose -f "$COMPOSE_FILE" logs --tail=50 backend
  rollback
fi

echo "Checking nginx..."
if ! curl -sfk https://localhost/ > /dev/null; then
  echo "ERROR: Nginx healthcheck failed"
  docker compose -f "$COMPOSE_FILE" logs --tail=50 nginx
  rollback
fi

echo "$TAG" > "$TAG_FILE"
echo "=== Deploy successful ==="
docker compose -f "$COMPOSE_FILE" ps

docker image prune -af --filter "until=168h"
DEPLOY_SCRIPT
chmod +x "$${DEPLOY_DIR}/deploy.sh"

# Create nginx configuration
cat > "$${DEPLOY_DIR}/nginx.conf" << 'NGINX_CONF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;

    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 10M;

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name _;

        ssl_certificate /etc/letsencrypt/live/${domain_name}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${domain_name}/privkey.pem;

        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # API routes
        location /api/ {
            proxy_pass http://backend:8000/api/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check
        location /health {
            proxy_pass http://backend:8000/health;
        }

        # Frontend (everything else)
        location / {
            proxy_pass http://frontend:5173/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
NGINX_CONF

# Create docker-compose.prod.yml
cat > "$${DEPLOY_DIR}/docker-compose.prod.yml" << 'COMPOSE'
services:
  nginx:
    image: nginx:alpine
    container_name: hub-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/config:/etc/letsencrypt:ro
    depends_on:
      - backend
      - frontend
    restart: unless-stopped

  frontend:
    image: ${ECR_URI}/frontend:${TAG:-latest}
    container_name: hub-frontend
    expose:
      - "5173"
    environment:
      - VITE_API_URL=https://${domain_name}
    restart: unless-stopped

  backend:
    image: ${ECR_URI}/backend:${TAG:-latest}
    container_name: hub-backend
    expose:
      - "8000"
    env_file:
      - .env.prod
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
    restart: unless-stopped

  worker:
    image: ${ECR_URI}/backend:${TAG:-latest}
    container_name: hub-worker
    command: arq app.worker.settings.WorkerSettings
    env_file:
      - .env.prod
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: hub-redis
    restart: unless-stopped
COMPOSE

# Ensure nothing is listening on port 80 before certbot
systemctl stop nginx 2>/dev/null || true
fuser -k 80/tcp 2>/dev/null || true

# Get SSL certificate
# NOTE: DNS must be pointing to this server's Elastic IP BEFORE this runs
echo "=== Attempting to get SSL certificate ==="
echo "Domain: $${DOMAIN_NAME}"
echo "If this fails, DNS is not yet pointing to this server."

if certbot certonly --standalone \
  -d "$${DOMAIN_NAME}" \
  --non-interactive \
  --agree-tos \
  --email "$${ADMIN_EMAIL}" \
  --config-dir "$${DEPLOY_DIR}/certbot/config" \
  --work-dir "$${DEPLOY_DIR}/certbot/work" \
  --logs-dir "$${DEPLOY_DIR}/certbot/logs"; then
  echo "SSL certificate obtained successfully"
else
  echo "WARNING: SSL certificate not obtained. Run certbot manually after DNS is configured."
fi

# Setup certbot renewal cron
cat > /etc/cron.d/certbot-renew << 'CRON'
0 3 * * * root certbot renew \
  --config-dir /opt/hub/certbot/config \
  --work-dir /opt/hub/certbot/work \
  --logs-dir /opt/hub/certbot/logs \
  --quiet \
  --deploy-hook "docker exec hub-nginx nginx -s reload >> /var/log/hub/certbot-reload.log 2>&1 || true"
CRON
chmod 644 /etc/cron.d/certbot-renew

echo "=== User data script completed at $(date) ==="
echo "Next steps:"
echo "1. Ensure DNS points to this server's Elastic IP"
echo "2. If SSL cert failed, run: /opt/hub/certbot-manual.sh"
echo "3. Fill manual secrets in AWS Secrets Manager"
echo "4. Run first deploy from GitHub Actions"
