from dataclasses import replace

from program.catalog import ProgramRevision
from program.signals import find_signal_definition
from show.repository import ShowSession


class SignalRequired(Exception):
    pass


def accept_signals(
    revision: ProgramRevision, show: ShowSession, tick: int, code: str | None
) -> ShowSession:
    if code is None:
        if show.edition_id is None and tick == revision.confirmation_tick:
            raise SignalRequired('signal_required')
        return show

    definition = find_signal_definition(revision.signals, code)
    if definition is None:
        raise ValueError('unknown_signal')
    if definition.tick != tick:
        raise ValueError('signal_at_wrong_tick')
    if show.signal is not None:
        raise ValueError('signal_already_accepted')
    if show.edition_id is not None and show.edition_id != definition.edition_id:
        raise ValueError('signal_conflicts_with_edition')
    return replace(show, edition_id=definition.edition_id, signal=code)
