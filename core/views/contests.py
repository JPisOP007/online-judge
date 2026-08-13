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
from core.views.problems import get_feedback_message
from collections import defaultdict
import json

def contest_list(request):
    contests = Contest.objects.all().order_by('-created_at')
    
    # Status filter
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        now = timezone.now()
        if status_filter == 'upcoming':
            contests = contests.filter(start_time__gt=now)
        elif status_filter == 'running':
            contests = contests.filter(start_time__lte=now, end_time__gt=now)
        elif status_filter == 'ended':
            contests = contests.filter(end_time__lt=now)
    
    # Search filter
    search_query = request.GET.get('search', '')
    if search_query:
        contests = contests.filter(title__icontains=search_query)
    
    # Type filter
    type_filter = request.GET.get('type', 'all')
    if type_filter != 'all':
        contests = contests.filter(contest_type=type_filter)
    
    # Pagination
    paginator = Paginator(contests, 10)
    page_number = request.GET.get('page')
    contests = paginator.get_page(page_number)
    
    # Add additional info for each contest
    for contest in contests:
        contest.participant_count = contest.participants.count()
        if request.user.is_authenticated:
            contest.is_registered = contest.participants.filter(id=request.user.id).exists()
        else:
            contest.is_registered = False
    
    context = {
        'contests': contests,
        'status_filter': status_filter,
        'search_query': search_query,
        'type_filter': type_filter,
    }
    return render(request, 'core/contest_list.html', context)

