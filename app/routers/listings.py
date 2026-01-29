from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Listing
from app.schemas.listing import ListingResponse, ListingListResponse, ListingUpdate
from app.services.cian_parser import CianParser
from app.services.listing_scorer import ListingScorer  # Старый сервис (для обратной совместимости)
from app.services.property_matcher import PropertyMatcher
from app.services.scoring import SaleProbabilityScorer, RegionalStatistics

DEAL_TYPE_SLUG_TO_NAME = {
    "sale": "Продажа",
    "rent": "Аренда",
    "prodam": "Продажа",
    "sdam": "Аренда",
    "kupit": "Продажа",
    "snyat": "Аренда",
}

PROPERTY_TYPE_SLUG_TO_NAME = {
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

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("", response_model=ListingListResponse)
def get_listings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    city: Optional[str] = None,
    deal_type: Optional[str] = None,
    property_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_rooms: Optional[int] = None,
    max_rooms: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получить список объявлений с фильтрацией и пагинацией"""
    query = db.query(Listing)
    
    if city:
        query = query.filter(Listing.city.ilike(f"%{city}%"))
    if deal_type:
        deal_type_variants = [deal_type]
        if deal_type in DEAL_TYPE_SLUG_TO_NAME:
            deal_type_variants.append(DEAL_TYPE_SLUG_TO_NAME[deal_type])
        for slug, name in DEAL_TYPE_SLUG_TO_NAME.items():
            if name == deal_type:
                deal_type_variants.append(slug)
        
        query = query.filter(Listing.deal_type.in_(deal_type_variants))
    if property_type:
        property_type_variants = [property_type]
        if property_type in PROPERTY_TYPE_SLUG_TO_NAME:
            property_type_variants.append(PROPERTY_TYPE_SLUG_TO_NAME[property_type])
        for slug, name in PROPERTY_TYPE_SLUG_TO_NAME.items():
            if name == property_type:
                property_type_variants.append(slug)
        
        query = query.filter(Listing.property_type.in_(property_type_variants))
    if is_active is not None:
        query = query.filter(Listing.is_active == is_active)
    if min_price:
        query = query.filter(Listing.price >= min_price)
    if max_price:
        query = query.filter(Listing.price <= max_price)
    if min_rooms is not None:
        query = query.filter(Listing.rooms >= min_rooms)
    if max_rooms is not None:
        query = query.filter(Listing.rooms <= max_rooms)
    if search:
        query = query.filter(
            or_(
                Listing.title.ilike(f"%{search}%"),
                Listing.address.ilike(f"%{search}%"),
                Listing.description.ilike(f"%{search}%")
            )
        )
    
    total = query.count()
    pages = (total + per_page - 1) // per_page
    
    items = query.order_by(Listing.parsed_at.desc())\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    return ListingListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/{listing_id}", response_model=ListingResponse)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    """Получить объявление по ID"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    return listing


@router.put("/{listing_id}", response_model=ListingResponse)
def update_listing(
    listing_id: int,
    listing_update: ListingUpdate,
    db: Session = Depends(get_db)
):
    """Обновить объявление"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    
    update_data = listing_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(listing, key, value)
    
    db.commit()
    db.refresh(listing)
    return listing


@router.delete("/{listing_id}")
def delete_listing(listing_id: int, db: Session = Depends(get_db)):
    """Удалить объявление"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    
    db.delete(listing)
    db.commit()
    return {"message": "Объявление удалено", "id": listing_id}


@router.get("/stats/summary")
def get_listings_stats(db: Session = Depends(get_db)):
    """Получить статистику по объявлениям"""
    total = db.query(Listing).count()
    active = db.query(Listing).filter(Listing.is_active == True).count()
    
    by_deal_type = {}
    for deal_type in ['Продажа', 'Аренда']:
        count = db.query(Listing).filter(Listing.deal_type == deal_type).count()
        if count > 0:
            by_deal_type[deal_type] = count
    for deal_type in ['prodam', 'sdam', 'sale', 'rent']:
        count = db.query(Listing).filter(Listing.deal_type == deal_type).count()
        if count > 0:
            by_deal_type[deal_type] = count
    
    from sqlalchemy import func
    cities = db.query(
        Listing.city, func.count(Listing.id).label('count')
    ).group_by(Listing.city).order_by(func.count(Listing.id).desc()).limit(5).all()
    
    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "by_deal_type": by_deal_type,
        "top_cities": [{"city": c[0], "count": c[1]} for c in cities if c[0]]
    }


