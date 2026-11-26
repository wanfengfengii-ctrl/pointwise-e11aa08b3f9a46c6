from dataclasses import asdict, dataclass
import json
import sqlite3

from program.catalog import ProgramRevision, decode_revision, encode_revision
from release.feasibility import DecisionBasis


@dataclass(frozen=True)
class IssuedProgram:
    issue_id: int
    revision_id: int
    revision: ProgramRevision
    basis: DecisionBasis


def initialize_issue_store(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS issued_programs (
            issue_id INTEGER PRIMARY KEY,
            revision_id INTEGER NOT NULL REFERENCES program_revisions(revision_id),
            snapshot TEXT NOT NULL,
            decision_basis TEXT NOT NULL
        )
    ''')


def save_issued_program(
    connection: sqlite3.Connection, revision_id: int, revision: ProgramRevision, basis: DecisionBasis
) -> IssuedProgram:
    cursor = connection.execute('''
        INSERT INTO issued_programs (revision_id, snapshot, decision_basis) VALUES (?, ?, ?)
    ''', (
        revision_id,
        json.dumps(encode_revision(revision), ensure_ascii=False),
        json.dumps(asdict(basis), ensure_ascii=False),
    ))
    return IssuedProgram(cursor.lastrowid, revision_id, revision, basis)


def get_issued_program(connection: sqlite3.Connection, issue_id: int) -> IssuedProgram:
    row = connection.execute('''
        SELECT revision_id, snapshot, decision_basis FROM issued_programs WHERE issue_id = ?
    ''', (issue_id,)).fetchone()
    if row is None:
        raise LookupError('issue_not_found')
    revision_id, snapshot, encoded_basis = row
    value = json.loads(encoded_basis)
    basis = DecisionBasis(
        value['confirmation_tick'],
        tuple((tick, segment_id) for tick, segment_id in value['shared_starts']),
        tuple(
            (edition_id, tuple((tick, segment_id) for tick, segment_id in starts))
            for edition_id, starts in value['edition_starts']
        ),
    )
    return IssuedProgram(issue_id, revision_id, decode_revision(json.loads(snapshot)), basis)
