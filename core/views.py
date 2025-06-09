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

from .models import (
    UserProfile, Problem, Solution, Contest, ContestParticipant,
    ContestProblem, ContestSubmission, ContestAnnouncement
)

from .forms import (
    SubmitSolutionForm, ProblemForm, UserProfileForm, ContestForm,
    ContestRegistrationForm, AnnouncementForm
)

from .utils.execution import execute_code

import json


def role_required(allowed_roles):
    """
    Decorator to check if user has required role
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            try:
                user_profile = UserProfile.objects.get(user=request.user)
                user_role = user_profile.role
            except UserProfile.DoesNotExist:
                user_role = 'participant'  # Default role
            
            if user_role not in allowed_roles:
                return render(request, 'core/forbidden.html', status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def home(request):
    return render(request, 'core/home.html')


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
        else:
            user = User.objects.create_user(username=username, password=password)
            UserProfile.objects.get_or_create(user=user, defaults={'role': 'participant'})
            messages.success(request, 'Registered successfully')
            return redirect('login')
    return render(request, 'core/register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid credentials')
    return render(request, 'core/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
@role_required(['problem_setter', 'admin'])  # Only problem setters and admins can add problems
def add_problem(request):
    if request.method == 'POST':
        form = ProblemForm(request.POST)
        if form.is_valid():
            problem = form.save(commit=False)
            problem.created_by = request.user

            test_cases_text = form.cleaned_data.get('test_cases')
            try:
                json.loads(test_cases_text or "[]")
                problem.test_cases_json = test_cases_text
            except json.JSONDecodeError:
                form.add_error('test_cases', 'Invalid JSON format.')
                return render(request, 'core/add_problem.html', {'form': form})

            problem.save()
            return redirect('problem_list')
    else:
        form = ProblemForm()
    return render(request, 'core/add_problem.html', {'form': form})


@login_required
def problem_list(request):
    problems = Problem.objects.all()
    problem_data = [
        (problem, [tag.strip() for tag in problem.tags.split(",")] if problem.tags else [])
        for problem in problems
    ]
    return render(request, "core/problem_list.html", {"problem_data": problem_data})


@login_required
def problem_detail(request, problem_id):
    problem = get_object_or_404(Problem, uuid=problem_id)
    form = SubmitSolutionForm(initial={'problem_id': str(problem.uuid)})
    output, verdict, feedback_message, debug = "", "", "", ""
    ai_feedback = None

    if request.method == "POST":
        form = SubmitSolutionForm(request.POST)
        if form.is_valid():
            language = form.cleaned_data['language']
            code = form.cleaned_data['source_code']
            action = request.POST.get('action')

            if action == "AI_Review":
                try:
                    from core.utils.ai_review import generate_code_review
                    ai_feedback = generate_code_review(code)
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'ai_feedback': ai_feedback
                        })
                        
                except Exception as e:
                    ai_feedback = f"⚠️ AI review failed: {e}"
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': str(e),
                            'ai_feedback': ai_feedback
                        })

            elif action == "Run":
                sample_input = problem.sample_input.strip() if problem.sample_input else ""
                sample_output = problem.sample_output.strip() if problem.sample_output else ""

                if not sample_input or not sample_output:
                    try:
                        test_cases = json.loads(problem.test_cases_json or "[]")
                        if test_cases:
                            sample_input = test_cases[0].get("input", "")
                            sample_output = test_cases[0].get("output", "")
                    except json.JSONDecodeError:
                        messages.error(request, "Invalid test cases format.")
                        sample_input, sample_output = "", ""

                result = execute_code(language, code, sample_input, sample_output)
                output = result.get('output', '') or result.get('error', '')
                verdict = result.get('verdict', '')
                feedback_message = get_feedback_message(verdict)
                debug = f"Input: '{sample_input}'\nExpected: '{sample_output}'\nActual: '{output}'\nVerdict: {verdict}"

            elif action == "Submit":
                try:
                    test_cases = json.loads(problem.test_cases_json or "[]")
                except json.JSONDecodeError:
                    messages.error(request, "Invalid test case format in the database.")
                    return redirect('problem_detail', problem_id=problem.uuid)

                all_passed = True
                failed_test_case = None

                for i, test_case in enumerate(test_cases):
                    test_input = test_case.get("input", "").strip()
                    expected_output = test_case.get("output", "").strip()

                    result = execute_code(language, code, test_input, expected_output)
                    current_verdict = result.get('verdict', '')
                    current_output = result.get('output', '') or result.get('error', '')

                    if current_verdict != 'AC':
                        all_passed = False
                        verdict = current_verdict
                        output = current_output
                        feedback_message = f"❌ Failed on test case {i+1}"
                        debug = f"Failed on test case {i+1}:\nInput: '{test_input}'\nExpected: '{expected_output}'\nActual: '{current_output}'\nVerdict: {current_verdict}"
                        break

                if all_passed:
                    verdict = "AC"
                    output = "✅ All test cases passed."
                    feedback_message = "🎉 Code Accepted!"
                    debug = f"All {len(test_cases)} test cases passed successfully!"

                Solution.objects.create(
                    user=request.user,
                    problem=problem,
                    code=code,
                    language=language,
                    verdict=verdict,
                    output=output
                )

                try:
                    from core.utils.ai_review import generate_code_review
                    ai_feedback = generate_code_review(code)
                except Exception as e:
                    ai_feedback = f"⚠️ AI review failed: {e}"

        else:
            debug = f"Form errors: {form.errors}"
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Form validation failed',
                    'form_errors': form.errors
                })

    return render(request, 'core/problem_detail.html', {
        'problem': problem,
        'form': form,
        'output': output,
        'verdict': verdict,
        'feedback_message': feedback_message,
        'debug': debug,
        'ai_feedback': ai_feedback,
    })


@login_required
def submit_solution(request, problem_id):
    problem = get_object_or_404(Problem, uuid=problem_id)
    if request.method == 'POST':
        form = SubmitSolutionForm(request.POST)
        if form.is_valid():
            Solution.objects.create(
                problem=problem,
                user=request.user,
                code=form.cleaned_data['source_code'],
                language=form.cleaned_data['language']
            )
            messages.success(request, "Solution submitted successfully")
            return redirect('problem_detail', problem_id=problem.uuid)
    else:
        form = SubmitSolutionForm(initial={'problem_id': str(problem.uuid)})
    return render(request, 'core/submit_solution.html', {'problem': problem, 'form': form})


@login_required
def submission_detail(request, submission_id):
    submission = get_object_or_404(Solution, pk=submission_id)
    if request.user != submission.user and not request.user.is_staff:
        return render(request, 'core/forbidden.html', status=403)
    return render(request, 'core/submission_detail.html', {'submission': submission})

@login_required
def profile_view(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=user_profile, user=request.user)

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
    })

@staff_member_required
@role_required(['admin'])  
def manage_roles(request):
    users = User.objects.all()
    for user in users:
        UserProfile.objects.get_or_create(user=user, defaults={'role': 'participant'})
    users = users.select_related('userprofile')

    if request.method == 'POST':
        for user in users:
            new_role = request.POST.get(f'role_{user.id}')
            if new_role and user.userprofile.role != new_role:
                user.userprofile.role = new_role
                user.userprofile.save()
        messages.success(request, "Roles updated successfully")
        return redirect('manage_roles')

    return render(request, 'core/manage_roles.html', {'users': users})


def contest_list(request):
    contests = Contest.objects.all().order_by('-created_at')
    
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        now = timezone.now()
        if status_filter == 'upcoming':
            contests = contests.filter(start_time__gt=now)
        elif status_filter == 'running':
            contests = contests.filter(start_time__lte=now, end_time__gt=now)
        elif status_filter == 'ended':
            contests = contests.filter(end_time__lt=now)
    
    search_query = request.GET.get('search', '')
    if search_query:
        contests = contests.filter(title__icontains=search_query)
    
    type_filter = request.GET.get('type', 'all')
    if type_filter != 'all':
        contests = contests.filter(contest_type=type_filter)
    
    paginator = Paginator(contests, 10)
    page_number = request.GET.get('page')
    contests = paginator.get_page(page_number)
    
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
    can_register = not is_registered and contest.is_upcoming and contest.registration_required
    
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
                        result = execute_code(language, code, sample_input, sample_output)
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
                try:
                    from .utils.execution import evaluate_submission
                    result = evaluate_submission(language, code, problem)
                    
                    verdict = result.get('verdict', 'IE')
                    score = result.get('score', 0)

                    solution = Solution.objects.create(
                        user=request.user,
                        problem=problem,
                        language=language,
                        code=code,
                        verdict=verdict,
                        status=verdict,
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
                        'feedback_message': get_feedback_message(submission.verdict),
                    })

                    messages.success(request, f'Solution submitted! Verdict: {get_feedback_message(verdict)}')

                except ImportError:
                    context.update({
                        'verdict': 'IE',
                        'feedback_message': 'Evaluation service not available'
                    })
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


@login_required
def contest_standings(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    participants = ContestParticipant.objects.filter(contest=contest).select_related('user')
    standings = []
    
    for participant in participants:
        user_points = 0
        solved_problems = 0
        submissions_count = 0
        
        problem_scores = {}
        for contest_problem in contest.contest_problems.all():
            best_submission = ContestSubmission.objects.filter(
                contest=contest,
                participant=participant,
                problem=contest_problem.problem
            ).order_by('-points_awarded', 'submitted_at').first()
            
            problem_key = str(contest_problem.problem.uuid)
            
            if best_submission:
                problem_scores[problem_key] = {
                    'points': best_submission.points_awarded,
                    'submissions': ContestSubmission.objects.filter(
                        contest=contest,
                        participant=participant,
                        problem=contest_problem.problem
                    ).count()
                }
                user_points += best_submission.points_awarded
                if best_submission.points_awarded > 0:
                    solved_problems += 1
            else:
                problem_scores[problem_key] = {
                    'points': 0, 
                    'submissions': 0
                }
        
        submissions_count = ContestSubmission.objects.filter(
            contest=contest,
            participant=participant
        ).count()
        
        standings.append({
            'participant': participant,
            'total_points': user_points,
            'solved_problems': solved_problems,
            'submissions_count': submissions_count,
            'problem_scores': problem_scores,
        })
    
    standings.sort(key=lambda x: (-x['total_points'], x['submissions_count']))
    
    for i, standing in enumerate(standings):
        standing['rank'] = i + 1
    
    context = {
        'contest': contest,
        'standings': standings,
        'contest_problems': contest.contest_problems.all(),
    }
    return render(request, 'core/contest_standings.html', context)


@staff_member_required
@role_required(['admin'])  
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


@staff_member_required
@role_required(['admin'])  
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
    
    can_manage = request.user.is_staff or (hasattr(contest, 'created_by') and contest.created_by == request.user)
    
    context = {
        'contest': contest,
        'announcements': announcements,
        'can_manage': can_manage,
    }
    return render(request, 'core/contest_announcements.html', context)


@login_required
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
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings

from .forms import AnnouncementForm
from .models import ContestAnnouncement, Contest


def get_feedback_message(verdict):
    feedback_messages = {
        'AC': '🎉 Accepted! Your solution is correct.',
        'WA': '❌ Wrong Answer. Your output doesn\'t match the expected output.',
        'TLE': '⏱️ Time Limit Exceeded. Your solution took too long to execute.',
        'MLE': '💾 Memory Limit Exceeded. Your solution used too much memory.',
        'CE': '🔧 Compilation Error. There are syntax errors in your code.',
        'RE': '💥 Runtime Error. Your program crashed during execution.',
        'PE': '📝 Presentation Error. Your output format is incorrect.',
        'OLE': '📤 Output Limit Exceeded. Your program produced too much output.',
        'IE': '🔧 Internal Error. Please try again later.',
        'SE': '🚨 System Error. Please contact support.',
    }
    return feedback_messages.get(verdict, f'Unknown verdict: {verdict}')


def get_default_context(contest, problem, contest_problem, form, user_submissions=None):
    return {
        'contest': contest,
        'problem': problem,
        'contest_problem': contest_problem,
        'form': form,
        'output': '',
        'verdict': '',
        'feedback_message': '',
        'user_submissions': user_submissions or [],
    }


@staff_member_required
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


@staff_member_required
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


@staff_member_required
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


@login_required
def contest_announcements(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    announcements = contest.announcements.all().order_by('-created_at')
    can_manage = request.user.is_staff or (hasattr(contest, 'created_by') and contest.created_by == request.user)

    return render(request, 'core/contest_announcements.html', {
        'contest': contest,
        'announcements': announcements,
        'can_manage': can_manage,
    })
