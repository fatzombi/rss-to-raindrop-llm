# Terraform State Bootstrap

This directory contains the Terraform configuration for creating the S3 bucket that will store the Terraform state for our main infrastructure.

## Prerequisites

- AWS CLI configured with admin credentials
- Terraform installed locally

## Usage

This configuration should be run **once** by an admin user to set up the S3 bucket for Terraform state. The GitHub Actions workflow will then use this bucket to store state for the main infrastructure.

```bash
# Initialize Terraform
terraform init

# Plan the changes
terraform plan

# Apply the changes
terraform apply
```

## Resources Created

- S3 bucket (`rss-to-raindrop-tfstate`) with:
  - Versioning enabled
  - Server-side encryption (AES-256)
  - Public access blocked
  - Protection against accidental deletion

## Important Notes

1. This configuration uses local state since it creates the remote state bucket itself.
2. The S3 bucket has `prevent_destroy = true` to protect against accidental deletion.
3. After creating these resources, the GitHub Actions workflow can manage the main infrastructure using the OIDC role.
