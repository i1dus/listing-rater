from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Property(Base):
    """
    Объект недвижимости (квартира, дом и т.д.)
    Группирует объявления об одном и том же объекте
    """
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    
    city = Column(String(255), nullable=True, index=True)
    district = Column(String(255), nullable=True)
    street = Column(String(255), nullable=True)
    house_number = Column(String(50), nullable=True)
    
    property_type = Column(String(50), nullable=True, index=True)
    rooms = Column(Integer, nullable=True)
    floor = Column(Integer, nullable=True)
    floors_total = Column(Integer, nullable=True)
    area_total = Column(Float, nullable=True)
    area_living = Column(Float, nullable=True)
    area_kitchen = Column(Float, nullable=True)
    
    property_hash = Column(String(64), unique=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    listings = relationship("Listing", back_populates="property")
    
    def __repr__(self):
        return f"<Property(id={self.id}, city={self.city}, street={self.street}, rooms={self.rooms})>"
