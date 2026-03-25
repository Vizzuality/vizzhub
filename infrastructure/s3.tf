# =============================================================================
# S3 Bucket — Application Assets (playbook images, static exports)
# =============================================================================

resource "aws_s3_bucket" "assets" {
  bucket = "${var.project_name}-vizzuality-assets"

  tags = {
    Name = "${var.project_name}-assets"
  }
}

# Block all public access at the bucket level — we use a bucket policy instead
resource "aws_s3_bucket_public_access_block" "assets" {
  bucket = aws_s3_bucket.assets.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = false # allow bucket policy to grant public read
  restrict_public_buckets = false # allow bucket policy to grant public read
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Access logging
resource "aws_s3_bucket" "assets_logs" {
  bucket = "${var.project_name}-vizzuality-assets-logs"

  tags = {
    Name = "${var.project_name}-assets-logs"
  }
}

resource "aws_s3_bucket_public_access_block" "assets_logs" {
  bucket = aws_s3_bucket.assets_logs.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets_logs" {
  bucket = aws_s3_bucket.assets_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "assets_logs_https_only" {
  bucket = aws_s3_bucket.assets_logs.id

  depends_on = [aws_s3_bucket_public_access_block.assets_logs]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.assets_logs.arn,
          "${aws_s3_bucket.assets_logs.arn}/*",
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid    = "AllowS3LogDelivery"
        Effect = "Allow"
        Principal = {
          Service = "logging.s3.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.assets_logs.arn}/*"
        Condition = {
          ArnLike = {
            "aws:SourceArn" = aws_s3_bucket.assets.arn
          }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_lifecycle_configuration" "assets_logs" {
  bucket = aws_s3_bucket.assets_logs.id

  rule {
    id     = "expire-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_logging" "assets" {
  bucket = aws_s3_bucket.assets.id

  target_bucket = aws_s3_bucket.assets_logs.id
  target_prefix = "access-logs/"
}

# CORS — allow browser requests from hub.vizzuality.com
resource "aws_s3_bucket_cors_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = [
      "https://${var.domain_name}",
      "http://localhost:5173",
    ]
    max_age_seconds = 3600
  }
}

# Bucket policy: HTTPS-only + public read for playbook assets
#
# Public read on playbook/* is intentional — these are wiki images and
# static HTML pages meant to be accessible without authentication.
resource "aws_s3_bucket_policy" "assets_public_read" {
  bucket = aws_s3_bucket.assets.id

  depends_on = [aws_s3_bucket_public_access_block.assets]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.assets.arn,
          "${aws_s3_bucket.assets.arn}/*",
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "PublicReadPlaybookAssets"
        Effect    = "Allow"
        Principal = "*" # intentional: playbook images and static pages are public
        Action    = "s3:GetObject"
        Resource = [
          "${aws_s3_bucket.assets.arn}/playbook/images/*",
          "${aws_s3_bucket.assets.arn}/playbook/public/*",
        ]
      }
    ]
  })
}
