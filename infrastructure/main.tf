# Hub Infrastructure - Main Configuration
#
# Usage:
#   1. First run with backend commented out: tofu init && tofu apply
#   2. Uncomment backend block below
#   3. Run: tofu init -migrate-state
#
# Commands:
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
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }

  # Uncomment after state resources are created (state.tf)
  backend "s3" {
    bucket         = "hub-vizzuality-tfstate"
    key            = "hub/prod/terraform.tfstate"
    region         = "eu-west-3"
    dynamodb_table = "hub-vizzuality-tflock"
    encrypt        = true
    profile = "aws-vizzhub"
  }
}

provider "aws" {
  region = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "opentofu"
    }
  }
}
