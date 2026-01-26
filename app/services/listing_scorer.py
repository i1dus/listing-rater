"""
Сервис для оценки вероятности продажи объявления
Использует простую эвристическую модель на основе характеристик объявления
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.models import Listing

logger = logging.getLogger(__name__)


class ListingScorer:
    """Оценивает вероятность продажи объявления"""
    
    def calculate_sale_probability(self, listing: Listing) -> Dict[str, Any]:
        """
        Вычисляет вероятность продажи объявления (0-100%)
        
        Факторы:
        - Цена за м² (чем ниже относительно среднего, тем выше вероятность)
        - Наличие метро (есть метро = выше вероятность)
        - Время до метро (ближе = выше вероятность)
        - Этаж (средние этажи лучше)
        - Площадь (оптимальный диапазон)
        - Комнаты (популярные варианты)
        - Полнота данных (больше данных = выше вероятность)
        """
        score = 50.0
        factors = []
        
        if listing.price and listing.area_total and listing.area_total > 0:
            price_per_m2 = listing.price / listing.area_total
            
            if price_per_m2 < 150000:
                score += 15
                factors.append("Низкая цена за м² (+15%)")
            elif price_per_m2 < 200000:
                score += 10
                factors.append("Умеренная цена за м² (+10%)")
            elif price_per_m2 < 250000:
                score += 5
                factors.append("Средняя цена за м² (+5%)")
            elif price_per_m2 > 350000:
                score -= 10
                factors.append("Высокая цена за м² (-10%)")
        
        if listing.metro:
            score += 10
            factors.append("Есть метро (+10%)")
            
            if listing.metro_time:
                if listing.metro_time <= 5:
                    score += 5
                    factors.append("Очень близко к метро (+5%)")
                elif listing.metro_time <= 10:
                    score += 3
                    factors.append("Близко к метро (+3%)")
                elif listing.metro_time > 15:
                    score -= 2
                    factors.append("Далеко от метро (-2%)")
        else:
            score -= 5
            factors.append("Нет информации о метро (-5%)")
        
        if listing.floor and listing.floors_total:
            floor_ratio = listing.floor / listing.floors_total if listing.floors_total > 0 else 0
            
            if 0.3 <= floor_ratio <= 0.7:
                score += 8
                factors.append("Оптимальный этаж (+8%)")
            elif floor_ratio < 0.2:
                score -= 5
                factors.append("Низкий этаж (-5%)")
            elif floor_ratio > 0.9:
                score -= 3
                factors.append("Высокий этаж (-3%)")
        
        if listing.area_total:
            if 30 <= listing.area_total <= 80:
                score += 8
                factors.append("Оптимальная площадь (+8%)")
            elif listing.area_total < 20:
                score -= 5
                factors.append("Маленькая площадь (-5%)")
            elif listing.area_total > 120:
                score -= 3
                factors.append("Большая площадь (-3%)")
        
        if listing.rooms is not None:
            if listing.rooms in [1, 2, 3]:
                score += 5
                factors.append("Популярное количество комнат (+5%)")
            elif listing.rooms == 0:
                score += 3
                factors.append("Студия (+3%)")
            elif listing.rooms > 4:
                score -= 3
                factors.append("Много комнат (-3%)")
        
        data_completeness = 0
        if listing.price:
            data_completeness += 1
        if listing.area_total:
            data_completeness += 1
        if listing.rooms is not None:
            data_completeness += 1
        if listing.floor is not None:
            data_completeness += 1
        if listing.metro:
            data_completeness += 1
        if listing.address:
            data_completeness += 1
        
        if data_completeness >= 5:
            score += 5
            factors.append("Полные данные (+5%)")
        elif data_completeness < 3:
            score -= 5
            factors.append("Неполные данные (-5%)")
        
        if listing.address and len(listing.address) > 10:
            score += 3
            factors.append("Есть адрес (+3%)")
        
        score = max(0, min(100, score))
        
        if score >= 75:
            category = "Высокая"
            category_color = "success"
        elif score >= 60:
            category = "Средняя"
            category_color = "info"
        elif score >= 45:
            category = "Низкая"
            category_color = "warning"
        else:
            category = "Очень низкая"
            category_color = "danger"
        
        return {
            "probability": round(score, 1),
            "category": category,
            "category_color": category_color,
            "factors": factors,
            "calculated_at": datetime.utcnow().isoformat()
        }
