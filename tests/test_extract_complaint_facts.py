"""Unit tests for extract_complaint_facts input handling."""

import pytest

from advocate_bot_qualtrics.extraction.extract_complaint_facts import extract_complaint_facts


def test_empty_text_raises():
    with pytest.raises(ValueError, match="empty"):
        extract_complaint_facts("   \n")
