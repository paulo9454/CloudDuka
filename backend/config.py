import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv('APP_NAME', 'CloudDuka POS API')
    app_env: str = os.getenv('APP_ENV', 'development')
    mongo_url: str = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    db_name: str = os.getenv('DB_NAME', 'cloudduka')
    jwt_secret: str = os.getenv('JWT_SECRET', 'cloudduka-secret-key-2024')
    jwt_algorithm: str = os.getenv('JWT_ALGORITHM', 'HS256')
    jwt_expiration_hours: int = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))
    refresh_token_expiration_days: int = int(os.getenv('REFRESH_TOKEN_EXPIRATION_DAYS', '30'))
    email_verification_expiration_hours: int = int(os.getenv('EMAIL_VERIFICATION_EXPIRATION_HOURS', '48'))
    cors_origins_raw: str = os.getenv('CORS_ORIGINS', '*')
    public_base_url: str = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
    media_dir: str = os.getenv('MEDIA_DIR', 'backend/media')
    media_base_url: str = os.getenv('MEDIA_BASE_URL', '').rstrip('/')
    mpesa_shortcode: str = os.getenv('MPESA_SHORTCODE', '174379')
    mpesa_passkey: str = os.getenv('MPESA_PASSKEY', 'sandbox-passkey')
    mpesa_callback_url: str = os.getenv('MPESA_CALLBACK_URL', '').rstrip('/')
    mpesa_webhook_secret: str = os.getenv('MPESA_WEBHOOK_SECRET', 'cloudduka-mpesa-secret')
    smtp_from_email: str = os.getenv('SMTP_FROM_EMAIL', 'no-reply@cloudduka.local')
    smtp_host: str = os.getenv('SMTP_HOST', '')
    smtp_port: int = int(os.getenv('SMTP_PORT', '587'))
    smtp_username: str = os.getenv('SMTP_USERNAME', '')
    smtp_password: str = os.getenv('SMTP_PASSWORD', '')
    smtp_use_tls: bool = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
    smtp_use_ssl: bool = os.getenv('SMTP_USE_SSL', 'false').lower() == 'true'
    smtp_enabled: bool = os.getenv('SMTP_ENABLED', 'false').lower() == 'true'
    require_secure_cookies: bool = os.getenv('REQUIRE_SECURE_COOKIES', 'false').lower() == 'true'

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(',') if origin.strip()]

    @property
    def media_path(self) -> Path:
        return Path(self.media_dir)


settings = Settings()
