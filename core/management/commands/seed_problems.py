import os
import json
import time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Problem
from groq import Groq

class Command(BaseCommand):
    help = 'Seeds problems using Groq AI'

    def handle(self, *args, **kwargs):
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            self.stdout.write(self.style.ERROR("Error: GROQ_API_KEY not found in environment."))
            return

        client = Groq(api_key=groq_api_key)

        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.first()

        problems_data = """July 25	Two Sum	Arrays	Easy
July 25	Remove Linked List Elements	Linked List	Easy
July 26	Group Anagrams	Strings	Medium"""

        def map_difficulty(diff_str):
            diff_str = diff_str.lower()
            if 'hard' in diff_str:
                return 'hard'
            elif 'medium' in diff_str:
                return 'medium'
            else:
                return 'easy'

        def generate_problem_details(title, topic):
            prompt = f"""You are a competitive programming problem setter. Provide the full details for the classic problem "{title}" relating to the topic "{topic}".
Return ONLY a raw, minified JSON object with the following string keys and no markdown wrapping or code blocks:
"description": A clear 2-3 paragraph explanation of the problem,
"constraints": Bulleted list of constraints (e.g. 1 <= N <= 10^5),
"input_format": Description of input,
"output_format": Description of output,
"sample_input": One raw text example of input,
"sample_output": One raw text example of output,
"test_cases": A JSON string array of 3 test cases in the format [{{"input":"...", "output":"..."}}]
Ensure all fields are strings (including test_cases which should be a stringified JSON array). Keep it concise and perfectly valid JSON."""
            
            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.1-8b-instant",
                    temperature=0.1,
                    max_tokens=1024
                )
                
                content = chat_completion.choices[0].message.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                    
                return json.loads(content.strip())
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error generating details for {title}: {e}"))
                return None

        count = 0
        lines = [l for l in problems_data.strip().split('\n') if l.strip()]

        self.stdout.write(f"Starting to add {len(lines)} problems...")

        for i, line in enumerate(lines, 1):
            parts = line.split('\t')
            if len(parts) >= 4:
                title = parts[1].strip()
                topic = parts[2].strip()
                difficulty = parts[3].strip()
                db_difficulty = map_difficulty(difficulty)
                
                if Problem.objects.filter(title=title).exists():
                    self.stdout.write(self.style.WARNING(f"[{i}/{len(lines)}] Skipped: {title} (Already exists)"))
                    continue
                    
                self.stdout.write(f"[{i}/{len(lines)}] Generating & Adding: {title}...")
                
                details = generate_problem_details(title, topic)
                
                if details:
                    test_cases_json = details.get("test_cases", "[]")
                    if not isinstance(test_cases_json, str):
                        test_cases_json = json.dumps(test_cases_json)
                        
                    Problem.objects.create(
                        title=title,
                        difficulty=db_difficulty,
                        description=details.get("description", f"Calculate the answer for {title}."),
                        constraints=details.get("constraints", ""),
                        input_format=details.get("input_format", ""),
                        output_format=details.get("output_format", ""),
                        sample_input=details.get("sample_input", ""),
                        sample_output=details.get("sample_output", ""),
                        tags=topic,
                        test_cases_json=test_cases_json,
                        created_by=user
                    )
                    count += 1
                else:
                    self.stdout.write(self.style.ERROR(f"    -> Failed to generate details for {title}"))
                    
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully generated and added {count} problems!"))
