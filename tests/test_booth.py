from tests.test_http import HttpCase, interval, sample, single_edition


class BoothTests(HttpCase):
    def test_wrong_issue(self):
        programme = single_edition(sample('branching'), 'alpha')
        first = self.issue(self.submit(programme))
        programme['segments'][0]['length'] = 1
        second = self.issue(self.submit(programme))
        mounted = self.mount(first)['assignment']
        self.assertEqual(self.call('start', {'booth': 'main', 'issue_id': second}, 409)['error'],
                         'issue_does_not_match_mount')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM show_sessions'), 0)
        show = self.open_show(first)
        self.assertEqual((show['mount_id'], show['issue_id'], show['next_tick']), (mounted['mount_id'], first, 0))
        for tick in range(4):
            self.advance(show['show_id'], tick)
        self.assertEqual(self.finish(show['show_id'])['intervals'], [interval('A', 0, 2), interval('B', 3, 4)])

    def test_occupied_booth_preserves_binding(self):
        issue = self.issue(self.submit(single_edition(sample('branching'), 'alpha')))
        self.call('mount', {'booth': 'main', 'issue_id': 99, 'operator': 'Lin'}, 404)
        show = self.mount_and_start(issue)
        self.call('mount', {'booth': 'main', 'issue_id': issue, 'operator': 'Wrong'}, 409)
        self.call('start', {'booth': 'main', 'issue_id': issue}, 409)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM booth_mounts'), 1)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM show_sessions'), 1)
        self.assertEqual(self.scalar('SELECT operator FROM booth_assignments WHERE booth = ?', ('main',)), 'Lin')
        self.assertEqual(self.scalar('SELECT show_id FROM booth_assignments WHERE booth = ?', ('main',)), show)

    def test_handover(self):
        issue_id = self.issue(self.submit(sample('branching')))
        show_id = self.mount_and_start(issue_id)
        for tick, signal in ((0, None), (1, None), (2, 'beta')):
            self.advance(show_id, tick, signal)
        before = self.read_show(show_id)
        self.call('handover', {'booth': 'other', 'show_id': show_id, 'operator': 'Wrong'}, 409)
        self.call('handover', {'booth': 'main', 'show_id': show_id + 1, 'operator': 'Wrong'}, 409)
        self.assertEqual(self.scalar('SELECT operator FROM booth_assignments WHERE booth = ?', ('main',)), 'Lin')
        transfer = self.call('handover', {'booth': 'main', 'show_id': show_id, 'operator': 'Zhou'})
        self.assertEqual(transfer['assignment']['operator'], 'Zhou')
        self.assertEqual(transfer['assignment']['show_id'], show_id)
        self.assertEqual(transfer['show'], before['show'])
        self.assertEqual(transfer['show']['next_tick'], 3)
        self.assertEqual(transfer['show']['signal'], 'beta')
        self.assertEqual(transfer['intervals'], before['intervals'])
        self.assertEqual(transfer['intervals'], [interval('A', 0, 2)])
        self.advance(show_id, 3)
        self.advance(show_id, 4)
        self.assertEqual(self.finish(show_id)['intervals'], [interval('A', 0, 2), interval('B', 4, 5)])
