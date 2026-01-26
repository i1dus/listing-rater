import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.parser import ParserConfig, ParserResult, RemoveCheckResult
from app.services.cian_parser import CianParser
from app.models import Listing

router = APIRouter(prefix="/api/parser", tags=["parser"])
logger = logging.getLogger(__name__)

parsing_status = {
    "is_running": False,
    "progress": None,
    "last_result": None
}


def run_parsing_task(config: ParserConfig, db: Session):
    """Фоновая задача парсинга (Cian)"""
    global parsing_status
    parsing_status["is_running"] = True
    parsing_status["progress"] = "Starting..."
    
    try:
        parser = CianParser(db)
        result = parser.run_parsing(
            city=config.city,
            category=config.category,
            deal_type=config.deal_type,
            max_pages=config.max_pages,
            filters=config.filters
        )
        parsing_status["last_result"] = result
        parsing_status["progress"] = "Completed"
    except Exception as e:
        logger.error(f"Parsing error: {e}")
        parsing_status["progress"] = f"Error: {str(e)}"
        parsing_status["last_result"] = {"error": str(e)}
    finally:
        parsing_status["is_running"] = False


@router.post("/start", response_model=dict)
def start_parsing(
    config: ParserConfig,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Запустить парсинг в фоновом режиме"""
    global parsing_status
    
    if parsing_status["is_running"]:
        return {
            "message": "Парсинг уже выполняется",
            "status": "already_running"
        }
    
    background_tasks.add_task(run_parsing_task, config, db)
    
    return {
        "message": "Парсинг запущен",
        "status": "started",
        "config": config.model_dump()
    }


@router.post("/start-sync", response_model=ParserResult)
def start_parsing_sync(
    config: ParserConfig,
    db: Session = Depends(get_db)
):
    """Запустить парсинг синхронно (для тестирования)"""
    global parsing_status
    
    if parsing_status["is_running"]:
        return ParserResult(
            total_found=0,
            new_listings=0,
            updated_listings=0,
            errors=1,
            pages_parsed=0
        )
    
    parsing_status["is_running"] = True
    
    try:
        parser = CianParser(db)
        result = parser.run_parsing(
            city=config.city,
            category=config.category,
            deal_type=config.deal_type,
            max_pages=config.max_pages,
            filters=config.filters
        )
        parsing_status["last_result"] = result
        return ParserResult(**result)
    finally:
        parsing_status["is_running"] = False


@router.get("/status")
def get_parsing_status():
    """Получить статус текущего парсинга"""
    return parsing_status


@router.post("/check-removed", response_model=RemoveCheckResult)
def check_removed_listings(db: Session = Depends(get_db)):
    """Проверить снятые объявления"""
    active_count = db.query(Listing).filter(Listing.is_active == True).count()
    
    # TODO: implement check_removed_listings for Cian
    removed = 0
    
    return RemoveCheckResult(
        checked=active_count,
        removed=removed
    )


@router.get("/config/cities")
def get_available_cities():
    """Получить список доступных городов (Cian)"""
    return {
        "cities": [
            {"slug": "spb", "name": "Санкт-Петербург"},
            {"slug": "moskva", "name": "Москва"},
            {"slug": "ekaterinburg", "name": "Екатеринбург"},
            {"slug": "novosibirsk", "name": "Новосибирск"},
            {"slug": "kazan", "name": "Казань"},
            {"slug": "nizhny-novgorod", "name": "Нижний Новгород"},
            {"slug": "chelyabinsk", "name": "Челябинск"},
            {"slug": "samara", "name": "Самара"},
            {"slug": "rostov-na-donu", "name": "Ростов-на-Дону"},
            {"slug": "ufa", "name": "Уфа"},
        ]
    }


@router.get("/config/categories")
def get_available_categories():
    """Получить список доступных категорий (Cian)"""
    return {
        "categories": [
            {"slug": "kvartiry", "name": "Квартиры"},
            {"slug": "komnaty", "name": "Комнаты"},
            {"slug": "doma", "name": "Дома"},
            {"slug": "uchastki", "name": "Участки"},
            {"slug": "kommercheskaya", "name": "Коммерческая недвижимость"},
        ]
    }


@router.get("/config/deal-types")
def get_available_deal_types():
    """Получить список типов сделок (Cian)"""
    return {
        "deal_types": [
            {"slug": "sale", "name": "Продажа"},
            {"slug": "rent", "name": "Аренда"},
        ]
    }


@router.get("/debug/fetch")
def debug_fetch_page(
    city: str = "spb",
    category: str = "kvartiry",
    deal_type: str = "sale"
):
    """Отладочный endpoint - показывает что приходит от Cian"""
    import httpx
    import re
    
    # Строим URL для Cian
    CITY_DOMAINS = {
        "moskva": "https://www.cian.ru",
        "spb": "https://spb.cian.ru",
    }
    DEAL_TYPES = {"sale": "kupit", "rent": "snyat"}
    PROPERTY_TYPES = {"kvartiry": "kvartiru", "komnaty": "komnatu", "doma": "dom"}
    
    base_domain = CITY_DOMAINS.get(city, f"https://{city}.cian.ru")
    deal = DEAL_TYPES.get(deal_type, "kupit")
    prop_type = PROPERTY_TYPES.get(category, "kvartiru")
    url = f"{base_domain}/{deal}-{prop_type}/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    try:
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            
            html = response.text
            
            result = {
                "source": "cian",
                "request_url": url,
                "final_url": str(response.url),
                "status_code": response.status_code,
                "html_length": len(html),
            }
            
            # Ищем cianId в HTML
            cian_ids = re.findall(r'"cianId":(\d+)', html)
            unique_ids = list(dict.fromkeys(cian_ids))
            result["unique_cian_ids"] = len(unique_ids)
            result["sample_ids"] = unique_ids[:5]
            
            # Ищем цены
            prices = re.findall(r'"price":(\d+)', html)
            result["prices_found"] = len(prices)
            result["sample_prices"] = [int(p) for p in prices[:5]]
            
            # Ищем комнаты
            rooms = re.findall(r'"roomsCount":(\d+)', html)
            result["rooms_found"] = len(rooms)
            
            # Ищем этажи
            floors = re.findall(r'"floorNumber":(\d+)', html)
            result["floors_found"] = len(floors)
            
            # Проверяем блокировку
            if 'captcha' in html.lower() or 'blocked' in html.lower():
                result["has_captcha"] = True
            else:
                result["has_captcha"] = False
            
            return result
            
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}
