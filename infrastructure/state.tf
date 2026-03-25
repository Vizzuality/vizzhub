# Terraform State Infrastructure
#
# These resources store OpenTofu state in S3 with DynamoDB locking.
# They were previously in bootstrap/ but are now managed alongside main infrastructure.
#
# IMPORTANT: After initial creation, uncomment the backend block in main.tf
# and run `tofu init -migrate-state` to migrate local state to S3.

# S3 bucket for access logs
resource "aws_s3_bucket" "state_logs" {
  bucket = "hub-vizzuality-tfstate-logs"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name      = "hub-tfstate-logs"
    Purpose   = "Access logs for state bucket"
    ManagedBy = "opentofu"
  }
}

resource "aws_s3_bucket_public_access_block" "state_logs" {
  bucket = aws_s3_bucket.state_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state_logs" {
  bucket = aws_s3_bucket.state_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state_logs" {
  bucket = aws_s3_bucket.state_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_policy" "state_logs_https_only" {
  bucket = aws_s3_bucket.state_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.state_logs.arn,
          "${aws_s3_bucket.state_logs.arn}/*"
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
        Resource = "${aws_s3_bucket.state_logs.arn}/*"
        Condition = {
          ArnLike = {
            "aws:SourceArn" = aws_s3_bucket.state.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.state_logs]
}

# S3 bucket for state storage
resource "aws_s3_bucket" "state" {
  bucket = "hub-vizzuality-tfstate"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name      = "hub-tfstate"
    Purpose   = "OpenTofu state storage"
    ManagedBy = "opentofu"
  }
}

resource "aws_s3_bucket_logging" "state" {
  bucket = aws_s3_bucket.state.id

  target_bucket = aws_s3_bucket.state_logs.id
  target_prefix = "state-access-logs/"
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "state_https_only" {
  bucket = aws_s3_bucket.state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.state.arn,
          "${aws_s3_bucket.state.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.state]
}

# DynamoDB table for state locking
resource "aws_dynamodb_table" "state_lock" {
  name         = "hub-vizzuality-tflock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name      = "hub-tflock"
    Purpose   = "OpenTofu state locking"
    ManagedBy = "opentofu"
  }
}
