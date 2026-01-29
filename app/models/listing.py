from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Listing(Base):
    """
    Объявление о продаже/аренде недвижимости
    """
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    avito_id = Column(BigInteger, unique=True, index=True, nullable=False)
    property_id = Column(Integer, ForeignKey("properties.id"), nullable=True, index=True)
    match_score = Column(Float, nullable=True, comment="Процент сходства с объектом недвижимости (0-100)")
    
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(1000), nullable=False)
    deal_type = Column(String(50), nullable=True, index=True)
    
    price = Column(BigInteger, nullable=True)
    price_per_meter = Column(Float, nullable=True)
    currency = Column(String(10), default="RUB")
    
    city = Column(String(255), nullable=True, index=True)
    district = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    
    metro = Column(String(255), nullable=True)
    metro_time = Column(Integer, nullable=True)
    metro_transport = Column(String(50), nullable=True)
    
    property_type = Column(String(50), nullable=True)
    rooms = Column(Integer, nullable=True)
    floor = Column(Integer, nullable=True)
    floors_total = Column(Integer, nullable=True)
    area_total = Column(Float, nullable=True)
    area_living = Column(Float, nullable=True)
    area_kitchen = Column(Float, nullable=True)
    
    building_type = Column(String(100), nullable=True)
    year_built = Column(Integer, nullable=True)
    renovation = Column(String(100), nullable=True)
    balcony = Column(String(100), nullable=True)
    bathroom = Column(String(100), nullable=True)
    
    seller_name = Column(String(255), nullable=True)
    seller_type = Column(String(50), nullable=True)
    
    images = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True, index=True)
    
    parsed_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    property = relationship("Property", back_populates="listings")
    status_logs = relationship("StatusLog", back_populates="listing", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Listing(id={self.id}, avito_id={self.avito_id}, title={self.title[:50] if self.title else None})>"
