from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MatchConfigBase(BaseModel):
    """Базовая схема настроек метчинга"""
    weights: Dict[str, float] = Field(..., description="Веса атрибутов для вычисления сходства")
    strict_attributes: List[str] = Field(..., description="Атрибуты, которые должны строго совпадать")
    threshold: float = Field(..., ge=0.0, le=100.0, description="Минимальный процент сходства (0-100)")
    
    @field_validator('weights')
    @classmethod
    def validate_weights(cls, v):
        if not v:
            raise ValueError('Веса не могут быть пустыми')
        # Проверяем, что все веса положительные
        for attr, weight in v.items():
            if weight < 0:
                raise ValueError(f'Вес атрибута "{attr}" не может быть отрицательным')
        return v
    
    @field_validator('strict_attributes')
    @classmethod
    def validate_strict_attributes(cls, v, info):
        # Проверяем, что все строгие атрибуты есть в весах
        if 'weights' in info.data:
            weights = info.data['weights']
            for attr in v:
                if attr not in weights:
                    raise ValueError(f'Строгий атрибут "{attr}" отсутствует в весах')
        return v


class MatchConfigCreate(MatchConfigBase):
    """Схема для создания конфигурации"""
    is_active: bool = Field(default=True, description="Активна ли эта конфигурация")


class MatchConfigUpdate(BaseModel):
    """Схема для обновления конфигурации"""
    weights: Optional[Dict[str, float]] = None
    strict_attributes: Optional[List[str]] = None
    threshold: Optional[float] = Field(None, ge=0.0, le=100.0)
    is_active: Optional[bool] = None


class MatchConfigResponse(MatchConfigBase):
    """Схема ответа с конфигурацией"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
