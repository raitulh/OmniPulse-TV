variable "aws_region" {
  description = "The AWS region where resources will be deployed"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (production, staging)"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name prefix used for resource naming"
  type        = string
  default     = "omnipulse-tv"
}

variable "domain_name" {
  description = "Optional custom root domain for OmniPulse TV (e.g. omnipulse.tv)"
  type        = string
  default     = ""
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "omnipulse"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "omnipulse_admin"
}

variable "backend_image" {
  description = "ECR image URI for the FastAPI backend container"
  type        = string
  default     = "public.ecr.aws/dummy/omnipulse-backend:latest"
}

variable "backend_cpu" {
  description = "Fargate CPU units (256, 512, 1024, 2048)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Fargate Memory in MB (512, 1024, 2048, 4096)"
  type        = number
  default     = 1024
}

variable "backend_replica_count" {
  description = "Desired number of ECS task replicas"
  type        = number
  default     = 2
}

variable "bedrock_model_id" {
  description = "Bedrock foundation model identifier"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}
