"""تست قواعد خالص ماژول اطلاعات بانکی (app/core/bank_rules.py)."""
import pytest

from app.core.bank_rules import (
    BankRulesError,
    changed_fields,
    clean_account_data,
    is_complete,
    is_valid_card,
    is_valid_sheba,
    mask,
    normalize_sheba,
)

# شبا با رقم کنترل درست (ساخته‌شده با همان الگوریتم IBAN) و کارت با Luhn درست
VALID_SHEBA = "IR820540102680020817909002"
VALID_CARD = "6037991234567893"


def test_sheba_normalize_and_check():
    assert normalize_sheba("ir82 0540 1026 8002 0817 9090 02") == VALID_SHEBA
    assert normalize_sheba("۸۲۰۵۴۰۱۰۲۶۸۰۰۲۰۸۱۷۹۰۹۰۰۲") == VALID_SHEBA  # ارقام فارسی بدون IR
    assert is_valid_sheba(VALID_SHEBA)
    assert not is_valid_sheba("IR830540102680020817909002")  # رقم کنترل غلط
    assert not is_valid_sheba("IR8205401026800208179090")  # کوتاه


def test_card_luhn():
    assert is_valid_card(VALID_CARD)
    assert not is_valid_card("6037991234567890")
    assert not is_valid_card("603799123456789")


def test_clean_account_data_modes():
    modes = {"account_number": "required", "sheba": "required", "card_number": "hidden"}
    out = clean_account_data(modes, {"account_number": "۱۲۳-۴۵۶۷۸۹", "sheba": VALID_SHEBA, "card_number": VALID_CARD})
    assert out == {"account_number": "123456789", "sheba": VALID_SHEBA, "card_number": None}
    with pytest.raises(BankRulesError):
        clean_account_data(modes, {"account_number": "", "sheba": VALID_SHEBA})
    with pytest.raises(BankRulesError):
        clean_account_data(modes, {"account_number": "123456", "sheba": "IR000"})
    optional = {"account_number": "optional", "sheba": "required", "card_number": "optional"}
    assert clean_account_data(optional, {"sheba": VALID_SHEBA})["account_number"] is None


def test_complete_changes_mask():
    modes = {"account_number": "required", "sheba": "optional", "card_number": "hidden"}
    assert is_complete(modes, {"account_number": "123456"})
    assert not is_complete(modes, {"sheba": VALID_SHEBA})
    assert not is_complete(modes, None)
    assert changed_fields({"account_number": "1"}, {"account_number": "2", "sheba": None}) == {"account_number": ["1", "2"]}
    assert mask("6037991234567893") == "************7893"
    assert mask(None) == "—"
