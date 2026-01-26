import hashlib
import re
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Property, Listing

logger = logging.getLogger(__name__)


class PropertyMatcher:
    """
    Сервис для сопоставления объявлений с объектами недвижимости.
    Использует простой подход: хеширование ключевых характеристик.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
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
                parts['house_number'] = house_match.group(1).strip()
                address = address[:house_match.start()].strip()
            
            parts['street'] = self._normalize_address(address)
        
        return parts
    
    def generate_property_hash(self, listing: Listing) -> str:
        """
        Генерирует уникальный хеш для объекта недвижимости.
        Хеш основан на: город + улица + номер дома + этаж + площадь + комнаты
        """
        address_parts = self._extract_address_parts(listing)
        
        hash_parts = [
            address_parts.get('city', ''),
            address_parts.get('street', ''),
            address_parts.get('house_number', ''),
            str(listing.floor or ''),
            str(round(listing.area_total, 1) if listing.area_total else ''),
            str(listing.rooms if listing.rooms is not None else ''),
        ]
        
        hash_string = '|'.join(hash_parts).lower()
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def find_or_create_property(self, listing: Listing) -> Optional[Property]:
        """
        Находит существующий или создает новый объект недвижимости для объявления.
        """
        if not listing.address and not (listing.city and listing.area_total):
            logger.debug(f"Not enough data to match property for listing {listing.avito_id}")
            return None
        
        property_hash = self.generate_property_hash(listing)
        
        existing_property = self.db.query(Property).filter(
            Property.property_hash == property_hash
        ).first()
        
        if existing_property:
            logger.debug(f"Found existing property {existing_property.id} for listing {listing.avito_id}")
            return existing_property
        
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
            property_hash=property_hash
        )
        
        self.db.add(new_property)
        self.db.flush()
        
        logger.debug(f"Created new property {new_property.id} for listing {listing.avito_id}")
        return new_property
    
    def rematch_all_listings(self) -> dict:
        """
        Пересопоставляет все объявления с объектами недвижимости.
        Полезно после изменения логики хеширования.
        """
        results = {
            'processed': 0,
            'matched': 0,
            'created': 0,
            'failed': 0
        }
        
        listings = self.db.query(Listing).all()
        
        for listing in listings:
            results['processed'] += 1
            
            try:
                property_obj = self.find_or_create_property(listing)
                
                if property_obj:
                    old_property_id = listing.property_id
                    listing.property_id = property_obj.id
                    
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
