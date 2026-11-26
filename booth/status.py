from dataclasses import asdict, dataclass
import sqlite3

from booth.sessions import BoothAssignment, load_assignment
from record.ledger import PlaybackInterval, list_intervals
from show.repository import ShowSession, load_show, show_view


@dataclass(frozen=True)
class BoothStatus:
    assignment: BoothAssignment
    show: ShowSession | None
    intervals: tuple[PlaybackInterval, ...]

    def public_view(self) -> dict:
        return {
            'assignment': asdict(self.assignment),
            'show': show_view(self.show) if self.show is not None else None,
            'intervals': [asdict(interval) for interval in self.intervals],
        }


def read_booth_status(connection: sqlite3.Connection, booth: str) -> BoothStatus:
    assignment = load_assignment(connection, booth)
    if assignment is None:
        raise LookupError('booth_not_found')
    if assignment.show_id is None:
        return BoothStatus(assignment, None, ())
    show = load_show(connection, assignment.show_id)
    return BoothStatus(assignment, show, list_intervals(connection, show.show_id))
