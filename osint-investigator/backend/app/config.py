from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite+aiosqlite:///./osint.db"
    hibp_api_key: str = ""
    cors_origins: List[str] = ["http://localhost:5173"]
    data_dir: str = "/app/data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
