"""
Региональная статистика для нормализации признаков
Поддерживает динамическое обновление статистики по городам/регионам
"""
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models import Listing, Property

logger = logging.getLogger(__name__)


class RegionalStatistics:
    """
    Управляет региональной статистикой для нормализации признаков.
    В будущем может быть заменено на ML модель для предсказания распределений.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get_statistics(
        self, 
        city: Optional[str] = None,
        district: Optional[str] = None,
        property_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получает статистику для региона.
        
        Args:
            city: Город
            district: Район (опционально)
            property_type: Тип недвижимости (опционально)
        
        Returns:
            Словарь со статистикой
        """
        cache_key = f"{city}_{district}_{property_type}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        stats = self._calculate_statistics(city, district, property_type)
        self._cache[cache_key] = stats
        
        return stats
    
    def _calculate_statistics(
        self,
        city: Optional[str] = None,
        district: Optional[str] = None,
        property_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Вычисляет статистику на основе данных из БД"""
        query = self.db.query(Listing).filter(Listing.is_active == True)
        
        if city:
            query = query.filter(Listing.city.ilike(f"%{city}%"))
        if district:
            query = query.filter(Listing.district.ilike(f"%{district}%"))
        if property_type:
            query = query.filter(Listing.property_type == property_type)
        
        listings = query.filter(
            Listing.price.isnot(None),
            Listing.area_total.isnot(None),
            Listing.area_total > 0
        ).all()
        
        if not listings:
            return self._get_default_statistics()
        
        prices_per_m2 = []
        for listing in listings:
            if listing.price and listing.area_total:
                prices_per_m2.append(listing.price / listing.area_total)
        
        if not prices_per_m2:
            return self._get_default_statistics()
        
        prices_per_m2.sort()
        n = len(prices_per_m2)
        
        mean_price = sum(prices_per_m2) / n
        median_price = prices_per_m2[n // 2]
        
        variance = sum((x - mean_price) ** 2 for x in prices_per_m2) / n
        std_price = variance ** 0.5
        
        percentiles = {
            "10": prices_per_m2[int(n * 0.1)],
            "25": prices_per_m2[int(n * 0.25)],
            "50": prices_per_m2[int(n * 0.5)],
            "75": prices_per_m2[int(n * 0.75)],
            "90": prices_per_m2[int(n * 0.9)],
        }
        
        areas = [l.area_total for l in listings if l.area_total]
        mean_area = sum(areas) / len(areas) if areas else 0
        
        rooms_distribution = {}
        for listing in listings:
            if listing.rooms is not None:
                rooms_distribution[listing.rooms] = rooms_distribution.get(listing.rooms, 0) + 1
        
        return {
            "price_per_m2": {
                "mean": mean_price,
                "median": median_price,
                "std": std_price,
                "min": prices_per_m2[0],
                "max": prices_per_m2[-1],
                "percentiles": percentiles,
                "sample_size": n,
            },
            "area_total": {
                "mean": mean_area,
                "sample_size": len(areas),
            },
            "rooms_distribution": rooms_distribution,
            "sample_size": n,
        }
    
    def _get_default_statistics(self) -> Dict[str, Any]:
        """Возвращает дефолтную статистику"""
        return {
            "price_per_m2": {
                "mean": 200000.0,
                "median": 190000.0,
                "std": 60000.0,
                "min": 100000.0,
                "max": 500000.0,
                "percentiles": {
                    "10": 120000.0,
                    "25": 150000.0,
                    "50": 190000.0,
                    "75": 240000.0,
                    "90": 300000.0,
                },
                "sample_size": 0,
            },
            "area_total": {
                "mean": 50.0,
                "sample_size": 0,
            },
            "rooms_distribution": {},
            "sample_size": 0,
        }
    
    def invalidate_cache(self, city: Optional[str] = None):
        """Очищает кэш статистики"""
        if city:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(city)]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()
    
    def update_statistics(self, city: Optional[str] = None):
        """
        Обновляет статистику для региона.
        В будущем может вызываться периодически или при изменении данных.
        """
        self.invalidate_cache(city)
