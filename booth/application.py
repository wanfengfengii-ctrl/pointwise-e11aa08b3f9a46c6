from contextlib import closing
from dataclasses import asdict
import sqlite3

from booth.handover import handover_show
from booth.mount import mount_issue
from booth.sessions import BoothConflict, initialize_booth_store, release_show
from booth.status import read_booth_status
from program.catalog import build_revision
from program.editions import require_identifier, require_integer
from program.repository import initialize_program_store, save_program_revision
from record.closeout import close_show, find_closeout_by_show, initialize_closeout_store
from record.ledger import initialize_ledger
from record.readback import read_show_record
from release.issue import issue_revision
from release.preview import preview_revision
from release.repository import get_issued_program, initialize_issue_store
from show.clock import AdvanceConflict, advance_show
from show.opening import start_show
from show.repository import initialize_show_store, load_show, mark_show_closed, show_view
from show.signal_input import SignalRequired


def _connect(database):
    connection = sqlite3.connect(database, timeout=5)
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def initialize_application(database) -> None:
    with closing(_connect(database)) as connection, connection:
        connection.execute('BEGIN IMMEDIATE')
        initialize_program_store(connection)
        initialize_issue_store(connection)
        initialize_booth_store(connection)
        initialize_show_store(connection)
        initialize_ledger(connection)
        initialize_closeout_store(connection)


def _number(body, field):
    return require_integer(body.get(field), field, 1)


def _text(body, field):
    return require_identifier(body.get(field), field)


def _program_input(connection, body):
    revision = build_revision(body)
    return 201, {'revision_id': save_program_revision(connection, revision)}


def _preview(connection, body):
    return 200, preview_revision(connection, _number(body, 'revision_id')).public_view()


def _issue(connection, body):
    preview, issued = issue_revision(connection, _number(body, 'revision_id'))
    if issued is None:
        return 409, {**preview.public_view(), 'issued': False, 'error': 'preview_rejected'}
    return 201, {'issued': True, 'issue_id': issued.issue_id, 'revision_id': issued.revision_id}


def _mount(connection, body):
    booth = _text(body, 'booth')
    mount_issue(connection, booth, _number(body, 'issue_id'), _text(body, 'operator'))
    return 201, read_booth_status(connection, booth).public_view()


def _start(connection, body):
    show = start_show(connection, _text(body, 'booth'), _number(body, 'issue_id'))
    return 201, show_view(show)


def _advance(connection, body):
    tick = require_integer(body.get('tick'), 'tick')
    signal = body.get('signal')
    if signal is not None:
        signal = require_identifier(signal, 'signal')
    result = advance_show(connection, _number(body, 'show_id'), tick, signal)
    return 200, {
        'tick': result.tick,
        'action': asdict(result.action),
        'ended_segment': result.ended_segment,
        'show': show_view(result.show),
    }


def _handover(connection, body):
    status = handover_show(connection, _text(body, 'booth'), _number(body, 'show_id'), _text(body, 'operator'))
    return 200, status.public_view()


def _close(connection, body):
    show = load_show(connection, _number(body, 'show_id'))
    if show.closed:
        previous = find_closeout_by_show(connection, show.show_id)
        if previous is None:
            raise RuntimeError('closed show has no summary')
        return 200, {'closed': True, 'summary': asdict(previous)}

    issued = get_issued_program(connection, show.issue_id)
    completion, summary = close_show(connection, issued, show)
    if summary is None:
        return 409, {'closed': False, 'error': 'show_incomplete', **asdict(completion)}
    mark_show_closed(connection, show.show_id)
    release_show(connection, show.booth, show.show_id)
    return 200, {'closed': True, 'summary': asdict(summary)}


def _read(connection, body):
    identifiers = {field: _number(body, field) for field in ('show_id', 'closeout_id') if field in body}
    return 200, read_show_record(connection, **identifiers)


_OPERATIONS = {
    'program_input': _program_input,
    'preview': _preview,
    'issue': _issue,
    'mount': _mount,
    'start': _start,
    'advance': _advance,
    'handover': _handover,
    'close': _close,
    'read': _read,
}


def handle_operation(database, operation: str, payload) -> tuple[int, dict]:
    handler = _OPERATIONS.get(operation)
    if handler is None:
        return 404, {'error': 'operation_not_found'}
    if not isinstance(payload, dict):
        return 400, {'error': 'request_must_be_an_object'}

    try:
        with closing(_connect(database)) as connection, connection:
            connection.execute('BEGIN' if operation in ('read', 'preview') else 'BEGIN IMMEDIATE')
            return handler(connection, payload)
    except ValueError as error:
        return 400, {'error': str(error)}
    except LookupError as error:
        return 404, {'error': str(error)}
    except (BoothConflict, AdvanceConflict, SignalRequired) as error:
        return 409, {'error': str(error)}
