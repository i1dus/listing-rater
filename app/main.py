import logging
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine, Base, get_db
from app.routers import listings_router, properties_router, parser_router, admin_router
from app.models import Listing, Property

settings = get_settings()

log_level = logging.DEBUG if settings.debug else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description="Система парсинга и анализа объявлений недвижимости с Avito",
    version="1.0.0"
)

app.include_router(listings_router)
app.include_router(properties_router)
app.include_router(parser_router)
app.include_router(admin_router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Главная страница - дашборд"""
    listings_count = db.query(Listing).count()
    active_listings = db.query(Listing).filter(Listing.is_active == True).count()
    properties_count = db.query(Property).count()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "listings_count": listings_count,
        "active_listings": active_listings,
        "properties_count": properties_count
    })


@app.get("/listings", response_class=HTMLResponse)
async def listings_page(request: Request):
    """Страница объявлений"""
    return templates.TemplateResponse("listings.html", {"request": request})


@app.get("/listings/{listing_id}", response_class=HTMLResponse)
async def listing_detail_page(request: Request, listing_id: int):
    """Страница детального просмотра объявления"""
    return templates.TemplateResponse("listing_detail.html", {
        "request": request,
        "listing_id": listing_id
    })


@app.get("/properties", response_class=HTMLResponse)
async def properties_page(request: Request):
    """Страница объектов недвижимости"""
    return templates.TemplateResponse("properties.html", {"request": request})


@app.get("/properties/{property_id}", response_class=HTMLResponse)
async def property_detail_page(request: Request, property_id: int):
    """Страница детального просмотра объекта"""
    return templates.TemplateResponse("property_detail.html", {
        "request": request,
        "property_id": property_id
    })


@app.get("/parser", response_class=HTMLResponse)
async def parser_page(request: Request):
    """Страница управления парсингом"""
    return templates.TemplateResponse("parser.html", {"request": request})


@app.get("/admin/match-config", response_class=HTMLResponse)
async def match_config_page(request: Request):
    """Страница настройки метчинга"""
    return templates.TemplateResponse("match_config.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"status": "ok"}
