output "cloudfront_distribution_domain" {
  description = "The HTTPS CloudFront domain hosting the TV frontend web application"
  value       = aws_cloudfront_distribution.spa.domain_name
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS name for the FastAPI backend"
  value       = aws_lb.api.dns_name
}

output "cognito_user_pool_id" {
  description = "Amazon Cognito User Pool ID"
  value       = aws_cognito_user_pool.pool.id
}

output "cognito_app_client_id" {
  description = "Amazon Cognito Public App Client ID for TV OAuth / PKCE"
  value       = aws_cognito_user_pool_client.client.id
}

output "rds_endpoint" {
  description = "PostgreSQL RDS connection endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "s3_frontend_bucket" {
  description = "S3 bucket for frontend asset deployment"
  value       = aws_s3_bucket.frontend.bucket
}

output "secrets_manager_arn" {
  description = "AWS Secrets Manager ARN storing database URL and JWT signing key"
  value       = aws_secretsmanager_secret.app_secrets.arn
}
