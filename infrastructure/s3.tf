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

# Public read access for playbook images and static export
resource "aws_s3_bucket_policy" "assets_public_read" {
  bucket = aws_s3_bucket.assets.id

  depends_on = [aws_s3_bucket_public_access_block.assets]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadPlaybookAssets"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource = [
          "${aws_s3_bucket.assets.arn}/playbook/images/*",
          "${aws_s3_bucket.assets.arn}/playbook/public/*",
        ]
      }
    ]
  })
}
