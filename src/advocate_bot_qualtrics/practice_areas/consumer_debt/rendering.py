"""Render approved script wording with recorded case facts."""

from __future__ import annotations

from datetime import date

from .session import InteractiveSessionState


def script_text(text: str, session: InteractiveSessionState) -> str:
    """Substitute facts in approved script wording without evaluating defenses."""
    from advocate_bot_qualtrics.practice_areas.consumer_debt.affirmative_defenses import (
        complaint_payment, personalize,
    )

    for token, tag in (("[OPEN.DATE]", "OPEN-DATE"), ("[LAST.PAYMENT.DATE]", "LAST-PAYMENT-DATE")):
        entry = session.preliminary_fields.get(tag)
        value = entry.complaint_value if entry else None
        text = text.replace(token, value.isoformat() if isinstance(value, date) else "unknown")
    text = text.replace("[LANGUAGE]", session.primary_language or "your primary language")
    payment = complaint_payment(session)
    filing = session.filing_date
    if "[COMPLAINT.DATE - 1 year]" in text:
        from .affirmative_defenses import calendar_cutoff
        text = text.replace("[COMPLAINT.DATE - 1 year]", calendar_cutoff(filing, 1).isoformat() if filing else "unknown")
    months = f"{(filing - payment).days / 30.4375:.1f}" if filing and payment else "unknown"
    text = text.replace("[months between that payment and filing]", months)
    restatement = f"The complaint lists your last payment as {payment.isoformat()}, about {months} months before it was filed." if payment else "The last-payment date in the complaint has not been established."
    text = text.replace("{complaint_payment_restatement}", restatement)
    return personalize(session, text)
