import sqlite3

from booth.sessions import BoothAssignment, BoothConflict, load_assignment, save_mount
from release.repository import get_issued_program


def mount_issue(
    connection: sqlite3.Connection, booth: str, issue_id: int, operator: str
) -> BoothAssignment:
    get_issued_program(connection, issue_id)
    current = load_assignment(connection, booth)
    if current is not None and current.show_id is not None:
        raise BoothConflict('booth_occupied')
    return save_mount(connection, booth, issue_id, operator)
