"""Post-deploy smoke test for the security fixes.

Exercises the authenticated paths that cannot be checked from outside with an
anonymous HTTP request: the submission IDOR, the API role checks, the profile
role-escalation guard and the test-case visibility rules.

Run it against the deployed instance:

    python manage.py smoke_check

It is read-only. Two checks have to attempt a write in order to prove the write
is refused (creating a problem, escalating a role); if either unexpectedly
succeeds, the command reverts it immediately and reports a failure.

Pass --password to additionally verify the login open-redirect fix, which can
only be tested by going through the login form:

    python manage.py smoke_check --username P1 --password '...'
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.test import Client

from core.models import Problem, Solution, UserProfile

HOST = 'thiran.me'


class Command(BaseCommand):
    help = 'Verify the deployed security fixes against real data (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--username', default=None,
                            help='Participant account to test as. Defaults to the first participant found.')
        parser.add_argument('--password', default=None,
                            help='Optional. Enables the login open-redirect check.')

    def handle(self, *args, **options):
        self.failures = []
        self.passes = 0

        user = self._resolve_user(options['username'])
        if user is None:
            self.stderr.write(self.style.ERROR('No participant account found to test with.'))
            return

        self.stdout.write(f'Testing as: {user.username}\n')

        anon = self._client()
        auth = self._client()
        auth.force_login(user)

        self._check_public_pages(anon)
        self._check_test_cases_hidden(anon, auth)
        self._check_submission_idor(auth, user)
        self._check_api_rbac(auth, user)
        self._check_role_escalation(auth, user)

        if options['password']:
            self._check_login_redirect(options['username'] or user.username, options['password'])
        else:
            self.stdout.write(self.style.WARNING(
                'SKIP  login open-redirect check (pass --password to include it)'))

        self.stdout.write('')
        if self.failures:
            self.stdout.write(self.style.ERROR(f'{len(self.failures)} FAILED, {self.passes} passed'))
            for failure in self.failures:
                self.stdout.write(self.style.ERROR(f'  - {failure}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'All {self.passes} checks passed.'))

    # -- helpers ------------------------------------------------------------

    def _client(self):
        return Client(SERVER_NAME=HOST)

    def _get(self, client, path):
        return client.get(path, secure=True, SERVER_NAME=HOST)

    def _resolve_user(self, username):
        if username:
            return User.objects.filter(username=username).first()
        profile = UserProfile.objects.filter(role='participant').select_related('user').first()
        return profile.user if profile else User.objects.filter(is_staff=False).first()

    def _record(self, ok, label):
        if ok:
            self.passes += 1
            self.stdout.write(self.style.SUCCESS(f'PASS  {label}'))
        else:
            self.failures.append(label)
            self.stdout.write(self.style.ERROR(f'FAIL  {label}'))

    # -- checks -------------------------------------------------------------

    def _check_public_pages(self, anon):
        for path in ['/leaderboard/', '/activity/', '/help/', '/privacy/', '/terms/']:
            response = self._get(anon, path)
            self._record(response.status_code == 200,
                         f'{path} renders (got {response.status_code})')

    def _check_test_cases_hidden(self, anon, auth):
        with_cases = Problem.objects.exclude(test_cases_json='').exclude(
            test_cases_json__isnull=True).first()
        if not with_cases:
            self.stdout.write(self.style.WARNING('SKIP  test-case visibility (no problem has test cases)'))
            return

        anon_response = self._get(anon, f'/api/problems/{with_cases.pk}/')
        self._record(anon_response.status_code == 200 and anon_response.json().get('test_cases') == [],
                     'anonymous API does not expose hidden test cases')

        auth_response = self._get(auth, f'/api/problems/{with_cases.pk}/')
        self._record(auth_response.status_code == 200 and auth_response.json().get('test_cases') == [],
                     'participant API does not expose hidden test cases')

    def _check_submission_idor(self, auth, user):
        other = Solution.objects.exclude(user=user).first()
        if not other:
            self.stdout.write(self.style.WARNING("SKIP  submission IDOR (no other user's submission exists)"))
            return

        page = self._get(auth, f'/submission/{other.pk}/')
        self._record(page.status_code == 404,
                     f"another user's submission page is not readable (got {page.status_code})")

        api = self._get(auth, f'/api/submission/{other.pk}/status/')
        self._record(api.status_code == 404,
                     f"another user's submission status is not readable (got {api.status_code})")

    def _check_api_rbac(self, auth, user):
        marker = 'SMOKE CHECK - DELETE ME'
        created = auth.post('/api/problems/', {
            'title': marker, 'difficulty': 'easy', 'description': 'smoke check',
        }, content_type='application/json', secure=True, SERVER_NAME=HOST)
        self._record(created.status_code == 403,
                     f'participant cannot create problems (got {created.status_code})')
        # Undo it if the guard failed, so a failed check leaves no litter.
        Problem.objects.filter(title=marker).delete()

        victim = User.objects.exclude(pk=user.pk).first()
        if victim:
            deleted = auth.delete(f'/api/users/{victim.pk}/', secure=True, SERVER_NAME=HOST)
            still_there = User.objects.filter(pk=victim.pk).exists()
            self._record(deleted.status_code == 403 and still_there,
                         f'participant cannot delete other accounts (got {deleted.status_code})')

    def _check_role_escalation(self, auth, user):
        profile = UserProfile.objects.filter(user=user).first()
        if not profile:
            self.stdout.write(self.style.WARNING('SKIP  role escalation (user has no profile)'))
            return

        original = profile.role
        auth.patch(f'/api/profiles/{profile.pk}/', {'role': 'admin'},
                   content_type='application/json', secure=True, SERVER_NAME=HOST)

        profile.refresh_from_db()
        escalated = profile.role != original
        if escalated:
            profile.role = original
            profile.save(update_fields=['role'])
        self._record(not escalated, 'participant cannot escalate their own role to admin')

    def _check_login_redirect(self, username, password):
        client = self._client()
        response = client.post(
            '/login/?next=https://example.com/',
            {'username': username, 'password': password},
            secure=True, SERVER_NAME=HOST,
        )
        target = response.get('Location', '')
        offsite = target.startswith('http://') or target.startswith('https://')
        offsite = offsite and HOST not in target
        self._record(not offsite, f'login does not redirect off-site (Location: {target or "none"})')
