from program.catalog import build_revision
from release.feasibility import find_single_edition_schedule
from tests.test_http import HttpCase, sample, scenario, single_edition


class ReleaseTests(HttpCase):
    def test_single_edition_schedules(self):
        programme = sample('incompatible')
        alpha = build_revision(single_edition(programme, 'alpha'))
        beta = build_revision(single_edition(programme, 'beta'))
        self.assertEqual(find_single_edition_schedule(alpha, 'alpha'), ((0, 'A'), (3, 'B')))
        self.assertEqual(find_single_edition_schedule(beta, 'beta'), ((0, 'B'), (3, 'A')))

    def test_incompatible_opening(self):
        programme = sample('incompatible')
        individual = []
        for edition_id in ('alpha', 'beta'):
            revision_id = self.submit(single_edition(programme, edition_id))
            proof = self.call('preview', {'revision_id': revision_id})
            self.assertTrue(proof['eligible'])
            individual.append(self.issue(revision_id))
        self.assertEqual(len(set(individual)), 2)

        revision_id = self.submit(programme)
        preview = self.call('preview', {'revision_id': revision_id})
        status, issue = self.request('issue', {'revision_id': revision_id})
        eligibility = {'eligible': preview['eligible'], 'reason': preview['reason']}
        issuance = {
            'status': status, 'issued': issue.get('issued'), 'has_issue_id': 'issue_id' in issue,
            'stored_issues': self.scalar('SELECT COUNT(*) FROM issued_programs WHERE revision_id = ?', (revision_id,)),
        }
        expected_preview = {'eligible': False, 'reason': 'no_common_schedule'}
        expected_issue = {'status': 409, 'issued': False, 'has_issue_id': False, 'stored_issues': 0}
        self.assertEqual((eligibility, issuance), (expected_preview, expected_issue), 'V3_DUAL_ISSUE')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM issued_programs'), 2)
        scenario(
            'v3', programme, expected_preview, eligibility, expected_issue, issuance,
            ['program/editions.py', 'release/feasibility.py', 'release/preview.py', 'release/issue.py'],
            '甲单版 A=[0,2)、B=[3,4)，乙单版 B=[0,1)、A=[3,5)。提示前共同的两拍装不下两项早截止义务。',
        )

    def test_unknown_revision_cannot_issue(self):
        for operation in ('preview', 'issue'):
            with self.subTest(operation=operation):
                self.assertEqual(self.call(operation, {'revision_id': 99}, 404)['error'], 'revision_not_found')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM issued_programs'), 0)
