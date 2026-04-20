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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
