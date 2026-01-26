from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database import get_db
from app.models import Property, Listing
from app.schemas.property import PropertyResponse, PropertyListResponse, PropertyUpdate
from app.services.property_matcher import PropertyMatcher

CITY_SLUG_TO_NAME = {
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

router = APIRouter(prefix="/api/properties", tags=["properties"])


@router.get("", response_model=PropertyListResponse)
def get_properties(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    city: Optional[str] = None,
    property_type: Optional[str] = None,
    min_rooms: Optional[int] = None,
    max_rooms: Optional[int] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    sort_by: Optional[str] = Query(None, description="Сортировка: price_asc, price_desc, created_at"),
    db: Session = Depends(get_db)
):
    """Получить список объектов недвижимости с фильтрацией"""
    query = db.query(Property)
    
    if city:
        city_variants = [city]
        for slug, name in CITY_SLUG_TO_NAME.items():
            if name == city:
                city_variants.append(slug)
        if city in CITY_SLUG_TO_NAME:
            city_variants.append(CITY_SLUG_TO_NAME[city])
        
        query = query.filter(Property.city.in_(city_variants))
    if property_type:
        property_type_variants = [property_type]
        if property_type in PROPERTY_TYPE_SLUG_TO_NAME:
            property_type_variants.append(PROPERTY_TYPE_SLUG_TO_NAME[property_type])
        for slug, name in PROPERTY_TYPE_SLUG_TO_NAME.items():
            if name == property_type:
                property_type_variants.append(slug)
        
        query = query.filter(Property.property_type.in_(property_type_variants))
    if min_rooms is not None:
        query = query.filter(Property.rooms >= min_rooms)
    if max_rooms is not None:
        query = query.filter(Property.rooms <= max_rooms)
    if min_area:
        query = query.filter(Property.area_total >= min_area)
    if max_area:
        query = query.filter(Property.area_total <= max_area)
    
    needs_join = (min_price is not None or max_price is not None or sort_by in ["price_asc", "price_desc"])
    
    total_query = db.query(Property.id)
    if city:
        city_variants = [city]
        for slug, name in CITY_SLUG_TO_NAME.items():
            if name == city:
                city_variants.append(slug)
        if city in CITY_SLUG_TO_NAME:
            city_variants.append(CITY_SLUG_TO_NAME[city])
        
        total_query = total_query.filter(Property.city.in_(city_variants))
    if property_type:
        property_type_variants = [property_type]
        if property_type in PROPERTY_TYPE_SLUG_TO_NAME:
            property_type_variants.append(PROPERTY_TYPE_SLUG_TO_NAME[property_type])
        for slug, name in PROPERTY_TYPE_SLUG_TO_NAME.items():
            if name == property_type:
                property_type_variants.append(slug)
        
        total_query = total_query.filter(Property.property_type.in_(property_type_variants))
    if min_rooms is not None:
        total_query = total_query.filter(Property.rooms >= min_rooms)
    if max_rooms is not None:
        total_query = total_query.filter(Property.rooms <= max_rooms)
    if min_area:
        total_query = total_query.filter(Property.area_total >= min_area)
    if max_area:
        total_query = total_query.filter(Property.area_total <= max_area)
    
    if min_price is not None or max_price is not None:
        total_query = total_query.join(Listing).group_by(Property.id)
        if min_price is not None:
            total_query = total_query.having(func.min(Listing.price) >= min_price)
        if max_price is not None:
            total_query = total_query.having(func.max(Listing.price) <= max_price)
        total = total_query.count()
    else:
        total = total_query.distinct().count()
    
    pages = (total + per_page - 1) // per_page
    
    if needs_join:
        query = query.outerjoin(Listing).group_by(Property.id)
        
        if min_price is not None:
            query = query.having(func.min(Listing.price) >= min_price)
        if max_price is not None:
            query = query.having(func.max(Listing.price) <= max_price)
        
        if sort_by == "price_asc":
            query = query.order_by(func.min(Listing.price).asc().nulls_last())
        elif sort_by == "price_desc":
            query = query.order_by(func.max(Listing.price).desc().nulls_last())
        else:
            query = query.order_by(Property.created_at.desc())
    else:
        query = query.order_by(Property.created_at.desc())
    
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    for item in items:
        item.listings_count = len(item.listings)
    
    return PropertyListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/{property_id}", response_model=PropertyResponse)
def get_property(property_id: int, db: Session = Depends(get_db)):
    """Получить объект недвижимости по ID"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Объект не найден")
    
    property_obj.listings_count = len(property_obj.listings)
    return property_obj


@router.put("/{property_id}", response_model=PropertyResponse)
def update_property(
    property_id: int,
    property_update: PropertyUpdate,
    db: Session = Depends(get_db)
):
    """Обновить объект недвижимости"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Объект не найден")
    
    update_data = property_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(property_obj, key, value)
    
    db.commit()
    db.refresh(property_obj)
    return property_obj


@router.delete("/{property_id}")
def delete_property(property_id: int, db: Session = Depends(get_db)):
    """Удалить объект недвижимости"""
    property_obj = db.query(Property).filter(Property.id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Объект не найден")
    
    db.query(Listing).filter(Listing.property_id == property_id).update(
        {"property_id": None}
    )
    
    db.delete(property_obj)
    db.commit()
    return {"message": "Объект удален", "id": property_id}


@router.post("/rematch")
def rematch_properties(db: Session = Depends(get_db)):
    """Пересопоставить все объявления с объектами недвижимости"""
    matcher = PropertyMatcher(db)
    results = matcher.rematch_all_listings()
    return results


@router.get("/cities")
def get_cities(db: Session = Depends(get_db)):
    """Получить список всех городов из объектов недвижимости"""
    cities = db.query(Property.city).distinct().filter(Property.city.isnot(None)).order_by(Property.city).all()
    return {"cities": [c[0] for c in cities if c[0]]}


@router.get("/stats/summary")
def get_properties_stats(db: Session = Depends(get_db)):
    """Получить статистику по объектам недвижимости"""
    total = db.query(Property).count()
    
    multi_listing = db.query(Property.id).join(Listing).group_by(Property.id)\
        .having(func.count(Listing.id) > 1).count()
    
    by_type = {}
    for ptype in ['kvartiry', 'doma_dachi_kottedzhi', 'komnaty']:
        by_type[ptype] = db.query(Property).filter(Property.property_type == ptype).count()
    
    cities = db.query(
        Property.city, func.count(Property.id).label('count')
    ).group_by(Property.city).order_by(func.count(Property.id).desc()).limit(5).all()
    
    return {
        "total": total,
        "with_multiple_listings": multi_listing,
        "by_type": by_type,
        "top_cities": [{"city": c[0], "count": c[1]} for c in cities if c[0]]
    }
