# =============================================================================
# CloudFront — Static assets (playbook.vizzuality.com)
#   Serves playbook pages/images and ISO docs images from S3 via OAC.
# =============================================================================

# CloudFront requires ACM certificates in us-east-1
provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "opentofu"
    }
  }
}

# ACM certificate for playbook.vizzuality.com (must be in us-east-1)
resource "aws_acm_certificate" "playbook" {
  provider          = aws.us_east_1
  domain_name       = var.playbook_domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.project_name}-playbook-cert"
  }
}

# Origin Access Control — CloudFront identity for S3 access
resource "aws_cloudfront_origin_access_control" "playbook" {
  name                              = "${var.project_name}-playbook-oac"
  description                       = "OAC for playbook static site S3 origin"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront distribution
#
# Two origins from the same S3 bucket:
#   - "s3-playbook-pages" (origin_path=/playbook/public) → default behavior
#     Maps playbook.vizzuality.com/* to s3://bucket/playbook/public/*
#   - "s3-playbook-images" (origin_path=/playbook) → /images/* path pattern
#     Maps playbook.vizzuality.com/images/* to s3://bucket/playbook/images/*
resource "aws_cloudfront_distribution" "playbook" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Static assets — ${var.playbook_domain_name}"
  default_root_object = "index.html"
  aliases             = [var.playbook_domain_name]
  price_class         = "PriceClass_100" # US + Europe (cheapest)

  # Pages origin: s3://bucket/playbook/public/
  origin {
    domain_name              = aws_s3_bucket.assets.bucket_regional_domain_name
    origin_id                = "s3-playbook-pages"
    origin_access_control_id = aws_cloudfront_origin_access_control.playbook.id
    origin_path              = "/playbook/public"
  }

  # Images origin: s3://bucket/playbook/
  origin {
    domain_name              = aws_s3_bucket.assets.bucket_regional_domain_name
    origin_id                = "s3-playbook-images"
    origin_access_control_id = aws_cloudfront_origin_access_control.playbook.id
    origin_path              = "/playbook"
  }

  # ISO docs images origin: s3://bucket/ (no origin path — key includes iso-docs/)
  origin {
    domain_name              = aws_s3_bucket.assets.bucket_regional_domain_name
    origin_id                = "s3-iso-docs-images"
    origin_access_control_id = aws_cloudfront_origin_access_control.playbook.id
    origin_path              = ""
  }

  # Default: serve pages from /playbook/public/
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-playbook-pages"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600     # 1 hour
    max_ttl     = 86400    # 24 hours
  }

  # /images/* → serve from /playbook/images/
  ordered_cache_behavior {
    path_pattern           = "/images/*"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-playbook-images"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400    # 24 hours (images change rarely)
    max_ttl     = 604800   # 7 days
  }

  # /iso-docs/images/* → serve from s3://bucket/iso-docs/images/
  ordered_cache_behavior {
    path_pattern           = "/iso-docs/images/*"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-iso-docs-images"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 604800
  }

  # S3 returns 403 for missing keys with OAC
  custom_error_response {
    error_code            = 403
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 60
  }

  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 60
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.playbook.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "${var.project_name}-playbook-cdn"
  }

  depends_on = [aws_acm_certificate.playbook]
}
