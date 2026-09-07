"""
Endpoint های «گزارش‌های مدیریتی ارزیابی عملکرد» - گزارش یک دوره برای یک
سایت (میانگین واحدها) و مقایسه دو دوره - با امکان دریافت خروجی Excel و
ارسال همان خروجی به ایمیل.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_permission_deps import require_site_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.evaluation_reports import EmailReportIn, PeriodComparisonOut, SitePeriodReportOut
from app.services.email_service import EmailError, send_email
from app.services.evaluation_report_xlsx import build_period_comparison_xlsx, build_site_period_report_xlsx
from app.services.evaluation_reports_service import EvaluationReportError, EvaluationReportsService

router = APIRouter()

PERMISSION_CODE = "performance.reports.view"


@router.get("/sites/{site_id}/periods/{period_id}", response_model=SitePeriodReportOut)
async def get_site_period_report(
    site_id: int,
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, PERMISSION_CODE)
    try:
        return await EvaluationReportsService(db).get_site_period_report(site_id, period_id)
    except EvaluationReportError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/sites/{site_id}/periods/{period_id}/export")
async def export_site_period_report(
    site_id: int,
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, PERMISSION_CODE)
    try:
        report = await EvaluationReportsService(db).get_site_period_report(site_id, period_id)
    except EvaluationReportError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    content = build_site_period_report_xlsx(report)
    filename = f"performance-report-{site_id}-{period_id}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/sites/{site_id}/periods/{period_id}/email")
async def email_site_period_report(
    site_id: int,
    period_id: int,
    payload: EmailReportIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, PERMISSION_CODE)
    try:
        report = await EvaluationReportsService(db).get_site_period_report(site_id, period_id)
    except EvaluationReportError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    content = build_site_period_report_xlsx(report)
    filename = f"performance-report-{site_id}-{period_id}.xlsx"
    try:
        await send_email(
            db,
            to_address=payload.email,
            subject=f"گزارش ارزیابی عملکرد - {report['site_name']} - {report['period_title']}",
            body_text="گزارش ارزیابی عملکرد پیوست این ایمیل است.",
            attachment=(filename, content),
        )
    except EmailError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"sent": True}


@router.get("/sites/{site_id}/compare", response_model=PeriodComparisonOut)
async def get_period_comparison(
    site_id: int,
    period_id_a: int,
    period_id_b: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, PERMISSION_CODE)
    try:
        return await EvaluationReportsService(db).get_period_comparison(site_id, period_id_a, period_id_b)
    except EvaluationReportError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/sites/{site_id}/compare/export")
async def export_period_comparison(
    site_id: int,
    period_id_a: int,
    period_id_b: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, PERMISSION_CODE)
    try:
        comparison = await EvaluationReportsService(db).get_period_comparison(site_id, period_id_a, period_id_b)
    except EvaluationReportError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    content = build_period_comparison_xlsx(comparison)
    filename = f"performance-comparison-{site_id}-{period_id_a}-{period_id_b}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/sites/{site_id}/compare/email")
async def email_period_comparison(
    site_id: int,
    period_id_a: int,
    period_id_b: int,
    payload: EmailReportIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, PERMISSION_CODE)
    try:
        comparison = await EvaluationReportsService(db).get_period_comparison(site_id, period_id_a, period_id_b)
    except EvaluationReportError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    content = build_period_comparison_xlsx(comparison)
    filename = f"performance-comparison-{site_id}-{period_id_a}-{period_id_b}.xlsx"
    try:
        await send_email(
            db,
            to_address=payload.email,
            subject=f"مقایسه دوره‌های ارزیابی عملکرد - {comparison['site_name']}",
            body_text="مقایسه دوره‌های ارزیابی عملکرد پیوست این ایمیل است.",
            attachment=(filename, content),
        )
    except EmailError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"sent": True}
