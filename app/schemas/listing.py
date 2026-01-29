from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ListingBase(BaseModel):
    """Базовая схема объявления"""
    title: Optional[str] = None
    description: Optional[str] = None
    url: str
    deal_type: Optional[str] = None
    price: Optional[int] = None
    price_per_meter: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    metro: Optional[str] = None
    metro_time: Optional[int] = None
    metro_transport: Optional[str] = None
    property_type: Optional[str] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    area_total: Optional[float] = None
    area_living: Optional[float] = None
    area_kitchen: Optional[float] = None
    building_type: Optional[str] = None
    year_built: Optional[int] = None
    renovation: Optional[str] = None
    balcony: Optional[str] = None
    bathroom: Optional[str] = None
    seller_name: Optional[str] = None
    seller_type: Optional[str] = None


class ListingCreate(ListingBase):
    """Схема для создания объявления"""
    avito_id: int


class ListingUpdate(BaseModel):
    """Схема для обновления объявления"""
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    area_total: Optional[float] = None
    area_living: Optional[float] = None
    area_kitchen: Optional[float] = None
    building_type: Optional[str] = None
    year_built: Optional[int] = None
    renovation: Optional[str] = None
    is_active: Optional[bool] = None
    property_id: Optional[int] = None


class StatusLogResponse(BaseModel):
    """Схема лога статуса"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: str
    published_at: Optional[datetime] = None
    removed_at: Optional[datetime] = None
    created_at: datetime


class ListingResponse(ListingBase):
    """Схема ответа с объявлением"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    avito_id: int
    property_id: Optional[int] = None
    match_score: Optional[float] = None  # Процент сходства с объектом недвижимости (0-100)
    is_active: bool
    images: Optional[str] = None
    parsed_at: datetime
    published_at: Optional[datetime] = None
    updated_at: datetime
    status_logs: List[StatusLogResponse] = []


class ListingListResponse(BaseModel):
    """Схема списка объявлений с пагинацией"""
    items: List[ListingResponse]
    total: int
    page: int
    per_page: int
    pages: int
