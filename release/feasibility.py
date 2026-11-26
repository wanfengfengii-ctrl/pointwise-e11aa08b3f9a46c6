from dataclasses import dataclass

from program.catalog import ProgramRevision
from program.editions import Edition, available_windows
from program.narration import NarrationSegment


Schedule = tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class DecisionBasis:
    confirmation_tick: int | None
    shared_starts: Schedule
    edition_starts: tuple[tuple[str, Schedule], ...]


@dataclass(frozen=True)
class FeasibilityResult:
    eligible: bool
    reason: str
    basis: DecisionBasis | None = None


def _first_start(windows, free_tick, length, deadline):
    for window in windows:
        start = max(free_tick, window.start)
        if start + length <= min(window.end, deadline):
            return start
    return None


def _prefixes(segments, windows, deadlines, first_tick=0):
    # With the same remaining segments, an earlier free tick can wait and copy
    # every continuation of a later one. Keep the earliest witness for each set.
    layer = {segments: (first_tick, ())}
    while layer:
        following = {}
        for remaining, (free_tick, prefix) in layer.items():
            yield remaining, free_tick, prefix
            for index, segment in enumerate(remaining):
                start = _first_start(
                    windows, free_tick, segment.length, deadlines[segment.segment_id]
                )
                if start is None:
                    continue
                rest = remaining[:index] + remaining[index + 1:]
                finish = start + segment.length
                old = following.get(rest)
                if old is None or finish < old[0]:
                    following[rest] = (finish, prefix + ((start, segment.segment_id),))
        layer = following


def _single_schedule(edition: Edition, segments: tuple[NarrationSegment, ...], first_tick: int) -> Schedule | None:
    deadlines = {segment.segment_id: segment.deadline_for(edition.edition_id) for segment in segments}
    for remaining, _, schedule in _prefixes(segments, available_windows(edition), deadlines, first_tick):
        if not remaining:
            return schedule
    return None


def find_single_edition_schedule(revision: ProgramRevision, edition_id: str) -> Schedule | None:
    return _single_schedule(revision.edition(edition_id), revision.segments, 0)


def assess_feasibility(revision: ProgramRevision) -> FeasibilityResult:
    edition = revision.editions[0]
    schedule = find_single_edition_schedule(revision, edition.edition_id)
    if schedule is None:
        reason = 'no_complete_schedule' if len(revision.editions) == 1 else 'no_common_schedule'
        return FeasibilityResult(False, reason)
    basis = DecisionBasis(None, (), ((edition.edition_id, schedule),))
    return FeasibilityResult(True, 'feasible', basis)
