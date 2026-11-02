"""تست قاعده‌ی متمرکز دسترسی نامه (core/oa_access_rules.can) — بدون دیتابیس."""

from app.core.oa_access_rules import can, delivery_grants, push_text_key, referral_grants

SENT = {"status": "dispatched", "confidentiality": "normal"}
SENT_C = {"status": "dispatched", "confidentiality": "confidential"}
DRAFT = {"status": "draft", "confidentiality": "normal"}


def row(source, act=False, refer=False, revoked=None):
    return {"source": source, "can_act": act, "can_refer": refer, "revoked_at": revoked}


def test_no_rows_no_access_even_for_confidential_or_admin():
    for action in ("view", "download", "refer", "act", "note", "manage", "make_confidential"):
        assert not can(action, letter=SENT_C, rows=[])
        assert not can(action, letter=SENT, rows=[])


def test_revoked_rows_block():
    assert not can("view", letter=SENT, rows=[row("recipient", True, True, revoked="2026-11-01")])


def test_recipient_cc_referral_matrix():
    to = delivery_grants("to")
    cc = delivery_grants("cc")
    r_to = [row(to["source"], to["can_act"], to["can_refer"])]
    r_cc = [row(cc["source"], cc["can_act"], cc["can_refer"])]
    assert can("view", letter=SENT_C, rows=r_to) and can("refer", letter=SENT_C, rows=r_to)
    assert can("act", letter=SENT, rows=r_to, open_task=True) and not can("act", letter=SENT, rows=r_to)
    assert can("view", letter=SENT_C, rows=r_cc)
    assert not can("refer", letter=SENT_C, rows=r_cc) and not can("act", letter=SENT_C, rows=r_cc)
    assert cc["task_kind"] is None and to["task_kind"] == "action"
    g = referral_grants("info", False)
    r_ref = [row(g["source"], g["can_act"], g["can_refer"])]
    assert not can("refer", letter=SENT, rows=r_ref) and can("refer", letter=SENT, rows=[row("referral", True, True)])


def test_confidential_change_only_by_creator_sender_after_send():
    assert can("make_confidential", letter=SENT, rows=[row("sender", refer=True)])
    assert not can("make_confidential", letter=SENT, rows=[row("recipient", True, True)])
    assert not can("make_confidential", letter=SENT_C, rows=[row("sender", refer=True)])  # محرمانه → عادی وجود ندارد
    assert not can("make_confidential", letter=DRAFT, rows=[row("creator")])


def test_manage_only_draft_creator_and_push_text():
    assert can("manage", letter=DRAFT, rows=[row("creator")]) and not can("manage", letter=SENT, rows=[row("creator")])
    assert push_text_key("new_letter", True) == "automation.confidential"
    assert push_text_key("referral", False) == "automation.referral"
