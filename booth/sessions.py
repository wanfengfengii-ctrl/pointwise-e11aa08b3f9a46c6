from dataclasses import dataclass
import sqlite3


class BoothConflict(Exception):
    pass


@dataclass(frozen=True)
class BoothAssignment:
    booth: str
    mount_id: int
    issue_id: int
    operator: str
    show_id: int | None


def initialize_booth_store(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS booth_mounts (
            mount_id INTEGER PRIMARY KEY,
            booth TEXT NOT NULL,
            issue_id INTEGER NOT NULL REFERENCES issued_programs(issue_id)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS booth_assignments (
            booth TEXT PRIMARY KEY,
            mount_id INTEGER NOT NULL UNIQUE REFERENCES booth_mounts(mount_id),
            operator TEXT NOT NULL,
            show_id INTEGER UNIQUE REFERENCES show_sessions(show_id)
        )
    ''')


def load_assignment(connection: sqlite3.Connection, booth: str) -> BoothAssignment | None:
    row = connection.execute('''
        SELECT current.booth, current.mount_id, mounts.issue_id, current.operator, current.show_id
        FROM booth_assignments AS current
        JOIN booth_mounts AS mounts ON current.mount_id = mounts.mount_id
        WHERE current.booth = ?
    ''', (booth,)).fetchone()
    return BoothAssignment(*row) if row is not None else None


def save_mount(connection: sqlite3.Connection, booth: str, issue_id: int, operator: str) -> BoothAssignment:
    mount_id = connection.execute(
        'INSERT INTO booth_mounts (booth, issue_id) VALUES (?, ?)', (booth, issue_id)
    ).lastrowid
    cursor = connection.execute('''
        INSERT INTO booth_assignments (booth, mount_id, operator) VALUES (?, ?, ?)
        ON CONFLICT(booth) DO UPDATE SET mount_id = excluded.mount_id, operator = excluded.operator
        WHERE booth_assignments.show_id IS NULL
    ''', (booth, mount_id, operator))
    if cursor.rowcount != 1:
        raise BoothConflict('booth_occupied')
    return BoothAssignment(booth, mount_id, issue_id, operator, None)


def bind_show(connection: sqlite3.Connection, assignment: BoothAssignment, show_id: int) -> None:
    cursor = connection.execute('''
        UPDATE booth_assignments SET show_id = ?
        WHERE booth = ? AND mount_id = ? AND show_id IS NULL
    ''', (show_id, assignment.booth, assignment.mount_id))
    if cursor.rowcount != 1:
        raise BoothConflict('mount_changed_or_occupied')


def change_operator(connection: sqlite3.Connection, booth: str, show_id: int, operator: str) -> None:
    cursor = connection.execute('''
        UPDATE booth_assignments SET operator = ? WHERE booth = ? AND show_id = ?
    ''', (operator, booth, show_id))
    if cursor.rowcount != 1:
        raise BoothConflict('show_does_not_match_booth')


def release_show(connection: sqlite3.Connection, booth: str, show_id: int) -> None:
    cursor = connection.execute('''
        UPDATE booth_assignments SET show_id = NULL WHERE booth = ? AND show_id = ?
    ''', (booth, show_id))
    if cursor.rowcount != 1:
        raise BoothConflict('show_does_not_match_booth')
