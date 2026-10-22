# OmniPulse TV Production Infrastructure (Terraform)

This directory contains full Infrastructure-as-Code (IaC) definitions using Terraform to deploy OmniPulse TV to AWS in compliance with the **AWS Well-Architected Framework**.

## Architecture Overview

```
                      +------------------------------------+
                      |            Amazon CloudFront        |
                      |        HTTPS CDN + Origin Access    |
                      +-----------------+------------------+
                                        |
                 +----------------------+----------------------+
                 | (Static SPA /assets)                        | (/v1/* & /health/* API)
                 v                                             v
     +-----------------------+                    +---------------------------+
     |       Amazon S3       |                    |  Application Load Balancer |
     | Private SPA Assets    |                    |     AWS WAF Protected     |
     +-----------------------+                    +-------------+-------------+
                                                                |
                                                                v
                                                  +---------------------------+
                                                  |   AWS ECS Fargate Cluster |
                                                  |      FastAPI Backend      |
                                                  +------+--------------+-----+
                                                         |              |
                                  +----------------------+              +----------------------+
                                  v                                                            v
                    +---------------------------+                                +---------------------------+
                    |    Amazon RDS Multi-AZ    |                                |       Amazon Bedrock      |
                    |     PostgreSQL 16 Engine  |                                | Foundation Model Inference|
                    +---------------------------+                                +---------------------------+
```

## Prerequisites
1. **Terraform CLI** `>= 1.5.0`
2. **AWS CLI** configured with appropriate permissions (`aws configure`)
3. Built Docker image pushed to **Amazon ECR**

## Deployment Steps

### 1. Initialize Terraform
```bash
cd infra
terraform init
```

### 2. Plan the deployment
```bash
terraform plan -var="environment=production" -var="backend_image=<your-account-id>.dkr.ecr.us-east-1.amazonaws.com/omnipulse-backend:latest" -out=tfplan
```

### 3. Apply the infrastructure
```bash
terraform apply tfplan
```

### 4. Database Migrations
Before directing user traffic to ECS, run Alembic migrations against the RDS instance:
```bash
cd backend
export DATABASE_URL="postgresql+psycopg://<username>:<password>@<rds-endpoint>/omnipulse"
alembic upgrade head
```

### 5. Frontend Static Asset Deploy
Build and upload the Vite frontend to the created S3 bucket:
```bash
cd frontend
npm ci
npm run build
aws s3 sync dist/ s3://<s3_frontend_bucket_name>/ --delete
aws cloudfront create-invalidation --distribution-id <distribution_id> --paths "/*"
```
