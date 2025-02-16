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

# Secrets Manager - Raindrop API Key
resource "aws_secretsmanager_secret" "raindrop_api_token" {
  name = "rss-to-raindrop/raindrop-api-token"
}

# Secrets Manager - OpenAI API Key
resource "aws_secretsmanager_secret" "openai_api_token" {
  name = "rss-to-raindrop/openai-api-token"
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
          aws_secretsmanager_secret.raindrop_api_token.arn,
          aws_secretsmanager_secret.openai_api_token.arn
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
      RAINDROP_SECRET_ARN  = aws_secretsmanager_secret.raindrop_api_token.arn
      OPENAI_SECRET_ARN    = aws_secretsmanager_secret.openai_api_token.arn
    }
  }
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
