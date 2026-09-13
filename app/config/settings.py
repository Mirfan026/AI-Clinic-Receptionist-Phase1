import os
from functools import lru_cache

class Settings:
    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite:///./storage/clinic.db")

@lru_cache
def get_settings() -> Settings:
    return Settings()
