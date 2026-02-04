variable "aws_region" {
  description = "AWS region for state storage"
  type        = string
  default     = "eu-west-1"
}

variable "state_bucket_name" {
  description = "Name of S3 bucket for OpenTofu state"
  type        = string
  default     = "hub-vizzuality-tfstate"
}

variable "lock_table_name" {
  description = "Name of DynamoDB table for state locking"
  type        = string
  default     = "hub-vizzuality-tflock"
}
