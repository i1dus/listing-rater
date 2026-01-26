from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ParserConfig(BaseModel):
    """Конфигурация для запуска парсера (Cian)"""
    city: str = Field(default="spb", description="Город для поиска (spb, moskva, и др.)")
    category: str = Field(default="kvartiry", description="Категория: kvartiry, komnaty, doma")
    deal_type: str = Field(default="sale", description="Тип сделки: sale или rent")
    max_pages: int = Field(default=1, ge=1, le=50, description="Максимальное количество страниц")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Дополнительные фильтры")
    
    class Config:
        json_schema_extra = {
            "example": {
                "city": "spb",
                "category": "kvartiry",
                "deal_type": "sale",
                "max_pages": 1,
                "filters": None
            }
        }


class ParserResult(BaseModel):
    """Результат работы парсера"""
    total_found: int = Field(description="Всего найдено объявлений")
    new_listings: int = Field(description="Новых объявлений добавлено")
    updated_listings: int = Field(description="Объявлений обновлено")
    errors: int = Field(description="Ошибок при обработке")
    pages_parsed: int = Field(description="Страниц обработано")
    rate_limited: bool = Field(default=False, description="Был ли превышен лимит запросов")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_found": 50,
                "new_listings": 35,
                "updated_listings": 15,
                "errors": 0,
                "pages_parsed": 1,
                "rate_limited": False
            }
        }


class RemoveCheckResult(BaseModel):
    """Результат проверки снятых объявлений"""
    checked: int = Field(description="Проверено объявлений")
    removed: int = Field(description="Помечено как снятые")
