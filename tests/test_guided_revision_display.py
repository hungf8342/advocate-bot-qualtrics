"""Revision comparisons need an actual earlier choice or completed review."""
from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import (
    COMPLETE, DEFENSE, SUMMARY, SUMMARIES,
)
from test_clickthrough_workflow import (
    advance_updated, answers, change, completed_history, default_answer, intake,
)


def test_sol_edit_does_not_add_previous_status_to_first_reviews_of_later_defenses():
    current = change(completed_history(), 'guided_payment_date', '2026-07-01')
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY
    assert current.page()['changes']  # The completed SOL review is a valid baseline.
    seen = set()
    for _ in range(250):
        current = advance_updated(current, default_answer(current))
        page = current.page()
        if current.current in SUMMARIES and current.current != SUMMARY:
            seen.add(current._current_defense())
            assert page['changes'] == []
            assert 'revision_notice' not in page
            assert all('previous_status' not in row for row in page['rows'])
        if current.current == COMPLETE:
            break
    assert current.current == COMPLETE
    assert len(seen) == 16
    page = current.page()
    assert any('previous_status' in row for row in page['rows'] if row['defense_id'] == DEFENSE)
    assert all('previous_status' not in row for row in page['rows'] if row['defense_id'] != DEFENSE)


def test_unanswered_checkbox_is_not_a_previous_no_offer_result():
    history = intake() + answers(('sol_payment_estimate_agree', 'yes'))
    current = change(history, 'guided_payment_date', '2026-07-01')
    current = advance_updated(current, 'yes')
    assert current.current == SUMMARY
    assert current.page()['changes'] == []
    assert 'revision_notice' not in current.page()
    assert all('previous_status' not in row for row in current.page()['rows'])


def test_real_previous_no_offer_result_is_still_compared_when_box_becomes_available():
    current = change(completed_history(), 'guided_oral', 'yes')
    assert current.current == 'sol_checkbox_second'
    current = advance_updated(current, 'yes')
    second = next(row for row in current.page()['rows'] if row['id'] == 'second')
    assert second['previous_status'] == 'Not offered on this path'
    assert current.page()['changes'] == [{
        'label': 'California oral contracts', 'before': 'Not offered on this path', 'after': 'Selected',
    }]
