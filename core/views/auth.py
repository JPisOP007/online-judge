from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from functools import wraps
from django.db import IntegrityError
from django.core.cache import cache
import logging
import re

logger = logging.getLogger('core.security')
from core.models import (
    UserProfile, Problem, Solution, Contest, ContestParticipant,
    ContestProblem, ContestSubmission, ContestAnnouncement
)
from core.forms import (
    SubmitSolutionForm, ProblemForm, UserProfileForm, ContestForm,
    ContestRegistrationForm, AnnouncementForm
)
from core.utils.secure_execution import secure_execute_code, secure_evaluate_submission
import json

def role_required(allowed_roles):
    """
    Decorator to check if user has required role
    Fixed version with proper authentication handling
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # First check if user is authenticated
            if not request.user.is_authenticated:
                messages.error(request, 'Please login to access this page.')
                return redirect('login')
            
            # Get or create user profile
            try:
                user_profile = UserProfile.objects.get(user=request.user)
                user_role = user_profile.role
            except UserProfile.DoesNotExist:
                # Create default profile if it doesn't exist
                user_profile = UserProfile.objects.create(
                    user=request.user, 
                    role='participant'
                )
                user_role = 'participant'
            
            # Check if user has required role
            if user_role not in allowed_roles:
                messages.error(request, f'Access denied. Required roles: {", ".join(allowed_roles)}')
                return render(request, 'core/forbidden.html', {'required_roles': allowed_roles}, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

HOME_STATS_CACHE_KEY = 'home_page_stats_v1'
HOME_STATS_CACHE_SECONDS = 60


def _build_home_stats():
    """The eight aggregate queries behind the home page."""
    now = timezone.now()

    # Leaderboard: top 4 users by distinct problems solved
    top_users = User.objects.annotate(
        solved=Count('solution__problem', filter=Q(solution__verdict='AC'), distinct=True)
    ).filter(solved__gt=0).order_by('-solved')[:4]

    # Recent activity: top 5 recent AC submissions
    recent_sols = Solution.objects.filter(verdict='AC').select_related('user', 'problem').order_by('-submitted_at')[:5]

    return {
        'total_problems': Problem.objects.count(),
        'active_contests': Contest.objects.filter(start_time__lte=now, end_time__gte=now).count(),
        'total_users': User.objects.count(),
        'total_contests': Contest.objects.count(),
        'total_submissions': Solution.objects.count(),
        'leaderboard': [{'username': u.username, 'solved': u.solved} for u in top_users],
        'recent_activity': [
            {'username': s.user.username, 'problem': s.problem.title, 'when': s.submitted_at}
            for s in recent_sols
        ],
    }


def home(request):
    # The landing page costs eight aggregate round trips and is identical for
    # every visitor, so it is the first thing to fall over under a traffic
    # spike. Cache it briefly; counters being up to a minute stale is fine.
    try:
        context = cache.get(HOME_STATS_CACHE_KEY)
        if context is None:
            context = _build_home_stats()
            cache.set(HOME_STATS_CACHE_KEY, context, HOME_STATS_CACHE_SECONDS)
    except Exception as exc:
        # An unreachable cache must not take the home page down with it.
        logger.warning(f"Home stats cache unavailable: {exc}")
        context = _build_home_stats()

    context = dict(context)

    if request.user.is_authenticated:
        user_solved = Solution.objects.filter(user=request.user, verdict='AC').values('problem').distinct().count()
        context['user_solved'] = user_solved

    return render(request, 'core/home.html', context)

def register(request):
    username = ''
    email = ''

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''

        errors = []

        if not username:
            errors.append('Username is required.')
        elif len(username) > 150:
            errors.append('Username must be 150 characters or fewer.')
        elif not re.match(r'^[\w.@+-]+$', username):
            errors.append('Username can only contain letters, digits and @/./+/-/_ characters.')
        elif User.objects.filter(username=username).exists():
            errors.append('Username already exists.')

        if email:
            try:
                validate_email(email)
            except ValidationError:
                errors.append('Enter a valid email address.')

        if not password:
            errors.append('Password is required.')
        else:
            # AUTH_PASSWORD_VALIDATORS were configured but never ran here, because
            # create_user() does not validate. Run them explicitly.
            try:
                validate_password(password, User(username=username, email=email))
            except ValidationError as exc:
                errors.extend(exc.messages)

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                user = User.objects.create_user(username=username, password=password, email=email)

                # Safe profile creation
                UserProfile.objects.get_or_create(user=user, defaults={'role': 'participant'})

                messages.success(request, 'Registration successful! Please login.')
                return redirect('login')

            except IntegrityError:
                # Lost a race on the username; don't leak database internals.
                messages.error(request, 'That username is already taken. Please choose another.')

    return render(request, 'core/register.html', {'username': username, 'email': email})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            # Create profile if it doesn't exist
            UserProfile.objects.get_or_create(user=user, defaults={'role': 'participant'})
            messages.success(request, f'Welcome back, {user.username}!')

            # Redirect to next page if specified, but only to URLs on this site.
            # An unvalidated ?next= lets an attacker bounce users to an external
            # phishing page straight off a genuine login on our own domain.
            next_page = request.POST.get('next') or request.GET.get('next')
            if next_page and url_has_allowed_host_and_scheme(
                url=next_page,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_page)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')

