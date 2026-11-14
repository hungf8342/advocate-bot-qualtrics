"""Validation for approved preliminary explanation content."""

import pytest
from pydantic import ValidationError

from advocate_bot_qualtrics.core.schemas import NodeExplanation


@pytest.mark.parametrize("invalid", [
    {}, {"text": ""}, {"blocks": [{"text": ""}]},
    {"text": "General", "blocks": [{"text": "Conditional"}]},
    {"blocks": [{"text": "Conditional", "creditor_type": "unknown"}]},
])
def test_explanation_schema_rejects_ambiguous_or_empty_content(invalid):
    with pytest.raises(ValidationError):
        NodeExplanation.model_validate(invalid)
