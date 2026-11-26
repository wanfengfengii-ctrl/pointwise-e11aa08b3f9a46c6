from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class TickWindow:
    start: int
    end: int

    def contains(self, start: int, end: int) -> bool:
        return self.start <= start < end <= self.end


@dataclass(frozen=True)
class Edition:
    edition_id: str
    length: int
    sound_windows: tuple[TickWindow, ...]


def require_identifier(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty string')
    return value


def require_integer(value, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f'{field} must be an integer >= {minimum}')
    return value


def parse_edition(value) -> Edition:
    if not isinstance(value, dict):
        raise ValueError('edition must be an object')
    edition_id = require_identifier(value.get('edition_id'), 'edition_id')
    length = require_integer(value.get('length'), 'edition length', 1)
    raw_windows = value.get('sound_windows')
    if not isinstance(raw_windows, list):
        raise ValueError('sound_windows must be an array')

    windows = []
    for raw in raw_windows:
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError('sound window must have two endpoints')
        start = require_integer(raw[0], 'sound window start')
        end = require_integer(raw[1], 'sound window end', 1)
        if not start < end <= length:
            raise ValueError('sound window must satisfy 0 <= start < end <= edition length')
        windows.append(TickWindow(start, end))
    return Edition(edition_id, length, tuple(windows))


def available_windows(edition: Edition) -> tuple[TickWindow, ...]:
    windows = []
    covered_until = 0
    for window in sorted(edition.sound_windows):
        if covered_until < window.start:
            windows.append(TickWindow(covered_until, window.start))
        covered_until = max(covered_until, window.end)
    if covered_until < edition.length:
        windows.append(TickWindow(covered_until, edition.length))
    return tuple(windows)


def fits_narration(edition: Edition, start: int, length: int, deadline: int) -> bool:
    end = start + length
    return end <= deadline and any(
        window.contains(start, end) for window in available_windows(edition)
    )
