from vertexai.generative_models import GenerativeModel
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging

logger = logging.getLogger(__name__)

def generate_code_review(code):
    """Generate AI code review with proper error handling"""
    try:
        model = GenerativeModel("gemini-2.0-flash")
        
        prompt = f"""
You are an AI code reviewer.

Review the following code based only on the following four criteria:

1. Logic – Does it correctly solve the problem?
2. Efficiency – Is it optimized in terms of time and space?
3. Clarity – Is the code easy to read and understand?
4. Best Practices – Does it follow standard naming, formatting, and style conventions?

Respond strictly in this JSON format:
{{
    "logic": "<your comment here>",
    "efficiency": "<your comment here>",
    "clarity": "<your comment here>",
    "best_practices": "<your comment here>"
}}

Code to review:
{code}
"""

        response = model.generate_content(prompt)
        
        if not response or not response.text:
            raise ValueError("Empty response from AI model")
            
        # Try to parse as JSON first
        try:
            # If the AI returns JSON format
            review_data = json.loads(response.text)
            return {
                "success": True,
                "review": review_data
            }
        except json.JSONDecodeError:
            # Fallback: parse the text format
            review_data = parse_text_review(response.text)
            return {
                "success": True,
                "review": review_data
            }
            
    except Exception as e:
        logger.error(f"Error generating code review: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to generate review: {str(e)}"
        }

def parse_text_review(text):
    """Parse text format review into structured data"""
    try:
        lines = text.strip().split('\n')
        review = {
            "logic": "",
            "efficiency": "",
            "clarity": "",
            "best_practices": ""
        }
        
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if line.startswith("Logic:"):
                if current_section:
                    review[current_section] = '\n'.join(current_content).strip()
                current_section = "logic"
                current_content = [line.replace("Logic:", "").strip()]
            elif line.startswith("Efficiency:"):
                if current_section:
                    review[current_section] = '\n'.join(current_content).strip()
                current_section = "efficiency"
                current_content = [line.replace("Efficiency:", "").strip()]
            elif line.startswith("Clarity:"):
                if current_section:
                    review[current_section] = '\n'.join(current_content).strip()
                current_section = "clarity"
                current_content = [line.replace("Clarity:", "").strip()]
            elif line.startswith("Best Practices:"):
                if current_section:
                    review[current_section] = '\n'.join(current_content).strip()
                current_section = "best_practices"
                current_content = [line.replace("Best Practices:", "").strip()]
            elif current_section and line:
                current_content.append(line)
        
        # Don't forget the last section
        if current_section:
            review[current_section] = '\n'.join(current_content).strip()
            
        return review
        
    except Exception as e:
        logger.error(f"Error parsing review text: {str(e)}")
        return {
            "logic": "Error parsing review",
            "efficiency": "Error parsing review", 
            "clarity": "Error parsing review",
            "best_practices": "Error parsing review"
        }

@csrf_exempt
@require_http_methods(["POST"])
def ai_review_view(request):
    """Django view for AI code review"""
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
            
        code = data.get('code', '').strip()
        
        if not code:
            return JsonResponse({
                "success": False,
                "error": "No code provided"
            }, status=400)
        
        # Generate review
        result = generate_code_review(code)
        
        if result["success"]:
            return JsonResponse({
                "success": True,
                "review": result["review"]
            })
        else:
            return JsonResponse({
                "success": False,
                "error": result["error"]
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "error": "Invalid JSON in request"
        }, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in ai_review_view: {str(e)}")
        return JsonResponse({
            "success": False,
            "error": "Internal server error"
        }, status=500)