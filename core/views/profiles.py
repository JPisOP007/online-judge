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
from functools import wraps
from django.db import IntegrityError
from core.models import (
    UserProfile, Problem, Solution, Contest, ContestParticipant,
    ContestProblem, ContestSubmission, ContestAnnouncement
)
from core.forms import (
    SubmitSolutionForm, ProblemForm, UserProfileForm, ContestForm,
    ContestRegistrationForm, AnnouncementForm
)
from core.utils.secure_execution import secure_execute_code, secure_evaluate_submission
from core.views.auth import role_required
import json

@login_required
def profile_view(request):
    user_profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'role': 'participant'}
    )

    # Handle admin settings for admin users
    admin_settings = None
    if user_profile.role == 'admin':
        from core.models import AdminSettings
        admin_settings = AdminSettings.get_settings()
        
        if request.method == 'POST':
            # Check if it's admin settings update
            if 'update_admin_settings' in request.POST:
                ai_review_enabled = request.POST.get('ai_review_enabled') == 'on'
                admin_settings.ai_review_enabled = ai_review_enabled
                admin_settings.save()
                messages.success(request, 'Admin settings updated successfully.')
                return redirect('profile')
            else:
                # Regular profile update
                form = UserProfileForm(request.POST, request.FILES, instance=user_profile, user=request.user)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Profile updated successfully.')
                    return redirect('profile')
        else:
            form = UserProfileForm(instance=user_profile, user=request.user)
    else:
        if request.method == 'POST':
            form = UserProfileForm(request.POST, request.FILES, instance=user_profile, user=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('profile')
        else:
            form = UserProfileForm(instance=user_profile, user=request.user)

    # Contest statistics
    contest_participations = ContestParticipant.objects.filter(user=request.user).select_related('contest')
    
    contest_rankings = {}  
    
    contest_stats = {
        'contests_participated': contest_participations.count(),
        'top_3_finishes': 0,
        'total_points': 0,
    }

    for participation in contest_participations:
        contest = participation.contest
        
        if contest.id not in contest_rankings:
            participant_scores = ContestSubmission.objects.filter(
                contest=contest
            ).values('participant__user').annotate(
                total_points=Sum('points_awarded')
            ).order_by('-total_points')
            
            rankings = {}
            for rank, score_data in enumerate(participant_scores, 1):
                user_id = score_data['participant__user']
                rankings[user_id] = {
                    'rank': rank,
                    'points': score_data['total_points'] or 0
                }
            
            contest_rankings[contest.id] = rankings
        
        user_data = contest_rankings[contest.id].get(request.user.id, {'rank': None, 'points': 0})
        contest_stats['total_points'] += user_data['points']
        
        if user_data['rank'] and user_data['rank'] <= 3:
            contest_stats['top_3_finishes'] += 1

    recent_contests = []
    for participation in contest_participations.order_by('-contest__start_time')[:5]:
        contest = participation.contest
        user_data = contest_rankings.get(contest.id, {}).get(request.user.id, {'rank': None, 'points': 0})
        
        recent_contests.append({
            'contest': contest,
            'rank': user_data['rank'],
            'participation': participation
        })

    # Problem statistics
    user_solutions = Solution.objects.filter(user=request.user).select_related('problem')
    solved_problems_query = user_solutions.filter(verdict='AC').select_related('problem')
    
    easy_solved = solved_problems_query.filter(problem__difficulty='easy').values('problem').distinct().count()
    medium_solved = solved_problems_query.filter(problem__difficulty='medium').values('problem').distinct().count()
    hard_solved = solved_problems_query.filter(problem__difficulty='hard').values('problem').distinct().count()
    
    total_problems_solved = solved_problems_query.values('problem').distinct().count()
    
    problem_stats = {
        'problems_solved': total_problems_solved,
        'total_submissions': user_solutions.count(),
        'easy_solved': easy_solved,
        'medium_solved': medium_solved,
        'hard_solved': hard_solved,
    }

    recent_submissions = user_solutions.order_by('-submitted_at')[:10]

    return render(request, 'core/profile.html', {
        'user_profile': user_profile,
        'form': form,
        'contest_stats': contest_stats,
        'recent_contests': recent_contests,
        'problem_stats': problem_stats,
        'recent_submissions': recent_submissions,
        'admin_settings': admin_settings,
    })

@login_required
@role_required(['admin'])
def manage_roles(request):
    users = User.objects.all()
    
    # Ensure all users have profiles
    for user in users:
        UserProfile.objects.get_or_create(user=user, defaults={'role': 'participant'})
    
    users = users.select_related('userprofile')

    if request.method == 'POST':
        updated_count = 0
        for user in users:
            new_role = request.POST.get(f'role_{user.id}')
            if new_role and user.userprofile.role != new_role:
                user.userprofile.role = new_role
                user.userprofile.save()
                updated_count += 1
        
        if updated_count > 0:
            messages.success(request, f"Updated {updated_count} user roles successfully")
        else:
            messages.info(request, "No changes were made")
        return redirect('manage_roles')

    return render(request, 'core/manage_roles.html', {'users': users})

