terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.100.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region  = "us-west-2"
  profile = "crop-classification"

  default_tags {
    tags = {
      Project     = "crop-classification"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}