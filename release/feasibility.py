from dataclasses import dataclass

from program.catalog import ProgramRevision
from program.editions import Edition, TickWindow, available_windows
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


def _prefixes(segments, windows, deadlines, first_tick=0, latest_start=None):
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
                if latest_start is not None and start > latest_start:
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


def _intersect_windows(left: tuple, right: tuple) -> tuple:
    intersections = []
    left_index = right_index = 0
    while left_index < len(left) and right_index < len(right):
        first = left[left_index]
        second = right[right_index]
        start = max(first.start, second.start)
        end = min(first.end, second.end)
        if start < end:
            intersections.append(TickWindow(start, end))
        if first.end < second.end:
            left_index += 1
        elif second.end < first.end:
            right_index += 1
        else:
            left_index += 1
            right_index += 1
    return tuple(intersections)


def _common_opening_constraints(revision: ProgramRevision):
    windows = available_windows(revision.editions[0])
    for edition in revision.editions[1:]:
        windows = _intersect_windows(windows, available_windows(edition))
    deadlines = {
        segment.segment_id: min(
            segment.deadline_for(edition.edition_id) for edition in revision.editions
        )
        for segment in revision.segments
    }
    return windows, deadlines


def assess_feasibility(revision: ProgramRevision) -> FeasibilityResult:
    if len(revision.editions) == 1:
        edition = revision.editions[0]
        schedule = find_single_edition_schedule(revision, edition.edition_id)
        if schedule is None:
            return FeasibilityResult(False, 'no_complete_schedule')
        basis = DecisionBasis(None, (), ((edition.edition_id, schedule),))
        return FeasibilityResult(True, 'feasible', basis)

    confirmation_tick = revision.confirmation_tick
    if confirmation_tick is None:
        raise RuntimeError('dual-edition programme has no confirmation tick')

    common_windows, common_deadlines = _common_opening_constraints(revision)
    shared_prefixes = tuple(
        _prefixes(
            revision.segments,
            common_windows,
            common_deadlines,
            latest_start=confirmation_tick - 1,
        )
    )

    # A prefix ending after the confirmation tick has its last segment on air
    # across the signal. Its finish tick is the earliest free point for the
    # edition-specific continuation. An earlier finish waits until the signal.
    for remaining, prefix_finish, shared_starts in shared_prefixes:
        continuation_tick = max(confirmation_tick, prefix_finish)
        edition_starts = []
        for edition in revision.editions:
            schedule = _single_schedule(edition, remaining, continuation_tick)
            if schedule is None:
                break
            edition_starts.append((edition.edition_id, schedule))
        else:
            basis = DecisionBasis(
                confirmation_tick, shared_starts, tuple(edition_starts)
            )
            return FeasibilityResult(True, 'feasible', basis)

    return FeasibilityResult(False, 'no_common_schedule')
