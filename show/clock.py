from dataclasses import dataclass
import sqlite3

from record.ledger import record_end, record_start
from release.repository import get_issued_program
from show.playback import TickAction, apply_tick_action, decide_tick_action
from show.repository import ShowSession, load_show, save_show_progress
from show.signal_input import accept_signals


class AdvanceConflict(Exception):
    pass


@dataclass(frozen=True)
class AdvanceResult:
    tick: int
    action: TickAction
    show: ShowSession
    ended_segment: str | None


def require_next_tick(show: ShowSession, tick: int) -> None:
    if show.closed:
        raise AdvanceConflict('show_already_closed')
    if type(tick) is not int or tick != show.next_tick:
        raise ValueError(f'expected_next_tick_{show.next_tick}')


def advance_show(
    connection: sqlite3.Connection, show_id: int, tick: int, signal: str | None
) -> AdvanceResult:
    show = load_show(connection, show_id)
    require_next_tick(show, tick)
    issued = get_issued_program(connection, show.issue_id)
    observed = accept_signals(issued.revision, show, tick, signal)

    if observed.edition_id is None:
        horizon = min(edition.length for edition in issued.revision.editions)
    else:
        horizon = issued.revision.edition(observed.edition_id).length
    if tick >= horizon:
        raise AdvanceConflict('edition_has_ended')

    action = decide_tick_action(issued, observed)
    updated, ended_segment = apply_tick_action(issued, observed, action)
    if action.kind == 'start':
        record_start(connection, show_id, action.segment_id, tick)
    if ended_segment is not None:
        record_end(connection, show_id, ended_segment, updated.next_tick)
    save_show_progress(connection, updated, expected_tick=tick)
    return AdvanceResult(tick, action, updated, ended_segment)
