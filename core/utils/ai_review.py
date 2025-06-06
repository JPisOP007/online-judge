from vertexai.generative_models import GenerativeModel

def generate_code_review(code):
    model = GenerativeModel("gemini-2.0-flash")

    
    prompt = f"""
You are an AI code reviewer.

Review the following code based only on the following four criteria:

1. Logic – Does it correctly solve the problem?
2. Efficiency – Is it optimized in terms of time and space?
3. Clarity – Is the code easy to read and understand?
4. Best Practices – Does it follow standard naming, formatting, and style conventions?

Respond strictly in this format, without any extra commentary before or after:

Logic:
<your comment here>

Efficiency:
<your comment here>

Clarity:
<your comment here>

Best Practices:
<your comment here>

{code}
"""

    response = model.generate_content(prompt)
    return response.text
