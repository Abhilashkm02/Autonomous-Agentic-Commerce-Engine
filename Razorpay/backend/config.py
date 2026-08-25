from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    LLM_API_KEY: str = ''
    MAX_TRANSACTION_AMOUNT: int = 500000
    AGENT_POLL_INTERVAL: int = 10
    DATABASE_URL: str = 'sqlite:///backend/db/commerce.db'

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

@lru_cache
def get_settings() -> Settings:
    """Returns a cached instance of the Settings class."""
    return Settings()
