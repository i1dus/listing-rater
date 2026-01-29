from app.routers.listings import router as listings_router
from app.routers.properties import router as properties_router
from app.routers.parser import router as parser_router
from app.routers.admin import router as admin_router

__all__ = ["listings_router", "properties_router", "parser_router", "admin_router"]
