"""
Интерфейс для ML моделей предсказания вероятности продажи
Сейчас используется заглушка, но архитектура готова для реальных ML моделей
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MLModelInterface(ABC):
    """
    Абстрактный интерфейс для ML моделей.
    Реальные модели должны наследоваться от этого класса.
    """
    
    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> float:
        """
        Предсказывает вероятность продажи на основе признаков.
        
        Args:
            features: Словарь с признаками
        
        Returns:
            Вероятность продажи (0.0 - 1.0)
        """
        pass
    
    @abstractmethod
    def predict_with_confidence(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Предсказывает вероятность с дополнительной информацией (confidence, intervals).
        
        Args:
            features: Словарь с признаками
        
        Returns:
            Словарь с вероятностью и метаданными
        """
        pass
    
    @abstractmethod
    def get_feature_importance(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        Возвращает важность признаков для данного предсказания.
        
        Args:
            features: Словарь с признаками
        
        Returns:
            Словарь с важностью каждого признака
        """
        pass


class DummyMLModel(MLModelInterface):
    """
    Заглушка ML модели.
    Использует простую эвристику, но имеет интерфейс реальной ML модели.
    В будущем может быть заменена на обученную модель (XGBoost, LightGBM, Neural Network и т.д.)
    """
    
    def __init__(self):
        self.model_name = "DummyHeuristicModel"
        self.model_version = "1.0.0"
        logger.info(f"Initialized {self.model_name} v{self.model_version}")
    
    def predict(self, features: Dict[str, Any]) -> float:
        """Предсказывает вероятность продажи (заглушка)"""
        score = 0.5
        
        price_norm = features.get("price_per_m2_normalized", 0.0)
        if price_norm < -1.0:
            score += 0.15
        elif price_norm < -0.5:
            score += 0.10
        elif price_norm > 1.5:
            score -= 0.10
        
        if features.get("has_metro", 0) == 1:
            score += 0.10
            metro_prox = features.get("metro_proximity", 0.0)
            score += metro_prox * 0.05
        
        floor_cat = features.get("floor_category", -1)
        if floor_cat == 2:
            score += 0.08
        elif floor_cat in [0, 4]:
            score -= 0.05
        
        area_cat = features.get("area_category", -1)
        if area_cat == 2:
            score += 0.08
        elif area_cat in [0, 4]:
            score -= 0.05
        
        rooms = features.get("rooms", -1)
        if rooms in [1, 2, 3]:
            score += 0.05
        
        data_quality = features.get("data_completeness", 0.0)
        score += data_quality * 0.05
        
        score = max(0.0, min(1.0, score))
        
        return score
    
    def predict_with_confidence(
        self, 
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Предсказывает вероятность с доверительным интервалом (заглушка).
        В реальной ML модели здесь будет использоваться uncertainty quantification.
        """
        probability = self.predict(features)
        confidence_interval = 0.1
        
        return {
            "probability": probability,
            "confidence_lower": max(0.0, probability - confidence_interval),
            "confidence_upper": min(1.0, probability + confidence_interval),
            "confidence_level": 0.95,
        }
    
    def get_feature_importance(
        self, 
        features: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Возвращает важность признаков (заглушка).
        В реальной ML модели здесь будет:
        - SHAP values
        - Permutation importance
        - Feature importance из модели
        """
        importance = {
            "price_per_m2_normalized": 0.25,
            "has_metro": 0.15,
            "metro_proximity": 0.10,
            "floor_category": 0.12,
            "area_category": 0.12,
            "rooms": 0.08,
            "data_completeness": 0.08,
            "living_area_ratio": 0.05,
            "days_since_published": 0.03,
            "other": 0.02,
        }
        
        return importance


class MLModelLoader:
    """
    Загрузчик ML моделей.
    В будущем будет загружать обученные модели из файлов или MLflow.
    """
    
    @staticmethod
    def load_model(model_path: Optional[str] = None) -> MLModelInterface:
        """
        Загружает ML модель.
        
        Args:
            model_path: Путь к файлу модели (опционально)
        
        Returns:
            Экземпляр ML модели
        """
        if model_path:
            logger.info(f"Loading model from {model_path} (not implemented, using dummy)")
        
        return DummyMLModel()
