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
    resend_from_email: str = "Raina <onboarding@raina-pilot.com>"

    # App base URL (used for magic links — no trailing slash)
    app_base_url: str = "http://localhost:5173"

    # AWS S3 (photo storage)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = ""
    aws_s3_region: str = "us-east-1"

    # Sentry (empty DSN → SDK init is a no-op)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0

    # Auth token signing secret. Used to sign every bearer token (parent,
    # teacher, director). Generate with:
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Empty in dev/test → token issuance refuses, verification returns None.
    auth_token_secret: str = ""

    # Pilot kill switch — when True, voice memos skip transcription + GPT-4o
    # extraction. Audio is still deleted from Twilio (zero-retention). Teacher
    # gets a "pending review" reply. Flip via Railway env when something is
    # noticeably wrong with the AI pipeline.
    extraction_disabled: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        # Ignore unknown env vars (e.g. VITE_* frontend keys that share .env).
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
