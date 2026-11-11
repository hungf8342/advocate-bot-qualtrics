"""Durable clickthrough research records and three materialized CSV datasets."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from .guided_sol import (
    COMPLETE, CONTINUE_PAGES, DEFENSES, PRELIMINARY_FIELDS, GuidedAdvanceRequest,
    GuidedSolReview, advance_review, TREE, PARENT_SCREENS, ACTION_SCREENS,
)
from .sol_dependency_map import affected_checkboxes

SESSION_COLUMNS = ['SESSION.ID', 'SESSION.START.TIME', 'SESSION.END.TIME',
                   'SESSION.COMPLETED', 'SESSION.TREE.VERSION']
DEFENSE_COLUMNS = ['SESSION.ID'] + [f'DEFENSE.{name}.{field}' for name in DEFENSES
    for field in ('CHECKED', 'CHANGED', 'TREE.PROJECTION')]
RESPONSE_COLUMNS = ['SESSION.ID', 'RESPONSE.ITEM.ID', 'RESPONSE.ITEM.VALUE',
    'RESPONSE.EVENT.TYPE', 'RESPONSE.REVISION.NUMBER',
    'RESPONSE.START.TIME', 'RESPONSE.CHECK.TIME', 'RESPONSE.END.TIME']


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class CollectionContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session_id: UUID
    event_id: UUID
    displayed_at: datetime
    checked_at: datetime | None = None
    ended_at: datetime

    @field_validator('displayed_at', 'checked_at', 'ended_at')
    @classmethod
    def aware_time(cls, value):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError('Collection timestamps must include a timezone.')
        return value.astimezone(timezone.utc)


def item_id(node: str) -> str:
    return PRELIMINARY_FIELDS[node]['field'] if node in PRELIMINARY_FIELDS else node


def defense_for(node: str) -> set[str]:
    if node in PRELIMINARY_FIELDS:
        shared = {"guided_consolidation": {"failure_to_mitigate", "rescission", "accord_satisfaction"},
                  "guided_suit_type": {"common_counts", "excuse_breach"},
                  "guided_recognize": {"lack_of_consideration"},
                  "guided_creditor_type": {"fraud", "waiver"},
                  "guided_open_date": {"capacity"}}
        return ({'statute_of_limitations'} if affected_checkboxes(node) else set()) | shared.get(node, set())
    definition = TREE.node_map.get(node)
    return {key for key, spec in DEFENSES.items()
            if definition and definition.discussion_topic == spec['label']}


def snapshot(current: GuidedSolReview) -> tuple[dict, dict, set[str]]:
    """Include valid retained answers beyond a revision's intermediate summary.

    Walk only previously visited continuation pages. This does not confirm anything
    in the actual workflow; it prevents retained future defenses appearing invalid.
    """
    effective = current
    if current.revision:
        visited = {a.node_id for a in current.revision.previous_history}
        visited.update(r.answer.node_id for r in current.revision.saved_answers)
        for _ in range(400):
            if effective.current not in CONTINUE_PAGES or effective.current not in visited:
                break
            effective = advance_review(current.defaults, GuidedAdvanceRequest(
                history=effective.history, revision=effective.revision, value='continue'))
    values = {item_id(a.node_id): a.value for a in effective.history
              if a.node_id not in CONTINUE_PAGES}
    # Preliminary answers stay facts even when a revised route no longer asks them.
    for node, spec in PRELIMINARY_FIELDS.items():
        entry = effective.session.preliminary_fields.get(spec['tag'])
        if entry and node == 'guided_original_creditor' and not any(
                a.node_id == node for a in effective.history):
            values[spec['field']] = str(entry.value) if entry.value is not None else entry.status
    # Capture deterministic condition results, using the tree's stable node IDs.
    values.update(effective.calculations)
    visited = {a.node_id for a in effective.history}
    defenses = {}
    for name, spec in DEFENSES.items():
        offered = any(TREE.node(a.node_id).selection_checkboxes and any(
            b.defense_id == name for b in TREE.node(a.node_id).selection_checkboxes)
            for a in effective.history if a.node_id in TREE.node_map)
        definition = TREE.node_map.get(effective.current)
        if definition:
            offered |= any(b.defense_id == name for b in definition.selection_checkboxes)
        checked = any(v == 'include' for v in effective.session.checkbox_selections.get(name, {}).values())
        settled = (name in effective.finish_reasons or spec['summary'] in visited
                   or effective.current == spec['summary']
                   or (name == 'statute_of_limitations' and effective.current == 'sol_written')
                   or PARENT_SCREENS.get(effective.current) == name
                   or (effective.current in ACTION_SCREENS and definition
                       and name in defense_for(effective.current)
                       and (definition.action or '').startswith('script_finish:')))
        # Reaching a checkbox question establishes an offer; starting the defense
        # does not. A negative result needs the completed no-offer path.
        projection = 'Yes' if offered else 'No' if settled else ''
        # Any explicit inclusion settles the aggregate positively. A negative
        # result must wait for every offered choice (including SOL sub-boxes).
        selection = 'Yes' if checked else 'No' if settled else ''
        defenses[name] = {'CHECKED': selection, 'TREE.PROJECTION': projection}
        for field, answer in defenses[name].items():
            if answer:
                values[f'DEFENSE.{name}.{field}'] = answer
    pending = set()
    if current.revision and effective.current != COMPLETE:
        current_defense = effective._current_defense()
        order = list(DEFENSES)
        pending = set(order[order.index(current_defense) + 1:])
        if effective.current in PRELIMINARY_FIELDS:
            pending = set(DEFENSES)
    return values, defenses, pending


class GuidedCollection:
    """SQLite is authoritative; CSVs are atomically replaced after each write.

    One local prototype server owns an output directory. A lock serializes its
    worker threads, and database transactions protect the longitudinal event log.
    """
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        digest = hashlib.sha256()
        for filename in ('interactive_tree.yaml', 'guided_preliminary_fields.yaml',
                         'guided_defense_content.yaml', 'guided_script_formatting.yaml',
                         'guided_script_formatting.py', 'guided_screen_layout.yaml', 'sol_checkbox_dependencies.yaml',
                         'guided_sol.py', 'affirmative_defenses.py', 'sol_dependency_map.py',
                         'session.py', 'preliminary.py', 'guided_collection.py'):
            digest.update(Path(__file__).with_name(filename).read_bytes())
        self.version = 'guided-17-defenses-2026-11-10-' + digest.hexdigest()[:16]
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (session_id TEXT, event_id TEXT,
                    PRIMARY KEY (session_id, event_id));
                CREATE TABLE IF NOT EXISTS responses (sequence INTEGER PRIMARY KEY,
                    session_id TEXT NOT NULL, data TEXT NOT NULL);
            ''')
        with self.lock:
            self.export()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.directory / 'collection.sqlite3')
        try:
            with db:
                yield db
        finally:
            db.close()

    def start(self, session_id: UUID):
        with self.lock, self.connect() as db:
            row = db.execute('SELECT data FROM sessions WHERE id=?', (str(session_id),)).fetchone()
            if row:
                data = json.loads(row[0])
                data['session']['SESSION.END.TIME'] = ''
            else:
                data = {'session': dict(zip(SESSION_COLUMNS, [str(session_id), now(), '', 'No', self.version])),
                        'values': {}, 'revisions': {}, 'defenses': {
                            name: {'CHECKED': '', 'CHANGED': 0, 'TREE.PROJECTION': ''} for name in DEFENSES}}
            self.save(db, session_id, data)
        self.refresh()

    @staticmethod
    def save(db, session_id, data):
        db.execute('INSERT OR REPLACE INTO sessions VALUES (?, ?)', (str(session_id), json.dumps(data)))

    def record(self, context: CollectionContext, current: GuidedSolReview, node: str, value: str):
        values, defenses, pending = snapshot(current)
        submitted = item_id(node)
        with self.lock, self.connect() as db:
            if db.execute('SELECT 1 FROM operations WHERE session_id=? AND event_id=?',
                          (str(context.session_id), str(context.event_id))).fetchone():
                return
            row = db.execute('SELECT data FROM sessions WHERE id=?', (str(context.session_id),)).fetchone()
            if not row:
                raise ValueError('Start a collection session before recording answers.')
            data = json.loads(row[0])
            for name in DEFENSES:
                data['defenses'].setdefault(name, {'CHECKED': '', 'CHANGED': 0, 'TREE.PROJECTION': ''})
            previous = data['values']
            # An unanswered question can stop reconciliation before later
            # defenses. Their records are pending replay, not invalidated.
            for key, answer in previous.items():
                owners = defense_for(key)
                if key.startswith('DEFENSE.'):
                    owners = {key.split('.')[1]}
                if owners & pending:
                    values[key] = answer
            for defense in pending:
                defenses[defense] = {key: data['defenses'][defense][key]
                                    for key in ('CHECKED', 'TREE.PROJECTION')}
            end = context.ended_at.isoformat(timespec='milliseconds')
            start = context.displayed_at.isoformat(timespec='milliseconds')
            if context.ended_at < context.displayed_at:
                raise ValueError('A response cannot end before it is displayed.')
            if context.checked_at is not None and not (
                    context.displayed_at <= context.checked_at <= context.ended_at):
                raise ValueError('The answer check time must be between display and submission.')
            checked = context.checked_at.isoformat(timespec='milliseconds') if context.checked_at else 'NA'

            def event(key, answer, kind, began=start, check='NA', ended=end):
                revision = data['revisions'].get(key, -1) + 1
                data['revisions'][key] = revision
                record = dict(zip(RESPONSE_COLUMNS, [str(context.session_id), key, answer, kind,
                    revision, began, check, ended]))
                db.execute('INSERT INTO responses(session_id, data) VALUES (?, ?)',
                           (str(context.session_id), json.dumps(record)))

            if node not in CONTINUE_PAGES:
                kind = 'User change' if submitted in data['revisions'] else 'First submission'
                if submitted not in previous or previous[submitted] != value:
                    event(submitted, value, kind, check=checked)
                    if kind == 'User change':
                        for defense in defense_for(node):
                            data['defenses'][defense]['CHANGED'] = 1
            computed_at = now()
            for key in previous.keys() - values.keys():
                event(key, '', 'Program invalidation', began=computed_at, ended=computed_at)
            for key, answer in values.items():
                if key == submitted and node not in CONTINUE_PAGES:
                    continue
                if key not in previous or previous[key] != answer:
                    event(key, answer, 'Program calculation', began=computed_at, ended=computed_at)
            data['values'] = values
            for defense, fields in defenses.items():
                data['defenses'][defense].update(fields)
            data['session']['SESSION.COMPLETED'] = 'Yes' if current.current == COMPLETE else 'No'
            self.save(db, context.session_id, data)
            db.execute('INSERT INTO operations VALUES (?, ?)', (str(context.session_id), str(context.event_id)))
        self.refresh()

    def end(self, session_id: UUID):
        with self.lock, self.connect() as db:
            row = db.execute('SELECT data FROM sessions WHERE id=?', (str(session_id),)).fetchone()
            if not row:
                raise ValueError('Unknown collection session.')
            data = json.loads(row[0])
            data['session']['SESSION.END.TIME'] = now()
            self.save(db, session_id, data)
        self.refresh()

    def refresh(self):
        with self.lock:
            self.export()

    def export(self):
        with self.connect() as db:
            sessions = [json.loads(row[0]) for row in db.execute('SELECT data FROM sessions ORDER BY rowid')]
            responses = [json.loads(row[0]) for row in db.execute('SELECT data FROM responses ORDER BY sequence')]
        defense_rows = []
        for data in sessions:
            row = {'SESSION.ID': data['session']['SESSION.ID']}
            row.update({f'DEFENSE.{name}.{key}': value for name, fields in data['defenses'].items()
                        for key, value in fields.items()})
            defense_rows.append(row)
        # Preserve historical defense columns when an earlier prototype used this directory.
        defense_columns = list(DEFENSE_COLUMNS)
        for row in defense_rows:
            defense_columns.extend(key for key in row if key not in defense_columns)
        for filename, columns, rows in [
            ('sessions.csv', SESSION_COLUMNS, [d['session'] for d in sessions]),
            ('defenses.csv', defense_columns, defense_rows),
            ('responses.csv', RESPONSE_COLUMNS, responses),
        ]:
            temporary = self.directory / (filename + '.tmp')
            with temporary.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temporary, self.directory / filename)
