output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.rss_to_raindrop.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.rss_to_raindrop.function_name
}

output "raindrop_secret_arn" {
  description = "ARN of the Raindrop token secret"
  value       = aws_secretsmanager_secret.raindrop_token.arn
}

output "openai_secret_arn" {
  description = "ARN of the OpenAI API key secret"
  value       = aws_secretsmanager_secret.openai_api_key.arn
}
