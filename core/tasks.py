import json
from celery import shared_task
from core.models import Solution, Problem
from core.utils.secure_execution import secure_evaluate_submission
from core.utils.ai_review import generate_code_review

@shared_task
def evaluate_submission_task(solution_id):
    try:
        solution = Solution.objects.get(id=solution_id)
    except Solution.DoesNotExist:
        return {'error': 'Solution not found'}

    problem = solution.problem
    code = solution.code
    language = solution.language

    try:
        test_cases = json.loads(problem.test_cases_json or "[]")
    except json.JSONDecodeError:
        solution.verdict = 'IE'
        solution.output = 'Invalid test case format in the database.'
        solution.status = 'Evaluated'
        solution.save()
        return {'status': 'Evaluated'}

    if not test_cases:
        solution.verdict = 'IE'
        solution.output = 'No test cases available for this problem.'
        solution.status = 'Evaluated'
        solution.save()
        return {'status': 'Evaluated'}

    result = secure_evaluate_submission(language, code, problem)
    
    solution.verdict = result.get('verdict', 'IE')
    solution.output = result.get('output', '')
    solution.error = result.get('error', '')
    solution.execution_time = result.get('execution_time', 0.0)
    solution.status = 'Evaluated'
    
    solution.save()

    return {'status': 'Evaluated', 'verdict': solution.verdict}
