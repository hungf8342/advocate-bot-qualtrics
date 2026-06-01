"""Schema validation tests (no live LLM calls)."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.schemas.complaint_fact_sheet import (
    ComplaintFactSheet,
    FdcpaFacts,
)


def test_minimal_fact_sheet_with_null_dates():
    sheet = ComplaintFactSheet.model_validate(
        {
            "schema_version": "1.0",
            "plaintiff_names": ["Jane Doe"],
            "defendant_names": ["ACME Collections LLC"],
            "jurisdiction": "Circuit Court of Cook County, Illinois",
            "amount_sued_for": "1250.00",
            "date_of_filing": None,
            "date_complaint_filed": None,
            "alleged_incident_date": None,
            "date_user_failed_to_pay": None,
            "causes_of_action": ["Breach of contract"],
            "statute_of_limitations": None,
            "failure_to_state_a_claim_mentioned": None,
            "failure_to_state_a_claim_adequate": None,
            "failure_to_state_a_claim_rationale": None,
            "original_contract_included": None,
            "payment_or_balance_log_included": False,
            "bill_of_assignment_or_debt_ownership_evidence": None,
            "fdcpa": {
                "applies_or_alleged": True,
                "allegations": ["Unfair collection practice"],
                "punishment_threatened": None,
            },
            "amount_inconsistent_with_case": None,
            "field_citations": {
                "plaintiff_names": "Plaintiff Jane Doe",
                "amount_sued_for": None,
            },
        }
    )
    assert sheet.plaintiff_names == ["Jane Doe"]
    assert sheet.amount_sued_for == Decimal("1250.00")
    assert sheet.date_of_filing is None
    assert sheet.fdcpa.applies_or_alleged is True


def test_explicit_dates_parse():
    sheet = ComplaintFactSheet(
        plaintiff_names=["P"],
        defendant_names=["D"],
        date_of_filing=date(2024, 3, 15),
        alleged_incident_date=date(2023, 1, 10),
    )
    assert sheet.date_of_filing == date(2024, 3, 15)
    assert sheet.alleged_incident_date == date(2023, 1, 10)


def test_json_schema_round_trip():
    schema = ComplaintFactSheet.model_json_schema()
    assert "properties" in schema
    assert "plaintiff_names" in schema["properties"]
    assert "fdcpa" in schema["properties"]


def test_mock_llm_payload_validates():
    payload = {
        "schema_version": "1.0",
        "plaintiff_names": [],
        "defendant_names": ["Defendant"],
        "causes_of_action": [],
        "fdcpa": {"allegations": []},
        "field_citations": {},
    }
    sheet = ComplaintFactSheet.model_validate(payload)
    assert sheet.defendant_names == ["Defendant"]


def test_invalid_schema_version_rejected():
    with pytest.raises(ValidationError):
        ComplaintFactSheet.model_validate({"schema_version": "2.0"})


def test_fdcpa_defaults():
    fdcpa = FdcpaFacts()
    assert fdcpa.allegations == []
    assert fdcpa.applies_or_alleged is None
