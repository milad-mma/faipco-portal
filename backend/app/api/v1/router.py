"""
روتر مرکزی نسخه v1 از API.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    attendance,
    auth,
    backup,
    departments,
    employees,
    evaluation_forms,
    evaluation_periods,
    evaluation_process,
    evaluation_reports,
    evaluation_structure,
    feedback,
    hr,
    mapping_suggestions,
    monthly_attendance,
    notices,
    push,
    sites,
    sync,
    system,
    users,
    vehicles,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(notices.router, prefix="/notices", tags=["notices"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(push.router, prefix="/push", tags=["push"])
api_router.include_router(backup.router, prefix="/backup", tags=["backup"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(monthly_attendance.router, prefix="/monthly-attendance", tags=["monthly-attendance"])
api_router.include_router(hr.router, prefix="/hr", tags=["hr"])
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(mapping_suggestions.router, prefix="/mapping-suggestions", tags=["mapping-suggestions"])
api_router.include_router(evaluation_structure.router, prefix="/performance", tags=["performance"])
api_router.include_router(evaluation_periods.router, prefix="/performance/periods", tags=["performance"])
api_router.include_router(evaluation_forms.router, prefix="/performance/forms", tags=["performance"])
api_router.include_router(evaluation_process.router, prefix="/performance", tags=["performance"])
api_router.include_router(evaluation_reports.router, prefix="/performance/reports", tags=["performance"])
