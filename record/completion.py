from dataclasses import dataclass

from program.editions import fits_narration
from record.ledger import PlaybackInterval
from release.repository import IssuedProgram
from show.repository import ShowSession


@dataclass(frozen=True)
class CompletionResult:
    missing: tuple[str, ...]
    unfinished: tuple[str, ...]
    inconsistent: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not (self.missing or self.unfinished or self.inconsistent)


def evaluate_completion(
    issued: IssuedProgram, show: ShowSession, intervals: tuple[PlaybackInterval, ...]
) -> CompletionResult:
    required = {segment.segment_id: segment for segment in issued.revision.segments}
    by_segment = {interval.segment_id: interval for interval in intervals}
    seen = set(by_segment)
    completed = set(show.completed)
    missing = set(required) - seen
    unfinished = set(show.remaining)
    if show.active is not None:
        unfinished.add(show.active.segment_id)

    inconsistent = (seen | completed | unfinished) - set(required)
    editions = issued.revision.editions
    if show.edition_id is not None:
        editions = (issued.revision.edition(show.edition_id),)

    previous_end = 0
    for interval in intervals:
        segment_id = interval.segment_id
        if interval.end_tick is None:
            unfinished.add(segment_id)
            if segment_id in completed:
                inconsistent.add(segment_id)
            continue
        segment = required.get(segment_id)
        if (
            segment is None or segment_id not in completed
            or interval.end_tick - interval.start_tick != segment.length
            or interval.start_tick < previous_end or interval.end_tick > show.next_tick
            or not all(
                fits_narration(edition, interval.start_tick, segment.length, segment.deadline_for(edition.edition_id))
                for edition in editions
            )
        ):
            inconsistent.add(segment_id)
        previous_end = max(previous_end, interval.end_tick)

    return CompletionResult(tuple(sorted(missing)), tuple(sorted(unfinished)), tuple(sorted(inconsistent)))
