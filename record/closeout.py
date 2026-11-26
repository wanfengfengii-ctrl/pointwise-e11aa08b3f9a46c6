from dataclasses import asdict, dataclass
import json
import sqlite3

from record.completion import CompletionResult, evaluate_completion
from record.ledger import PlaybackInterval, list_intervals
from release.repository import IssuedProgram
from show.repository import ShowSession


@dataclass(frozen=True)
class CloseoutSummary:
    closeout_id: int
    show_id: int
    issue_id: int
    edition_id: str | None
    signal: str | None
    closed_at_tick: int
    intervals: tuple[PlaybackInterval, ...]


def initialize_closeout_store(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS closeouts (
            closeout_id INTEGER PRIMARY KEY,
            show_id INTEGER NOT NULL UNIQUE REFERENCES show_sessions(show_id),
            summary TEXT NOT NULL
        )
    ''')


def close_show(
    connection: sqlite3.Connection, issued: IssuedProgram, show: ShowSession
) -> tuple[CompletionResult, CloseoutSummary | None]:
    intervals = list_intervals(connection, show.show_id)
    completion = evaluate_completion(issued, show, intervals)
    if not completion.complete:
        return completion, None

    payload = {
        'issue_id': show.issue_id,
        'edition_id': show.edition_id,
        'signal': show.signal,
        'closed_at_tick': show.next_tick,
        'intervals': [asdict(interval) for interval in intervals],
    }
    cursor = connection.execute(
        'INSERT INTO closeouts (show_id, summary) VALUES (?, ?)',
        (show.show_id, json.dumps(payload, ensure_ascii=False)),
    )
    return completion, CloseoutSummary(
        cursor.lastrowid, show.show_id, show.issue_id, show.edition_id, show.signal, show.next_tick, intervals
    )


def _decode_summary(row) -> CloseoutSummary | None:
    if row is None:
        return None
    closeout_id, show_id, raw = row
    payload = json.loads(raw)
    payload['intervals'] = tuple(PlaybackInterval(**item) for item in payload['intervals'])
    return CloseoutSummary(closeout_id, show_id, **payload)


def find_closeout_by_show(connection: sqlite3.Connection, show_id: int) -> CloseoutSummary | None:
    row = connection.execute(
        'SELECT closeout_id, show_id, summary FROM closeouts WHERE show_id = ?', (show_id,)
    ).fetchone()
    return _decode_summary(row)


def find_closeout_by_number(connection: sqlite3.Connection, closeout_id: int) -> CloseoutSummary | None:
    row = connection.execute(
        'SELECT closeout_id, show_id, summary FROM closeouts WHERE closeout_id = ?', (closeout_id,)
    ).fetchone()
    return _decode_summary(row)
