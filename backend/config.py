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

    # ── Legal Compliance (L-5, L-9) ──────────────────────────
    # Set to "confirmed" in production after manually verifying OpenAI DPA is active.
    # See README_LEGAL.md for verification instructions.
    openai_zero_retention_confirmed: str = ""

    # Set to "confirmed" in production after executing DPAs with each processor.
    dpa_openai_confirmed: str = ""
    dpa_twilio_confirmed: str = ""

    # WhatsApp mode: "sandbox" for Twilio Sandbox (pilot), "production" for live number.
    # No code differences between modes at the compliance layer.
    whatsapp_mode: str = "sandbox"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
