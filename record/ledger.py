from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class PlaybackInterval:
    segment_id: str
    start_tick: int
    end_tick: int | None


def initialize_ledger(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS playback_intervals (
            show_id INTEGER NOT NULL REFERENCES show_sessions(show_id),
            segment_id TEXT NOT NULL,
            start_tick INTEGER NOT NULL CHECK (start_tick >= 0),
            end_tick INTEGER CHECK (end_tick > start_tick),
            PRIMARY KEY (show_id, segment_id)
        )
    ''')


def record_start(connection: sqlite3.Connection, show_id: int, segment_id: str, tick: int) -> None:
    connection.execute('''
        INSERT INTO playback_intervals (show_id, segment_id, start_tick) VALUES (?, ?, ?)
    ''', (show_id, segment_id, tick))


def record_end(connection: sqlite3.Connection, show_id: int, segment_id: str, tick: int) -> None:
    cursor = connection.execute('''
        UPDATE playback_intervals SET end_tick = ?
        WHERE show_id = ? AND segment_id = ? AND end_tick IS NULL AND start_tick < ?
    ''', (tick, show_id, segment_id, tick))
    if cursor.rowcount != 1:
        raise RuntimeError('playback end requires an unfinished start')


def list_intervals(connection: sqlite3.Connection, show_id: int) -> tuple[PlaybackInterval, ...]:
    rows = connection.execute('''
        SELECT segment_id, start_tick, end_tick FROM playback_intervals
        WHERE show_id = ? ORDER BY start_tick, segment_id
    ''', (show_id,))
    return tuple(PlaybackInterval(*row) for row in rows)
