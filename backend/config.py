from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Database
    database_url: str = "postgresql://localhost/daycare_dev"

    # Environment
    environment: str = "development"

    # WhatsApp mode: "sandbox" for Twilio Sandbox (pilot), "production" for live number.
    whatsapp_mode: str = "sandbox"

    # Resend (transactional email)
    resend_api_key: str = ""
    resend_from_email: str = "Raina <onboarding@raina.com>"

    # App base URL (used for magic links — no trailing slash)
    app_base_url: str = "http://localhost:5173"

    # AWS S3 (photo storage)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = ""
    aws_s3_region: str = "us-east-1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
