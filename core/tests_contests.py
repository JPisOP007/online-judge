"""Tests for the contest flow: registration, entry, scoring and standings."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase as DjangoTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Contest, ContestAnnouncement, ContestParticipant, ContestProblem,
    ContestSubmission, Problem, Solution, UserProfile,
)


@override_settings(
    # The production static storage reads a manifest that only exists after
    # collectstatic; rendering any page under test would fail without this.
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class TestCase(DjangoTestCase):
    """Base case for the contest tests."""


def make_user(username, role='participant'):
    user = User.objects.create_user(username=username, password='testpass123')
    # A post_save signal already created the profile; adding a second one would
    # make every user.userprofile lookup raise MultipleObjectsReturned.
    UserProfile.objects.update_or_create(user=user, defaults={'role': role})
    return user


def make_problem(title='Doubler', points=None, created_by=None):
    return Problem.objects.create(
        title=title,
        description='Double the input',
        sample_input='2',
        sample_output='4',
        test_cases_json='[{"input": "2", "output": "4"}, {"input": "3", "output": "6"}]',
        created_by=created_by,
    )


def make_contest(owner, **kwargs):
    now = timezone.now()
    defaults = {
        'title': 'Test Contest',
        'description': 'A contest',
        'contest_type': 'rated',
        'start_time': now - timedelta(hours=1),
        'end_time': now + timedelta(hours=1),
        'created_by': owner,
    }
    defaults.update(kwargs)
    return Contest.objects.create(**defaults)


class RegistrationTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner', role='setter')
        self.user = make_user('player')
        self.client.login(username='player', password='testpass123')

    def test_registering_twice_does_not_error(self):
        """The unique (contest, user) constraint used to surface as a 500."""
        contest = make_contest(self.owner)
        url = reverse('contest_detail', args=[contest.uuid])

        first = self.client.post(url, {'password': ''}, follow=True)
        self.assertEqual(first.status_code, 200)
        second = self.client.post(url, {'password': ''}, follow=True)
        self.assertEqual(second.status_code, 200)

        self.assertEqual(
            ContestParticipant.objects.filter(contest=contest, user=self.user).count(), 1
        )

    def test_wrong_password_is_rejected(self):
        contest = make_contest(self.owner, password='letmein')
        self.client.post(reverse('contest_detail', args=[contest.uuid]), {'password': 'nope'})
        self.assertFalse(
            ContestParticipant.objects.filter(contest=contest, user=self.user).exists()
        )

    def test_correct_password_registers(self):
        contest = make_contest(self.owner, password='letmein')
        self.client.post(reverse('contest_detail', args=[contest.uuid]), {'password': 'letmein'})
        self.assertTrue(
            ContestParticipant.objects.filter(contest=contest, user=self.user).exists()
        )

    def test_full_contest_refuses_registration(self):
        contest = make_contest(self.owner, max_participants=1)
        ContestParticipant.objects.create(contest=contest, user=self.owner)

        self.client.post(reverse('contest_detail', args=[contest.uuid]), {'password': ''})
        self.assertFalse(
            ContestParticipant.objects.filter(contest=contest, user=self.user).exists()
        )

    def test_open_contest_can_be_entered_without_registering(self):
        """registration_required=False used to leave a contest unenterable."""
        contest = make_contest(self.owner, registration_required=False)
        make_problem(created_by=self.owner)

        response = self.client.get(reverse('contest_problems', args=[contest.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ContestParticipant.objects.filter(contest=contest, user=self.user).exists()
        )

    def test_open_contest_stops_taking_entrants_once_it_ends(self):
        """Joining after the end would add a blank row to the final standings."""
        now = timezone.now()
        contest = make_contest(
            self.owner,
            registration_required=False,
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=1),
        )

        response = self.client.get(reverse('contest_problems', args=[contest.uuid]))
        self.assertRedirects(response, reverse('contest_detail', args=[contest.uuid]))
        self.assertFalse(
            ContestParticipant.objects.filter(contest=contest, user=self.user).exists()
        )

    def test_unregistered_user_cannot_see_problems_of_closed_contest(self):
        contest = make_contest(self.owner)
        response = self.client.get(reverse('contest_problems', args=[contest.uuid]))
        self.assertRedirects(response, reverse('contest_detail', args=[contest.uuid]))

    def test_problems_are_hidden_before_the_contest_starts(self):
        now = timezone.now()
        contest = make_contest(
            self.owner,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
        )
        ContestParticipant.objects.create(contest=contest, user=self.user)
        problem = make_problem(created_by=self.owner)
        ContestProblem.objects.create(contest=contest, problem=problem, order=1)

        listing = self.client.get(reverse('contest_problems', args=[contest.uuid]))
        self.assertRedirects(listing, reverse('contest_detail', args=[contest.uuid]))

        detail = self.client.get(
            reverse('contest_problem_detail', args=[contest.uuid, problem.uuid])
        )
        self.assertRedirects(detail, reverse('contest_detail', args=[contest.uuid]))

        overview = self.client.get(reverse('contest_detail', args=[contest.uuid]))
        self.assertNotContains(overview, problem.title)


class ContestListTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner', role='setter')
        self.user = make_user('player')
        self.client.login(username='player', password='testpass123')

    def test_unlisted_contests_are_hidden_from_other_users(self):
        make_contest(self.owner, title='Public One')
        make_contest(self.owner, title='Hidden One', is_public=False)

        response = self.client.get(reverse('contest_list'))
        self.assertContains(response, 'Public One')
        self.assertNotContains(response, 'Hidden One')

    def test_owner_still_sees_their_unlisted_contest(self):
        make_contest(self.owner, title='Hidden One', is_public=False)

        self.client.login(username='owner', password='testpass123')
        response = self.client.get(reverse('contest_list'))
        self.assertContains(response, 'Hidden One')

    def test_type_filter_matches_the_model_choices(self):
        make_contest(self.owner, title='Rated One', contest_type='rated')
        make_contest(self.owner, title='Practice One', contest_type='practice')

        response = self.client.get(reverse('contest_list'), {'type': 'practice'})
        self.assertContains(response, 'Practice One')
        self.assertNotContains(response, 'Rated One')


class SubmissionScoringTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner', role='setter')
        self.user = make_user('player')
        self.client.login(username='player', password='testpass123')

        self.contest = make_contest(self.owner)
        self.problem = make_problem(created_by=self.owner)
        self.contest_problem = ContestProblem.objects.create(
            contest=self.contest, problem=self.problem, order=1, points=200
        )
        self.participant = ContestParticipant.objects.create(
            contest=self.contest, user=self.user
        )
        self.url = reverse(
            'contest_problem_detail', args=[self.contest.uuid, self.problem.uuid]
        )

    def submit(self, verdicts):
        """POST a submission, with the judge stubbed to return `verdicts`."""
        with patch('core.views.contests.secure_execute_code') as execute:
            execute.side_effect = [{'verdict': v, 'output': v} for v in verdicts]
            return self.client.post(self.url, {
                'action': 'submit',
                'language': 'python',
                'source_code': 'print(1)',
            })

    def test_accepted_submission_awards_the_problem_points(self):
        self.submit(['AC', 'AC'])
        submission = ContestSubmission.objects.get(participant=self.participant)
        self.assertEqual(submission.verdict, 'AC')
        self.assertEqual(submission.points_awarded, 200)
        self.assertEqual(submission.score, 200)

    def test_partial_score_is_scaled_to_the_problem_points(self):
        self.submit(['AC', 'WA'])
        submission = ContestSubmission.objects.get(participant=self.participant)
        self.assertEqual(submission.verdict, 'WA')
        # One of two test cases passed, out of 200 points.
        self.assertEqual(submission.points_awarded, 100)

    def test_first_test_case_failure_scores_zero(self):
        self.submit(['WA'])
        submission = ContestSubmission.objects.get(participant=self.participant)
        self.assertEqual(submission.points_awarded, 0)

    def test_submissions_after_the_contest_ends_are_rejected(self):
        self.contest.start_time = timezone.now() - timedelta(hours=3)
        self.contest.end_time = timezone.now() - timedelta(hours=1)
        self.contest.save()

        response = self.submit(['AC', 'AC'])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContestSubmission.objects.filter(participant=self.participant).exists())


class StandingsTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner', role='setter')
        self.contest = make_contest(self.owner)
        self.problems = [
            make_problem(title='P1', created_by=self.owner),
            make_problem(title='P2', created_by=self.owner),
        ]
        for order, problem in enumerate(self.problems, start=1):
            ContestProblem.objects.create(
                contest=self.contest, problem=problem, order=order, points=100
            )

    def add_submission(self, user, problem, verdict, points):
        participant, _ = ContestParticipant.objects.get_or_create(
            contest=self.contest, user=user
        )
        solution = Solution.objects.create(
            user=user, problem=problem, code='x', language='python', verdict=verdict
        )
        return ContestSubmission.objects.create(
            contest=self.contest, participant=participant, problem=problem,
            solution=solution, verdict=verdict, score=points, points_awarded=points,
        )

    def standings(self):
        response = self.client.get(reverse('contest_standings', args=[self.contest.uuid]))
        self.assertEqual(response.status_code, 200)
        return response.context['standings']

    def test_best_attempt_counts_not_the_sum_of_attempts(self):
        user = make_user('grinder')
        self.add_submission(user, self.problems[0], 'WA', 40)
        self.add_submission(user, self.problems[0], 'AC', 100)

        row = self.standings()[0]
        self.assertEqual(row['total_points'], 100)
        self.assertEqual(row['submissions_count'], 2)

    def test_partial_credit_is_not_counted_as_solved(self):
        user = make_user('partial')
        self.add_submission(user, self.problems[0], 'WA', 60)

        row = self.standings()[0]
        self.assertEqual(row['total_points'], 60)
        self.assertEqual(row['solved_problems'], 0)

    def test_accepted_problem_counts_as_solved(self):
        user = make_user('solver')
        self.add_submission(user, self.problems[0], 'AC', 100)

        row = self.standings()[0]
        self.assertEqual(row['solved_problems'], 1)

    def test_fewer_submissions_wins_a_tie(self):
        quick = make_user('quick')
        slow = make_user('slow')
        self.add_submission(quick, self.problems[0], 'AC', 100)
        self.add_submission(slow, self.problems[0], 'WA', 0)
        self.add_submission(slow, self.problems[0], 'AC', 100)

        rows = self.standings()
        self.assertEqual(rows[0]['participant'].user, quick)
        self.assertEqual(rows[0]['rank'], 1)
        self.assertEqual(rows[1]['rank'], 2)

    def test_equal_scores_share_a_rank(self):
        first = make_user('first')
        second = make_user('second')
        self.add_submission(first, self.problems[0], 'AC', 100)
        self.add_submission(second, self.problems[0], 'AC', 100)

        rows = self.standings()
        self.assertEqual([row['rank'] for row in rows], [1, 1])


class ContestManagementTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner', role='setter')
        self.other_setter = make_user('other', role='setter')
        self.admin = make_user('boss', role='admin')
        self.contest = make_contest(self.owner)

    def edit_url(self):
        return reverse('edit_contest', args=[self.contest.uuid])

    def test_owner_can_open_the_edit_page(self):
        self.client.login(username='owner', password='testpass123')
        self.assertEqual(self.client.get(self.edit_url()).status_code, 200)

    def test_admin_can_open_the_edit_page(self):
        self.client.login(username='boss', password='testpass123')
        self.assertEqual(self.client.get(self.edit_url()).status_code, 200)

    def test_another_setter_cannot_edit_someone_elses_contest(self):
        self.client.login(username='other', password='testpass123')
        response = self.client.get(self.edit_url())
        self.assertNotEqual(response.status_code, 200)

    def test_another_setter_cannot_post_announcements(self):
        self.client.login(username='other', password='testpass123')
        response = self.client.post(
            reverse('create_announcement', args=[self.contest.uuid]),
            {'title': 'Hi', 'content': 'There'},
        )
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(ContestAnnouncement.objects.filter(contest=self.contest).exists())

    def test_owner_can_post_and_delete_an_announcement(self):
        self.client.login(username='owner', password='testpass123')
        self.client.post(
            reverse('create_announcement', args=[self.contest.uuid]),
            {'title': 'Clarification', 'content': 'Read the constraints'},
        )
        announcement = ContestAnnouncement.objects.get(contest=self.contest)

        confirm_url = reverse(
            'delete_announcement', args=[self.contest.uuid, announcement.id]
        )
        # The confirmation page must render rather than blow up on a missing
        # template, and a GET must not delete anything.
        self.assertEqual(self.client.get(confirm_url).status_code, 200)
        self.assertTrue(ContestAnnouncement.objects.filter(id=announcement.id).exists())

        self.client.post(confirm_url)
        self.assertFalse(ContestAnnouncement.objects.filter(id=announcement.id).exists())


class ContestFormTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner', role='setter')
        self.client.login(username='owner', password='testpass123')

    def post_contest(self, url, start, end, **extra):
        data = {
            'title': 'Formed Contest',
            'description': 'Made through the form',
            'contest_type': 'rated',
            'start_time': start.strftime('%Y-%m-%dT%H:%M'),
            'end_time': end.strftime('%Y-%m-%dT%H:%M'),
            'is_public': 'on',
            'registration_required': 'on',
            'password': '',
        }
        data.update(extra)
        return self.client.post(url, data)

    def test_create_page_offers_the_visibility_toggle(self):
        response = self.client.get(reverse('create_contest'))
        self.assertContains(response, 'name="is_public"')

    def test_created_contest_is_public_and_has_a_duration(self):
        start = timezone.localtime() + timedelta(days=1)
        end = start + timedelta(hours=3)

        self.post_contest(reverse('create_contest'), start, end)

        contest = Contest.objects.get(title='Formed Contest')
        self.assertTrue(contest.is_public)
        self.assertEqual(contest.duration, timedelta(hours=3))

    def test_unticking_the_visibility_toggle_unlists_the_contest(self):
        start = timezone.localtime() + timedelta(days=1)
        end = start + timedelta(hours=3)

        data_without_is_public = {'is_public': ''}
        self.post_contest(reverse('create_contest'), start, end, **data_without_is_public)

        self.assertFalse(Contest.objects.get(title='Formed Contest').is_public)

    def test_edit_page_prefills_the_contest_window(self):
        contest = make_contest(self.owner)
        response = self.client.get(reverse('edit_contest', args=[contest.uuid]))

        expected = timezone.localtime(contest.start_time).strftime('%Y-%m-%dT%H:%M')
        self.assertContains(response, f'value="{expected}"')

    def test_editing_the_times_updates_the_duration(self):
        contest = make_contest(self.owner)
        start = timezone.localtime() + timedelta(days=2)
        end = start + timedelta(hours=5)

        self.post_contest(
            reverse('edit_contest', args=[contest.uuid]), start, end,
            title=contest.title, description=contest.description,
        )

        contest.refresh_from_db()
        self.assertEqual(contest.duration, timedelta(hours=5))

    def test_editing_keeps_the_contest_password(self):
        contest = make_contest(self.owner, password='letmein')
        start = timezone.localtime(contest.start_time)
        end = timezone.localtime(contest.end_time)

        self.post_contest(
            reverse('edit_contest', args=[contest.uuid]), start, end,
            title=contest.title, description=contest.description,
            password=contest.password,
        )

        contest.refresh_from_db()
        self.assertEqual(contest.password, 'letmein')

    def test_an_inverted_window_is_reported_once(self):
        start = timezone.localtime() + timedelta(days=1)
        response = self.post_contest(
            reverse('create_contest'), start, start - timedelta(hours=1)
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contest.objects.filter(title='Formed Contest').exists())


class ContestPageSmokeTests(TestCase):
    """Every contest page renders for a registered participant."""

    def setUp(self):
        self.owner = make_user('owner', role='setter')
        self.user = make_user('player')
        self.client.login(username='player', password='testpass123')

        self.contest = make_contest(self.owner)
        self.problem = make_problem(created_by=self.owner)
        ContestProblem.objects.create(
            contest=self.contest, problem=self.problem, order=1, points=150
        )
        ContestParticipant.objects.create(contest=self.contest, user=self.user)
        ContestAnnouncement.objects.create(
            contest=self.contest, title='Note', content='Read this',
            created_by=self.owner,
        )

    def contest_urls(self):
        return [
            reverse('contest_list'),
            reverse('contest_detail', args=[self.contest.uuid]),
            reverse('contest_problems', args=[self.contest.uuid]),
            reverse('contest_problem_detail', args=[self.contest.uuid, self.problem.uuid]),
            reverse('contest_standings', args=[self.contest.uuid]),
            reverse('contest_announcements', args=[self.contest.uuid]),
        ]

    def test_no_page_leaks_template_syntax(self):
        """A {# #} comment split over two lines is not a comment - Django's
        lexer does not match across newlines - so it renders as page text."""
        for url in self.contest_urls():
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn('{#', html)
                self.assertNotIn('{%', html)

    def test_pages_render(self):
        urls = [
            reverse('contest_list'),
            reverse('contest_detail', args=[self.contest.uuid]),
            reverse('contest_problems', args=[self.contest.uuid]),
            reverse('contest_problem_detail', args=[self.contest.uuid, self.problem.uuid]),
            reverse('contest_standings', args=[self.contest.uuid]),
            reverse('contest_announcements', args=[self.contest.uuid]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_problem_page_ships_the_code_editor(self):
        """The contest editor is the same CodeMirror the practice page uses."""
        response = self.client.get(
            reverse('contest_problem_detail', args=[self.contest.uuid, self.problem.uuid])
        )
        self.assertContains(response, 'codemirror.min.js')
        self.assertContains(response, 'class="editor-wrapper"')
        self.assertContains(response, 'id="id_source_code"')

    def test_problem_page_shows_the_judge_limits(self):
        response = self.client.get(
            reverse('contest_problem_detail', args=[self.contest.uuid, self.problem.uuid])
        )
        self.assertContains(response, '150 points')
        self.assertContains(response, '5s')
        self.assertContains(response, '128MB')

    def test_participant_does_not_see_management_actions(self):
        response = self.client.get(reverse('contest_announcements', args=[self.contest.uuid]))
        self.assertNotContains(response, 'New Announcement')


class ContestTimerAPITests(TestCase):
    def test_timer_reports_seconds_remaining(self):
        owner = make_user('owner', role='setter')
        contest = make_contest(owner)

        response = self.client.get(reverse('contest_timer_api', args=[contest.uuid]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'running')
        self.assertGreater(payload['time_remaining'], 0)
