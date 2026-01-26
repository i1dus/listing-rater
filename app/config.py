from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/listing_rater"
    app_name: str = "Listing Rater"
    debug: bool = True
    
    avito_base_url: str = "https://www.avito.ru"
    request_delay: float = 5.0  # Base delay between page requests in seconds
    request_delay_random: float = 3.0  # Random additional delay (0 to this value)
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
