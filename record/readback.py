from dataclasses import asdict
import sqlite3

from record.closeout import find_closeout_by_number, find_closeout_by_show
from record.ledger import list_intervals
from show.repository import load_show, show_view


def read_show_record(
    connection: sqlite3.Connection, *, show_id: int | None = None, closeout_id: int | None = None
) -> dict:
    if (show_id is None) == (closeout_id is None):
        raise ValueError('provide exactly one of show_id and closeout_id')
    if closeout_id is not None:
        summary = find_closeout_by_number(connection, closeout_id)
        if summary is None:
            raise LookupError('closeout_not_found')
        show_id = summary.show_id
    else:
        summary = find_closeout_by_show(connection, show_id)

    show = load_show(connection, show_id)
    intervals = summary.intervals if summary is not None else list_intervals(connection, show_id)
    return {
        'show': show_view(show),
        'intervals': [asdict(interval) for interval in intervals],
        'closeout': asdict(summary) if summary is not None else None,
    }
