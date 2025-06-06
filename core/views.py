from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse  # Add this import

from .models import UserProfile, Problem, Solution
from .forms import SubmitSolutionForm, ProblemForm, UserProfileForm
from .utils.execution import execute_code

import json
from django.db.models import Sum, Count, Q
from .models import ContestParticipant, ContestSubmission


# ---------------------
# Auth Views
# ---------------------

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


# ---------------------
# Problem Views
# ---------------------

@login_required
def add_problem(request):
    if request.method == 'POST':
        form = ProblemForm(request.POST)
        if form.is_valid():
            problem = form.save(commit=False)
            problem.created_by = request.user

            test_cases_text = form.cleaned_data.get('test_cases')
            try:
                json.loads(test_cases_text or "[]")  # Validate JSON
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

from core.utils.ai_review import generate_code_review

@login_required
def problem_detail(request, problem_id):
    problem = get_object_or_404(Problem, uuid=problem_id)
    form = SubmitSolutionForm(initial={'problem_id': str(problem.uuid)})
    output, verdict, feedback_message, debug = "", "", "", ""
    ai_feedback = None

    if request.method == "POST":
        print(f"POST request received - Action: {request.POST.get('action')}")  # Debug

        form = SubmitSolutionForm(request.POST)
        if form.is_valid():
            language = form.cleaned_data['language']
            code = form.cleaned_data['source_code']
            action = request.POST.get('action')

            print(f"Form valid - Language: {language}, Action: {action}")  # Debug
            print(f"Code length: {len(code)}")  # Debug

            # Handle AI Review action
            if action == "AI_Review":
                print("Executing AI_Review action")  # Debug
                
                try:
                    ai_feedback = generate_code_review(code)
                    print(f"[DEBUG] AI feedback generated: {ai_feedback[:100]}...")
                    
                    # Return JSON response for AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'ai_feedback': ai_feedback
                        })
                        
                except Exception as e:
                    ai_feedback = f"⚠️ AI review failed: {e}"
                    print(f"[ERROR] AI review failed: {e}")
                    
                    # Return JSON response for AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': str(e),
                            'ai_feedback': ai_feedback
                        })

            elif action == "Run":
                print("Executing Run action")  # Debug

                sample_input = problem.sample_input.strip() if problem.sample_input else ""
                sample_output = problem.sample_output.strip() if problem.sample_output else ""

                # Use first test case if sample input/output is missing
                if not sample_input or not sample_output:
                    try:
                        test_cases = json.loads(problem.test_cases_json or "[]")
                        if test_cases:
                            sample_input = test_cases[0].get("input", "")
                            sample_output = test_cases[0].get("output", "")
                    except json.JSONDecodeError:
                        messages.error(request, "Invalid test cases format.")
                        sample_input, sample_output = "", ""

                print(f"Sample input: '{sample_input}'")
                print(f"Sample output: '{sample_output}'")

                result = execute_code(language, code, sample_input, sample_output)
                print(f"Execution result: {result}")

                output = result.get('output', '') or result.get('error', '')
                verdict = result.get('verdict', '')
                feedback_message = get_feedback_message(verdict)
                debug = f"Input: '{sample_input}'\nExpected: '{sample_output}'\nActual: '{output}'\nVerdict: {verdict}"

            elif action == "Submit":
                print("Executing Submit action")  # Debug

                try:
                    test_cases = json.loads(problem.test_cases_json or "[]")
                    print(f"Test cases loaded: {len(test_cases)} cases")
                except json.JSONDecodeError:
                    messages.error(request, "Invalid test case format in the database.")
                    return redirect('problem_detail', problem_id=problem.uuid)

                all_passed = True
                failed_test_case = None

                for i, test_case in enumerate(test_cases):
                    test_input = test_case.get("input", "").strip()
                    expected_output = test_case.get("output", "").strip()

                    print(f"Testing case {i+1}: input='{test_input}', expected='{expected_output}'")

                    result = execute_code(language, code, test_input, expected_output)
                    current_verdict = result.get('verdict', '')
                    current_output = result.get('output', '') or result.get('error', '')

                    print(f"Test case {i+1} result: verdict={current_verdict}, output='{current_output}'")

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

                print(f"Final verdict: {verdict}")

                # Save submission
                Solution.objects.create(
                    user=request.user,
                    problem=problem,
                    code=code,
                    language=language,
                    verdict=verdict,
                    output=output
                )

                # ✅ Generate AI feedback after verdict
                try:
                    print("[DEBUG] Calling generate_code_review()")
                    ai_feedback = generate_code_review(code)
                    print("[DEBUG] AI feedback:", ai_feedback)
                except Exception as e:
                    ai_feedback = f"⚠️ AI review failed: {e}"
                    print("[ERROR] AI review failed:", e)

        else:
            print(f"Form invalid: {form.errors}")
            debug = f"Form errors: {form.errors}"
            
            # Return JSON response for AJAX requests with form errors
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Form validation failed',
                    'form_errors': form.errors
                })

    print("Rendering template with: output={!r}, verdict={!r}, feedback={!r}, ai_feedback={!r}".format(
        output, verdict, feedback_message, ai_feedback
    ))

    return render(request, 'core/problem_detail.html', {
        'problem': problem,
        'form': form,
        'output': output,
        'verdict': verdict,
        'feedback_message': feedback_message,
        'debug': debug,
        'ai_feedback': ai_feedback,
    })


