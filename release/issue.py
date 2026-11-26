import sqlite3

from release.preview import PreviewResult, preview_revision
from release.repository import IssuedProgram, save_issued_program


def issue_revision(
    connection: sqlite3.Connection, revision_id: int
) -> tuple[PreviewResult, IssuedProgram | None]:
    preview = preview_revision(connection, revision_id)
    if not preview.eligible:
        return preview, None
    if preview.basis is None:
        raise RuntimeError('eligible preview has no decision basis')
    issued = save_issued_program(connection, preview.revision_id, preview.revision, preview.basis)
    return preview, issued
