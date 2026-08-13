"""Static informational pages and the full leaderboard.

These back the footer links, which previously all pointed at href="#".
"""
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from core.models import Solution


def leaderboard(request):
    """Full ranking by distinct problems solved.

    The home page shows only the top four; this is the "Full Leaderboard"
    target. Uses the same annotation shape as core.views.auth.home so both
    pages agree on what "solved" means.
    """
    ranked_users = (
        User.objects
        .annotate(solved=Count('solution__problem', filter=Q(solution__verdict='AC'), distinct=True))
        .filter(solved__gt=0)
        .order_by('-solved', 'username')
    )

    paginator = Paginator(ranked_users, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    offset = (page_obj.number - 1) * paginator.per_page
    rows = [
        {'rank': offset + position, 'username': user.username, 'solved': user.solved}
        for position, user in enumerate(page_obj, start=1)
    ]

    return render(request, 'core/leaderboard.html', {
        'rows': rows,
        'page_obj': page_obj,
        'total_ranked': paginator.count,
    })


def activity(request):
    """Recent accepted submissions across the platform.

    The home page shows the last five; this is the "All Activity" target. Only
    accepted submissions appear, and only the username and problem title - the
    same information already published on the home page.
    """
    accepted = (
        Solution.objects
        .filter(verdict='AC')
        .select_related('user', 'problem')
        .order_by('-submitted_at')
    )

    paginator = Paginator(accepted, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'core/activity.html', {
        'page_obj': page_obj,
        'total_accepted': paginator.count,
    })


def help_page(request):
    return render(request, 'core/help.html')


def privacy(request):
    return render(request, 'core/privacy.html')


def terms(request):
    return render(request, 'core/terms.html')
