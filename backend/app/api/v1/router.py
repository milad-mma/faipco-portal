"""
روتر مرکزی نسخه v1 از API.
همه روترهای endpoint (احراز هویت، پرسنل، سایت‌ها، حضور و غیاب، ارزیابی عملکرد،
مرخصی، بیمه و ...) را با prefix و tag مربوط به خودشان در api_router ثبت می‌کند؛
main.py این روتر را زیر API_V1_PREFIX سوار می‌کند.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    access_gate,
    announcement,
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
    insurance,
    leave_requests,
    leave_requests_admin,
    mapping_suggestions,
    monthly_attendance,
    notices,
    push,
    sites,
    sync,
    system,
    turnover_report,
    users,
    vehicles,
)

api_router = APIRouter()  # روتر تجمیعی که در main.py با prefix نسخه ثبت می‌شود

# ثبت روترهای پایه: احراز هویت، پرسنل، سایت‌ها، واحدها، همگام‌سازی، اطلاعیه‌ها و کاربران
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(notices.router, prefix="/notices", tags=["notices"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
# اعلان Push، پشتیبان‌گیری و تنظیمات سیستم
api_router.include_router(push.router, prefix="/push", tags=["push"])
api_router.include_router(backup.router, prefix="/backup", tags=["backup"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
# حضور و غیاب، منابع انسانی، خودروها، بیمه، انتقادات و پیشنهاد نگاشت
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(monthly_attendance.router, prefix="/monthly-attendance", tags=["monthly-attendance"])
api_router.include_router(hr.router, prefix="/hr", tags=["hr"])
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(insurance.router, prefix="/insurance", tags=["insurance"])
api_router.include_router(turnover_report.router, prefix="/reports/turnover", tags=["reports"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(mapping_suggestions.router, prefix="/mapping-suggestions", tags=["mapping-suggestions"])
# ارزیابی عملکرد: چند روتر زیر prefix مشترک /performance
api_router.include_router(evaluation_structure.router, prefix="/performance", tags=["performance"])
api_router.include_router(evaluation_periods.router, prefix="/performance/periods", tags=["performance"])
api_router.include_router(evaluation_forms.router, prefix="/performance/forms", tags=["performance"])
api_router.include_router(evaluation_process.router, prefix="/performance", tags=["performance"])
api_router.include_router(evaluation_reports.router, prefix="/performance/reports", tags=["performance"])
# مرخصی: روتر کاربر و روتر مدیریتی هر دو زیر /leave-requests
api_router.include_router(leave_requests.router, prefix="/leave-requests", tags=["leave-requests"])
api_router.include_router(leave_requests_admin.router, prefix="/leave-requests", tags=["leave-requests"])
# دروازه دسترسی (IP/سایت) و اعلان عمومی
api_router.include_router(access_gate.router, prefix="/access-gate", tags=["access-gate"])
api_router.include_router(announcement.router, prefix="/announcement", tags=["announcement"])
