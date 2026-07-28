"""
روتر مرکزی نسخه v1 از API.
هر ماژول جدید در مراحل بعدی همین‌طور اضافه می‌شود.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, employees, notices, sites, sync

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(notices.router, prefix="/notices", tags=["notices"])
