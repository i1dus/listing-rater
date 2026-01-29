"""
Основной сервис оценки вероятности продажи
Использует ML модель и региональную статистику
"""
import logging
from typing import Dict, Any, Optional, Tuple

from app.models import Listing
from app.services.scoring.features import FeatureExtractor
from app.services.scoring.regional_stats import RegionalStatistics
from app.services.scoring.ml_model import MLModelInterface, MLModelLoader

logger = logging.getLogger(__name__)


class SaleProbabilityScorer:
    """
    Сервис для оценки вероятности продажи объявления.
    Использует ML модель (или заглушку) и региональную статистику.
    """
    
    def __init__(
        self,
        ml_model: Optional[MLModelInterface] = None,
        regional_stats: Optional[RegionalStatistics] = None,
        feature_extractor: Optional[FeatureExtractor] = None
    ):
        """
        Инициализирует сервис оценки.
        
        Args:
            ml_model: ML модель (если None, загружается дефолтная)
            regional_stats: Региональная статистика (обязательно)
            feature_extractor: Извлекатель признаков (если None, создается новый)
        """
        self.ml_model = ml_model or MLModelLoader.load_model()
        self.regional_stats = regional_stats
        self.feature_extractor = feature_extractor or FeatureExtractor()
        
        logger.info(f"Initialized SaleProbabilityScorer with model: {self.ml_model.model_name}")
    
    def calculate_probability(
        self, 
        listing: Listing,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Вычисляет вероятность продажи объявления.
        
        Args:
            listing: Объявление
            include_details: Включать ли детальную информацию
        
        Returns:
            Словарь с результатами оценки
        """
        regional_stats = None
        if self.regional_stats:
            regional_stats = self.regional_stats.get_statistics(
                city=listing.city,
                district=listing.district,
                property_type=listing.property_type
            )
        
        features = self.feature_extractor.extract(listing, regional_stats)
        
        if include_details:
            prediction = self.ml_model.predict_with_confidence(features)
            feature_importance = self.ml_model.get_feature_importance(features)
        else:
            probability = self.ml_model.predict(features)
            prediction = {"probability": probability}
            feature_importance = {}
        
        probability = prediction["probability"]
        probability_percent = probability * 100.0
        
        category, category_color = self._categorize_probability(probability_percent)
        factors = self._generate_factors(features, prediction, feature_importance)
        
        result = {
            "probability": round(probability_percent, 1),
            "category": category,
            "category_color": category_color,
            "factors": factors,
            "model_name": self.ml_model.model_name,
            "model_version": self.ml_model.model_version,
        }
        
        if include_details:
            result.update({
                "confidence_interval": {
                    "lower": round(prediction.get("confidence_lower", probability) * 100, 1),
                    "upper": round(prediction.get("confidence_upper", probability) * 100, 1),
                    "level": prediction.get("confidence_level", 0.95),
                },
                "feature_importance": {
                    k: round(v * 100, 1) 
                    for k, v in feature_importance.items()
                },
                "features_count": len(features),
                "regional_stats_used": regional_stats is not None,
            })
        
        return result
    
    def _categorize_probability(self, probability: float) -> Tuple[str, str]:
        """Определяет категорию вероятности"""
        if probability >= 75:
            return "Высокая", "success"
        elif probability >= 60:
            return "Средняя", "info"
        elif probability >= 45:
            return "Низкая", "warning"
        else:
            return "Очень низкая", "danger"
    
    def _generate_factors(
        self,
        features: Dict[str, Any],
        prediction: Dict[str, Any],
        feature_importance: Dict[str, float]
    ) -> list[str]:
        """Генерирует список факторов для отображения"""
        factors = []
        
        price_norm = features.get("price_per_m2_normalized", 0.0)
        if price_norm < -1.0:
            factors.append("Низкая цена за м² относительно региона (+15%)")
        elif price_norm < -0.5:
            factors.append("Умеренная цена за м² (+10%)")
        elif price_norm > 1.5:
            factors.append("Высокая цена за м² (-10%)")
        
        if features.get("has_metro", 0) == 1:
            metro_prox = features.get("metro_proximity", 0.0)
            if metro_prox >= 0.7:
                factors.append("Очень близко к метро (+10%)")
            elif metro_prox >= 0.4:
                factors.append("Близко к метро (+7%)")
            else:
                factors.append("Есть метро (+5%)")
        else:
            factors.append("Нет информации о метро (-5%)")
        
        floor_cat = features.get("floor_category", -1)
        if floor_cat == 2:
            factors.append("Оптимальный этаж (+8%)")
        elif floor_cat in [0, 4]:
            factors.append("Неоптимальный этаж (-5%)")
        
        area_cat = features.get("area_category", -1)
        if area_cat == 2:
            factors.append("Оптимальная площадь (+8%)")
        elif area_cat in [0, 4]:
            factors.append("Неоптимальная площадь (-5%)")
        
        rooms = features.get("rooms", -1)
        if rooms in [1, 2, 3]:
            factors.append("Популярное количество комнат (+5%)")
        
        data_quality = features.get("data_completeness", 0.0)
        if data_quality >= 0.8:
            factors.append("Полные данные (+5%)")
        elif data_quality < 0.5:
            factors.append("Неполные данные (-5%)")
        
        if features.get("price_per_m2_percentile", 50.0) < 25:
            factors.append("Цена ниже 25% объявлений в регионе")
        
        return factors
