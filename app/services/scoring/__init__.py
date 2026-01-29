"""
Сервис оценки вероятности продажи объявлений
Архитектура готова для интеграции ML моделей
"""
from app.services.scoring.scorer import SaleProbabilityScorer
from app.services.scoring.features import FeatureExtractor
from app.services.scoring.regional_stats import RegionalStatistics
from app.services.scoring.ml_model import MLModelInterface, DummyMLModel, MLModelLoader

__all__ = [
    "SaleProbabilityScorer",
    "FeatureExtractor",
    "RegionalStatistics",
    "MLModelInterface",
    "DummyMLModel",
    "MLModelLoader",
]
