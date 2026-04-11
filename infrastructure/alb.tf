# Application Load Balancer with ACM Certificate
#
# Architecture:
#   Internet → ALB (HTTPS/ACM) → EC2 (Docker)
#                ↓ path routing       ├── /api/* → backend:8000
#                └── /* → frontend:5173
#
# DNS Workflow:
#   1. Run tofu apply → creates ACM cert in pending validation
#   2. Get CNAME from output: tofu output acm_validation_record
#   3. Add CNAME to DNS (external AWS account)
#   4. Wait ~5 min for validation
#   5. Run tofu apply again → ALB uses validated cert
#   6. Add final CNAME: hub.vizzuality.com → ALB DNS name

# ACM Certificate
resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.project_name}-cert"
  }
}

# ACM Certificate Validation (waits for DNS validation to complete)
resource "aws_acm_certificate_validation" "main" {
  certificate_arn = aws_acm_certificate.main.arn

  # Note: This will wait for DNS validation. If DNS is not configured,
  # this will timeout after ~45 minutes. You can run tofu apply without
  # this resource first, add DNS, then add this resource back.
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = true

  tags = {
    Name = "${var.project_name}-alb"
  }
}

# Target Group - Backend (API)
resource "aws_lb_target_group" "backend" {
  name     = "${var.project_name}-backend-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
  }

  tags = {
    Name = "${var.project_name}-backend-tg"
  }
}

# Target Group - Frontend
resource "aws_lb_target_group" "frontend" {
  name     = "${var.project_name}-frontend-tg"
  port     = 5173
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    matcher             = "200"
  }

  tags = {
    Name = "${var.project_name}-frontend-tg"
  }
}

# Target Group Attachments
resource "aws_lb_target_group_attachment" "backend" {
  target_group_arn = aws_lb_target_group.backend.arn
  target_id        = aws_instance.main.id
  port             = 8000
}

resource "aws_lb_target_group_attachment" "frontend" {
  target_group_arn = aws_lb_target_group.frontend.arn
  target_id        = aws_instance.main.id
  port             = 5173
}

# Listener - HTTP (redirect to HTTPS)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# Listener - HTTPS
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn

  # Default action: forward to frontend
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

# Listener Rule - /api/* → backend
resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

# Block common vulnerability scanner paths
resource "aws_lb_listener_rule" "block_scanners" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 1

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = ""
      status_code  = "403"
    }
  }

  condition {
    path_pattern {
      values = ["/phpmyadmin*", "/pma*", "/mysql*", "/db*", "/adminer*"]
    }
  }
}

resource "aws_lb_listener_rule" "block_scanners_wp" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 2

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = ""
      status_code  = "403"
    }
  }

  condition {
    path_pattern {
      values = ["/wp-admin*", "/wp-login*", "/wp-includes*", "/wp-content*", "/wordpress*"]
    }
  }
}

resource "aws_lb_listener_rule" "block_scanners_dotfiles" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 3

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = ""
      status_code  = "403"
    }
  }

  condition {
    path_pattern {
      values = ["/.env*", "/.git*", "/.aws*", "/.ssh*", "/.htaccess*"]
    }
  }
}

resource "aws_lb_listener_rule" "block_scanners_misc" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 4

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = ""
      status_code  = "403"
    }
  }

  condition {
    path_pattern {
      values = ["/cgi-bin*", "/vendor*", "/xmlrpc*", "/config.php*", "/admin/config*"]
    }
  }
}

# Listener Rule - /mcp* and OAuth discovery paths → backend
resource "aws_lb_listener_rule" "mcp" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 50

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/mcp*", "/.well-known/oauth-protected-resource*", "/.well-known/oauth-authorization-server*"]
    }
  }
}

# Listener Rule - /health → backend
resource "aws_lb_listener_rule" "health" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 99

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/health"]
    }
  }
}
