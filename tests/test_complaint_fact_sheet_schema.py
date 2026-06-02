"""Schema validation tests (no live LLM calls)."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.schemas.complaint_fact_sheet import ComplaintFactSheet


def test_minimal_fact_sheet_with_null_dates():
    sheet = ComplaintFactSheet.model_validate(
        {
            "schema_version": "1.1",
            "plaintiff_names": ["Jane Doe"],
            "defendant_names": ["ACME Collections LLC"],
            "jurisdiction": "Circuit Court of Cook County, Illinois",
            "amount_sued_for": "1250.00",
            "date_complaint_filed": None,
            "alleged_incident_date": None,
            "date_user_failed_to_pay": None,
            "causes_of_action": ["Breach of contract"],
            "original_contract_included": None,
            "payment_or_balance_log_included": False,
            "bill_of_assignment_or_debt_ownership_evidence": None,
            "amount_inconsistent_with_case": None,
            "field_citations": {
                "plaintiff_names": "Plaintiff Jane Doe",
                "amount_sued_for": None,
            },
        }
    )
    assert sheet.plaintiff_names == ["Jane Doe"]
    assert sheet.amount_sued_for == Decimal("1250.00")
    assert sheet.date_complaint_filed is None


def test_explicit_dates_parse():
    sheet = ComplaintFactSheet(
        plaintiff_names=["P"],
        defendant_names=["D"],
        date_complaint_filed=date(2024, 3, 15),
        alleged_incident_date=date(2023, 1, 10),
    )
    assert sheet.date_complaint_filed == date(2024, 3, 15)
    assert sheet.alleged_incident_date == date(2023, 1, 10)


def test_json_schema_excludes_defense_fields():
    schema = ComplaintFactSheet.model_json_schema()
    props = schema["properties"]
    assert "plaintiff_names" in props
    assert "fdcpa" not in props
    assert "statute_of_limitations" not in props
    assert "failure_to_state_a_claim_mentioned" not in props


def test_mock_llm_payload_validates():
    payload = {
        "schema_version": "1.1",
        "plaintiff_names": [],
        "defendant_names": ["Defendant"],
        "causes_of_action": [],
        "field_citations": {},
    }
    sheet = ComplaintFactSheet.model_validate(payload)
    assert sheet.defendant_names == ["Defendant"]


def test_invalid_schema_version_rejected():
    with pytest.raises(ValidationError):
        ComplaintFactSheet.model_validate({"schema_version": "1.0"})
