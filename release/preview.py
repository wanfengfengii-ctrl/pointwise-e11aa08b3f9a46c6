from dataclasses import dataclass
import sqlite3

from program.catalog import ProgramRevision
from program.repository import get_program_revision
from release.feasibility import DecisionBasis, assess_feasibility


@dataclass(frozen=True)
class PreviewResult:
    revision_id: int
    revision: ProgramRevision
    eligible: bool
    reason: str
    basis: DecisionBasis | None

    def public_view(self) -> dict:
        return {'revision_id': self.revision_id, 'eligible': self.eligible, 'reason': self.reason}


def preview_revision(connection: sqlite3.Connection, revision_id: int) -> PreviewResult:
    revision = get_program_revision(connection, revision_id)
    result = assess_feasibility(revision)
    return PreviewResult(revision_id, revision, result.eligible, result.reason, result.basis)
