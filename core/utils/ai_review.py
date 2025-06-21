from vertexai.generative_models import GenerativeModel
import json
import logging

logger = logging.getLogger(__name__)

def generate_code_review(code):
    """Generate AI code review with structured response"""
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
    "logic": "your detailed comment here",
    "efficiency": "your detailed comment here", 
    "clarity": "your detailed comment here",
    "best_practices": "your detailed comment here"
}}

Code to review:
{code}
"""

        response = model.generate_content(prompt)
        
        if not response or not response.text:
            raise ValueError("Empty response from AI model")
        
        # Try to parse as JSON first
        try:
            structured_review = json.loads(response.text.strip())
            return {
                'success': True,
                'review': structured_review,
                'raw': response.text
            }
        except json.JSONDecodeError:
            # Fallback: parse text format
            structured_review = parse_text_review(response.text)
            return {
                'success': True,
                'review': structured_review,
                'raw': response.text
            }
            
    except Exception as e:
        logger.error(f"Error generating code review: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'review': {
                "logic": "AI review failed - please try again",
                "efficiency": "AI review failed - please try again",
                "clarity": "AI review failed - please try again", 
                "best_practices": "AI review failed - please try again"
            }
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
            "logic": "Error parsing AI response",
            "efficiency": "Error parsing AI response",
            "clarity": "Error parsing AI response",
            "best_practices": "Error parsing AI response"
        }