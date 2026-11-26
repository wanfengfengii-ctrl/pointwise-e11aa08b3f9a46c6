import json
import sqlite3

from program.catalog import ProgramRevision, decode_revision, encode_revision


def initialize_program_store(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS program_revisions (
            revision_id INTEGER PRIMARY KEY,
            payload TEXT NOT NULL
        )
    ''')


def save_program_revision(connection: sqlite3.Connection, revision: ProgramRevision) -> int:
    cursor = connection.execute(
        'INSERT INTO program_revisions (payload) VALUES (?)',
        (json.dumps(encode_revision(revision), ensure_ascii=False),),
    )
    return cursor.lastrowid


def get_program_revision(connection: sqlite3.Connection, revision_id: int) -> ProgramRevision:
    row = connection.execute(
        'SELECT payload FROM program_revisions WHERE revision_id = ?', (revision_id,)
    ).fetchone()
    if row is None:
        raise LookupError('revision_not_found')
    return decode_revision(json.loads(row[0]))
