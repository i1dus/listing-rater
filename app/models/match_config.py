from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class MatchConfig(Base):
    """
    Конфигурация метчинга объявлений с объектами недвижимости.
    Хранит веса атрибутов и список строгих атрибутов.
    """
    __tablename__ = "match_configs"

    id = Column(Integer, primary_key=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, comment="Активна ли эта конфигурация")
    
    # Веса атрибутов в формате JSON: {"city": 15.0, "street": 20.0, ...}
    weights = Column(JSON, nullable=False, comment="Веса атрибутов для вычисления сходства")
    
    # Список строгих атрибутов: ["city", "street", "house_number"]
    strict_attributes = Column(JSON, nullable=False, comment="Атрибуты, которые должны строго совпадать")
    
    # Минимальный процент сходства для сопоставления
    threshold = Column(String(10), nullable=False, default="70.0", comment="Минимальный процент сходства (0-100)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<MatchConfig(id={self.id}, active={self.is_active}, threshold={self.threshold})>"
