from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = "https://api.groq.com/openai/v1"
    openai_model: str = "llama-3.3-70b-versatile"
    catalog_path: Path = ROOT / "data" / "catalog.json"
    host: str = "0.0.0.0"
    port: int = 8000
    max_turns: int = 8
    retrieval_pool: int = 30
    shortlist_max: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
