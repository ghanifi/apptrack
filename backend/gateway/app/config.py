from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    DATABASE_URL: str = "postgresql+asyncpg://apptrack:apptrack@postgres:5432/apptrack"

    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    AUTH_SERVICE_URL: str = "http://auth-service:8001"
    PROJECT_SERVICE_URL: str = "http://project-service:8002"
    REPO_SYNC_SERVICE_URL: str = "http://repo-sync-service:8003"
    FRAMEWORK_DETECTION_SERVICE_URL: str = "http://framework-detection-service:8004"
    PREVIEW_SERVICE_URL: str = "http://preview-service:8005"
    BUILD_SERVICE_URL: str = "http://build-service:8006"
    ARTIFACT_SERVICE_URL: str = "http://artifact-service:8007"
    STORE_DEPLOY_SERVICE_URL: str = "http://store-deploy-service:8008"

    REDIS_URL: str = "redis://redis:6379/0"

    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:3000"

    GITHUB_WEBHOOK_SECRET: str = ""
    GATEWAY_URL: str = "http://localhost:8000"

    FERNET_SALT: str
    SECRET_KEY_OLD: str = ""

    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AUTH: str = "5/minute"

    SERVICE_TOKEN_SECRET: str = ""
    MAX_REQUEST_SIZE_MB: int = 10
    DEVICE_FINGERPRINT_ENABLED: bool = True

    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_API_KEY: str = ""

    EAS_WEBHOOK_SECRET: str = ""
    CODEMAGIC_WEBHOOK_SECRET: str = ""

    ENVIRONMENT: str = "development"

    @model_validator(mode='after')
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if "change-me" in self.SECRET_KEY or "apptrack-fernet" in self.FERNET_SALT:
                raise ValueError(
                    "Production ortamında SECRET_KEY ve FERNET_SALT için "
                    "güvenli değerler kullanılmalıdır. "
                    "Varsayılan veya geçici değerler kabul edilmez."
                )
        return self

    class Config:
        env_file = ".env"


settings = Settings()
