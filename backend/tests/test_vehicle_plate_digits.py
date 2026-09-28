"""پلاک با ارقام فارسی/عربی پذیرفته و لاتین ذخیره می‌شود."""
import pytest

pydantic = pytest.importorskip("pydantic")

from app.schemas.vehicle import VehicleIn  # noqa: E402


def _vehicle(**plate):
    base = dict(vehicle_type="پراید", color="سفید", plate_digits1="12", plate_letter="ب", plate_digits2="345", plate_iran_code="67")
    base.update(plate)
    return VehicleIn(**base)


def test_persian_digits_stored_as_latin():
    v = _vehicle(plate_digits1="۱۲", plate_digits2="٣٤٥", plate_iran_code="۶۷", plate_letter="ي")
    assert (v.plate_digits1, v.plate_digits2, v.plate_iran_code, v.plate_letter) == ("12", "345", "67", "ی")


def test_invalid_length_rejected():
    with pytest.raises(pydantic.ValidationError):
        _vehicle(plate_digits2="۱۲")
