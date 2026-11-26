import sqlite3

from booth.sessions import change_operator
from booth.status import BoothStatus, read_booth_status


def handover_show(
    connection: sqlite3.Connection, booth: str, show_id: int, operator: str
) -> BoothStatus:
    change_operator(connection, booth, show_id, operator)
    return read_booth_status(connection, booth)
