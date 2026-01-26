from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class StatusLog(Base):
    """
    Лог изменения статуса объявления
    Отслеживает публикацию и снятие объявлений
    """
    __tablename__ = "status_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Связь с объявлением
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Статус
    status = Column(String(50), nullable=False)  # published, removed, reactivated
    
    # Даты
    published_at = Column(DateTime(timezone=True), nullable=True)  # Дата публикации
    removed_at = Column(DateTime(timezone=True), nullable=True)    # Дата снятия
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Дополнительная информация
    note = Column(String(500), nullable=True)
    
    # Связи
    listing = relationship("Listing", back_populates="status_logs")
    
    def __repr__(self):
        return f"<StatusLog(id={self.id}, listing_id={self.listing_id}, status={self.status})>"
