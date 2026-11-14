"""Section skipping is explicit, reproducible, and isolated from research data."""
from pathlib import Path
import runpy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from advocate_bot_qualtrics.practice_areas.consumer_debt.debug_navigation import jump_to_section
from advocate_bot_qualtrics.practice_areas.consumer_debt.workflow import (
    DEFENSES, PRELIMINARY_FIELDS, PRELIMINARY_SUMMARY, GuidedAnswer, ClickthroughReview,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def debug_client(tmp_path):
    module = runpy.run_path(str(ROOT/'scripts/run_clickthrough.py'))
    app = module['create_app'](debug=True, collection_dir=tmp_path/'research')
    return TestClient(app), tmp_path/'research'


def advance(client, result, value):
    response = client.post('/api/advance',json={'history':result['history'], 'debug_section':result['debug_section'], 'revision':result['revision'], 'value':value})
    assert response.status_code == 200,response.text
    return response.json()


@pytest.mark.parametrize('section',DEFENSES)
def test_jump_to_every_defense_fills_intake_without_answering_skipped_defenses(debug_client,section):
    client,directory = debug_client
    response = client.post('/api/debug/jump',json={'section':section})
    assert response.status_code == 200,response.text
    result = response.json()
    current = ClickthroughReview(debug_section=section).replay([GuidedAnswer(**a) for a in result['history']])
    assert current._current_defense() == section
    assert current.session.preliminary_fields['SUIT-TYPE'].value == 'both'
    assert current.session.preliminary_fields['ORAL'].value == 'no'
    assert current.session.preliminary_fields['RECOGNIZE'].value == 'yes'
    assert current.session.preliminary_fields['CONSOLIDATION'].value == 'no'
    assert len(current.case_details()) == 18
    assert not current.session.checkbox_selections
    assert not current.session.defense_results
    if 'intro' in DEFENSES[section] and section not in {'mistake','unconscionable_contract'}:
        result = advance(client,result,'continue')
        assert result['page']['section'] == DEFENSES[section]['label']
    assert not directory.exists()


def test_partial_intake_and_valid_current_draft_are_preserved():
    current = ClickthroughReview().replay([
        GuidedAnswer(node_id='guided_welcome',value='continue'),
        GuidedAnswer(node_id='guided_case_number',value='MY-CASE'),
    ])
    result = jump_to_section(current,'ambiguity','My Test Creditor')
    assert result.session.plaintiff_name == 'My Test Creditor'
    assert result.session.preliminary_fields['CASE.NUMBER'].value == 'MY-CASE'
    assert result.session.original_creditor == 'My Test Creditor'
    assert result.current == 'ambiguity_decision'


def test_repeated_jumps_keep_case_details_and_never_mark_prior_defenses_complete(debug_client):
    client,_ = debug_client
    first = client.post('/api/debug/jump',json={'section':'capacity'}).json()
    second = client.post('/api/debug/jump',json={'history':first['history'],'debug_section':'capacity','section':'common_counts'}).json()
    assert second['debug_section'] == 'common_counts'
    current = ClickthroughReview(debug_section='common_counts').replay([GuidedAnswer(**a) for a in second['history']])
    assert current.session.preliminary_fields['SUIT-TYPE'].value == 'both'
    assert current.session.defense_results == {}
    assert not any(a.node_id=='capacity_minor' for a in current.history)
    preliminary = client.post('/api/debug/jump',json={'history':second['history'],'debug_section':'common_counts','section':'preliminary'}).json()
    assert preliminary['page']['node_id'] == PRELIMINARY_SUMMARY


def test_debug_can_answer_edit_preview_and_restore_after_jump(debug_client):
    client,_ = debug_client
    result = client.post('/api/debug/jump',json={'section':'ambiguity'}).json()
    preview = client.post('/api/preview',json={'history':result['history'],'debug_section':'ambiguity','value':'yes'})
    assert preview.status_code == 200
    result = advance(client,result,'yes')
    index = next(i for i,a in enumerate(result['history']) if a['node_id']=='ambiguity_decision')
    changed = client.post('/api/edit',json={'history':result['history'],'debug_section':'ambiguity','edit_index':index,'value':'no'})
    assert changed.status_code == 200,changed.text
    result = changed.json()
    assert result['page']['rows'][0]['checked'] is False
    restored = client.post('/api/state',json={'history':result['history'],'debug_section':'ambiguity','revision':result['revision']})
    assert restored.status_code == 200,restored.text
    assert restored.json()['node_id'] == result['page']['node_id']


def test_debug_never_creates_research_records_even_if_collection_context_is_sent(debug_client):
    client,directory = debug_client
    sid=str(uuid4())
    assert client.post('/api/state',json={'session_id':sid}).status_code == 200
    result=client.post('/api/debug/jump',json={'section':'ambiguity'}).json()
    collection={'session_id':sid,'event_id':str(uuid4()),'displayed_at':'2026-11-08T12:00:00Z','ended_at':'2026-11-08T12:00:02Z'}
    response=client.post('/api/advance',json={'history':result['history'],'debug_section':'ambiguity','value':'no','collection':collection})
    assert response.status_code == 200,response.text
    assert client.post('/api/collection/end',json={'session_id':sid}).json()['saved'] is False
    assert not directory.exists()


def test_normal_mode_rejects_debug_jumps_and_debug_anchors(tmp_path):
    module=runpy.run_path(str(ROOT/'scripts/run_clickthrough.py'))
    client=TestClient(module['create_app'](collection_dir=tmp_path))
    assert 'data-debug-mode="true"' not in client.get('/').text
    assert client.post('/api/debug/jump',json={'section':'ambiguity'}).status_code == 404
    assert client.post('/api/state',json={'debug_section':'ambiguity'}).status_code == 422
    assert client.post('/api/advance',json={'debug_section':'ambiguity','value':'continue'}).status_code == 422
    assert 'data-debug-mode="true"' in TestClient(module['create_app'](debug=True)).get('/').text


def test_invalid_section_and_draft_are_rejected(debug_client):
    client,_=debug_client
    assert client.post('/api/debug/jump',json={'section':'identity_theft'}).status_code == 422
    assert client.post('/api/debug/jump',json={'section':'nonsense'}).status_code == 422


def test_jump_after_back_preserves_other_confirmed_fields_and_current_draft(debug_client):
    client,_=debug_client
    result=client.post('/api/debug/jump',json={'section':'ambiguity'}).json()
    for answer in result['history']:
        if answer['node_id']=='guided_amount': answer['value']='999.00'
    cursor=next(i for i,a in enumerate(result['history']) if a['node_id']=='guided_law_firm')
    response=client.post('/api/debug/jump',json={'history':result['history'],'debug_section':'ambiguity','cursor':cursor,'section':'capacity','draft_value':'Changed Law Firm'})
    assert response.status_code==200,response.text
    result=response.json()
    values={a['node_id']:a['value'] for a in result['history']}
    assert values['guided_amount']=='999.00'
    assert values['guided_law_firm']=='Changed Law Firm'
    assert result['debug_section']=='capacity'


def test_page_versions_assets_and_refreshes_version_when_asset_changes(tmp_path):
    import re
    import shutil
    module=runpy.run_path(str(ROOT/'scripts/run_clickthrough.py'))
    assets=tmp_path/'assets'
    assets.mkdir()
    for name in ['index.html','app.js','style.css']:
        shutil.copyfile(ROOT/'scripts/assets/clickthrough'/name, assets/name)
    module['create_app'].__globals__['ASSETS']=assets
    client=TestClient(module['create_app'](debug=True))
    first=client.get('/')
    assert first.headers['cache-control']=='no-store'
    first_version=re.search(r'/assets/app.js\?v=([a-f0-9]+)', first.text).group(1)
    assert f'/assets/style.css?v={first_version}' in first.text
    with (assets/'app.js').open('a') as handle:handle.write('\n// Updated asset for cache test.\n')
    second=client.get('/')
    second_version=re.search(r'/assets/app.js\?v=([a-f0-9]+)', second.text).group(1)
    assert first_version!=second_version
