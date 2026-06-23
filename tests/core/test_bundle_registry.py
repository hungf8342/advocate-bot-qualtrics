"""Practice-area bundle registry."""

from advocate_bot_qualtrics.core.bundle import get_bundle, list_practice_areas
from advocate_bot_qualtrics.practice_areas.consumer_debt.tree import INTERACTIVE_START_NODE_ID


def test_registry_loads_consumer_debt():
    areas = list_practice_areas()
    assert "consumer_debt" in areas

    bundle = get_bundle("consumer_debt")
    assert bundle.id == "consumer_debt"
    assert bundle.start_node_id == INTERACTIVE_START_NODE_ID
    assert bundle.facts_payload_key == "complaint_fact_sheet"


def test_unknown_practice_area_raises():
    try:
        get_bundle("family_law")
    except KeyError as exc:
        assert "family_law" in str(exc)
    else:
        raise AssertionError("expected KeyError for unknown practice area")
