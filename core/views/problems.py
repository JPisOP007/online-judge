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
from core.tasks import evaluate_submission_task
import json

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
            messages.success(request, 'Problem added successfully!')
            return redirect('problem_list')
    else:
        form = ProblemForm()
    return render(request, 'core/add_problem.html', {'form': form})

def problem_list(request):
    problems = Problem.objects.all().order_by('-created_at')
    
    # Add search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        problems = problems.filter(
            Q(title__icontains=search_query) | 
            Q(tags__icontains=search_query)
        )
    
    # Add difficulty filter
    difficulty_filter = request.GET.get('difficulty', 'all')
    if difficulty_filter != 'all':
        problems = problems.filter(difficulty=difficulty_filter)
    
    # Pagination
    paginator = Paginator(problems, 20)
    page_number = request.GET.get('page')
    problems = paginator.get_page(page_number)
    
    problem_data = []
    for problem in problems:
        tags = [tag.strip() for tag in problem.tags.split(",")] if problem.tags else []
        
        # Check if user has solved this problem
        user_solved = False
        if request.user.is_authenticated:
            user_solved = Solution.objects.filter(
                user=request.user,
                problem=problem,
                verdict='AC'
            ).exists()
        
        problem_data.append({
            'problem': problem,
            'tags': tags,
            'solved': user_solved
        })
    
    context = {
        'problem_data': problem_data,
        'search_query': search_query,
        'difficulty_filter': difficulty_filter,
        'problems': problems,  # For pagination
    }
    return render(request, "core/problem_list.html", context)

