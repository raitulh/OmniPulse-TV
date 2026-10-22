from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OmniPulse TV API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = "sqlite:///./data/omnipulse.db"
    jwt_secret: str = "local-only-change-me-before-deployment"
    jwt_issuer: str = "omnipulse-tv"
    jwt_ttl_minutes: int = 720
    demo_mode: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"
    aws_region: str = "us-east-1"
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    ai_provider: str = "rules"
    bedrock_model_id: str = ""
    sports_provider: str = "sample"
    sports_provider_api_key: str = ""
    log_level: str = "INFO"
    max_request_bytes: int = 128_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    def validate_for_startup(self) -> None:
        if self.environment.lower() == "production":
            if self.demo_mode:
                raise RuntimeError("DEMO_MODE must be false in production")
            if not self.cognito_user_pool_id or not self.cognito_app_client_id:
                raise RuntimeError("Configure COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID before production startup")
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise RuntimeError("Production DATABASE_URL must use PostgreSQL")
            if not self.allowed_origins or "*" in self.allowed_origins:
                raise RuntimeError("Production CORS_ORIGINS must contain exact origins; wildcard or empty is forbidden")
            if len(self.jwt_secret) < 32 or self.jwt_secret == "local-only-change-me-before-deployment":
                raise RuntimeError("Set a non-default JWT_SECRET of at least 32 characters before production startup")
            if self.ai_provider.lower() not in {"rules", "bedrock"}:
                raise RuntimeError("AI_PROVIDER must be 'rules' or 'bedrock'")
            if self.ai_provider.lower() == "bedrock" and not self.bedrock_model_id:
                raise RuntimeError("Configure BEDROCK_MODEL_ID when AI_PROVIDER=bedrock")


@lru_cache
def get_settings() -> Settings:
    return Settings()
