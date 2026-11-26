from program.catalog import build_revision
from program.editions import TickWindow, available_windows, fits_narration
from tests.test_http import HttpCase, interval, sample, scenario, single_edition


class ShowTests(HttpCase):
    def test_actual_edition(self):
        programme = sample('branching')
        issue_id = self.issue(self.submit(programme))
        actual = {}
        expected = {
            'alpha': [interval('A', 0, 2), interval('B', 3, 4)],
            'beta': [interval('A', 0, 2), interval('B', 4, 5)],
        }
        for edition_id, b_tick in (('alpha', 3), ('beta', 4)):
            show = self.mount_and_start(issue_id, edition_id)
            for tick in range(5):
                advance = self.advance(show, tick, edition_id if tick == 2 else None)
                kind = 'start' if tick in (0, b_tick) else 'continue' if tick == 1 else 'wait'
                self.assertEqual(advance['action']['kind'], kind, f'V4_ACTUAL_EDITION {edition_id} tick {tick}')
                heard = [interval('A', 0, None if tick == 0 else 2)]
                if tick >= b_tick:
                    heard.append(interval('B', b_tick, b_tick + 1))
                self.assertEqual(self.read_show(show)['intervals'], heard, f'V4_ACTUAL_EDITION {edition_id} ledger')
                if tick < 2:
                    self.assertIsNone(advance['show']['edition_id'])
                else:
                    self.assertEqual(advance['show']['edition_id'], edition_id)
            summary = self.finish(show)
            self.assertEqual(summary['issue_id'], issue_id)
            self.assertEqual(summary['edition_id'], edition_id)
            self.assertTrue(self.read_show(show)['show']['closed'])
            actual[edition_id] = summary['intervals']
        self.assertEqual(actual, expected)
        scenario(
            'v4', programme, expected, actual, {'closed_editions': ['alpha', 'beta']},
            {'closed_editions': list(actual)},
            ['release/feasibility.py', 'show/clock.py', 'show/playback.py', 'record/closeout.py'],
            '两版 A 的截止为 2，只能占 [0,2)。甲和乙后续唯一可播 B 的拍分别是 3 和 4。',
        )

    def test_same_tick_signal_start(self):
        programme = sample('branching')
        programme['editions'][0]['sound_windows'] = [[3, 5]]
        programme['segments'][1]['deadlines']['alpha'] = 3
        show = self.mount_and_start(self.issue(self.submit(programme)))
        self.advance(show, 0)
        self.advance(show, 1)
        before = self.read_show(show)
        missing = self.call('advance', {'show_id': show, 'tick': 2}, 409)
        self.assertEqual(missing['error'], 'signal_required')
        self.assertEqual(self.read_show(show), before)
        result = self.advance(show, 2, 'alpha')
        self.assertEqual(result['action'], {'kind': 'start', 'segment_id': 'B'})
        self.assertEqual(result['ended_segment'], 'B')
        self.assertEqual(self.finish(show)['intervals'], [interval('A', 0, 2), interval('B', 2, 3)])

    def test_confirmation_at_zero_precedes_first_start(self):
        programme = sample('incompatible')
        for signal in programme['signals']:
            signal['tick'] = 0
        issue_id = self.issue(self.submit(programme))
        for edition, segment in (('alpha', 'A'), ('beta', 'B')):
            show = self.mount_and_start(issue_id, edition)
            self.assertEqual(self.advance(show, 0, edition)['action'], {'kind': 'start', 'segment_id': segment})

    def test_carry_active_over_signal(self):
        show = self.mount_and_start(self.issue(self.submit(sample('crossing'))))
        self.advance(show, 0)
        self.advance(show, 1)
        self.assertEqual(self.read_show(show)['intervals'], [interval('A', 0, None)])
        at_signal = self.advance(show, 2, 'beta')
        self.assertEqual(at_signal['show']['edition_id'], 'beta')
        self.assertEqual(at_signal['action'], {'kind': 'continue', 'segment_id': 'A'})
        self.assertEqual(at_signal['ended_segment'], 'A')
        self.assertEqual(self.read_show(show)['intervals'], [interval('A', 0, 3)])
        self.assertEqual(self.advance(show, 3)['action']['kind'], 'wait')
        self.advance(show, 4)
        self.assertEqual(self.finish(show)['intervals'], [interval('A', 0, 3), interval('B', 4, 5)])

    def test_boundary_and_continuity(self):
        programme = single_edition(sample('branching'), 'alpha')
        edition = programme['editions'][0]
        edition.update(length=6, sound_windows=[[5, 6], [4, 5], [2, 3], [1, 3]])
        parsed = build_revision(programme).edition('alpha')
        self.assertEqual(available_windows(parsed), (TickWindow(0, 1), TickWindow(3, 4)))
        self.assertFalse(fits_narration(parsed, 0, 2, 4))
        self.assertTrue(fits_narration(parsed, 3, 1, 4))
        self.assertFalse(self.call('preview', {'revision_id': self.submit(programme)})['eligible'])
        edition['sound_windows'] = []
        self.assertEqual(available_windows(build_revision(programme).edition('alpha')), (TickWindow(0, 6),))
        edition['sound_windows'] = [[0, 6]]
        self.assertEqual(available_windows(build_revision(programme).edition('alpha')), ())
        self.assertFalse(self.call('preview', {'revision_id': self.submit(programme)})['eligible'])

    def test_unknown_signal(self):
        show = self.mount_and_start(self.issue(self.submit(sample('crossing'))))
        self.advance(show, 0)
        self.advance(show, 1)
        before = self.read_show(show)
        self.assertEqual(before['show']['active']['remaining_ticks'], 1)
        self.assertEqual(before['intervals'], [interval('A', 0, None)])
        rejected = self.call('advance', {'show_id': show, 'tick': 2, 'signal': 'outside'}, 400)
        self.assertEqual(rejected['error'], 'unknown_signal')
        self.assertEqual(self.read_show(show), before)
        result = self.advance(show, 2, 'beta')
        self.assertEqual(result['show']['next_tick'], 3)
        self.assertEqual(self.read_show(show)['intervals'], [interval('A', 0, 3)])
        self.advance(show, 3)
        self.advance(show, 4)
        self.assertEqual(self.finish(show)['intervals'], [interval('A', 0, 3), interval('B', 4, 5)])

    def test_early_late_and_wrong_tick_are_atomic(self):
        show = self.mount_and_start(self.issue(self.submit(sample('branching'))))
        initial = self.read_show(show)
        self.call('advance', {'show_id': show, 'tick': 0, 'signal': 'beta'}, 400)
        self.call('advance', {'show_id': show, 'tick': 1}, 400)
        self.assertEqual(self.read_show(show), initial)
        self.advance(show, 0)
        self.advance(show, 1)
        self.advance(show, 2, 'beta')
        before = self.read_show(show)
        self.call('advance', {'show_id': show, 'tick': 3, 'signal': 'alpha'}, 400)
        self.call('advance', {'show_id': show, 'tick': 2, 'signal': 'beta'}, 400)
        self.assertEqual(self.read_show(show), before)
        self.advance(show, 3)
        self.advance(show, 4)
        finished = self.read_show(show)
        self.assertEqual(self.call('advance', {'show_id': show, 'tick': 5}, 409)['error'], 'edition_has_ended')
        self.assertEqual(self.read_show(show), finished)
