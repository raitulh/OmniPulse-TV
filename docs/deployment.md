# Deployment Guide

## Local / hackathon

Use `docker compose up --build`. This enables local demo auth and a SQLite volume. Do not expose this compose configuration to the public internet.

## Production reference

1. Create a Cognito user pool and public app client for Authorization Code + PKCE. Configure exact redirect/logout URLs and HTTPS.
2. Create managed PostgreSQL (for example, Amazon RDS) with TLS, private networking, least-privilege DB credentials and backups.
3. Build and deploy `backend/Dockerfile` to a managed container runtime (for example, AWS App Runner or ECS/Fargate). Configure environment variables using Secrets Manager; use `ENVIRONMENT=production`, `DEMO_MODE=false`, Cognito settings, `DATABASE_URL`, `CORS_ORIGINS` and provider settings.
4. Run `alembic upgrade head` as a release migration job before switching traffic. Production app startup intentionally does not call `create_all` or seed sample data.
5. Add an approved sports data provider and populate verified events through a controlled ingestion process. The current fixture is not imported in production.
6. Configure `AI_PROVIDER=bedrock` and `BEDROCK_MODEL_ID` only if the selected model is enabled in the target AWS account and the runtime role can invoke it. Rules-based responses remain the fallback.
7. Build `frontend/` with production `VITE_API_BASE_URL`, `VITE_AUTH_MODE=cognito`, `VITE_COGNITO_DOMAIN`, `VITE_COGNITO_CLIENT_ID`, and callback/logout URLs. These values are public configuration, not secrets.
8. Host the static frontend over HTTPS (for example, an S3 + CloudFront origin or another static host) and update API CORS and Cognito callbacks.
9. Confirm CloudWatch log retention/alarms, DB backup and restore, throttling, vulnerability scanning, error budgets and a rollback path.
10. Run target-device tests and a full journey rehearsal before public submission/release.
