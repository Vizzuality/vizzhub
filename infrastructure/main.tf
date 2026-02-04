# Hub Infrastructure - Main Configuration
#
# Prerequisites:
#   1. Run bootstrap/ first to create state bucket
#   2. Configure backend below with bootstrap outputs
#   3. Create prod.tfvars with your values
#
# Usage:
#   tofu init
#   tofu plan -var-file=environments/prod.tfvars
#   tofu apply -var-file=environments/prod.tfvars

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Uncomment after running bootstrap/
  # backend "s3" {
  #   bucket         = "hub-vizzuality-tfstate"
  #   key            = "hub/prod/terraform.tfstate"
  #   region         = "eu-west-1"
  #   dynamodb_table = "hub-vizzuality-tflock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "opentofu"
    }
  }
}

# Current AWS account and region data
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
