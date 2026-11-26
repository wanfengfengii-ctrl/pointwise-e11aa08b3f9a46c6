from dataclasses import dataclass

from program.editions import Edition, require_identifier, require_integer


@dataclass(frozen=True)
class NarrationSegment:
    segment_id: str
    length: int
    deadlines: tuple[tuple[str, int], ...]

    def deadline_for(self, edition_id: str) -> int:
        for candidate, deadline in self.deadlines:
            if edition_id == candidate:
                return deadline
        raise LookupError(f'no deadline for edition {edition_id}')


def validate_segments(value, editions: tuple[Edition, ...]) -> tuple[NarrationSegment, ...]:
    if not isinstance(value, list):
        raise ValueError('segments must be an array')
    by_edition = {edition.edition_id: edition for edition in editions}
    seen = set()
    segments = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError('segment must be an object')
        segment_id = require_identifier(raw.get('segment_id'), 'segment_id')
        if segment_id in seen:
            raise ValueError(f'duplicate segment {segment_id}')
        seen.add(segment_id)
        length = require_integer(raw.get('length'), 'segment length', 1)
        deadlines = raw.get('deadlines')
        if not isinstance(deadlines, dict) or deadlines.keys() != by_edition.keys():
            raise ValueError(f'deadlines for {segment_id} must cover exactly the programme editions')

        entries = []
        for edition_id, edition in by_edition.items():
            deadline = require_integer(deadlines[edition_id], 'segment deadline')
            if deadline > edition.length:
                raise ValueError(f'deadline for {segment_id} exceeds length of {edition_id}')
            entries.append((edition_id, deadline))
        segments.append(NarrationSegment(segment_id, length, tuple(entries)))
    return tuple(sorted(segments, key=lambda segment: segment.segment_id))
