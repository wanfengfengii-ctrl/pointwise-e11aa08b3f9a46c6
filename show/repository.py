from dataclasses import asdict, dataclass
import json
import sqlite3


@dataclass(frozen=True)
class ActiveSegment:
    segment_id: str
    start_tick: int
    finish_tick: int


@dataclass(frozen=True)
class ShowSession:
    show_id: int
    booth: str
    mount_id: int
    issue_id: int
    next_tick: int
    edition_id: str | None
    signal: str | None
    remaining: tuple[str, ...]
    active: ActiveSegment | None
    completed: tuple[str, ...]
    closed: bool


def show_view(show: ShowSession) -> dict:
    view = asdict(show)
    if show.active is not None:
        view['active'] = {
            'segment_id': show.active.segment_id,
            'start_tick': show.active.start_tick,
            'remaining_ticks': show.active.finish_tick - show.next_tick,
        }
    return view


def initialize_show_store(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS show_sessions (
            show_id INTEGER PRIMARY KEY,
            booth TEXT NOT NULL,
            mount_id INTEGER NOT NULL REFERENCES booth_mounts(mount_id),
            issue_id INTEGER NOT NULL REFERENCES issued_programs(issue_id),
            next_tick INTEGER NOT NULL CHECK (next_tick >= 0),
            edition_id TEXT,
            signal TEXT,
            remaining TEXT NOT NULL,
            active TEXT,
            completed TEXT NOT NULL,
            closed INTEGER NOT NULL DEFAULT 0 CHECK (closed IN (0, 1))
        )
    ''')


def insert_show(
    connection: sqlite3.Connection, booth: str, mount_id: int, issue_id: int,
    edition_id: str | None, remaining: tuple[str, ...],
) -> ShowSession:
    cursor = connection.execute('''
        INSERT INTO show_sessions (booth, mount_id, issue_id, next_tick, edition_id, remaining, completed)
        VALUES (?, ?, ?, 0, ?, ?, '[]')
    ''', (booth, mount_id, issue_id, edition_id, json.dumps(remaining, ensure_ascii=False)))
    return ShowSession(cursor.lastrowid, booth, mount_id, issue_id, 0, edition_id, None, remaining, None, (), False)


def load_show(connection: sqlite3.Connection, show_id: int) -> ShowSession:
    row = connection.execute('''
        SELECT booth, mount_id, issue_id, next_tick, edition_id, signal, remaining, active, completed, closed
        FROM show_sessions WHERE show_id = ?
    ''', (show_id,)).fetchone()
    if row is None:
        raise LookupError('show_not_found')
    booth, mount_id, issue_id, tick, edition_id, signal, remaining, active, completed, closed = row
    return ShowSession(
        show_id, booth, mount_id, issue_id, tick, edition_id, signal,
        tuple(json.loads(remaining)), ActiveSegment(**json.loads(active)) if active is not None else None,
        tuple(json.loads(completed)), bool(closed),
    )


def save_show_progress(connection: sqlite3.Connection, show: ShowSession, expected_tick: int) -> None:
    active = None if show.active is None else json.dumps(asdict(show.active), ensure_ascii=False)
    cursor = connection.execute('''
        UPDATE show_sessions
        SET next_tick = ?, edition_id = ?, signal = ?, remaining = ?, active = ?, completed = ?
        WHERE show_id = ? AND next_tick = ? AND closed = 0
    ''', (
        show.next_tick, show.edition_id, show.signal, json.dumps(show.remaining, ensure_ascii=False),
        active, json.dumps(show.completed, ensure_ascii=False), show.show_id, expected_tick,
    ))
    if cursor.rowcount != 1:
        raise RuntimeError('show progress was not updated')


def mark_show_closed(connection: sqlite3.Connection, show_id: int) -> None:
    cursor = connection.execute(
        'UPDATE show_sessions SET closed = 1 WHERE show_id = ? AND closed = 0', (show_id,)
    )
    if cursor.rowcount != 1:
        raise RuntimeError('show was not closed')
