from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Dict, List


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/listing_rater"
    app_name: str = "Listing Rater"
    debug: bool = True
    
    avito_base_url: str = "https://www.avito.ru"
    request_delay: float = 5.0  # Base delay between page requests in seconds
    request_delay_random: float = 3.0  # Random additional delay (0 to this value)
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # Настройки метчинга недвижимости
    # Веса атрибутов для вычисления сходства (сумма должна быть ~100)
    property_match_weights: Dict[str, float] = {
        "city": 15.0,
        "street": 20.0,
        "house_number": 15.0,
        "rooms": 10.0,
        "area_total": 15.0,
        "floor": 5.0,
        "property_type": 10.0,
        "district": 5.0,
        "area_living": 3.0,
        "area_kitchen": 2.0,
    }
    
    # Атрибуты, которые должны строго совпадать (иначе сходство = 0)
    property_match_strict_attributes: List[str] = [
        "city",
        "street",
        "house_number",
    ]
    
    # Минимальный процент сходства для сопоставления (0-100)
    property_match_threshold: float = 70.0
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
