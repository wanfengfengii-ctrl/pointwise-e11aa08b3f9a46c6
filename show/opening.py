import sqlite3

from booth.sessions import BoothConflict, bind_show, load_assignment
from release.repository import get_issued_program
from show.repository import ShowSession, insert_show


def start_show(connection: sqlite3.Connection, booth: str, issue_id: int) -> ShowSession:
    assignment = load_assignment(connection, booth)
    if assignment is None:
        raise BoothConflict('booth_not_mounted')
    if assignment.show_id is not None:
        raise BoothConflict('booth_occupied')
    if assignment.issue_id != issue_id:
        raise BoothConflict('issue_does_not_match_mount')

    issued = get_issued_program(connection, assignment.issue_id)
    revision = issued.revision
    known_edition = revision.editions[0].edition_id if len(revision.editions) == 1 else None
    show = insert_show(
        connection, booth, assignment.mount_id, issued.issue_id,
        known_edition, tuple(segment.segment_id for segment in revision.segments),
    )
    bind_show(connection, assignment, show.show_id)
    return show
