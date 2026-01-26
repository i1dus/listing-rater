import re
import json
import time
import random
import hashlib
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Listing, Property, StatusLog
from app.services.property_matcher import PropertyMatcher

logger = logging.getLogger(__name__)
settings = get_settings()


class CianParser:
    """Парсер объявлений недвижимости с Cian.ru"""
    
    CITY_DOMAINS = {
        "moskva": "https://www.cian.ru",
        "spb": "https://spb.cian.ru",
        "sankt-peterburg": "https://spb.cian.ru",
        "ekaterinburg": "https://ekb.cian.ru",
        "novosibirsk": "https://nsk.cian.ru",
        "kazan": "https://kazan.cian.ru",
        "nizhny-novgorod": "https://nn.cian.ru",
        "chelyabinsk": "https://chelyabinsk.cian.ru",
        "samara": "https://samara.cian.ru",
        "rostov-na-donu": "https://rostov.cian.ru",
        "ufa": "https://ufa.cian.ru",
    }
    
    DEAL_TYPES = {
        "sale": "kupit",
        "rent": "snyat",
        "prodam": "kupit",
        "sdam": "snyat",
    }
    
    PROPERTY_TYPES = {
        "kvartiry": "kvartiru",
        "komnaty": "komnatu",
        "doma": "dom",
        "uchastki": "uchastok",
        "kommercheskaya": "kommercheskuyu-nedvizhimost",
    }
    
    CITY_NAMES = {
        "spb": "Санкт-Петербург",
        "sankt-peterburg": "Санкт-Петербург",
        "moskva": "Москва",
        "ekaterinburg": "Екатеринбург",
        "novosibirsk": "Новосибирск",
        "kazan": "Казань",
        "nizhny-novgorod": "Нижний Новгород",
        "chelyabinsk": "Челябинск",
        "samara": "Самара",
        "rostov-na-donu": "Ростов-на-Дону",
        "ufa": "Уфа",
    }
    
    DEAL_TYPE_NAMES = {
        "sale": "Продажа",
        "rent": "Аренда",
        "prodam": "Продажа",
        "sdam": "Аренда",
        "kupit": "Продажа",
        "snyat": "Аренда",
    }
    
    PROPERTY_TYPE_NAMES = {
        "kvartiry": "Квартиры",
        "kvartiru": "Квартиры",
        "komnaty": "Комнаты",
        "komnatu": "Комнаты",
        "doma": "Дома",
        "dom": "Дома",
        "uchastki": "Участки",
        "uchastok": "Участки",
        "kommercheskaya": "Коммерческая недвижимость",
        "kommercheskuyu-nedvizhimost": "Коммерческая недвижимость",
    }
    
    def __init__(self, db: Session):
        self.db = db
        self.property_matcher = PropertyMatcher(db)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        self.client = httpx.Client(headers=self.headers, timeout=30.0, follow_redirects=True)
    
    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()
    
    def build_search_url(
        self,
        city: str = "spb",
        category: str = "kvartiry",
        deal_type: str = "sale",
        page: int = 1,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """Формирует URL для поиска на Cian
        
        Примеры URL:
        - https://spb.cian.ru/kupit-kvartiru/
        - https://spb.cian.ru/kupit-kvartiru/?p=2
        """
        base_domain = self.CITY_DOMAINS.get(city, f"https://{city}.cian.ru")
        deal = self.DEAL_TYPES.get(deal_type, "kupit")
        prop_type = self.PROPERTY_TYPES.get(category, "kvartiru")
        
        url = f"{base_domain}/{deal}-{prop_type}/"
        
        query_params = {}
        if page > 1:
            query_params["p"] = page
        if params:
            query_params.update(params)
        
        if query_params:
            query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
            return f"{url}?{query_string}"
        return url
    
    def parse_search_page(self, url: str) -> List[Dict[str, Any]]:
        """Парсит страницу поиска и возвращает список объявлений"""
        try:
            logger.info(f"Fetching: {url}")
            response = self.client.get(url)
            
            if response.status_code == 429:
                logger.warning(f"Rate limited (429) for {url}")
                return []
            
            response.raise_for_status()
            html = response.text
            
            logger.info(f"Response: {response.status_code}, {len(html)} bytes")
            
            listings = self._extract_listings_from_html(html)
            
            if listings:
                logger.info(f"Found {len(listings)} listings")
            else:
                logger.warning(f"No listings found on {url}")
                
            return listings
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
            return []
    
    def _extract_listings_from_html(self, html: str) -> List[Dict[str, Any]]:
        """Извлекает объявления из HTML страницы Cian"""
        listings = []
        
        # Парсим HTML с BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        
        # Ищем все карточки объявлений по ссылкам на /sale/flat/ или /rent/flat/
        listing_links = soup.find_all('a', href=re.compile(r'/(?:sale|rent)/flat/\d+/'))
        
        # Собираем уникальные ID
        seen_ids = set()
        
        for link in listing_links:
            # Извлекаем ID из URL
            href = link.get('href', '')
            id_match = re.search(r'/(?:sale|rent)/flat/(\d+)/', href)
            if not id_match:
                continue
            
            cian_id = id_match.group(1)
            if cian_id in seen_ids:
                continue
            seen_ids.add(cian_id)
            
            # Ищем родительский контейнер карточки
            # Поднимаемся вверх по DOM чтобы найти контейнер с классом содержащим "container"
            card = link
            for _ in range(10):  # Увеличил до 10 уровней
                parent = card.parent
                if parent and parent.name:
                    # Проверяем есть ли у родителя класс с "container" или "card"
                    parent_class = parent.get('class', [])
                    if any('container' in str(cls).lower() or 'card' in str(cls).lower() 
                           for cls in parent_class):
                        card = parent
                        break
                    card = parent
                else:
                    break
            
            listing = self._extract_listing_from_card(card, cian_id, href)
            if listing:
                listings.append(listing)
            else:
                # Если не нашли в карточке, пробуем из JSON
                json_listing = self._extract_listing_by_id(html, cian_id)
                if json_listing:
                    json_listing['url'] = href if href.startswith('http') else f"https://spb.cian.ru{href}"
                    listings.append(json_listing)
        
        logger.info(f"Extracted {len(listings)} listings from HTML cards")
        
        return listings
    
    def _extract_listing_from_card(self, card, cian_id: str, href: str) -> Optional[Dict[str, Any]]:
        """Извлекает данные из HTML карточки объявления"""
        try:
            listing = {
                'cian_id': int(cian_id),
                'url': href if href.startswith('http') else f"https://spb.cian.ru{href}"
            }
            
            # Определяем тип сделки из URL
            if '/sale/' in href:
                listing['deal_type'] = 'sale'
            elif '/rent/' in href:
                listing['deal_type'] = 'rent'
            
            # Получаем весь текст карточки для поиска паттернов
            card_text = card.get_text(' ', strip=True)
            
            # Цена - ищем паттерн с рублями в любом месте карточки
            price_match = re.search(r'(\d[\d\s]*\d)\s*₽', card_text.replace('\xa0', ' ').replace('&nbsp;', ' '))
            if price_match:
                price_str = price_match.group(1).replace(' ', '').replace('\xa0', '')
                try:
                    listing['price'] = int(price_str)
                except ValueError:
                    pass
            
            # Ищем ссылку с описанием - она содержит "комн", "м²", "этаж"
            desc_links = card.find_all('a', href=True)
            desc_text = ''
            for link in desc_links:
                link_text = link.get_text(' ', strip=True)
                if 'комн' in link_text or 'м²' in link_text or 'этаж' in link_text:
                    desc_text = link_text
                    break
            
            # Если не нашли в ссылке, ищем в любом тексте карточки
            if not desc_text:
                # Ищем паттерн типа "2-комн. кв. · 77,50 м² · 4/15 этаж"
                desc_match = re.search(r'(\d+-комн[^·]*·[^·]*м²[^·]*·[^·]*этаж)', card_text)
                if desc_match:
                    desc_text = desc_match.group(1)
            
            # Парсим описание
            if desc_text:
                # Комнаты
                rooms_match = re.search(r'(\d+)-комн', desc_text)
                if rooms_match:
                    listing['rooms'] = int(rooms_match.group(1))
                elif 'Студия' in desc_text or 'студия' in desc_text:
                    listing['rooms'] = 0
                
                # Площадь - ищем число перед м² (может быть с запятой или точкой)
                area_match = re.search(r'(\d+[,.]?\d*)\s*м²', desc_text.replace(',', '.'))
                if area_match:
                    area_str = area_match.group(1).replace(',', '.')
                    try:
                        area = float(area_str)
                        if 10 <= area <= 500:  # Реалистичные значения
                            listing['area_total'] = area
                    except ValueError:
                        pass
                
                # Этаж / этажность
                floor_match = re.search(r'(\d+)/(\d+)\s*этаж', desc_text)
                if floor_match:
                    listing['floor'] = int(floor_match.group(1))
                    listing['floors_total'] = int(floor_match.group(2))
            
            # Метро - ищем элемент с data-name="Underground"
            metro_elem = card.find(attrs={'data-name': 'Underground'})
            if metro_elem:
                metro_text = metro_elem.get_text(' ', strip=True)
                
                # Название станции - ищем span с классом содержащим "name"
                name_spans = metro_elem.find_all('span')
                metro_name = None
                for span in name_spans:
                    span_text = span.get_text(strip=True)
                    # Название метро обычно короткое, без цифр в начале, и не пустое
                    if span_text and len(span_text) < 50 and not re.match(r'^\d+', span_text) and span_text != '6':
                        # Проверяем что это не время (цифра)
                        if not span_text.isdigit():
                            metro_name = span_text
                            break
                
                # Если не нашли в span, ищем в тексте элемента
                if not metro_name:
                    # Ищем текст который выглядит как название станции (заглавные буквы, русские)
                    metro_match = re.search(r'([А-ЯЁ][А-Яа-яЁё\s\-]+)', metro_text)
                    if metro_match:
                        metro_name = metro_match.group(1).strip()
                        # Убираем время если попало
                        metro_name = re.sub(r'\s+\d+\s*$', '', metro_name)
                
                if metro_name and self._is_valid_metro_name(metro_name):
                    listing['metro'] = metro_name
                
                # Время до метро - ищем в GeoTravelTime
                time_elem = metro_elem.find(attrs={'data-name': 'GeoTravelTime'})
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    time_match = re.search(r'(\d+)', time_text)
                    if time_match:
                        listing['metro_time'] = int(time_match.group(1))
                    
                    # Тип (пешком/транспорт) - по data-name внутри
                    if time_elem.find(attrs={'data-name': 'walk'}):
                        listing['metro_transport'] = 'walk'
                    elif time_elem.find(attrs={'data-name': re.compile(r'transport|bus')}):
                        listing['metro_transport'] = 'transport'
                else:
                    # Если нет GeoTravelTime, ищем время в тексте metro_elem
                    time_match = re.search(r'(\d+)\s*(?:мин|мин\.|минут)', metro_text, re.IGNORECASE)
                    if time_match:
                        listing['metro_time'] = int(time_match.group(1))
                        # Определяем тип по иконке или тексту
                        if 'walk' in str(metro_elem) or 'пешком' in metro_text.lower():
                            listing['metro_transport'] = 'walk'
                        elif 'transport' in str(metro_elem) or 'автобус' in metro_text.lower() or 'bus' in str(metro_elem):
                            listing['metro_transport'] = 'transport'
            
            # Fallback: ищем метро по тексту в карточке (если не нашли через data-name)
            if not listing.get('metro'):
                # Ищем паттерн типа "метро Название" или просто название станции (заглавные буквы)
                metro_patterns = [
                    r'метро\s+([А-ЯЁ][А-Яа-яЁё\s\-]+)',
                    r'([А-ЯЁ][А-Яа-яЁё\s\-]+)\s+метро',
                    r'([А-ЯЁ][А-Яа-яЁё]{3,20})\s+\d+\s*мин',  # Название + время
                ]
                for pattern in metro_patterns:
                    metro_match = re.search(pattern, card_text, re.IGNORECASE)
                    if metro_match:
                        metro_name = metro_match.group(1).strip()
                        # Фильтруем - название должно быть валидным
                        if self._is_valid_metro_name(metro_name):
                            listing['metro'] = metro_name
                            # Пытаемся найти время рядом
                            time_match = re.search(r'(\d+)\s*(?:мин|мин\.)', card_text[metro_match.end():metro_match.end()+50])
                            if time_match:
                                listing['metro_time'] = int(time_match.group(1))
                            break
            
            # Адрес - ищем span с классом содержащим "address"
            # Обычно это короткий текст после метро
            address_spans = card.find_all('span')
            for span in address_spans:
                span_class = span.get('class', [])
                if any('address' in str(cls).lower() for cls in span_class):
                    addr_text = span.get_text(strip=True)
                    # Адрес должен быть коротким и содержать улицу/проспект
                    if len(addr_text) < 200 and (addr_text and not addr_text.startswith('Квартиры')):
                        listing['address'] = addr_text
                        break
            
            # Логируем что нашли для отладки
            if listing.get('price'):
                logger.debug(f"Listing {cian_id}: price={listing.get('price')}, rooms={listing.get('rooms')}, "
                           f"area={listing.get('area_total')}, floor={listing.get('floor')}/{listing.get('floors_total')}, "
                           f"metro={listing.get('metro')}, metro_time={listing.get('metro_time')}, address={listing.get('address')}")
            
            # Дополнительное логирование если метро не найдено но должно быть
            if not listing.get('metro') and listing.get('price'):
                # Проверяем есть ли упоминание метро в тексте карточки
                if 'метро' in card_text.lower() or 'подземн' in card_text.lower():
                    logger.debug(f"Metro mentioned but not extracted for listing {cian_id}. Card text snippet: {card_text[:200]}")
            
            # Валидация - нужна хотя бы цена или площадь
            if listing.get('price') or listing.get('area_total'):
                return listing
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting card {cian_id}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _extract_from_json(self, html: str) -> List[Dict[str, Any]]:
        """Fallback: извлекает данные из JSON в HTML"""
        listings = []
        
        cian_ids = re.findall(r'"cianId":(\d+)', html)
        unique_ids = list(dict.fromkeys(cian_ids))
        
        logger.info(f"Fallback: found {len(unique_ids)} cianIds in JSON")
        
        for cian_id in unique_ids:
            listing = self._extract_listing_by_id(html, cian_id)
            if listing:
                listings.append(listing)
        
        return listings
    
    def _parse_product(self, product: Dict) -> Optional[Dict[str, Any]]:
        """Парсит объект product из JSON"""
        try:
            cian_id = product.get('cianId') or product.get('id')
            if not cian_id:
                return None
            
            return {
                'cian_id': int(cian_id),
                'price': product.get('price'),
                'deal_type': product.get('dealType'),
                'object_type': product.get('objectType'),
                'photos_count': product.get('photosCount', 0),
                'published': product.get('published', True),
            }
        except Exception as e:
            logger.debug(f"Error parsing product: {e}")
            return None
    
    def _extract_listing_by_id(self, html: str, cian_id: str) -> Optional[Dict[str, Any]]:
        """Извлекает данные объявления по его ID из HTML (JSON fallback)"""
        try:
            listing = {'cian_id': int(cian_id)}
            
            # Ищем более широкий контекст - до 2000 символов после cianId
            pattern = rf'"cianId":{cian_id}(.{{0,2000}})'
            match = re.search(pattern, html, re.DOTALL)
            
            if match:
                context = match.group(1)
                
                # Извлекаем цену
                price_match = re.search(r'"price":(\d+)', context)
                if price_match:
                    listing['price'] = int(price_match.group(1))
                
                # Извлекаем тип объекта
                obj_type_match = re.search(r'"objectType":"([^"]+)"', context)
                if obj_type_match:
                    listing['object_type'] = obj_type_match.group(1)
                
                # Извлекаем тип сделки
                deal_match = re.search(r'"dealType":"([^"]+)"', context)
                if deal_match:
                    listing['deal_type'] = deal_match.group(1)
                
                # Комнаты
                rooms_match = re.search(r'"roomsCount":(\d+)', context)
                if rooms_match:
                    listing['rooms'] = int(rooms_match.group(1))
                
                # Этаж
                floor_match = re.search(r'"floorNumber":(\d+)', context)
                if floor_match:
                    listing['floor'] = int(floor_match.group(1))
                
                # Этажность
                floors_match = re.search(r'"floorsCount":(\d+)', context)
                if floors_match:
                    listing['floors_total'] = int(floors_match.group(1))
                
                # Площадь (может быть totalArea, livingArea, или area)
                area_match = re.search(r'"(?:totalArea|area|livingArea)":([0-9.]+)', context)
                if area_match:
                    try:
                        area = float(area_match.group(1))
                        if 10 <= area <= 500:
                            listing['area_total'] = area
                    except ValueError:
                        pass
            
            # Строим URL объявления
            if not listing.get('url'):
                deal_type = listing.get('deal_type', 'sale')
                listing['url'] = f"https://www.cian.ru/{deal_type}/flat/{cian_id}/"
            
            return listing if listing.get('price') or listing.get('rooms') else None
            
        except Exception as e:
            logger.debug(f"Error extracting listing {cian_id}: {e}")
            return None
    
    def _is_valid_metro_name(self, name: str) -> bool:
        """Проверяет что название метро валидное"""
        if not name or len(name) < 2:
            return False
        
        # Список невалидных значений
        invalid_patterns = [
            'минут', 'минуты', 'минута', 'мин', 'мин.',
            'рядом', 'до', 'от', 'пешком', 'на', 'транспорт',
            'автобус', 'bus', 'walk', 'transport',
            'метро', 'подземн', 'станция', 'станции',
            'и', 'или', 'к', 'от', 'до',
        ]
        
        name_lower = name.lower().strip()
        
        # Проверяем что это не одно из невалидных слов
        if name_lower in invalid_patterns:
            return False
        
        # Проверяем что название не начинается с невалидных слов
        for pattern in invalid_patterns:
            if name_lower.startswith(pattern + ' ') or name_lower.startswith(pattern + ','):
                return False
        
        # Проверяем что название содержит хотя бы одну русскую букву
        if not re.search(r'[А-Яа-яЁё]', name):
            return False
        
        # Проверяем что название не состоит только из цифр и знаков
        if re.match(r'^[\d\s\-\.,]+$', name):
            return False
        
        # Проверяем длину (названия станций обычно 3-30 символов)
        if len(name.strip()) < 3 or len(name.strip()) > 30:
            return False
        
        return True
    
    def _get_random_delay(self) -> float:
        """Возвращает случайную задержку"""
        base = settings.request_delay
        random_part = random.uniform(0, getattr(settings, 'request_delay_random', 2.0))
        return base + random_part
    
    def parse_listing_details(self, url: str) -> Optional[Dict[str, Any]]:
        """Парсит детальную страницу объявления и извлекает все данные"""
        try:
            logger.info(f"Parsing listing details from: {url}")
            response = self.client.get(url)
            
            if response.status_code == 429:
                logger.warning(f"Rate limited (429) for {url}")
                return None
            
            response.raise_for_status()
            html = response.text
            
            soup = BeautifulSoup(html, 'lxml')
            listing_data = {}
            
            # Извлекаем ID из URL
            id_match = re.search(r'/(?:sale|rent)/flat/(\d+)/', url)
            if id_match:
                listing_data['cian_id'] = int(id_match.group(1))
            
            # Ищем JSON данные в HTML (initialState или другие JSON структуры)
            # Cian часто хранит данные в скриптах
            scripts = soup.find_all('script', type='application/json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    # Рекурсивно ищем данные объявления
                    self._extract_from_json_data(data, listing_data)
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            # Также ищем в тексте скриптов
            all_scripts = soup.find_all('script')
            for script in all_scripts:
                if script.string:
                    # Ищем паттерны типа "cianId":123
                    cian_id_match = re.search(r'"cianId":(\d+)', script.string)
                    if cian_id_match:
                        # Ищем данные вокруг этого ID
                        context = script.string
                        self._extract_listing_data_from_text(context, listing_data)
            
            # Парсим HTML элементы
            # Цена
            price_elem = soup.find(string=re.compile(r'\d+.*₽'))
            if price_elem:
                price_text = price_elem.strip()
                price_match = re.search(r'(\d[\d\s]*\d)\s*₽', price_text.replace('\xa0', ' '))
                if price_match:
                    price_str = price_match.group(1).replace(' ', '')
                    listing_data['price'] = int(price_str)
            
            # Заголовок
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                listing_data['title'] = title_elem.get_text(strip=True)
            
            # Описание
            desc_elem = soup.find('div', class_=re.compile(r'description')) or soup.find('p', class_=re.compile(r'description'))
            if desc_elem:
                listing_data['description'] = desc_elem.get_text(strip=True)
            
            # Характеристики из таблицы или списка
            # Ищем элементы с характеристиками
            features = soup.find_all(['div', 'span', 'p'], string=re.compile(r'(комнат|м²|этаж|год|ремонт)'))
            for feature in features:
                text = feature.get_text(strip=True)
                
                # Комнаты
                if 'комнат' in text.lower():
                    rooms_match = re.search(r'(\d+)\s*комнат', text, re.IGNORECASE)
                    if rooms_match:
                        listing_data['rooms'] = int(rooms_match.group(1))
                
                # Площадь
                if 'м²' in text or 'м2' in text:
                    area_match = re.search(r'(\d+[,.]?\d*)\s*м[²2]', text)
                    if area_match:
                        area_str = area_match.group(1).replace(',', '.')
                        try:
                            area = float(area_str)
                            if 'общая' in text.lower() or 'total' in text.lower():
                                listing_data['area_total'] = area
                            elif 'жилая' in text.lower() or 'living' in text.lower():
                                listing_data['area_living'] = area
                            elif 'кухн' in text.lower() or 'kitchen' in text.lower():
                                listing_data['area_kitchen'] = area
                            elif not listing_data.get('area_total'):
                                listing_data['area_total'] = area
                        except ValueError:
                            pass
                
                # Этаж
                if 'этаж' in text.lower():
                    floor_match = re.search(r'(\d+)/(\d+)', text)
                    if floor_match:
                        listing_data['floor'] = int(floor_match.group(1))
                        listing_data['floors_total'] = int(floor_match.group(2))
            
            # Адрес
            address_elem = soup.find(['div', 'span'], class_=re.compile(r'address')) or soup.find('meta', property='og:street-address')
            if address_elem:
                addr_text = address_elem.get('content') or address_elem.get_text(strip=True)
                if addr_text and len(addr_text) < 500:
                    listing_data['address'] = addr_text
            
            # Метро
            metro_elem = soup.find(string=re.compile(r'метро|подземн'))
            if metro_elem:
                parent = metro_elem.parent
                metro_text = parent.get_text(strip=True) if parent else metro_elem.strip()
                metro_match = re.search(r'([А-Яа-яЁё\s\-]+)', metro_text)
                if metro_match:
                    listing_data['metro'] = metro_match.group(1).strip()
            
            logger.info(f"Extracted data for listing {listing_data.get('cian_id')}: {list(listing_data.keys())}")
            return listing_data if listing_data.get('cian_id') else None
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error parsing {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing listing details {url}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _extract_from_json_data(self, data: Any, listing_data: Dict[str, Any], path: str = ""):
        """Рекурсивно извлекает данные из JSON структуры"""
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                
                # Ищем известные поля
                if key in ['cianId', 'id'] and isinstance(value, (int, str)):
                    listing_data['cian_id'] = int(value)
                elif key == 'price' and isinstance(value, (int, float)):
                    listing_data['price'] = int(value)
                elif key == 'roomsCount' and isinstance(value, int):
                    listing_data['rooms'] = value
                elif key == 'floorNumber' and isinstance(value, int):
                    listing_data['floor'] = value
                elif key == 'floorsCount' and isinstance(value, int):
                    listing_data['floors_total'] = value
                elif key in ['totalArea', 'area', 'livingArea'] and isinstance(value, (int, float)):
                    if not listing_data.get('area_total') or key == 'totalArea':
                        listing_data['area_total'] = float(value)
                elif key == 'kitchenArea' and isinstance(value, (int, float)):
                    listing_data['area_kitchen'] = float(value)
                elif key == 'address' and isinstance(value, str):
                    listing_data['address'] = value
                elif key == 'description' and isinstance(value, str):
                    listing_data['description'] = value
                elif key == 'title' and isinstance(value, str):
                    listing_data['title'] = value
                
                # Рекурсивно обрабатываем вложенные структуры
                if isinstance(value, (dict, list)):
                    self._extract_from_json_data(value, listing_data, new_path)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._extract_from_json_data(item, listing_data, f"{path}[{i}]")
    
    def _extract_listing_data_from_text(self, text: str, listing_data: Dict[str, Any]):
        """Извлекает данные из текста (JSON строки в скриптах)"""
        # Цена
        if not listing_data.get('price'):
            price_match = re.search(r'"price":(\d+)', text)
            if price_match:
                listing_data['price'] = int(price_match.group(1))
        
        # Комнаты
        if not listing_data.get('rooms'):
            rooms_match = re.search(r'"roomsCount":(\d+)', text)
            if rooms_match:
                listing_data['rooms'] = int(rooms_match.group(1))
        
        # Этаж
        if not listing_data.get('floor'):
            floor_match = re.search(r'"floorNumber":(\d+)', text)
            if floor_match:
                listing_data['floor'] = int(floor_match.group(1))
        
        # Этажность
        if not listing_data.get('floors_total'):
            floors_match = re.search(r'"floorsCount":(\d+)', text)
            if floors_match:
                listing_data['floors_total'] = int(floors_match.group(1))
        
        # Площадь
        if not listing_data.get('area_total'):
            area_match = re.search(r'"(?:totalArea|area)":([0-9.]+)', text)
            if area_match:
                try:
                    listing_data['area_total'] = float(area_match.group(1))
                except ValueError:
                    pass
    
    def save_listing(self, listing_data: Dict[str, Any]) -> Optional[Listing]:
        """Сохраняет объявление в базу данных"""
        try:
            cian_id = listing_data.get('cian_id')
            if not cian_id:
                return None
            
            # Генерируем заголовок из данных
            title = self._generate_title(listing_data)
            
            # Ищем существующее объявление
            existing = self.db.query(Listing).filter(
                Listing.avito_id == cian_id  # Используем avito_id для совместимости
            ).first()
            
            if existing:
                # Обновляем существующее
                existing.price = listing_data.get('price', existing.price)
                existing.rooms = listing_data.get('rooms', existing.rooms)
                existing.floor = listing_data.get('floor', existing.floor)
                existing.floors_total = listing_data.get('floors_total', existing.floors_total)
                existing.area_total = listing_data.get('area_total', existing.area_total)
                
                # Адрес - только если короткий (реальный адрес)
                new_address = listing_data.get('address')
                if new_address and len(new_address) < 200:
                    existing.address = new_address
                
                # Метро - обновляем только если есть валидное значение
                if 'metro' in listing_data:
                    metro_value = listing_data.get('metro')
                    if metro_value and self._is_valid_metro_name(metro_value):
                        existing.metro = metro_value
                    elif metro_value is None:
                        # Если явно None, не трогаем существующее значение
                        pass
                
                if 'metro_time' in listing_data:
                    existing.metro_time = listing_data.get('metro_time')
                if 'metro_transport' in listing_data:
                    existing.metro_transport = listing_data.get('metro_transport')
                
                # Title - ограничиваем длину
                if title:
                    existing.title = title[:490] if len(title) > 490 else title
                
                existing.parsed_at = datetime.utcnow()
                self.db.commit()
                return existing
            else:
                # Подготавливаем данные с ограничением длины
                address = listing_data.get('address')
                if address and len(address) > 200:
                    address = None  # Скорее всего это не адрес
                
                safe_title = title[:490] if title and len(title) > 490 else title
                
                # Валидируем метро перед сохранением
                metro_value = listing_data.get('metro')
                if metro_value and not self._is_valid_metro_name(metro_value):
                    metro_value = None
                
                # Создаём новое
                listing = Listing(
                    avito_id=cian_id,
                    url=listing_data.get('url', ''),
                    title=safe_title,
                    price=listing_data.get('price'),
                    address=address,
                    rooms=listing_data.get('rooms'),
                    area_total=listing_data.get('area_total'),
                    floor=listing_data.get('floor'),
                    floors_total=listing_data.get('floors_total'),
                    metro=metro_value,
                    metro_time=listing_data.get('metro_time'),
                    metro_transport=listing_data.get('metro_transport'),
                    description=listing_data.get('description'),
                    city=listing_data.get('city'),
                    deal_type=listing_data.get('deal_type'),
                    property_type=listing_data.get('property_type'),
                    is_active=True,
                    parsed_at=datetime.utcnow(),
                )
                
                self.db.add(listing)
                self.db.commit()
                self.db.refresh(listing)
                
                # Пытаемся сопоставить с недвижимостью
                property_obj = self.property_matcher.find_or_create_property(listing)
                if property_obj:
                    listing.property_id = property_obj.id
                    self.db.commit()
                
                return listing
                
        except Exception as e:
            logger.error(f"Error saving listing {listing_data.get('cian_id')}: {e}")
            self.db.rollback()
            return None
    
    def _generate_title(self, listing_data: Dict[str, Any]) -> str:
        """Генерирует заголовок из данных объявления"""
        parts = []
        
        rooms = listing_data.get('rooms')
        if rooms == 0:
            parts.append("Студия")
        elif rooms:
            parts.append(f"{rooms}-комн. кв.")
        
        area = listing_data.get('area_total')
        if area:
            parts.append(f"{area} м²")
        
        floor = listing_data.get('floor')
        floors_total = listing_data.get('floors_total')
        if floor and floors_total:
            parts.append(f"{floor}/{floors_total} эт.")
        elif floor:
            parts.append(f"{floor} эт.")
        
        if parts:
            return ", ".join(parts)
        
        return f"Квартира {listing_data.get('cian_id', '')}"
    
    def run_parsing(
        self,
        city: str = "spb",
        category: str = "kvartiry",
        deal_type: str = "sale",
        max_pages: int = 1,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Запускает парсинг с заданными параметрами"""
        results = {
            "total_found": 0,
            "new_listings": 0,
            "updated_listings": 0,
            "errors": 0,
            "pages_parsed": 0,
            "rate_limited": False
        }
        
        for page in range(1, max_pages + 1):
            # Задержка перед запросом (кроме первой страницы)
            if page > 1:
                delay = self._get_random_delay()
                logger.info(f"Waiting {delay:.1f}s before page {page}...")
                time.sleep(delay)
            
            logger.info(f"Parsing page {page}...")
            
            url = self.build_search_url(city, category, deal_type, page, filters)
            listings = self.parse_search_page(url)
            
            if not listings:
                logger.warning(f"No listings found on page {page}")
                results["rate_limited"] = True
                break
            
            results["total_found"] += len(listings)
            results["pages_parsed"] = page
            
            for listing_data in listings:
                # Добавляем метаданные
                # Преобразуем slug города в полное название
                listing_data['city'] = self.CITY_NAMES.get(city, city)
                # Преобразуем тип сделки в русское название
                listing_data['deal_type'] = self.DEAL_TYPE_NAMES.get(deal_type, deal_type)
                # Преобразуем тип недвижимости в русское название
                listing_data['property_type'] = self.PROPERTY_TYPE_NAMES.get(category, category)
                
                # Проверяем существует ли
                existing = self.db.query(Listing).filter(
                    Listing.avito_id == listing_data.get('cian_id')
                ).first()
                
                saved = self.save_listing(listing_data)
                
                if saved:
                    if existing:
                        results["updated_listings"] += 1
                    else:
                        results["new_listings"] += 1
                else:
                    results["errors"] += 1
        
        logger.info(f"Parsing completed: {results}")
        return results
