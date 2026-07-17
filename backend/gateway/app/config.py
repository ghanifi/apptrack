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
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_ENTERPRISE: str = ""

    EAS_WEBHOOK_SECRET: str = ""
    CODEMAGIC_WEBHOOK_SECRET: str = ""
    ASC_WEBHOOK_SECRET: str = ""  # App Store Connect Webhooks API (WWDC25) imza anahtarı

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""

    SENTRY_AUTH_TOKEN: str = ""

    ENVIRONMENT: str = "development"

    # Bilinen zayıf/varsayılan sır işaretleri (docker-compose default 'dev-secret-key' dahil).
    _WEAK_SECRET_MARKERS = (
        "change-me", "changeme", "dev-secret", "secret-key", "your-", "placeholder",
        "example", "default", "apptrack-fernet", "test-secret", "insecure",
    )

    @model_validator(mode='after')
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            # SECRET_KEY: >=32 karakter ve tahmin edilemez. Aksi halde bilinen bir
            # secret ile HS256 imzalanır → sahte is_admin:true token forge edilebilir.
            for name, val, min_len in (("SECRET_KEY", self.SECRET_KEY, 32),
                                       ("FERNET_SALT", self.FERNET_SALT, 16)):
                low = (val or "").lower()
                if len(val or "") < min_len or any(m in low for m in self._WEAK_SECRET_MARKERS):
                    raise ValueError(
                        f"Production ortamında {name} en az {min_len} karakter ve tahmin "
                        "edilemez olmalıdır; varsayılan/zayıf değerler (dev-secret-key, "
                        "change-me vb.) kabul edilmez."
                    )
        return self

    class Config:
        env_file = ".env"


settings = Settings()
