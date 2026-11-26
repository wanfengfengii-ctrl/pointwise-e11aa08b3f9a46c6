from tests.test_http import HttpCase, interval, sample, single_edition


class CloseoutTests(HttpCase):
    def test_close_only_when_complete(self):
        issue_id = self.issue(self.submit(single_edition(sample('branching'), 'alpha')))
        show = self.mount_and_start(issue_id)
        self.advance(show, 0)
        self.advance(show, 1)
        early = self.call('close', {'show_id': show}, 409)
        self.assertFalse(early['closed'])
        self.assertEqual(early['missing'], ['B'])
        self.assertNotIn('summary', early)
        self.assertIsNone(self.read_show(show)['closeout'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM closeouts'), 0)
        self.advance(show, 2)
        self.advance(show, 3)
        summary = self.finish(show)
        self.assertEqual(summary['intervals'], [interval('A', 0, 2), interval('B', 3, 4)])
        self.assertEqual(self.finish(show), summary)
        self.assertEqual(self.call('advance', {'show_id': show, 'tick': 4}, 409)['error'], 'show_already_closed')
        self.restart_server()
        self.assertEqual(self.call('read', {'closeout_id': summary['closeout_id']})['closeout'], summary)

    def test_close_requires_actual_intervals(self):
        programme = single_edition(sample('branching'), 'alpha')
        programme['editions'][0].update(length=7, sound_windows=[[2, 3]])
        programme['segments'][1].update(length=2, deadlines={'alpha': 5})
        issue_id = self.issue(self.submit(programme))
        show = self.mount_and_start(issue_id)
        for tick in range(4):
            self.advance(show, tick)
        before = self.read_show(show)
        self.assertEqual(before['intervals'], [interval('A', 0, 2), interval('B', 3, None)])
        early = self.call('close', {'show_id': show}, 409)
        self.assertEqual(early['unfinished'], ['B'])
        self.assertEqual(self.read_show(show), before)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM closeouts'), 0)
        self.call('start', {'booth': 'main', 'issue_id': issue_id}, 409)
        self.assertEqual(self.advance(show, 4)['ended_segment'], 'B')
        self.assertEqual(self.finish(show)['intervals'], [interval('A', 0, 2), interval('B', 3, 5)])

    def test_reopen_by_original_id(self):
        old_issue = self.issue(self.submit(single_edition(sample('branching'), 'alpha')))
        old_show = self.mount_and_start(old_issue)
        for tick in range(4):
            self.advance(old_show, tick)
        summary = self.finish(old_show)
        original = self.read_show(old_show)
        self.restart_server()
        new_issue = self.issue(self.submit(sample('crossing')))
        new_show = self.mount_and_start(new_issue)
        for tick, signal in ((0, None), (1, None), (2, 'beta')):
            self.advance(new_show, tick, signal)
        self.assertEqual(self.read_show(new_show)['intervals'], [interval('A', 0, 3)])
        from_closeout = self.call('read', {'closeout_id': summary['closeout_id']})
        self.assertEqual(from_closeout, original)
        self.assertEqual(self.read_show(old_show), original)
        self.assertEqual(self.finish(old_show), summary)
        self.assertEqual(self.scalar('SELECT show_id FROM booth_assignments WHERE booth = ?', ('main',)), new_show)
        self.assertEqual(self.call('read', {'closeout_id': 99}, 404)['error'], 'closeout_not_found')
        self.assertEqual(self.call('read', {'show_id': 99}, 404)['error'], 'show_not_found')
        self.call('read', {'show_id': old_show, 'closeout_id': summary['closeout_id']}, 400)