def problem_detail(request, problem_id):
    problem = get_object_or_404(Problem, uuid=problem_id)
    form = SubmitSolutionForm(initial={'problem_id': str(problem.uuid)})
    output, verdict, feedback_message, debug = "", "", "", ""
    ai_feedback = None

    # Check if user has solved this problem
    user_solved = Solution.objects.filter(
        user=request.user,
        problem=problem,
        verdict='AC'
    ).exists()

    if request.method == "POST":
        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        form = SubmitSolutionForm(request.POST)
        if form.is_valid():
            language = form.cleaned_data['language']
            code = form.cleaned_data['source_code']
            action = request.POST.get('action', '').lower()

            if action == "ai_review":
                # Check if AI review is enabled by admin
                from core.models import AdminSettings
                admin_settings = AdminSettings.get_settings()
                
                if not admin_settings.ai_review_enabled:
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': 'AI review is currently disabled by administrator',
                            'review': {
                                "logic": "AI review is currently disabled",
                                "efficiency": "AI review is currently disabled",
                                "clarity": "AI review is currently disabled", 
                                "best_practices": "AI review is currently disabled"
                            },
                            'ai_feedback': {
                                "logic": "AI review is currently disabled",
                                "efficiency": "AI review is currently disabled",
                                "clarity": "AI review is currently disabled", 
                                "best_practices": "AI review is currently disabled"
                            }
                        }, status=403)
                
                try:
                    from core.utils.ai_review import generate_code_review
                    ai_result = generate_code_review(code)
        
                    if is_ajax:
                        if ai_result['success']:
                            return JsonResponse({
                                'success': True,
                                'review': ai_result['review'],
                                'ai_feedback': ai_result['review']
                            })
                        else:
                            return JsonResponse({
                                'success': False,
                                'error': ai_result['error'],
                                'review': ai_result['review'],
                                'ai_feedback': ai_result['review']
                            }, status=500)
                
                except Exception as e:
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': str(e),
                            'review': {
                                "logic": "AI review unavailable",
                                "efficiency": "AI review unavailable",
                                "clarity": "AI review unavailable", 
                                "best_practices": "AI review unavailable"
                            },
                            'ai_feedback': {
                                "logic": "AI review unavailable",
                                "efficiency": "AI review unavailable",
                                "clarity": "AI review unavailable", 
                                "best_practices": "AI review unavailable"
                            }
                        }, status=500)

            elif action == "run":
                sample_input = problem.sample_input.strip() if problem.sample_input else ""
                sample_output = problem.sample_output.strip() if problem.sample_output else ""

                if not sample_input or not sample_output:
                    try:
                        test_cases = json.loads(problem.test_cases_json or "[]")
                        if test_cases:
                            sample_input = test_cases[0].get("input", "")
                            sample_output = test_cases[0].get("output", "")
                    except json.JSONDecodeError:
                        sample_input, sample_output = "", ""

                if sample_input and sample_output:
                    try:
                        result = secure_execute_code(language, code, sample_input, sample_output)
                        
                        # For Run Code, always show the Expected vs Actual mismatch if it failed the sample test
                        verdict = result.get('verdict', '')
                        if verdict != 'AC' and result.get('error'):
                            output = result.get('error')
                        else:
                            output = result.get('output', '') or result.get('error', '')
                            
                        feedback_message = get_feedback_message(verdict)
                        debug = f"Input: '{sample_input}'\nExpected: '{sample_output}'\nActual: '{result.get('output', '')}'\nVerdict: {verdict}"
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': True,
                                'output': output,
                                'verdict': verdict,
                                'feedback_message': feedback_message,
                                'debug': debug
                            })
                            
                    except Exception as e:
                        output = f"Execution error: {str(e)}"
                        verdict = "IE"
                        feedback_message = get_feedback_message("IE")
                        
                        if is_ajax:
                            return JsonResponse({
                                'success': False,
                                'output': output,
                                'verdict': verdict,
                                'feedback_message': feedback_message,
                                'error': str(e)
                            })
                else:
                    output = "No sample test case available"
                    verdict = "IE"
                    feedback_message = "Cannot run without sample test cases"
                    
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'output': output,
                            'verdict': verdict,
                            'feedback_message': feedback_message,
                            'error': 'No test cases available'
                        })

            elif action == "submit":
                try:
                    test_cases = json.loads(problem.test_cases_json or "[]")
                except json.JSONDecodeError:
                    error_msg = "Invalid test case format in the database."
                    
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': error_msg,
                            'verdict': 'IE',
                            'feedback_message': 'Database error'
                        })
                    
                    messages.error(request, error_msg)
                    return redirect('problem_detail', problem_id=problem.uuid)

                if not test_cases:
                    error_msg = "No test cases available for this problem."
                    
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'error': error_msg,
                            'verdict': 'IE',
                            'feedback_message': 'No test cases'
                        })
                    
                    messages.error(request, error_msg)
                    return redirect('problem_detail', problem_id=problem.uuid)

                # 1. Create the solution immediately as Pending
                solution = Solution.objects.create(
                    user=request.user,
                    problem=problem,
                    code=code,
                    language=language,
                    verdict=None,
                    status='Pending'
                )

                # 2. Dispatch the Celery task
                evaluate_submission_task.delay(str(solution.id))

                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'solution_id': str(solution.id),
                        'status': 'Pending',
                        'feedback_message': 'Code queued for evaluation...'
                    })
                
                messages.success(request, f"Solution submitted and queued!")

                # Generate AI feedback for submitted solutions
                try:
                    from core.utils.ai_review import generate_code_review
                    ai_feedback = generate_code_review(code)
                except Exception as e:
                    ai_feedback = f"⚠️ AI review failed: {e}"

                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'verdict': verdict,
                        'output': output,
                        'feedback_message': feedback_message,
                        'debug': debug,
                        'ai_feedback': ai_feedback
                    })
                
                messages.success(request, f"Solution submitted! {feedback_message}")
            
            else:
                # Unknown action
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'error': f'Unknown action: {action}',
                        'debug': f'Received action: "{action}", expected: "run", "submit", or "ai_review"'
                    })

        else:
            # Form validation failed
            debug = f"Form errors: {form.errors}"
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Form validation failed',
                    'form_errors': form.errors,
                    'debug': debug
                })

    # Get user's previous submissions for this problem
    user_submissions = Solution.objects.filter(
        user=request.user,
        problem=problem
    ).order_by('-submitted_at')[:10]

    # Get admin settings for AI review
    from core.models import AdminSettings
    admin_settings = AdminSettings.get_settings()

    return render(request, 'core/problem_detail.html', {
        'problem': problem,
        'form': form,
        'output': output,
        'verdict': verdict,
        'feedback_message': feedback_message,
        'debug': debug,
        'ai_feedback': ai_feedback,
        'user_solved': user_solved,
        'user_submissions': user_submissions,
        'ai_review_enabled': admin_settings.ai_review_enabled,
    })

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

def submission_detail(request, submission_id):
    submission = get_object_or_404(Solution, pk=submission_id)
    return render(request, 'core/submission_detail.html', {'submission': submission})


def submission_status_api(request, submission_id):
    try:
        solution = Solution.objects.get(id=submission_id)
        
        # Generate AI feedback if it's newly evaluated
        ai_feedback = None
        if solution.status == 'Evaluated' and solution.verdict == 'AC':
            try:
                from core.utils.ai_review import generate_code_review
                ai_feedback = generate_code_review(solution.code)
            except Exception:
                pass

        return JsonResponse({
            'status': solution.status,
            'verdict': solution.verdict,
            'output': solution.output,
            'error': solution.error,
            'feedback_message': get_feedback_message(solution.verdict) if solution.verdict else 'Evaluation in progress...',
            'ai_feedback': ai_feedback
        })
    except Solution.DoesNotExist:
        return JsonResponse({'error': 'Solution not found'}, status=404)

def get_feedback_message(verdict):
    """Get user-friendly feedback message for submission verdict"""
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