# ---------------------
# Submission and Profile Views
# ---------------------

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

    # Contest Statistics
    contest_participations = ContestParticipant.objects.filter(user=request.user).select_related('contest')
    contest_stats = {
        'contests_participated': contest_participations.count(),
        'top_3_finishes': 0,
        'total_points': 0,
    }

    # Calculate contest rankings and points
    for participation in contest_participations:
        contest = participation.contest
        
        # Get all participants' total points for this contest
        participant_scores = []
        all_participants = ContestParticipant.objects.filter(contest=contest).select_related('user')
        
        for participant in all_participants:
            total_points = ContestSubmission.objects.filter(
                contest=contest,
                participant=participant
            ).aggregate(total=Sum('points_awarded'))['total'] or 0
            participant_scores.append((participant, total_points))
        
        # Sort by points (descending)
        participant_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Find user's rank and points
        for rank, (participant, points) in enumerate(participant_scores, 1):
            if participant.user == request.user:
                contest_stats['total_points'] += points
                if rank <= 3:
                    contest_stats['top_3_finishes'] += 1
                break

    # Recent Contest Participation (last 5)
    recent_contests = []
    for participation in contest_participations.order_by('-contest__start_time')[:5]:
        contest = participation.contest
        
        # Calculate user's rank in this contest
        participant_scores = []
        all_participants = ContestParticipant.objects.filter(contest=contest).select_related('user')
        
        for participant in all_participants:
            total_points = ContestSubmission.objects.filter(
                contest=contest,
                participant=participant
            ).aggregate(total=Sum('points_awarded'))['total'] or 0
            participant_scores.append((participant, total_points))
        
        participant_scores.sort(key=lambda x: x[1], reverse=True)
        
        user_rank = None
        for rank, (participant, points) in enumerate(participant_scores, 1):
            if participant.user == request.user:
                user_rank = rank
                break
        
        recent_contests.append({
            'contest': contest,
            'rank': user_rank,
            'participation': participation
        })

    # Problem Solving Statistics - FIXED VERSION
    user_solutions = Solution.objects.filter(user=request.user).select_related('problem')
    
    # Get distinct problems solved with AC verdict - using the correct approach
    solved_problems_query = user_solutions.filter(verdict='AC').select_related('problem')
    
    # Use a more efficient approach to count by difficulty (using lowercase to match database)
    easy_solved = solved_problems_query.filter(problem__difficulty='easy').values('problem').distinct().count()
    medium_solved = solved_problems_query.filter(problem__difficulty='medium').values('problem').distinct().count()
    hard_solved = solved_problems_query.filter(problem__difficulty='hard').values('problem').distinct().count()
    
    # Total unique problems solved
    total_problems_solved = solved_problems_query.values('problem').distinct().count()
    
    problem_stats = {
        'problems_solved': total_problems_solved,
        'total_submissions': user_solutions.count(),
        'easy_solved': easy_solved,
        'medium_solved': medium_solved,
        'hard_solved': hard_solved,
    }

    # Recent Submissions (last 10)
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


# ---------------------
# Helper
# ---------------------

