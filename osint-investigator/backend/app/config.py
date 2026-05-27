from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite+aiosqlite:///./osint.db"
    hibp_api_key: str = ""
    google_search_api_key: str = ""   # Google Custom Search API key
    google_search_cx: str = ""        # Google Custom Search Engine ID
    serper_api_key: str = ""          # Serper.dev API key (alternativa ao Google CSE)
    cgu_api_key: str = ""             # CGU Portal Transparência — PEP Brasil (grátis)
    brasilio_token: str = ""          # brasil.io token — QSA socios dataset (opcional, melhora rate limit)
    # In production (Railway), frontend is served from the same origin,
    # so CORS is only needed for local dev. Allow all origins as fallback.
    cors_origins: List[str] = ["*"]
    data_dir: str = "/app/data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