@router.post("/{listing_id}/parse-details", response_model=ListingResponse)
def parse_listing_details(listing_id: int, db: Session = Depends(get_db)):
    """Спарсить полные данные объявления с детальной страницы"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    
    if not listing.url:
        raise HTTPException(status_code=400, detail="У объявления нет URL")
    
    parser = CianParser(db)
    listing_data = parser.parse_listing_details(listing.url)
    
    if not listing_data:
        raise HTTPException(status_code=500, detail="Не удалось извлечь данные со страницы")
    
    if 'price' in listing_data:
        listing.price = listing_data['price']
    if 'rooms' in listing_data:
        listing.rooms = listing_data['rooms']
    if 'floor' in listing_data:
        listing.floor = listing_data['floor']
    if 'floors_total' in listing_data:
        listing.floors_total = listing_data['floors_total']
    if 'area_total' in listing_data:
        listing.area_total = listing_data['area_total']
    if 'area_living' in listing_data:
        listing.area_living = listing_data['area_living']
    if 'area_kitchen' in listing_data:
        listing.area_kitchen = listing_data['area_kitchen']
    if 'address' in listing_data and listing_data['address']:
        listing.address = listing_data['address']
    if 'description' in listing_data:
        listing.description = listing_data['description']
    if 'title' in listing_data:
        listing.title = listing_data['title']
    if 'metro' in listing_data:
        listing.metro = listing_data['metro']
    if 'metro_time' in listing_data:
        listing.metro_time = listing_data['metro_time']
    if 'metro_transport' in listing_data:
        listing.metro_transport = listing_data['metro_transport']
    
    from datetime import datetime
    listing.parsed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(listing)
    
    return listing


@router.get("/{listing_id}/sale-probability")
def get_sale_probability(
    listing_id: int, 
    db: Session = Depends(get_db),
    include_details: bool = Query(True, description="Включать детальную информацию")
):
    """Вычислить вероятность продажи объявления"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    
    has_sufficient_data = (
        listing.price is not None or
        listing.area_total is not None or
        listing.rooms is not None
    )
    
    if not has_sufficient_data:
        raise HTTPException(
            status_code=400, 
            detail="Недостаточно данных для вычисления вероятности. Сначала выполните 'Спарсить полностью'."
        )
    
    # Используем новый ML-готовый сервис
    regional_stats = RegionalStatistics(db)
    scorer = SaleProbabilityScorer(regional_stats=regional_stats)
    result = scorer.calculate_probability(listing, include_details=include_details)
    
    return result


@router.get("/{listing_id}/match-details")
def get_match_details(listing_id: int, db: Session = Depends(get_db)):
    """Получить детали метчинга объявления с объектом недвижимости"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    
    if not listing.property_id:
        return {
            "has_match": False,
            "message": "Объявление не сопоставлено с объектом недвижимости"
        }
    
    property_obj = listing.property
    if not property_obj:
        return {
            "has_match": False,
            "message": "Объект недвижимости не найден"
        }
    
    # Вычисляем детали метчинга
    matcher = PropertyMatcher(db)
    match_result = matcher._calculate_similarity(listing, property_obj)
    
    # Форматируем результаты для отображения
    attribute_labels = {
        'city': 'Город',
        'street': 'Улица',
        'house_number': 'Номер дома',
        'rooms': 'Комнаты',
        'area_total': 'Общая площадь',
        'floor': 'Этаж',
        'property_type': 'Тип недвижимости',
        'district': 'Район',
        'area_living': 'Жилая площадь',
        'area_kitchen': 'Площадь кухни'
    }
    
    matched_details = []
    for attr_name, (matches, similarity) in match_result.matched_attributes.items():
        label = attribute_labels.get(attr_name, attr_name)
        is_strict = attr_name in match_result.strict_violations
        
        # Получаем значения из объявления и объекта
        listing_val = getattr(listing, attr_name, None)
        if attr_name in ['city', 'street', 'house_number', 'district']:
            # Для адресных полей используем специальную логику
            address_parts = matcher._extract_address_parts(listing)
            if attr_name == 'city':
                listing_val = address_parts.get('city') or listing.city
            elif attr_name == 'street':
                listing_val = address_parts.get('street')
            elif attr_name == 'house_number':
                listing_val = address_parts.get('house_number')
            elif attr_name == 'district':
                listing_val = address_parts.get('district') or listing.district
        
        property_val = getattr(property_obj, attr_name, None)
        
        matched_details.append({
            'attribute': attr_name,
            'label': label,
            'matches': matches,
            'similarity': similarity,
            'is_strict': attr_name in matcher.strict_attrs,
            'listing_value': listing_val,
            'property_value': property_val,
            'weight': matcher.weights.get(attr_name, 0.0)
        })
    
    return {
        "has_match": True,
        "similarity_score": match_result.similarity_score,
        "threshold": matcher.threshold,
        "strict_violations": match_result.strict_violations,
        "matched_attributes": matched_details,
        "property_id": property_obj.id
    }