def get_feedback_message(verdict):
    messages = {
        'AC': '✅ Output matched the sample output!',
        'WA': '❌ Wrong output for the sample input.',
        'TLE': '⏱️ Time Limit Exceeded on sample input.',
        'RE': '💥 Runtime Error on sample input.',
        'CE': '🛠️ Compilation Error on sample input.',
    }
    return messages.get(verdict, f'Unexpected result: {verdict}')


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator
from .models import Contest, ContestParticipant, ContestProblem, ContestSubmission, ContestAnnouncement, Problem, Solution
from .forms import ContestForm, ContestRegistrationForm, ContestAnnouncementForm
import json
from django import forms
# ---------------------
# Contest Views - Complete Updated Version
# ---------------------

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
import json

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
import json

def contest_list(request):
    """Display all contests with filtering and search"""
    contests = Contest.objects.all().order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        now = timezone.now()
        if status_filter == 'upcoming':
            contests = contests.filter(start_time__gt=now)
        elif status_filter == 'running':
            contests = contests.filter(start_time__lte=now, end_time__gt=now)
        elif status_filter == 'ended':
            contests = contests.filter(end_time__lt=now)
    
    # Search by title
    search_query = request.GET.get('search', '')
    if search_query:
        contests = contests.filter(title__icontains=search_query)
    
    # Filter by type
    type_filter = request.GET.get('type', 'all')
    if type_filter != 'all':
        contests = contests.filter(contest_type=type_filter)
    
    # Pagination
    paginator = Paginator(contests, 10)
    page_number = request.GET.get('page')
    contests = paginator.get_page(page_number)
    
    # Add participant count and user registration status
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
    """Display contest details and handle registration"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    is_registered = contest.participants.filter(id=request.user.id).exists()
    can_register = not is_registered and contest.is_upcoming and contest.registration_required
    
    # Handle registration
    if request.method == 'POST' and can_register:
        form = ContestRegistrationForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data.get('password', '')
            
            # Check password if required
            if contest.password and contest.password != password:
                messages.error(request, 'Incorrect contest password')
            # Check participant limit
            elif contest.max_participants and contest.participants.count() >= contest.max_participants:
                messages.error(request, 'Contest is full')
            else:
                ContestParticipant.objects.create(contest=contest, user=request.user)
                messages.success(request, 'Successfully registered for the contest!')
                return redirect('contest_detail', contest_uuid=contest.uuid)
    else:
        form = ContestRegistrationForm()
    
    # Get contest problems
    contest_problems = ContestProblem.objects.filter(contest=contest).select_related('problem')
    
    # Get announcements
    announcements = contest.announcements.all()[:5]
    
    # Get user's submissions and problem status if registered
    user_submissions = []
    problem_status = {}
    
    if is_registered and not contest.is_upcoming:
        user_submissions = ContestSubmission.objects.filter(
            contest=contest,
            participant__user=request.user
        ).select_related('problem', 'solution')
        
        # Calculate problem status for each problem
        for contest_problem in contest_problems:
            problem_uuid = contest_problem.problem.uuid
            problem_submissions = user_submissions.filter(problem=contest_problem.problem)
            
            if problem_submissions.exists():
                # Check if any submission is accepted
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
    """Display contest problems for registered participants"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    # Check if user is registered
    if not contest.participants.filter(id=request.user.id).exists():
        messages.error(request, 'You must be registered to view contest problems')
        return redirect('contest_detail', contest_uuid=contest.uuid)
    
    # Check if contest has started
    if contest.is_upcoming:
        messages.error(request, 'Contest has not started yet')
        return redirect('contest_detail', contest_uuid=contest.uuid)
    
    contest_problems = ContestProblem.objects.filter(contest=contest).select_related('problem').order_by('order')
    
    # Get user's submissions for each problem
    user_submissions = {}
    total_submissions = 0
    accepted_problems = 0
    
    if request.user.is_authenticated:
        # Get participant object
        try:
            participant = ContestParticipant.objects.get(contest=contest, user=request.user)
        except ContestParticipant.DoesNotExist:
            participant = None
        
        if participant:
            submissions = ContestSubmission.objects.filter(
                contest=contest,
                participant=participant
            ).select_related('problem', 'solution').order_by('-submitted_at')
            
            # Group submissions by problem UUID (as string for template compatibility)
            accepted_problem_uuids = set()  # Track which problems are accepted
            
            for submission in submissions:
                problem_id = str(submission.problem.uuid)
                if problem_id not in user_submissions:
                    user_submissions[problem_id] = []
                user_submissions[problem_id].append(submission)
                total_submissions += 1
                
                # Track accepted problems
                if submission.verdict == 'AC':
                    accepted_problem_uuids.add(problem_id)
            
            # Count unique accepted problems
            accepted_problems = len(accepted_problem_uuids)
    
    # Create progress stats
    progress_stats = {
        'accepted_problems': accepted_problems,
        'total_problems': contest_problems.count(),
        'total_submissions': total_submissions,
    }
    
    # Debug print to verify data
    print(f"DEBUG: Progress stats - {progress_stats}")
    print(f"DEBUG: User submissions count - {len(user_submissions)}")
    print(f"DEBUG: Accepted problems - {accepted_problems}")
    
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
    
    # Initialize context with default values
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
                # Get sample input/output
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
                        from .utils.execution import execute_code
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
                    
                    # Get the verdict from evaluation
                    verdict = result.get('verdict', 'IE')
                    score = result.get('score', 0)

                    # Save the solution WITH the verdict
                    solution = Solution.objects.create(
                        user=request.user,
                        problem=problem,
                        language=language,
                        code=code,
                        verdict=verdict,  # IMPORTANT: Save verdict to solution too
                        status=verdict,   # If you have a status field
                    )

                    # Save the submission
                    submission = ContestSubmission.objects.create(
                        contest=contest,
                        participant=participant,
                        problem=problem,
                        solution=solution,
                        verdict=verdict,
                        score=score,
                        points_awarded=score,  # Make sure points are set
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
    
    # Load user submissions
    context['user_submissions'] = ContestSubmission.objects.filter(
        contest=contest,
        participant=participant,
        problem=problem
    ).select_related('solution').order_by('-submitted_at')[:10]
    
    return render(request, 'core/contest_problem_detail.html', context)

@login_required
def contest_standings(request, contest_uuid):
    """Display contest leaderboard/standings"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    # Calculate standings
    participants = ContestParticipant.objects.filter(contest=contest).select_related('user')
    standings = []
    
    for participant in participants:
        # Get user's best submission for each problem
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
            
            # Convert UUID to string for consistent template access
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
    
    # Sort by total points (descending), then by submissions count (ascending)
    standings.sort(key=lambda x: (-x['total_points'], x['submissions_count']))
    
    # Add rank
    for i, standing in enumerate(standings):
        standing['rank'] = i + 1
    
    context = {
        'contest': contest,
        'standings': standings,
        'contest_problems': contest.contest_problems.all(),
    }
    return render(request, 'core/contest_standings.html', context)

@staff_member_required
def create_contest(request):
    """Create a new contest with enhanced debugging"""
    if request.method == 'POST':
        form = ContestForm(request.POST)
        
        if not form.is_valid():
            print(f"Form errors: {form.errors}")
            print(f"Non field errors: {form.non_field_errors()}")
        
        if form.is_valid():
            try:
                # Don't commit yet so we can debug
                contest = form.save(commit=False)
                print(f"Contest object created: {contest}")
                
                # Set the creator
                contest.created_by = request.user
                print(f"Set created_by to: {contest.created_by}")
                
                # Ensure duration is set - calculate from start/end times if not provided
                if not contest.duration and contest.start_time and contest.end_time:
                    contest.duration = contest.end_time - contest.start_time
                    print(f"Calculated duration: {contest.duration}")
                
                # Validate the contest object
                contest.full_clean()
                print("Contest validation passed")
                
                # Save the contest
                contest.save()
                print(f"Contest saved with ID: {contest.id}, UUID: {contest.uuid}")
                
                # Add selected problems to contest
                problems = form.cleaned_data.get('problems', [])
                print(f"Selected problems: {problems}")
                
                for i, problem in enumerate(problems):
                    contest_problem = ContestProblem.objects.create(
                        contest=contest,
                        problem=problem,
                        order=i + 1,
                        points=100  # Default points
                    )
                    print(f"Added problem {problem} with order {i+1}")
                
                messages.success(request, f'Contest "{contest.title}" created successfully!')
                return redirect('contest_detail', contest_uuid=contest.uuid)
                
            except Exception as e:
                print(f"Error saving contest: {e}")
                print(f"Error type: {type(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error creating contest: {str(e)}')
        else:
            # Form is not valid, show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ContestForm()
    
    return render(request, 'core/create_contest.html', {'form': form})

@staff_member_required
def edit_contest(request, contest_uuid):
    """Edit an existing contest"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    if request.method == 'POST':
        form = ContestForm(request.POST, instance=contest)
        if form.is_valid():
            contest = form.save()
            
            # Update contest problems
            existing_problems = set(contest.contest_problems.values_list('problem', flat=True))
            new_problems = set(form.cleaned_data.get('problems', []).values_list('id', flat=True))
            
            # Remove problems that are no longer selected
            for problem_id in existing_problems - new_problems:
                ContestProblem.objects.filter(contest=contest, problem_id=problem_id).delete()
            
            # Add new problems
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
    """Display contest announcements"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    announcements = contest.announcements.all()
    
    context = {
        'contest': contest,
        'announcements': announcements,
    }
    return render(request, 'core/contest_announcements.html', context)

# AJAX endpoint for real-time contest timer
@login_required
def contest_timer_api(request, contest_uuid):
    """API endpoint for contest timer updates"""
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

def debug_contest_status(request, contest_uuid):
    """Debug endpoint to check contest timing"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    now = timezone.now()
    
    debug_info = {
        'current_time': str(now),
        'contest_start': str(contest.start_time),
        'contest_end': str(contest.end_time),
        'status': contest.status,
        'is_upcoming': contest.is_upcoming,
        'is_running': contest.is_running,
        'is_ended': contest.is_ended,
        'time_until_start': str(contest.time_until_start) if contest.time_until_start else None,
        'time_remaining': str(contest.time_remaining) if contest.time_remaining else None,
        'timezone_info': {
            'USE_TZ': getattr(settings, 'USE_TZ', None),
            'TIME_ZONE': getattr(settings, 'TIME_ZONE', None),
        }
    }
    
    return JsonResponse(debug_info, indent=2)

def get_feedback_message(verdict):
    """
    Generate user-friendly feedback messages based on verdict
    """
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
    """Helper function to ensure all required context variables are set"""
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
from .forms import AnnouncementForm
from .models import ContestAnnouncement


# Add these views to your existing views.py file

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone

@staff_member_required
def create_announcement(request, contest_uuid):
    """Create a new announcement for a contest"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.contest = contest
            announcement.created_by = request.user  # If your model uses created_by, fix the field name here
            announcement.created_at = timezone.now()
            announcement.save()
            
            messages.success(request, 'Announcement created successfully!')
            return redirect('contest_announcements', contest_uuid=contest.uuid)
    else:
        form = AnnouncementForm()
    
    context = {
        'contest': contest,
        'form': form,
    }
    return render(request, 'core/create_announcement.html', context)

@staff_member_required
def edit_announcement(request, contest_uuid, announcement_id):
    """Edit an existing announcement"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    announcement = get_object_or_404(ContestAnnouncement, id=announcement_id, contest=contest)
    
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, instance=announcement)
        if form.is_valid():
            announcement = form.save(commit=False)
            #announcement.updated_at = timezone.now()  # Make sure this field exists, or remove this line
            announcement.save()
            
            messages.success(request, 'Announcement updated successfully!')
            return redirect('contest_announcements', contest_uuid=contest.uuid)
    else:
        form = AnnouncementForm(instance=announcement)
    
    context = {
        'contest': contest,
        'announcement': announcement,
        'form': form,
    }
    return render(request, 'core/edit_announcement.html', context)

@staff_member_required
def delete_announcement(request, contest_uuid, announcement_id):
    """Delete an announcement"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    announcement = get_object_or_404(ContestAnnouncement, id=announcement_id, contest=contest)
    
    if request.method == 'POST':
        announcement.delete()
        messages.success(request, 'Announcement deleted successfully!')
        return redirect('contest_announcements', contest_uuid=contest.uuid)
    
    context = {
        'contest': contest,
        'announcement': announcement,
    }
    return render(request, 'core/delete_announcement.html', context)

# Update your existing contest_announcements view to include management functionality
@login_required
def contest_announcements(request, contest_uuid):
    """Display contest announcements with management options for staff"""
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    announcements = contest.announcements.all().order_by('-created_at')
    
    # Check if user can manage announcements
    can_manage = request.user.is_staff or (hasattr(contest, 'created_by') and contest.created_by == request.user)
    
    context = {
        'contest': contest,
        'announcements': announcements,
        'can_manage': can_manage,
    }
    return render(request, 'core/contest_announcements.html', context)
