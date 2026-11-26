from dataclasses import dataclass

from program.editions import Edition, parse_edition, require_identifier
from program.narration import NarrationSegment, validate_segments
from program.signals import EditionSignal, validate_signal_definitions


@dataclass(frozen=True)
class ProgramRevision:
    title: str | None
    editions: tuple[Edition, ...]
    segments: tuple[NarrationSegment, ...]
    signals: tuple[EditionSignal, ...]

    @property
    def confirmation_tick(self) -> int | None:
        if len(self.editions) == 2:
            return self.signals[0].tick
        return None

    def edition(self, edition_id: str) -> Edition:
        for edition in self.editions:
            if edition.edition_id == edition_id:
                return edition
        raise LookupError(f'unknown edition {edition_id}')

    def segment(self, segment_id: str) -> NarrationSegment:
        for segment in self.segments:
            if segment.segment_id == segment_id:
                return segment
        raise LookupError(f'unknown segment {segment_id}')


def build_revision(payload) -> ProgramRevision:
    if not isinstance(payload, dict):
        raise ValueError('programme must be an object')
    raw_editions = payload.get('editions')
    if not isinstance(raw_editions, list) or len(raw_editions) not in (1, 2):
        raise ValueError('editions must be an array with one or two editions')
    editions = tuple(parse_edition(raw) for raw in raw_editions)
    if len({edition.edition_id for edition in editions}) != len(editions):
        raise ValueError('duplicate edition_id')

    title = payload.get('title')
    if title is not None:
        title = require_identifier(title, 'title')
    return ProgramRevision(
        title,
        editions,
        validate_segments(payload.get('segments'), editions),
        validate_signal_definitions(payload.get('signals'), editions),
    )


def encode_revision(revision: ProgramRevision) -> dict:
    return {
        'title': revision.title,
        'editions': [
            {
                'edition_id': edition.edition_id,
                'length': edition.length,
                'sound_windows': [[window.start, window.end] for window in edition.sound_windows],
            }
            for edition in revision.editions
        ],
        'segments': [
            {'segment_id': segment.segment_id, 'length': segment.length, 'deadlines': dict(segment.deadlines)}
            for segment in revision.segments
        ],
        'signals': [
            {'code': signal.code, 'tick': signal.tick, 'edition_id': signal.edition_id}
            for signal in revision.signals
        ],
    }


def decode_revision(payload: dict) -> ProgramRevision:
    return build_revision(payload)
