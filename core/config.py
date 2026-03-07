from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict as ConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cable Service Management"
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days
    GOOGLE_API_KEY: Optional[str] = None

    # SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_EMAIL: str = ""
    SMTP_PASSWORD: str = ""
    ADMIN_EMAIL: str = ""

    # Keep-Alive Settings
    RENDER_EXTERNAL_URL: Optional[str] = None
    KEEP_ALIVE_INTERVAL_MINUTES: int = 5

    model_config = ConfigDict(env_file=".env")

settings = Settings()
