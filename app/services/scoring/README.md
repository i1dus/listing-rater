# Сервис оценки вероятности продажи

Архитектура сервиса спроектирована для будущей интеграции ML моделей. Сейчас используются заглушки и эвристики.

## Архитектура

### Компоненты

1. **FeatureExtractor** (`features.py`)
   - Извлекает признаки из объявлений
   - Нормализует признаки для ML моделей
   - Учитывает региональную статистику для нормализации

2. **RegionalStatistics** (`regional_stats.py`)
   - Вычисляет статистику по городам/регионам
   - Динамические распределения цен, площадей и т.д.
   - Кэширование статистики для производительности
   - В будущем может быть заменено на ML модель для предсказания распределений

3. **MLModelInterface** (`ml_model.py`)
   - Абстрактный интерфейс для ML моделей
   - `DummyMLModel` - текущая заглушка с эвристикой
   - `MLModelLoader` - загрузчик моделей (готов для реальных моделей)

4. **SaleProbabilityScorer** (`scorer.py`)
   - Основной сервис, объединяющий все компоненты
   - Использует ML модель для предсказания
   - Возвращает детальную информацию о предсказании

## Интеграция реальной ML модели

### Вариант 1: XGBoost / LightGBM

```python
import xgboost as xgb

class XGBoostModel(MLModelInterface):
    def __init__(self, model_path: str):
        self.model = xgb.Booster()
        self.model.load_model(model_path)
    
    def predict(self, features: Dict[str, Any]) -> float:
        # Преобразуем features в формат для XGBoost
        feature_vector = self._features_to_vector(features)
        prediction = self.model.predict(feature_vector)
        return float(prediction[0])
```

### Вариант 2: TensorFlow / PyTorch

```python
import tensorflow as tf

class TensorFlowModel(MLModelInterface):
    def __init__(self, model_path: str):
        self.model = tf.keras.models.load_model(model_path)
    
    def predict(self, features: Dict[str, Any]) -> float:
        feature_vector = self._features_to_vector(features)
        prediction = self.model.predict(feature_vector)
        return float(prediction[0][0])
```

### Вариант 3: MLflow

```python
import mlflow

class MLflowModel(MLModelInterface):
    def __init__(self, model_uri: str):
        self.model = mlflow.pyfunc.load_model(model_uri)
    
    def predict(self, features: Dict[str, Any]) -> float:
        prediction = self.model.predict([features])
        return float(prediction[0])
```

## Региональная статистика

Текущая реализация вычисляет статистику на основе данных из БД:
- Средняя/медианная цена за м²
- Процентили распределения цен
- Распределение по количеству комнат
- И т.д.

В будущем можно:
- Использовать ML модель для предсказания распределений
- Учитывать временные тренды
- Учитывать сезонность
- Использовать внешние данные (экономические индикаторы)

## Feature Engineering

Все признаки нормализованы и готовы для ML:
- Числовые признаки нормализованы
- Категориальные признаки закодированы
- Отсутствующие значения обработаны
- Региональная нормализация применена

## Примеры использования

```python
from app.services.scoring import SaleProbabilityScorer, RegionalStatistics
from app.database import get_db

# Инициализация
db = next(get_db())
regional_stats = RegionalStatistics(db)
scorer = SaleProbabilityScorer(regional_stats=regional_stats)

# Вычисление вероятности
result = scorer.calculate_probability(listing, include_details=True)

print(f"Вероятность: {result['probability']}%")
print(f"Категория: {result['category']}")
print(f"Доверительный интервал: {result['confidence_interval']}")
print(f"Важность признаков: {result['feature_importance']}")
```
