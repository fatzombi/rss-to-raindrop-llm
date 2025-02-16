output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.rss_to_raindrop.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.rss_to_raindrop.function_name
}

output "raindrop_secret_arn" {
  description = "ARN of the Raindrop API key"
  value       = aws_secretsmanager_secret.raindrop_api_token_rss_to_raindrop_llm.arn
}

output "openai_secret_arn" {
  description = "ARN of the OpenAI API key"
  value       = aws_secretsmanager_secret.openai_api_token_rss_to_raindrop_llm.arn
}
