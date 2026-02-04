output "state_bucket_name" {
  description = "S3 bucket name for OpenTofu state"
  value       = aws_s3_bucket.state.id
}

output "state_bucket_arn" {
  description = "S3 bucket ARN for OpenTofu state"
  value       = aws_s3_bucket.state.arn
}

output "lock_table_name" {
  description = "DynamoDB table name for state locking"
  value       = aws_dynamodb_table.lock.name
}

output "lock_table_arn" {
  description = "DynamoDB table ARN for state locking"
  value       = aws_dynamodb_table.lock.arn
}

output "backend_config" {
  description = "Backend configuration to use in main infrastructure"
  value       = <<-EOT
    # Add this to infrastructure/main.tf after bootstrap:
    backend "s3" {
      bucket         = "${aws_s3_bucket.state.id}"
      key            = "hub/prod/terraform.tfstate"
      region         = "${var.aws_region}"
      dynamodb_table = "${aws_dynamodb_table.lock.name}"
      encrypt        = true
    }
  EOT
}