@login_required
def contest_detail(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    is_registered = contest.participants.filter(id=request.user.id).exists()
    can_register = not is_registered and not contest.is_ended and contest.registration_required
    
    if request.method == 'POST' and can_register:
        form = ContestRegistrationForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data.get('password', '')
            
            if contest.password and contest.password != password:
                messages.error(request, 'Incorrect contest password')
            elif contest.max_participants and contest.participants.count() >= contest.max_participants:
                messages.error(request, 'Contest is full')
            else:
                ContestParticipant.objects.create(contest=contest, user=request.user)
                messages.success(request, 'Successfully registered for the contest!')
                return redirect('contest_detail', contest_uuid=contest.uuid)
    else:
        form = ContestRegistrationForm()
    
    contest_problems = ContestProblem.objects.filter(contest=contest).select_related('problem')
    announcements = contest.announcements.all()[:5]
    
    user_submissions = []
    problem_status = {}
    
    if is_registered and not contest.is_upcoming:
        user_submissions = ContestSubmission.objects.filter(
            contest=contest,
            participant__user=request.user
        ).select_related('problem', 'solution')
        
        for contest_problem in contest_problems:
            problem_uuid = contest_problem.problem.uuid
            problem_submissions = user_submissions.filter(problem=contest_problem.problem)
            
            if problem_submissions.exists():
                if problem_submissions.filter(verdict='AC').exists():
                    problem_status[problem_uuid] = 'Accepted'
                else:
                    problem_status[problem_uuid] = 'Attempted'
            else:
                problem_status[problem_uuid] = 'Not Attempted'
    
    context = {
        'contest': contest,
        'is_registered': is_registered,
        'can_register': can_register,
        'form': form,
        'contest_problems': contest_problems,
        'announcements': announcements,
        'user_submissions': user_submissions,
        'problem_status': problem_status,
    }
    return render(request, 'core/contest_detail.html', context)

@login_required
def contest_problems(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    if not contest.participants.filter(id=request.user.id).exists():
        messages.error(request, 'You must be registered to view contest problems')
        return redirect('contest_detail', contest_uuid=contest.uuid)
    
    if contest.is_upcoming:
        messages.error(request, 'Contest has not started yet')
        return redirect('contest_detail', contest_uuid=contest.uuid)
    
    contest_problems = ContestProblem.objects.filter(contest=contest).select_related('problem').order_by('order')
    
    user_submissions = {}
    total_submissions = 0
    accepted_problems = 0
    
    if request.user.is_authenticated:
        try:
            participant = ContestParticipant.objects.get(contest=contest, user=request.user)
        except ContestParticipant.DoesNotExist:
            participant = None
        
        if participant:
            submissions = ContestSubmission.objects.filter(
                contest=contest,
                participant=participant
            ).select_related('problem', 'solution').order_by('-submitted_at')
            
            accepted_problem_uuids = set()
            
            for submission in submissions:
                problem_id = str(submission.problem.uuid)
                if problem_id not in user_submissions:
                    user_submissions[problem_id] = []
                user_submissions[problem_id].append(submission)
                total_submissions += 1
                
                if submission.verdict == 'AC':
                    accepted_problem_uuids.add(problem_id)
            
            accepted_problems = len(accepted_problem_uuids)
    
    progress_stats = {
        'accepted_problems': accepted_problems,
        'total_problems': contest_problems.count(),
        'total_submissions': total_submissions,
    }
    
    context = {
        'contest': contest,
        'contest_problems': contest_problems,
        'user_submissions': user_submissions,
        'progress_stats': progress_stats,
    }
    return render(request, 'core/contest_problems.html', context)

@login_required
def contest_problem_detail(request, contest_uuid, problem_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    problem = get_object_or_404(Problem, uuid=problem_uuid)
    participant = get_object_or_404(ContestParticipant, contest=contest, user=request.user)

    # Problems must not be readable before the contest opens, even by people
    # who have already registered. contest_problems() enforces this too.
    if contest.is_upcoming:
        messages.error(request, 'Contest has not started yet')
        return redirect('contest_detail', contest_uuid=contest.uuid)

    context = {
        'contest': contest,
        'problem': problem,
        'contest_problem': get_object_or_404(ContestProblem, contest=contest, problem=problem),
        'output': '',
        'verdict': '',
        'feedback_message': '',
        'user_submissions': [],
    }

    if request.method == "POST":
        form = SubmitSolutionForm(request.POST)
        if form.is_valid():
            action = request.POST.get('action')
            language = form.cleaned_data['language']
            code = form.cleaned_data['source_code']
            
            if action == "run":
                sample_input = problem.sample_input or ""
                sample_output = problem.sample_output or ""
                
                if not sample_input or not sample_output:
                    try:
                        test_cases = json.loads(problem.test_cases_json or "[]")
                        if test_cases:
                            sample_input = test_cases[0].get("input", "")
                            sample_output = test_cases[0].get("output", "")
                    except json.JSONDecodeError:
                        pass
                
                if sample_input and sample_output:
                    try:
                        result = secure_execute_code(language, code, sample_input, sample_output)
                        context.update({
                            'output': result.get('output', '') or result.get('error', 'No output'),
                            'verdict': result.get('verdict', 'IE'),
                            'feedback_message': get_feedback_message(result.get('verdict', 'IE'))
                        })
                    except ImportError:
                        context.update({
                            'output': "Execution service unavailable",
                            'verdict': "IE",
                            'feedback_message': "Code execution service not configured"
                        })
                else:
                    context.update({
                        'output': "No test cases available",
                        'verdict': "IE",
                        'feedback_message': "Problem has no test cases"
                    })
            
            elif action == "submit":
                # Scored submissions are only accepted while the contest is live.
                # Without this, submissions after the end time were still judged
                # and still counted towards the standings.
                if not contest.is_running:
                    context.update({
                        'form': form,
                        'verdict': 'IE',
                        'feedback_message': 'This contest is not currently accepting submissions.',
                        'output': 'The contest has ended.' if contest.is_ended
                                  else 'The contest has not started yet.',
                        'user_submissions': ContestSubmission.objects.filter(
                            contest=contest, participant=participant, problem=problem
                        ).select_related('solution').order_by('-submitted_at')[:10],
                    })
                    return render(request, 'core/contest_problem_detail.html', context)

                try:
                    test_cases = json.loads(problem.test_cases_json or "[]")
                except json.JSONDecodeError:
                    context.update({
                        'verdict': 'IE',
                        'feedback_message': 'Invalid test case format in the database'
                    })
                    return render(request, 'core/contest_problem_detail.html', context)

                if not test_cases:
                    context.update({
                        'verdict': 'IE',
                        'feedback_message': 'No test cases available for this problem'
                    })
                    return render(request, 'core/contest_problem_detail.html', context)

                all_passed = True
                failed_test_case = None
                verdict = "AC"
                output = ""
                feedback_message = ""
                score = 0

                for i, test_case in enumerate(test_cases):
                    test_input = test_case.get("input", "").strip()
                    expected_output = test_case.get("output", "").strip()

                    try:
                        result = secure_execute_code(language, code, test_input, expected_output)
                        current_verdict = result.get('verdict', '')
                        current_output = result.get('output', '') or result.get('error', '')

                        if current_verdict != 'AC':
                            all_passed = False
                            verdict = current_verdict
                            output = current_output
                            feedback_message = f"❌ Failed on test case {i+1}"
                            failed_test_case = i + 1
                            break
                    except Exception as e:
                        all_passed = False
                        verdict = "IE"
                        output = f"Execution error: {str(e)}"
                        feedback_message = f"❌ Error on test case {i+1}"
                        failed_test_case = i + 1
                        break

                if all_passed:
                    verdict = "AC"
                    output = "✅ All test cases passed."
                    feedback_message = "🎉 Code Accepted!"
                    score = 100
                else:
                    # Calculate partial score based on passed test cases
                    passed_cases = failed_test_case - 1 if failed_test_case else 0
                    score = int((passed_cases / len(test_cases)) * 100)

                try:
                    solution = Solution.objects.create(
                        user=request.user,
                        problem=problem,
                        language=language,
                        code=code,
                        verdict=verdict,
                        status=verdict,
                        output=output
                    )

                    submission = ContestSubmission.objects.create(
                        contest=contest,
                        participant=participant,
                        problem=problem,
                        solution=solution,
                        verdict=verdict,
                        score=score,
                        points_awarded=score,
                    )

                    context.update({
                        'verdict': submission.verdict,
                        'feedback_message': feedback_message,
                        'output': output,
                    })

                    messages.success(request, f'Solution submitted! {feedback_message}')

                except Exception as e:
                    context.update({
                        'verdict': 'IE',
                        'feedback_message': f'Error during submission: {str(e)}'
                    })
    
    else:
        form = SubmitSolutionForm(initial={'problem_id': str(problem.uuid)})
    
    context['form'] = form
    
    context['user_submissions'] = ContestSubmission.objects.filter(
        contest=contest,
        participant=participant,
        problem=problem
    ).select_related('solution').order_by('-submitted_at')[:10]
    
    return render(request, 'core/contest_problem_detail.html', context)

def contest_standings(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)

    participants = list(
        ContestParticipant.objects.filter(contest=contest).select_related('user')
    )
    contest_problems = list(
        contest.contest_problems.select_related('problem').all()
    )

    # This used to run two queries per participant per problem, plus one more
    # per participant, plus a fresh contest_problems query inside the loop:
    # 50 participants over 5 problems was 550+ queries for one page. Pull every
    # submission for the contest once and aggregate in memory instead.
    tally = {}
    submission_totals = defaultdict(int)
    submissions = ContestSubmission.objects.filter(contest=contest).values_list(
        'participant_id', 'problem_id', 'points_awarded'
    )
    for participant_id, problem_id, points in submissions:
        entry = tally.setdefault((participant_id, problem_id), {'points': 0, 'submissions': 0})
        entry['submissions'] += 1
        entry['points'] = max(entry['points'], points or 0)
        submission_totals[participant_id] += 1

    standings = []
    for participant in participants:
        user_points = 0
        solved_problems = 0
        problem_scores = {}

        for contest_problem in contest_problems:
            entry = tally.get(
                (participant.id, contest_problem.problem_id),
                {'points': 0, 'submissions': 0},
            )
            # get_item looks these up by str(uuid); keep that key shape.
            problem_scores[str(contest_problem.problem.uuid)] = dict(entry)
            user_points += entry['points']
            if entry['points'] > 0:
                solved_problems += 1

        standings.append({
            'participant': participant,
            'total_points': user_points,
            'solved_problems': solved_problems,
            'submissions_count': submission_totals.get(participant.id, 0),
            'problem_scores': problem_scores,
        })

    standings.sort(key=lambda x: (-x['total_points'], x['submissions_count']))

    for i, standing in enumerate(standings):
        standing['rank'] = i + 1

    context = {
        'contest': contest,
        'standings': standings,
        'contest_problems': contest_problems,
    }
    return render(request, 'core/contest_standings.html', context)

@login_required
@role_required(['setter', 'admin'])
def create_contest(request):
    if request.method == 'POST':
        form = ContestForm(request.POST)
        
        if form.is_valid():
            try:
                contest = form.save(commit=False)
                contest.created_by = request.user
                
                if not contest.duration and contest.start_time and contest.end_time:
                    contest.duration = contest.end_time - contest.start_time
                
                contest.full_clean()
                contest.save()
                
                # Auto-register the creator
                if contest.registration_required:
                    ContestParticipant.objects.create(contest=contest, user=request.user)
                
                problems = form.cleaned_data.get('problems', [])
                
                for i, problem in enumerate(problems):
                    contest_problem = ContestProblem.objects.create(
                        contest=contest,
                        problem=problem,
                        order=i + 1,
                        points=100
                    )
                
                messages.success(request, f'Contest "{contest.title}" created successfully!')
                return redirect('contest_detail', contest_uuid=contest.uuid)
                
            except Exception as e:
                messages.error(request, f'Error creating contest: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ContestForm()
    
    return render(request, 'core/create_contest.html', {'form': form})

@login_required
@role_required(['setter', 'admin'])
def edit_contest(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    if request.method == 'POST':
        form = ContestForm(request.POST, instance=contest)
        if form.is_valid():
            contest = form.save()
            
            existing_problems = set(contest.contest_problems.values_list('problem', flat=True))
            new_problems = set(form.cleaned_data.get('problems', []).values_list('id', flat=True))
            
            for problem_id in existing_problems - new_problems:
                ContestProblem.objects.filter(contest=contest, problem_id=problem_id).delete()
            
            for i, problem in enumerate(form.cleaned_data.get('problems', [])):
                contest_problem, created = ContestProblem.objects.get_or_create(
                    contest=contest,
                    problem=problem,
                    defaults={'order': i + 1, 'points': 100}
                )
                if not created:
                    contest_problem.order = i + 1
                    contest_problem.save()
            
            messages.success(request, 'Contest updated successfully!')
            return redirect('contest_detail', contest_uuid=contest.uuid)
    else:
        form = ContestForm(instance=contest)
        form.fields['problems'].initial = contest.contest_problems.values_list('problem', flat=True)
    
    return render(request, 'core/edit_contest.html', {'form': form, 'contest': contest})

@login_required
def contest_announcements(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    announcements = contest.announcements.all().order_by('-created_at')
    
    try:
        user_role = request.user.userprofile.role
    except UserProfile.DoesNotExist:
        user_role = 'participant'
    can_manage = user_role in ('setter', 'admin') or contest.created_by == request.user
    
    context = {
        'contest': contest,
        'announcements': announcements,
        'can_manage': can_manage,
    }
    return render(request, 'core/contest_announcements.html', context)

def contest_timer_api(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    time_data = {
        'status': contest.status,
        'time_remaining': None,
        'time_until_start': None,
    }
    
    if contest.is_running and contest.time_remaining:
        time_data['time_remaining'] = int(contest.time_remaining.total_seconds())
    elif contest.is_upcoming and contest.time_until_start:
        time_data['time_until_start'] = int(contest.time_until_start.total_seconds())
    
    return JsonResponse(time_data)

@login_required
@role_required(['setter', 'admin'])
def create_announcement(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.contest = contest
            announcement.created_by = request.user
            announcement.created_at = timezone.now()
            announcement.save()
            messages.success(request, 'Announcement created successfully!')
            return redirect('contest_announcements', contest_uuid=contest.uuid)
    else:
        form = AnnouncementForm()
    
    return render(request, 'core/create_announcement.html', {
        'contest': contest,
        'form': form,
    })

@login_required
@role_required(['setter', 'admin'])
def edit_announcement(request, contest_uuid, announcement_id):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    announcement = get_object_or_404(ContestAnnouncement, id=announcement_id, contest=contest)
    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.save()
            messages.success(request, 'Announcement updated successfully!')
            return redirect('contest_announcements', contest_uuid=contest.uuid)
    else:
        form = AnnouncementForm(instance=announcement)
    
    return render(request, 'core/edit_announcement.html', {
        'contest': contest,
        'announcement': announcement,
        'form': form,
    })

@login_required
@role_required(['setter', 'admin'])
def delete_announcement(request, contest_uuid, announcement_id):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    announcement = get_object_or_404(ContestAnnouncement, id=announcement_id, contest=contest)
    
    if request.method == 'POST':
        announcement.delete()
        messages.success(request, 'Announcement deleted successfully!')
        return redirect('contest_announcements', contest_uuid=contest.uuid)
    
    return render(request, 'core/delete_announcement.html', {
        'contest': contest,
        'announcement': announcement,
    })

