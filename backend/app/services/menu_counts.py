"""شمارندهٔ صف‌های مدیریتی، محدود به مجوز اقدام در هر سایت."""
from sqlalchemy import func, select

from app.core import advance_rules, loan_rules
from app.core.permission_grants import grants_subquery
from app.core.site_access import all_site_ids, covers_all_sites
from app.models.advance import AdvanceRequest
from app.models.careers import CareerApplication
from app.models.employee import Employee
from app.models.family import FamilyProfile
from app.models.feedback import FeedbackMessage, FeedbackReply, FeedbackStatus
from app.models.loan import LoanRequest
from app.models.user import User


async def pending_menu_counts(db, user):
    """برای هر صف مجاز یک عدد می‌دهد؛ فقط شمارش در دیتابیس انجام می‌شود."""
    last_sender = (
        select(FeedbackReply.is_from_sender)
        .where(FeedbackReply.feedback_id == FeedbackMessage.id)
        .order_by(FeedbackReply.created_at.desc(), FeedbackReply.id.desc())
        .limit(1).correlate(FeedbackMessage).scalar_subquery()
    )
    queues = {
        "careers": ("careers.manage", None,
                    select(func.count(CareerApplication.id)).where(CareerApplication.status == "new")),
        "family": ("family.manage", Employee.site_id,
                   select(func.count(FamilyProfile.id)).join(Employee, Employee.id == FamilyProfile.employee_id)
                   .where(FamilyProfile.status == "pending", Employee.is_active.is_(True))),
        "loans": ("loans.finance", LoanRequest.site_id,
                  select(func.count(LoanRequest.id)).where(LoanRequest.status == loan_rules.STATUS_WAITING_FINANCE)),
        "advances": ("advances.finance", AdvanceRequest.site_id,
                     select(func.count(AdvanceRequest.id)).where(AdvanceRequest.status.in_(
                         (advance_rules.STATUS_WAITING_FINANCE, advance_rules.STATUS_APPROVED)))),
        "feedback": ("feedback.reply", Employee.site_id,
                     select(func.count(FeedbackMessage.id)).join(User, User.id == FeedbackMessage.sender_id)
                     .outerjoin(Employee, Employee.id == User.employee_id)
                     .where(FeedbackMessage.is_deleted.is_(False), FeedbackMessage.status != FeedbackStatus.closed.value,
                            func.coalesce(last_sender, True).is_(True))),
    }
    scopes = {}
    if not user.is_superuser:
        grants = grants_subquery()
        rows = await db.execute(select(grants.c.code, grants.c.site_id).where(
            grants.c.user_id == user.id, grants.c.code.in_([code for code, _, _ in queues.values()])))
        for code, site in rows:
            scopes.setdefault(code, set()).add(site)

    # A reporter without an employee is visible to a reviewer covering every site.
    reply_sites = scopes.get("feedback.reply")
    if reply_sites and None not in reply_sites and covers_all_sites(reply_sites, await all_site_ids(db)):
        reply_sites.add(None)

    columns = []
    for key, (code, site_column, query) in queues.items():
        sites = scopes.get(code, set())
        if not user.is_superuser and None not in sites:
            if not sites or site_column is None:
                continue
            query = query.where(site_column.in_(sites))
        columns.append(query.scalar_subquery().label(key))
    if not columns:
        return {}
    return dict((await db.execute(select(*columns))).mappings().one())
