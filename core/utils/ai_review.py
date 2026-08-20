from django.conf import settings
import json
import logging
import re

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT = 30
REVIEW_SECTIONS = ("logic", "efficiency", "clarity", "best_practices")

# Hosted models are retired regularly, and when one goes the API answers 404
# and the feature simply stops working - which is how llama-3.3-70b-versatile
# broke this. Ask for the configured model first, then fall through these, and
# let GROQ_MODEL override the lot without a code change.
DEFAULT_MODELS = (
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "groq/compound-mini",
)


def _failure(message, error=None):
    """A failed review still has to fill every panel the template renders."""
    return {
        'success': False,
        'error': error or message,
        'review': {section: message for section in REVIEW_SECTIONS},
    }


def _model_candidates():
    configured = (getattr(settings, 'GROQ_MODEL', '') or '').strip()
    candidates = [configured] if configured else []
    candidates += [model for model in DEFAULT_MODELS if model != configured]
    return candidates


def _build_prompt(code):
    return f"""
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


def _chat(requests, model, prompt, json_mode=True):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1000,
    }
    if json_mode:
        # Supported by every model in DEFAULT_MODELS, and it removes the need
        # to scrape JSON back out of prose.
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {str(settings.GROQ_API_KEY).strip()}",
        "Content-Type": "application/json",
    }
    return requests.post(GROQ_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)


def _parse_review(response_text):
    """Return the four review sections from whatever the model sent back."""
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    json_text = json_match.group() if json_match else response_text

    try:
        structured = json.loads(json_text)
        if not all(key in structured for key in REVIEW_SECTIONS):
            raise ValueError("Missing required keys in JSON response")
        return structured
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("JSON parsing failed: %s, attempting text parsing", exc)
        return parse_text_review(response_text)


def generate_code_review(code):
    """Generate AI code review with structured response using Groq"""
    if not getattr(settings, 'AI_FEATURES_ENABLED', False):
        return _failure('AI review is not configured on this server (no Groq API key).')

    import requests

    prompt = _build_prompt(code)
    tried = []

    for model in _model_candidates():
        tried.append(model)
        try:
            response = _chat(requests, model, prompt)

            # Some models reject response_format; retry once in plain mode
            # rather than losing the review over a formatting flag.
            if response.status_code == 400 and 'json' in response.text.lower():
                logger.info("Model %s rejected JSON mode, retrying without it", model)
                response = _chat(requests, model, prompt, json_mode=False)

            if response.status_code == 404:
                logger.warning("Groq model %s is unavailable, trying the next one", model)
                continue
            if response.status_code in (401, 403):
                return _failure('The Groq API key was rejected. Check GROQ_API_KEY.')
            if response.status_code == 429:
                return _failure('The AI reviewer is rate limited right now. Try again shortly.')

            response.raise_for_status()

        except requests.Timeout:
            return _failure('The AI reviewer took too long to respond. Try again.')
        except requests.RequestException as exc:
            logger.error("Groq request failed on %s: %s", model, exc)
            return _failure('Could not reach the AI reviewer.', error=str(exc))

        choices = response.json().get('choices')
        if not choices:
            logger.warning("Groq returned no choices for %s", model)
            continue

        response_text = choices[0]['message']['content'].strip()
        return {
            'success': True,
            'review': _parse_review(response_text),
            'model': model,
            'raw': response_text,
        }

    return _failure(
        'No AI model is currently available. Set GROQ_MODEL to a model your key can use.',
        error='All candidate models unavailable: ' + ', '.join(tried),
    )

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