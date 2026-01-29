import re
import logging
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.config import get_settings
from app.models import Property, Listing, MatchConfig

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class MatchResult:
    """Результат сопоставления объявления с объектом недвижимости"""
    property: Property
    similarity_score: float  # Процент сходства (0-100)
    matched_attributes: Dict[str, Tuple[bool, float]]  # Атрибут -> (совпадает, вес)
    strict_violations: List[str]  # Список нарушенных строгих атрибутов


class PropertyMatcher:
    """
    Сервис для сопоставления объявлений с объектами недвижимости.
    Использует модель сходства с весами атрибутов.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._load_config()
    
    def _load_config(self):
        """Загружает конфигурацию метчинга из БД или использует дефолтные значения из config"""
        # Пытаемся загрузить активную конфигурацию из БД
        config = self.db.query(MatchConfig).filter(MatchConfig.is_active == True).first()
        
        if config:
            self.weights = config.weights
            self.strict_attrs = config.strict_attributes
            self.threshold = float(config.threshold)
        else:
            # Используем дефолтные значения из config
            self.weights = settings.property_match_weights
            self.strict_attrs = settings.property_match_strict_attributes
            self.threshold = settings.property_match_threshold
    
    def _normalize_address(self, address: str) -> str:
        """Нормализует адрес для сравнения"""
        if not address:
            return ""
        
        normalized = address.lower()
        
        replacements = [
            (r'\bул\.?\s*', ''),
            (r'\bулица\s*', ''),
            (r'\bпр\.?\s*', ''),
            (r'\bпроспект\s*', ''),
            (r'\bпер\.?\s*', ''),
            (r'\bпереулок\s*', ''),
            (r'\bд\.?\s*', ''),
            (r'\bдом\s*', ''),
            (r'\bкв\.?\s*', ''),
            (r'\bквартира\s*', ''),
            (r'\bкорп\.?\s*', 'к'),
            (r'\bкорпус\s*', 'к'),
            (r'\bстр\.?\s*', 'с'),
            (r'\bстроение\s*', 'с'),
            (r'\s+', ' '),
        ]
        
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized)
        
        return normalized.strip()
    
    def _extract_address_parts(self, listing: Listing) -> dict:
        """Извлекает компоненты адреса из объявления"""
        parts = {
            'city': '',
            'district': '',
            'street': '',
            'house_number': ''
        }
        
        if listing.city:
            parts['city'] = listing.city.lower().strip()
        
        if listing.district:
            parts['district'] = listing.district.lower().strip()
        
        if listing.address:
            address = listing.address
            
            house_match = re.search(r'[,\s]+(\d+[а-яА-Яa-zA-Z]?(?:/\d+)?(?:\s*к\s*\d+)?(?:\s*с\s*\d+)?)\s*$', address)
            if house_match:
                parts['house_number'] = house_match.group(1).strip().lower()
                address = address[:house_match.start()].strip()
            
            parts['street'] = self._normalize_address(address)
        
        return parts
    
    def _compare_values(self, val1, val2, attr_name: str) -> Tuple[bool, float]:
        """
        Сравнивает два значения и возвращает (совпадает, процент совпадения).
        Для числовых значений допускается небольшая погрешность.
        """
        if val1 is None and val2 is None:
            return (True, 1.0)
        
        if val1 is None or val2 is None:
            return (False, 0.0)
        
        # Строковые значения
        if isinstance(val1, str) and isinstance(val2, str):
            v1 = val1.lower().strip()
            v2 = val2.lower().strip()
            if v1 == v2:
                return (True, 1.0)
            # Частичное совпадение для адресов
            if attr_name in ['street', 'house_number']:
                if v1 in v2 or v2 in v1:
                    return (True, 0.8)
            return (False, 0.0)
        
        # Числовые значения
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            if attr_name == 'area_total' or attr_name == 'area_living' or attr_name == 'area_kitchen':
                # Для площади допускаем погрешность 2 м²
                diff = abs(val1 - val2)
                if diff <= 2.0:
                    return (True, 1.0)
                elif diff <= 5.0:
                    return (True, 0.7)
                else:
                    return (False, 0.0)
            elif attr_name == 'floor':
                # Для этажа допускаем погрешность 1 этаж (на случай ошибок)
                if abs(val1 - val2) <= 1:
                    return (True, 1.0)
                return (False, 0.0)
            else:
                # Для остальных числовых (rooms и т.д.) - строгое равенство
                return (val1 == val2, 1.0 if val1 == val2 else 0.0)
        
        return (val1 == val2, 1.0 if val1 == val2 else 0.0)
    
    def _calculate_similarity(self, listing: Listing, property: Property) -> MatchResult:
        """
        Вычисляет сходство между объявлением и объектом недвижимости.
        Возвращает MatchResult с процентом сходства и деталями.
        """
        address_parts = self._extract_address_parts(listing)
        
        # Словарь для хранения результатов сравнения атрибутов
        matched_attrs = {}
        strict_violations = []
        total_weight = 0.0
        matched_weight = 0.0
        
        # Сравниваем каждый атрибут
        attributes_map = {
            'city': (address_parts.get('city') or listing.city, property.city),
            'street': (address_parts.get('street'), property.street),
            'house_number': (address_parts.get('house_number'), property.house_number),
            'rooms': (listing.rooms, property.rooms),
            'area_total': (listing.area_total, property.area_total),
            'floor': (listing.floor, property.floor),
            'property_type': (listing.property_type, property.property_type),
            'district': (address_parts.get('district') or listing.district, property.district),
            'area_living': (listing.area_living, property.area_living),
            'area_kitchen': (listing.area_kitchen, property.area_kitchen),
        }
        
        for attr_name, (listing_val, property_val) in attributes_map.items():
            if attr_name not in self.weights:
                continue
            
            weight = self.weights[attr_name]
            is_strict = attr_name in self.strict_attrs
            
            # Если оба значения None, пропускаем (не учитываем в весе)
            if listing_val is None and property_val is None:
                continue
            
            # Если одно из значений None, но атрибут строгий - это нарушение
            if is_strict and (listing_val is None or property_val is None):
                strict_violations.append(attr_name)
                matched_attrs[attr_name] = (False, 0.0)
                continue
            
            total_weight += weight
            
            matches, similarity = self._compare_values(listing_val, property_val, attr_name)
            matched_attrs[attr_name] = (matches, similarity)
            
            if matches:
                matched_weight += weight * similarity
            elif is_strict:
                # Строгий атрибут не совпал - это нарушение
                strict_violations.append(attr_name)
        
        # Если есть нарушения строгих атрибутов, сходство = 0
        if strict_violations:
            similarity_score = 0.0
        elif total_weight == 0:
            # Нет данных для сравнения
            similarity_score = 0.0
        else:
            similarity_score = (matched_weight / total_weight) * 100.0
        
        return MatchResult(
            property=property,
            similarity_score=similarity_score,
            matched_attributes=matched_attrs,
            strict_violations=strict_violations
        )
    
    def find_best_match(self, listing: Listing) -> Optional[MatchResult]:
        """
        Находит лучший подходящий объект недвижимости для объявления.
        Возвращает MatchResult с наибольшим процентом сходства или None.
        """
        if not listing.address and not (listing.city and listing.area_total):
            logger.debug(f"Not enough data to match property for listing {listing.avito_id}")
            return None
        
        address_parts = self._extract_address_parts(listing)
        
        # Строим базовый запрос для поиска потенциальных совпадений
        query = self.db.query(Property)
        
        # Фильтруем по городу (если есть)
        if address_parts.get('city') or listing.city:
            city = (address_parts.get('city') or listing.city).lower()
            query = query.filter(Property.city.ilike(f"%{city}%"))
        
        # Фильтруем по типу недвижимости (если есть)
        if listing.property_type:
            query = query.filter(Property.property_type == listing.property_type)
        
        # Получаем все потенциальные совпадения
        candidates = query.all()
        
        if not candidates:
            logger.debug(f"No property candidates found for listing {listing.avito_id}")
            return None
        
        # Вычисляем сходство для каждого кандидата
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            match_result = self._calculate_similarity(listing, candidate)
            
            if match_result.similarity_score > best_score:
                best_score = match_result.similarity_score
                best_match = match_result
        
        # Проверяем, превышает ли сходство порог
        if best_match and best_match.similarity_score >= self.threshold:
            logger.debug(
                f"Found matching property {best_match.property.id} for listing {listing.avito_id} "
                f"with similarity {best_match.similarity_score:.2f}%"
            )
            return best_match
        
        logger.debug(
            f"No property match found for listing {listing.avito_id} "
            f"(best score: {best_score:.2f}%, threshold: {self.threshold}%)"
        )
        return None
    
    def find_or_create_property(self, listing: Listing, save_match_score: bool = True) -> Optional[Property]:
        """
        Находит существующий или создает новый объект недвижимости для объявления.
        Сохраняет процент сходства в listing.match_score.
        Возвращает Property или None.
        """
        # Ищем лучшее совпадение
        match_result = self.find_best_match(listing)
        
        if match_result:
            # Нашли подходящий объект
            if save_match_score:
                listing.match_score = match_result.similarity_score
            return match_result.property
        
        # Не нашли подходящий объект - создаем новый
        address_parts = self._extract_address_parts(listing)
        
        new_property = Property(
            city=address_parts.get('city') or listing.city,
            district=address_parts.get('district') or listing.district,
            street=address_parts.get('street'),
            house_number=address_parts.get('house_number'),
            property_type=listing.property_type,
            rooms=listing.rooms,
            floor=listing.floor,
            floors_total=listing.floors_total,
            area_total=listing.area_total,
            area_living=listing.area_living,
            area_kitchen=listing.area_kitchen,
            property_hash=None  # Больше не используем хэш
        )
        
        self.db.add(new_property)
        self.db.flush()
        
        if save_match_score:
            listing.match_score = 100.0  # Новый объект = 100% сходство
        
        logger.debug(f"Created new property {new_property.id} for listing {listing.avito_id}")
        return new_property
    
    def rematch_all_listings(self) -> dict:
        """
        Пересопоставляет все объявления с объектами недвижимости.
        Полезно после изменения логики метчинга.
        """
        results = {
            'processed': 0,
            'matched': 0,
            'created': 0,
            'failed': 0,
            'low_similarity': 0  # Совпадения с низким процентом сходства
        }
        
        listings = self.db.query(Listing).all()
        
        for listing in listings:
            results['processed'] += 1
            
            try:
                property_obj = self.find_or_create_property(listing, save_match_score=True)
                
                if property_obj:
                    old_property_id = listing.property_id
                    listing.property_id = property_obj.id
                    
                    # Проверяем процент сходства
                    if listing.match_score and listing.match_score < self.threshold:
                        results['low_similarity'] += 1
                    
                    if old_property_id == property_obj.id:
                        results['matched'] += 1
                    else:
                        results['created'] += 1
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error rematching listing {listing.id}: {e}")
                results['failed'] += 1
        
        self.db.commit()
        return results
