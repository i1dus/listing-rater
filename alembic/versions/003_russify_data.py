"""Russify existing data - convert translit to Russian

Revision ID: 003
Revises: 002
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

# Маппинги для обновления данных
CITY_MAPPING = {
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

DEAL_TYPE_MAPPING = {
    "sale": "Продажа",
    "rent": "Аренда",
    "prodam": "Продажа",
    "sdam": "Аренда",
    "kupit": "Продажа",
    "snyat": "Аренда",
}

PROPERTY_TYPE_MAPPING = {
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


def upgrade() -> None:
    """Обновляем существующие данные - заменяем транслит на русские названия"""
    connection = op.get_bind()
    
    # Обновляем города в listings
    for slug, name in CITY_MAPPING.items():
        connection.execute(
            sa.text("UPDATE listings SET city = :name WHERE city = :slug"),
            {"name": name, "slug": slug}
        )
    
    # Обновляем города в properties
    for slug, name in CITY_MAPPING.items():
        connection.execute(
            sa.text("UPDATE properties SET city = :name WHERE city = :slug"),
            {"name": name, "slug": slug}
        )
    
    # Обновляем типы сделок в listings
    for slug, name in DEAL_TYPE_MAPPING.items():
        connection.execute(
            sa.text("UPDATE listings SET deal_type = :name WHERE deal_type = :slug"),
            {"name": name, "slug": slug}
        )
    
    # Обновляем типы недвижимости в listings
    for slug, name in PROPERTY_TYPE_MAPPING.items():
        connection.execute(
            sa.text("UPDATE listings SET property_type = :name WHERE property_type = :slug"),
            {"name": name, "slug": slug}
        )
    
    # Обновляем типы недвижимости в properties
    for slug, name in PROPERTY_TYPE_MAPPING.items():
        connection.execute(
            sa.text("UPDATE properties SET property_type = :name WHERE property_type = :slug"),
            {"name": name, "slug": slug}
        )


def downgrade() -> None:
    """Откат - заменяем русские названия обратно на транслит"""
    connection = op.get_bind()
    
    # Обратный маппинг (берем первый slug для каждого названия)
    CITY_REVERSE = {v: k for k, v in CITY_MAPPING.items() if k not in ["sankt-peterburg"]}  # Исключаем дубликаты
    DEAL_TYPE_REVERSE = {v: k for k, v in DEAL_TYPE_MAPPING.items() if k not in ["prodam", "sdam", "kupit", "snyat"]}
    PROPERTY_TYPE_REVERSE = {v: k for k, v in PROPERTY_TYPE_MAPPING.items() if k not in ["kvartiru", "komnatu", "dom", "uchastok", "kommercheskuyu-nedvizhimost"]}
    
    # Откатываем изменения
    for name, slug in CITY_REVERSE.items():
        connection.execute(
            sa.text("UPDATE listings SET city = :slug WHERE city = :name"),
            {"slug": slug, "name": name}
        )
        connection.execute(
            sa.text("UPDATE properties SET city = :slug WHERE city = :name"),
            {"slug": slug, "name": name}
        )
    
    for name, slug in DEAL_TYPE_REVERSE.items():
        connection.execute(
            sa.text("UPDATE listings SET deal_type = :slug WHERE deal_type = :name"),
            {"slug": slug, "name": name}
        )
    
    for name, slug in PROPERTY_TYPE_REVERSE.items():
        connection.execute(
            sa.text("UPDATE listings SET property_type = :slug WHERE property_type = :name"),
            {"slug": slug, "name": name}
        )
        connection.execute(
            sa.text("UPDATE properties SET property_type = :slug WHERE property_type = :name"),
            {"slug": slug, "name": name}
        )
