from django.conf import settings
import json
import logging
import re

logger = logging.getLogger(__name__)

def generate_code_review(code):
    """Generate AI code review with structured response using Groq"""
    # Check if AI features are enabled
    if not getattr(settings, 'AI_FEATURES_ENABLED', False):
        return {
            'success': False,
            'error': 'AI features are not enabled. Please configure Groq API key.',
            'review': {
                "logic": "AI review not available - API key not configured",
                "efficiency": "AI review not available - API key not configured",
                "clarity": "AI review not available - API key not configured", 
                "best_practices": "AI review not available - API key not configured"
            }
        }
    
    try:
        import requests
        
        prompt = f"""
You are an AI code reviewer. Review the following code and provide feedback in EXACTLY this JSON format (no additional text before or after):

{{
    "logic": "your detailed comment about logic and correctness",
    "efficiency": "your detailed comment about performance and optimization", 
    "clarity": "your detailed comment about readability and understanding",
    "best_practices": "your detailed comment about coding standards and conventions"
}}

Code to review:
{code}

Return ONLY the JSON object, no other text.
"""
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {str(settings.GROQ_API_KEY).strip()}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        
        result_json = response.json()
        if not result_json.get('choices'):
            raise ValueError("Empty response from AI model")
        
        # Clean the response text
        response_text = result_json['choices'][0]['message']['content'].strip()
        
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group()
        else:
            json_text = response_text
        
        # Try to parse as JSON
        try:
            structured_review = json.loads(json_text)
            
            # Validate that all required keys are present
            required_keys = ["logic", "efficiency", "clarity", "best_practices"]
            if not all(key in structured_review for key in required_keys):
                raise ValueError("Missing required keys in JSON response")
                
            return {
                'success': True,
                'review': structured_review,
                'raw': response_text
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON parsing failed: {e}, attempting text parsing")
            # Fallback: parse text format
            structured_review = parse_text_review(response_text)
            return {
                'success': True,
                'review': structured_review,
                'raw': response_text
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
    """Parse text format review into structured data with improved parsing"""
    try:
        review = {
            "logic": "",
            "efficiency": "",
            "clarity": "",
            "best_practices": ""
        }
        
        # Try different parsing strategies
        
        # Strategy 1: Look for numbered sections
        sections = re.split(r'\d+\.\s*(Logic|Efficiency|Clarity|Best Practices)', text, flags=re.IGNORECASE)
        if len(sections) > 1:
            for i in range(1, len(sections), 2):
                if i + 1 < len(sections):
                    section_name = sections[i].lower().replace(' ', '_')
                    section_content = sections[i + 1].strip()
                    if section_name in review:
                        review[section_name] = section_content
        
        # Strategy 2: Look for section headers followed by content
        else:
            patterns = [
                (r'Logic[:\-\s]+([^#]*?)(?=Efficiency|Clarity|Best Practices|$)', 'logic'),
                (r'Efficiency[:\-\s]+([^#]*?)(?=Logic|Clarity|Best Practices|$)', 'efficiency'),
                (r'Clarity[:\-\s]+([^#]*?)(?=Logic|Efficiency|Best Practices|$)', 'clarity'),
                (r'Best Practices[:\-\s]+([^#]*?)(?=Logic|Efficiency|Clarity|$)', 'best_practices')
            ]
            
            for pattern, key in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    review[key] = match.group(1).strip()
        
        # Strategy 3: If still empty, try simple keyword extraction
        if not any(review.values()):
            lines = text.split('\n')
            current_section = None
            current_content = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Check for section headers
                if any(keyword in line.lower() for keyword in ['logic', 'efficiency', 'clarity', 'best practices']):
                    # Save previous section
                    if current_section and current_content:
                        review[current_section] = ' '.join(current_content)
                    
                    # Determine new section
                    if 'logic' in line.lower():
                        current_section = 'logic'
                    elif 'efficiency' in line.lower():
                        current_section = 'efficiency'
                    elif 'clarity' in line.lower():
                        current_section = 'clarity'
                    elif 'best practices' in line.lower():
                        current_section = 'best_practices'
                    
                    current_content = []
                    # Add content after the header
                    content_after_header = re.sub(r'^.*?(logic|efficiency|clarity|best practices)[:\-\s]*', '', line, flags=re.IGNORECASE)
                    if content_after_header.strip():
                        current_content.append(content_after_header.strip())
                elif current_section:
                    current_content.append(line)
            
            # Don't forget the last section
            if current_section and current_content:
                review[current_section] = ' '.join(current_content)
        
        # Fallback: if we still don't have content, provide a generic message
        for key in review:
            if not review[key]:
                review[key] = "Unable to parse this section from AI response. Please try again."
                
        return review
        
    except Exception as e:
        logger.error(f"Error parsing review text: {str(e)}")
        return {
            "logic": f"Error parsing AI response: {str(e)}",
            "efficiency": f"Error parsing AI response: {str(e)}",
            "clarity": f"Error parsing AI response: {str(e)}",
            "best_practices": f"Error parsing AI response: {str(e)}"
        }

# Alternative function with more robust error handling
def generate_code_review_robust(code):
    """More robust version with multiple retry strategies"""
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            result = generate_code_review(code)
            
            # Check if we got a valid response
            if result['success'] and all(
                result['review'][key] and 
                'failed' not in result['review'][key].lower() and
                'error' not in result['review'][key].lower()
                for key in ['logic', 'efficiency', 'clarity', 'best_practices']
            ):
                return result
            
            logger.warning(f"Attempt {attempt + 1} returned incomplete review, retrying...")
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            
        if attempt < max_retries - 1:
            import time
            time.sleep(1)  # Brief delay before retry
    
    # Final fallback
    return {
        'success': False,
        'error': 'Failed to generate review after multiple attempts',
        'review': {
            "logic": "Unable to generate AI review after multiple attempts",
            "efficiency": "Unable to generate AI review after multiple attempts",
            "clarity": "Unable to generate AI review after multiple attempts", 
            "best_practices": "Unable to generate AI review after multiple attempts"
        }
    }