import argparse
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from booth.http_api import serve


def sample(name):
    path = Path(__file__).resolve().parents[1] / 'samples' / f'{name}.json'
    return json.loads(path.read_text(encoding='utf-8'))


def single_edition(programme, edition_id):
    result = deepcopy(programme)
    result['editions'] = [edition for edition in result['editions'] if edition['edition_id'] == edition_id]
    for segment in result['segments']:
        segment['deadlines'] = {edition_id: segment['deadlines'][edition_id]}
    result['signals'] = []
    return result


def interval(segment_id, start_tick, end_tick):
    return {'segment_id': segment_id, 'start_tick': start_tick, 'end_tick': end_tick}


def scenario(case_id, input_data, expected, actual, downstream_expected, downstream_actual, paths, oracle):
    print('POINTWISE_SCENARIO ' + json.dumps({
        'case_id': case_id, 'input': input_data, 'expected': expected, 'actual': actual,
        'downstream_expected': downstream_expected, 'downstream_actual': downstream_actual,
        'code_paths': paths, 'oracle': oracle,
    }, ensure_ascii=False, separators=(',', ':')), flush=True)


class HttpCase(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix='theatre-test-')
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / 'theatre.sqlite3'
        self.server = None
        self.addCleanup(self.stop_server)
        self.start_server()

    def start_server(self):
        self.server = serve(self.database, 0)
        self.thread = Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True)
        self.thread.start()

    def stop_server(self):
        if self.server is None:
            return
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError('HTTP test server did not stop')
        self.server = None

    def restart_server(self):
        self.stop_server()
        self.start_server()

    def request(self, operation, payload):
        request = Request(
            f'http://127.0.0.1:{self.server.server_port}/{operation}',
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.code, json.load(response)

    def call(self, operation, payload, status=200):
        received, body = self.request(operation, payload)
        self.assertEqual(received, status, (operation, received, body))
        return body

    def scalar(self, sql, parameters=()):
        with closing(sqlite3.connect(self.database)) as connection:
            return connection.execute(sql, parameters).fetchone()[0]

    def submit(self, programme):
        return self.call('program_input', programme, 201)['revision_id']

    def issue(self, revision_id):
        return self.call('issue', {'revision_id': revision_id}, 201)['issue_id']

    def mount(self, issue_id, booth='main', operator='Lin'):
        return self.call('mount', {'booth': booth, 'issue_id': issue_id, 'operator': operator}, 201)

    def open_show(self, issue_id, booth='main'):
        return self.call('start', {'booth': booth, 'issue_id': issue_id}, 201)

    def mount_and_start(self, issue_id, booth='main'):
        self.mount(issue_id, booth)
        return self.open_show(issue_id, booth)['show_id']

    def advance(self, show_id, tick, signal=None):
        return self.call('advance', {'show_id': show_id, 'tick': tick, 'signal': signal})

    def read_show(self, show_id):
        return self.call('read', {'show_id': show_id})

    def finish(self, show_id):
        return self.call('close', {'show_id': show_id})['summary']


class HttpWorkflowTests(HttpCase):
    def test_http_day(self):
        programme = sample('branching')
        revision_id = self.submit(programme)
        preview = self.call('preview', {'revision_id': revision_id})
        self.assertEqual(preview, {'revision_id': revision_id, 'eligible': True, 'reason': 'feasible'})
        issue_id = self.issue(revision_id)
        show_id = self.mount_and_start(issue_id)
        self.assertEqual(self.read_show(show_id)['intervals'], [])
        self.advance(show_id, 0)
        self.advance(show_id, 1)
        self.advance(show_id, 2, 'beta')
        transfer = self.call('handover', {'booth': 'main', 'show_id': show_id, 'operator': 'Zhou'})
        self.assertEqual(transfer['assignment']['operator'], 'Zhou')
        self.assertEqual(transfer['show']['show_id'], show_id)
        self.assertEqual(transfer['show']['next_tick'], 3)
        self.assertEqual(transfer['show']['signal'], 'beta')
        self.assertEqual(transfer['intervals'], [interval('A', 0, 2)])
        self.assertEqual(self.advance(show_id, 3)['action']['kind'], 'wait')
        self.assertEqual(self.advance(show_id, 4)['ended_segment'], 'B')
        summary = self.finish(show_id)
        self.restart_server()
        record = self.call('read', {'closeout_id': summary['closeout_id']})
        expected = [interval('A', 0, 2), interval('B', 4, 5)]
        self.assertEqual(record['intervals'], expected)
        self.assertEqual(record['closeout'], summary)
        self.assertEqual(record, self.read_show(show_id))
        self.assertTrue(record['show']['closed'])
        scenario(
            'v7', {'programme': programme, 'confirmation': 'beta', 'handover_after_tick': 2},
            {'next_tick': 3, 'intervals': [interval('A', 0, 2)]},
            {'next_tick': transfer['show']['next_tick'], 'intervals': transfer['intervals']},
            {'closed': True, 'intervals': expected},
            {'closed': record['show']['closed'], 'intervals': record['intervals']},
            ['booth/handover.py', 'show/clock.py', 'record/ledger.py', 'record/readback.py'],
            '乙原声占 [2,4)，A 必须在第 2 拍前结束，B 只能占 [4,5)。接班和重开均按原号对账。',
        )

    def test_http_rejects_non_object_and_unknown_operation(self):
        self.assertEqual(self.call('program_input', [], 400)['error'], 'request_must_be_an_object')
        self.assertEqual(self.call('unknown', {}, 404)['error'], 'operation_not_found')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM program_revisions'), 0)


def main():
    parser = argparse.ArgumentParser(description='Run the theatre demonstration over local HTTP')
    parser.add_argument('--demo', action='store_true', required=True)
    parser.parse_args()
    suite = unittest.TestSuite([HttpWorkflowTests('test_http_day')])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
