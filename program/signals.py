from dataclasses import dataclass

from program.editions import Edition, require_identifier, require_integer


@dataclass(frozen=True)
class EditionSignal:
    code: str
    tick: int
    edition_id: str


def validate_signal_definitions(value, editions: tuple[Edition, ...]) -> tuple[EditionSignal, ...]:
    if not isinstance(value, list):
        raise ValueError('signals must be an array')
    by_edition = {edition.edition_id: edition for edition in editions}
    codes = set()
    covered = set()
    signals = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError('signal definition must be an object')
        code = require_identifier(raw.get('code'), 'signal code')
        tick = require_integer(raw.get('tick'), 'signal tick')
        edition_id = require_identifier(raw.get('edition_id'), 'signal edition_id')
        if edition_id not in by_edition:
            raise ValueError(f'signal {code} refers to an unknown edition')
        if code in codes or edition_id in covered:
            raise ValueError('signal codes and their editions must be unique')
        if tick >= by_edition[edition_id].length:
            raise ValueError(f'signal {code} is outside the edition timeline')
        codes.add(code)
        covered.add(edition_id)
        signals.append(EditionSignal(code, tick, edition_id))

    if len(editions) == 2 and (covered != by_edition.keys() or len({s.tick for s in signals}) != 1):
        raise ValueError('both editions must have one distinct code at the same confirmation tick')
    return tuple(sorted(signals, key=lambda signal: signal.code))


def find_signal_definition(signals: tuple[EditionSignal, ...], code: str) -> EditionSignal | None:
    return next((signal for signal in signals if signal.code == code), None)
