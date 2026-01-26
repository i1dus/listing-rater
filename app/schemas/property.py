from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PropertyBase(BaseModel):
    """Базовая схема объекта недвижимости"""
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    house_number: Optional[str] = None
    property_type: Optional[str] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    area_total: Optional[float] = None
    area_living: Optional[float] = None
    area_kitchen: Optional[float] = None


class PropertyCreate(PropertyBase):
    """Схема для создания объекта"""
    pass


class PropertyUpdate(BaseModel):
    """Схема для обновления объекта"""
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    house_number: Optional[str] = None
    property_type: Optional[str] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    area_total: Optional[float] = None
    area_living: Optional[float] = None
    area_kitchen: Optional[float] = None


class ListingBriefResponse(BaseModel):
    """Краткая информация об объявлении для отображения в объекте"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    avito_id: int
    title: Optional[str] = None
    price: Optional[int] = None
    deal_type: Optional[str] = None
    is_active: bool
    parsed_at: datetime


class PropertyResponse(PropertyBase):
    """Схема ответа с объектом недвижимости"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    property_hash: str
    created_at: datetime
    updated_at: datetime
    listings: List[ListingBriefResponse] = []
    listings_count: Optional[int] = None


class PropertyListResponse(BaseModel):
    """Схема списка объектов с пагинацией"""
    items: List[PropertyResponse]
    total: int
    page: int
    per_page: int
    pages: int
