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

# Variables for API tokens
variable "raindrop_api_token_rss_to_raindrop_llm" {
  description = "Raindrop API token"
  type        = string
  sensitive   = true
}

variable "openai_api_token_rss_to_raindrop_llm" {
  description = "OpenAI API token"
  type        = string
  sensitive   = true
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

# Secrets Manager - Raindrop API Key
resource "aws_secretsmanager_secret" "raindrop_api_token_rss_to_raindrop_llm" {
  name_prefix = "rss-to-raindrop-llm/raindrop-api-token-"
  
  force_overwrite_replica_secret = true
}

resource "aws_secretsmanager_secret_version" "raindrop_api_token_rss_to_raindrop_llm" {
  secret_id     = aws_secretsmanager_secret.raindrop_api_token_rss_to_raindrop_llm.id
  secret_string = var.raindrop_api_token_rss_to_raindrop_llm
}

# Secrets Manager - OpenAI API Key
resource "aws_secretsmanager_secret" "openai_api_token_rss_to_raindrop_llm" {
  name_prefix = "rss-to-raindrop-llm/openai-api-token-"
  
  force_overwrite_replica_secret = true
}

resource "aws_secretsmanager_secret_version" "openai_api_token_rss_to_raindrop_llm" {
  secret_id     = aws_secretsmanager_secret.openai_api_token_rss_to_raindrop_llm.id
  secret_string = var.openai_api_token_rss_to_raindrop_llm
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
          aws_secretsmanager_secret.raindrop_api_token_rss_to_raindrop_llm.arn,
          aws_secretsmanager_secret.openai_api_token_rss_to_raindrop_llm.arn
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

# Create an AWS KMS key that we control explicitly
resource "aws_kms_key" "lambda_env_vars" {
  description             = "KMS key for Lambda environment variables encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        },
        Action   = "kms:*",
        Resource = "*"
      },
      {
        Effect = "Allow",
        Principal = {
          AWS = aws_iam_role.lambda_role.arn
        },
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ],
        Resource = "*"
      }
    ]
  })
}

# Create a friendly alias for the key
resource "aws_kms_alias" "lambda_env_vars" {
  name          = "alias/rss-to-raindrop-lambda-env-vars"
  target_key_id = aws_kms_key.lambda_env_vars.key_id
}

# Get current account ID
data "aws_caller_identity" "current" {}

# IAM policy for Lambda to access KMS
resource "aws_iam_role_policy" "kms_access" {
  name = "kms_access"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = [
          # The KMS key we're creating specifically for this Lambda
          aws_kms_key.lambda_env_vars.arn,
          # Also include the problematic key from the error message
          "arn:aws:kms:us-east-1:490004617599:key/509ca696-d54f-4b56-99e8-f11688b96ac7",
          # And any default AWS Lambda keys in the region
          "arn:aws:kms:${var.aws_region}:${data.aws_caller_identity.current.account_id}:key/*"
        ]
      }
    ]
  })
}

# DynamoDB table for feed state
resource "aws_dynamodb_table" "feed_state" {
  name           = "rss-to-raindrop-feed-state"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "feed_url"
  range_key      = "entry_id"

  attribute {
    name = "feed_url"
    type = "S"
  }

  attribute {
    name = "entry_id"
    type = "S"
  }

  tags = {
    Name = "RSS to Raindrop Feed State"
  }
}

# IAM policy for Lambda to access DynamoDB
resource "aws_iam_role_policy" "dynamodb_access" {
  name = "dynamodb_access"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.feed_state.arn,
          "${aws_dynamodb_table.feed_state.arn}/index/*"
        ]
      }
    ]
  })
}

# Lambda function
resource "aws_lambda_function" "rss_to_raindrop" {
  filename         = "${path.module}/lambda_function.zip"
  function_name    = "rss-to-raindrop"
  role            = aws_iam_role.lambda_role.arn
  handler         = "rss_bouncer.lambda_handler"
  source_code_hash = filebase64sha256("${path.module}/lambda_function.zip")
  runtime         = "python3.11"
  timeout         = 300
  memory_size     = 256
  
  environment {
    variables = {
      CONFIG_PATH           = "/tmp/config.yaml"
      RAINDROP_SECRET_ARN  = aws_secretsmanager_secret.raindrop_api_token_rss_to_raindrop_llm.arn
      OPENAI_SECRET_ARN    = aws_secretsmanager_secret.openai_api_token_rss_to_raindrop_llm.arn
    }
  }
  
  # Explicitly use our own KMS key that we have proper permissions for
  kms_key_arn = aws_kms_key.lambda_env_vars.arn
}

# CloudWatch Event Rule to trigger Lambda every hour
resource "aws_cloudwatch_event_rule" "hourly" {
  name                = "trigger-rss-to-raindrop-hourly"
  description         = "Trigger RSS to Raindrop Lambda function every hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.hourly.name
  target_id = "RSSToRaindropLambda"
  arn       = aws_lambda_function.rss_to_raindrop.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rss_to_raindrop.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.hourly.arn
}
