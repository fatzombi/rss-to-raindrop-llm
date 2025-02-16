terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.2.0"
}

provider "aws" {
  region = var.aws_region
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "rss_to_raindrop_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

# Secrets Manager - Raindrop Token
resource "aws_secretsmanager_secret" "raindrop_token" {
  name = "rss-to-raindrop/raindrop-token"
}

# Secrets Manager - OpenAI API Key
resource "aws_secretsmanager_secret" "openai_api_key" {
  name = "rss-to-raindrop/openai-api-key"
}

# IAM policy for Lambda to access secrets
resource "aws_iam_policy" "secrets_access" {
  name = "rss_to_raindrop_secrets_access"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.raindrop_token.arn,
          aws_secretsmanager_secret.openai_api_key.arn
        ]
      }
    ]
  })
}

# Attach secrets policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_secrets" {
  policy_arn = aws_iam_policy.secrets_access.arn
  role       = aws_iam_role.lambda_role.name
}

# Archive the Python code
#data "archive_file" "lambda_zip" {
#  type        = "zip"
#  source_dir  = "${path.module}/.."
#  output_path = "${path.module}/lambda_function.zip"
#  excludes    = [
#    "infrastructure",
#    ".git",
#    ".venv",
#    "*.yaml",
#    "state.json",
#    ".DS_Store",
#    ".gitignore"
#  ]
#}

# Lambda function
#resource "aws_lambda_function" "rss_to_raindrop" {
#  filename         = data.archive_file.lambda_zip.output_path
#  function_name    = "rss-to-raindrop"
#  role            = aws_iam_role.lambda_role.arn
#  handler         = "rss_bouncer.lambda_handler"
#  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
#  runtime         = "python3.11"
#  timeout         = 300
#  memory_size     = 256

#  environment {
#    variables = {
#      CONFIG_PATH           = "/tmp/config.yaml"
#      RAINDROP_SECRET_ARN  = aws_secretsmanager_secret.raindrop_token.arn
#      OPENAI_SECRET_ARN    = aws_secretsmanager_secret.openai_api_key.arn
#    }
#  }
#}
