"""Pydantic schema for structured complaint fact extraction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ComplaintFactSheet(BaseModel):
    """Structured facts extracted from a legal complaint (no defense analysis)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: Literal["1.1"] = Field(
        default="1.1",
        description="Schema version for downstream migrations.",
    )

    plaintiff_names: list[str] = Field(
        default_factory=list,
        description="All named plaintiffs; empty if none identified.",
    )
    defendant_names: list[str] = Field(
        default_factory=list,
        description="All named defendants; empty if none identified.",
    )
    jurisdiction: str | None = Field(
        default=None,
        description="Court, venue, or jurisdictional statement (e.g. county and state).",
    )

    amount_sued_for: Decimal | None = Field(
        default=None,
        description="Principal amount sued for in numeric form; null if not stated.",
    )

    date_complaint_filed: date | None = Field(
        default=None,
        description=(
            "Date the complaint document itself shows or claims as filed (ISO YYYY-MM-DD). "
            "Null if not stated — never infer."
        ),
    )
    alleged_incident_date: date | None = Field(
        default=None,
        description=(
            "Date of the alleged breach, default, injury, or incident (ISO YYYY-MM-DD). "
            "Null if not stated — never infer."
        ),
    )
    date_user_failed_to_pay: date | None = Field(
        default=None,
        description=(
            "Date the complaint states the defendant failed to pay or defaulted (ISO YYYY-MM-DD). "
            "Null if not stated — never infer."
        ),
    )

    causes_of_action: list[str] = Field(
        default_factory=list,
        description="Distinct causes of action or counts pleaded.",
    )

    original_contract_included: bool | None = Field(
        default=None,
        description=(
            "True if the complaint indicates an original contract is attached, exhibited, "
            "or incorporated; false if it states none; null if not stated."
        ),
    )
    payment_or_balance_log_included: bool | None = Field(
        default=None,
        description=(
            "True if a payment log or balance history is attached, exhibited, or incorporated; "
            "null if not stated."
        ),
    )
    bill_of_assignment_or_debt_ownership_evidence: bool | None = Field(
        default=None,
        description=(
            "True if a bill of assignment or evidence that the defendant owes the debt "
            "is attached or described; null if not stated."
        ),
    )

    amount_inconsistent_with_case: str | None = Field(
        default=None,
        description=(
            "Description of any internal contradiction between dollar amounts in the complaint; "
            "null if none found."
        ),
    )

    field_citations: dict[str, str | None] = Field(
        default_factory=dict,
        description=(
            "Optional verbatim quotes from the complaint supporting extracted fields. "
            "Keys match field names (e.g. plaintiff_names, amount_sued_for); "
            "values are short quotes or null when no supporting text exists."
        ),
    )
