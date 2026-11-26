from dataclasses import dataclass, replace

from program.editions import fits_narration
from release.repository import IssuedProgram
from show.repository import ActiveSegment, ShowSession


@dataclass(frozen=True)
class TickAction:
    kind: str
    segment_id: str | None = None


def decide_tick_action(issued: IssuedProgram, show: ShowSession) -> TickAction:
    tick = show.next_tick
    if show.active is not None:
        return TickAction('continue', show.active.segment_id)

    edition_schedules = dict(issued.basis.edition_starts)
    if show.edition_id is None:
        # Before a dual-edition confirmation the audience has one observation.
        # Edition-specific starts may only be consulted after the signal.
        starts = issued.basis.shared_starts
        checked_editions = issued.revision.editions
    else:
        edition = issued.revision.edition(show.edition_id)
        starts = issued.basis.shared_starts + edition_schedules[edition.edition_id]
        checked_editions = (edition,)

    segment_id = next((segment_id for start, segment_id in starts if start == tick), None)
    if segment_id is None:
        return TickAction('wait')
    if segment_id not in show.remaining:
        raise RuntimeError('issued start is not for a pending narration segment')

    segment = issued.revision.segment(segment_id)
    for edition in checked_editions:
        if not fits_narration(
            edition, tick, segment.length, segment.deadline_for(edition.edition_id)
        ):
            raise RuntimeError('issued start does not fit the scheduled edition constraints')
    return TickAction('start', segment_id)


def apply_tick_action(
    issued: IssuedProgram, show: ShowSession, action: TickAction
) -> tuple[ShowSession, str | None]:
    next_tick = show.next_tick + 1
    active = show.active
    remaining = show.remaining
    completed = show.completed

    if action.kind == 'start':
        if active is not None or action.segment_id not in remaining:
            raise RuntimeError('start conflicts with current playback')
        segment = issued.revision.segment(action.segment_id)
        active = ActiveSegment(segment.segment_id, show.next_tick, show.next_tick + segment.length)
        remaining = tuple(segment_id for segment_id in remaining if segment_id != segment.segment_id)
    elif action.kind == 'continue':
        if active is None or active.segment_id != action.segment_id:
            raise RuntimeError('continuation does not match active narration')
    elif action.kind != 'wait' or active is not None:
        raise RuntimeError('cannot wait while narration is active')

    ended = None
    if active is not None and active.finish_tick == next_tick:
        ended = active.segment_id
        completed += (ended,)
        active = None
    return replace(show, next_tick=next_tick, remaining=remaining, completed=completed, active=active), ended
