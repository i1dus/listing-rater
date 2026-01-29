"""
Извлечение признаков (features) из объявлений
Готово для использования в ML моделях
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.models import Listing

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Извлекает признаки из объявления для использования в ML моделях.
    Все признаки нормализованы и готовы для подачи в модель.
    """
    
    def extract(self, listing: Listing, regional_stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Извлекает все признаки из объявления.
        
        Args:
            listing: Объявление
            regional_stats: Региональная статистика (опционально)
        
        Returns:
            Словарь с признаками
        """
        features = {}
        features.update(self._extract_basic_features(listing))
        features.update(self._extract_price_features(listing, regional_stats))
        features.update(self._extract_location_features(listing))
        features.update(self._extract_property_features(listing))
        features.update(self._extract_data_quality_features(listing))
        features.update(self._extract_temporal_features(listing))
        return features
    
    def _extract_basic_features(self, listing: Listing) -> Dict[str, Any]:
        """Базовые признаки"""
        return {
            "rooms": listing.rooms if listing.rooms is not None else -1,
            "area_total": listing.area_total if listing.area_total else -1.0,
            "area_living": listing.area_living if listing.area_living else -1.0,
            "area_kitchen": listing.area_kitchen if listing.area_kitchen else -1.0,
            "floor": listing.floor if listing.floor is not None else -1,
            "floors_total": listing.floors_total if listing.floors_total else -1,
            "property_type": self._encode_property_type(listing.property_type),
            "deal_type": self._encode_deal_type(listing.deal_type),
        }
    
    def _extract_price_features(
        self, 
        listing: Listing, 
        regional_stats: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Признаки цены с учетом региональной статистики"""
        features = {}
        
        if listing.price and listing.area_total and listing.area_total > 0:
            price_per_m2 = listing.price / listing.area_total
            features["price"] = float(listing.price)
            features["price_per_m2"] = price_per_m2
            
            if regional_stats and "price_per_m2" in regional_stats:
                stats = regional_stats["price_per_m2"]
                mean_price = stats.get("mean", price_per_m2)
                std_price = stats.get("std", mean_price * 0.3)
                
                if std_price > 0:
                    features["price_per_m2_normalized"] = (price_per_m2 - mean_price) / std_price
                    features["price_per_m2_percentile"] = self._calculate_percentile(
                        price_per_m2, stats.get("percentiles", {})
                    )
                else:
                    features["price_per_m2_normalized"] = 0.0
                    features["price_per_m2_percentile"] = 50.0
            else:
                features["price_per_m2_normalized"] = 0.0
                features["price_per_m2_percentile"] = 50.0
        else:
            features["price"] = -1.0
            features["price_per_m2"] = -1.0
            features["price_per_m2_normalized"] = 0.0
            features["price_per_m2_percentile"] = 50.0
        
        return features
    
    def _extract_location_features(self, listing: Listing) -> Dict[str, Any]:
        """Признаки местоположения"""
        features = {
            "has_metro": 1 if listing.metro else 0,
            "metro_time": listing.metro_time if listing.metro_time else -1,
            "metro_transport": self._encode_metro_transport(listing.metro_transport),
            "has_city": 1 if listing.city else 0,
            "has_district": 1 if listing.district else 0,
            "has_address": 1 if listing.address else 0,
        }
        
        if listing.metro_time is not None:
            if listing.metro_time <= 5:
                features["metro_proximity"] = 1.0
            elif listing.metro_time <= 10:
                features["metro_proximity"] = 0.7
            elif listing.metro_time <= 15:
                features["metro_proximity"] = 0.4
            else:
                features["metro_proximity"] = 0.1
        else:
            features["metro_proximity"] = 0.0
        
        return features
    
    def _extract_property_features(self, listing: Listing) -> Dict[str, Any]:
        """Признаки недвижимости"""
        features = {}
        
        if listing.floor and listing.floors_total and listing.floors_total > 0:
            floor_ratio = listing.floor / listing.floors_total
            features["floor_ratio"] = floor_ratio
            
            if floor_ratio < 0.2:
                features["floor_category"] = 0
            elif floor_ratio < 0.4:
                features["floor_category"] = 1
            elif floor_ratio <= 0.7:
                features["floor_category"] = 2
            elif floor_ratio <= 0.9:
                features["floor_category"] = 3
            else:
                features["floor_category"] = 4
        else:
            features["floor_ratio"] = -1.0
            features["floor_category"] = -1
        
        if listing.area_total:
            if listing.area_total < 20:
                features["area_category"] = 0
            elif listing.area_total < 30:
                features["area_category"] = 1
            elif listing.area_total <= 80:
                features["area_category"] = 2
            elif listing.area_total <= 120:
                features["area_category"] = 3
            else:
                features["area_category"] = 4
        else:
            features["area_category"] = -1
        
        if listing.area_total and listing.area_living and listing.area_total > 0:
            features["living_area_ratio"] = listing.area_living / listing.area_total
        else:
            features["living_area_ratio"] = -1.0
        
        return features
    
    def _extract_data_quality_features(self, listing: Listing) -> Dict[str, Any]:
        """Признаки качества данных"""
        filled_fields = sum([
            1 if listing.price else 0,
            1 if listing.area_total else 0,
            1 if listing.rooms is not None else 0,
            1 if listing.floor is not None else 0,
            1 if listing.metro else 0,
            1 if listing.address else 0,
            1 if listing.description else 0,
            1 if listing.images else 0,
        ])
        
        return {
            "data_completeness": filled_fields / 8.0,
            "has_description": 1 if listing.description else 0,
            "has_images": 1 if listing.images else 0,
            "description_length": len(listing.description) if listing.description else 0,
        }
    
    def _extract_temporal_features(self, listing: Listing) -> Dict[str, Any]:
        """Временные признаки"""
        now = datetime.utcnow()
        features = {}
        
        if listing.parsed_at:
            days_since_parsed = (now - listing.parsed_at.replace(tzinfo=None)).days
            features["days_since_parsed"] = days_since_parsed
        else:
            features["days_since_parsed"] = -1
        
        if listing.published_at:
            days_since_published = (now - listing.published_at.replace(tzinfo=None)).days
            features["days_since_published"] = days_since_published
        else:
            features["days_since_published"] = -1
        
        features["is_active"] = 1 if listing.is_active else 0
        
        return features
    
    def _encode_property_type(self, property_type: Optional[str]) -> int:
        """Кодирование типа недвижимости"""
        encoding = {
            "Квартиры": 0,
            "Комнаты": 1,
            "Дома": 2,
            "Участки": 3,
            "Коммерческая недвижимость": 4,
        }
        return encoding.get(property_type, -1)
    
    def _encode_deal_type(self, deal_type: Optional[str]) -> int:
        """Кодирование типа сделки"""
        if deal_type in ["Продажа", "sale", "prodam", "kupit"]:
            return 0
        elif deal_type in ["Аренда", "rent", "sdam", "snyat"]:
            return 1
        return -1
    
    def _encode_metro_transport(self, transport: Optional[str]) -> int:
        """Кодирование типа транспорта до метро"""
        if transport == "walk":
            return 0
        elif transport in ["transport", "public"]:
            return 1
        return -1
    
    def _calculate_percentile(self, value: float, percentiles: Dict[str, float]) -> float:
        """Вычисляет процентиль значения на основе распределения"""
        if not percentiles:
            return 50.0
        
        sorted_percentiles = sorted(percentiles.items(), key=lambda x: x[1])
        
        for i, (pct, pct_value) in enumerate(sorted_percentiles):
            if value <= pct_value:
                if i == 0:
                    return float(pct)
                prev_pct_str, prev_value = sorted_percentiles[i - 1]
                ratio = (value - prev_value) / (pct_value - prev_value) if (pct_value - prev_value) > 0 else 0
                prev_pct_float = float(prev_pct_str)
                pct_float = float(pct)
                return prev_pct_float + ratio * (pct_float - prev_pct_float)
        
        return 100.0
