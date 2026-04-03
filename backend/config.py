from pydantic_settings import BaseSettings
from functools import lru_cache


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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
