"""Single source of truth for approval returns awaiting a creator's correction.

A returned letter remains an editable draft, but is an actionable inbox item until
it is re-submitted, sent directly or discarded. A voluntary withdrawal does not
create an actionable return. Correlate to OaLetter so the expression is safe in
cartable queries, counters, dashboards and the draft list.
"""
from sqlalchemy import select

from app.models.office_automation import OaApprovalStep, OaLetter


def is_returned_for_revision():
    return (
        select(OaApprovalStep.id)
        .where(
            OaApprovalStep.letter_id == OaLetter.id,
            OaApprovalStep.round == OaLetter.approval_round,
            OaApprovalStep.status == "returned",
        )
        .correlate(OaLetter)
        .exists()
    )
