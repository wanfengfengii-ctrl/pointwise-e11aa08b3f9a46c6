from contextlib import closing
import sqlite3

from program.editions import TickWindow, available_windows
from program.repository import get_program_revision
from release.repository import get_issued_program
from tests.test_http import HttpCase, interval, sample, single_edition


class ProgramTests(HttpCase):
    def _correction(self):
        original = single_edition(sample('branching'), 'alpha')
        original_id = self.submit(original)
        issue_id = self.issue(original_id)
        revised = single_edition(sample('branching'), 'alpha')
        revised['editions'][0]['sound_windows'] = [[1, 3], [4, 5]]
        revised['segments'][0]['length'] = 1
        revised_id = self.submit(revised)
        self.assertNotEqual(revised_id, original_id)
        return original_id, issue_id, revised_id

    def test_frozen_issue(self):
        original_id, issue_id, revised_id = self._correction()
        with closing(sqlite3.connect(self.database)) as connection:
            issued = get_issued_program(connection, issue_id)
            revised = get_program_revision(connection, revised_id)
        self.assertEqual(issued.revision_id, original_id)
        self.assertEqual(issued.revision.segment('A').length, 2)
        self.assertEqual(available_windows(issued.revision.edition('alpha')), (TickWindow(0, 2), TickWindow(3, 4)))
        self.assertEqual(revised.segment('A').length, 1)
        self.assertEqual(available_windows(revised.edition('alpha')), (TickWindow(0, 1), TickWindow(3, 4)))

        show = self.mount_and_start(issue_id)
        for tick in range(4):
            self.advance(show, tick)
        self.assertEqual(self.finish(show)['intervals'], [interval('A', 0, 2), interval('B', 3, 4)])

    def test_init_preserves_revisions(self):
        original_id, issue_id, revised_id = self._correction()
        self.restart_server()
        self.restart_server()
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM program_revisions'), 2)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM issued_programs'), 1)
        for revision_id in (original_id, revised_id):
            self.assertTrue(self.call('preview', {'revision_id': revision_id})['eligible'])
        self.assertEqual(self.mount(issue_id)['assignment']['issue_id'], issue_id)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(get_issued_program(connection, issue_id).revision_id, original_id)
            self.assertEqual(get_program_revision(connection, original_id).segment('A').length, 2)
            self.assertEqual(get_program_revision(connection, revised_id).segment('A').length, 1)

    def test_invalid_window(self):
        valid = sample('branching')
        original_id = self.submit(valid)
        invalid = sample('branching')
        invalid['editions'][0]['sound_windows'] = [[4, 2]]
        error = self.call('program_input', invalid, 400)
        self.assertIn('start < end', error['error'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM program_revisions'), 1)
        self.assertTrue(self.call('preview', {'revision_id': original_id})['eligible'])

    def test_other_invalid_programme_inputs_are_atomic(self):
        missing_window = sample('branching')
        del missing_window['editions'][0]['sound_windows']
        outside = sample('branching')
        outside['editions'][0]['sound_windows'] = [[3, 6]]
        bad_length = sample('branching')
        bad_length['segments'][0]['length'] = True
        missing_deadline = sample('branching')
        del missing_deadline['segments'][0]['deadlines']['beta']
        duplicate = sample('branching')
        duplicate['segments'][1]['segment_id'] = 'A'
        duplicate_edition = sample('branching')
        duplicate_edition['editions'][1]['edition_id'] = 'alpha'
        external_signal = sample('branching')
        external_signal['signals'][1]['edition_id'] = 'outside'
        conflicting_tick = sample('branching')
        conflicting_tick['signals'][1]['tick'] = 3
        for invalid in (missing_window, outside, bad_length, missing_deadline, duplicate,
                        duplicate_edition, external_signal, conflicting_tick):
            with self.subTest(programme=invalid):
                self.call('program_input', invalid, 400)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM program_revisions'), 0)
