"""Recruitment validation security regression tests (run in configured backend venv)."""
import pytest
from fastapi import HTTPException
from app.api.v1.endpoints.careers import CareerSubmitIn, validate_application


def payload(**changes):
    data = {
        "full_name":"علی احمدی", "mobile":"09123456789", "requested_position":"کارشناس",
        "consent": True,
        "details": {"gender":"female", "religion":"اسلام", "denomination":"شیعه", "city":"تهران",
                    "employment_type":"fulltime", "available_from":"فوری", "education":"دیپلم",
                    "skills":"تولید", "employed_now":"no", "has_work_experience":"no",
                    "health_status":"healthy", "had_surgery":"no", "smokes":"no", "accuracy_confirmed": True}
    }
    data.update(changes)
    return CareerSubmitIn(**data)


def test_valid_anonymous_application():
    validate_application(payload())


def test_military_required_only_for_males():
    d = dict(payload().details, gender="male")
    with pytest.raises(HTTPException) as exc:
        validate_application(payload(details=d))
    assert exc.value.status_code == 422
    validate_application(payload(details={**d,"military_status":"completed"}))


def test_manual_resume_reference_injection_is_rejected():
    d = dict(payload().details, _resume_file="arbitrary.pdf")
    with pytest.raises(HTTPException):
        validate_application(payload(details=d))


def test_work_history_required_for_experienced_candidate():
    d = dict(payload().details, has_work_experience="yes")
    with pytest.raises(HTTPException):
        validate_application(payload(details=d))
    d["work_history"] = [{"company":"شرکت", "position":"اپراتور"}]
    validate_application(payload(details=d))


def test_wrong_honeypot_and_missing_consent_rejected():
    for item in (payload(website="spam"), payload(consent=False)):
        with pytest.raises(HTTPException):
            validate_application(item)


def test_excess_repeating_rows_rejected():
    d = dict(payload().details, references=[{"full_name":"X"} for _ in range(13)])
    with pytest.raises(HTTPException):
        validate_application(payload(details=d))
