import os
import django
import json
import time
from dotenv import load_dotenv

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "online_judge.settings")
django.setup()

from core.models import Problem
from django.contrib.auth.models import User
from groq import Groq

# Load .env to get GROQ_API_KEY
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    print("Error: GROQ_API_KEY not found in environment.")
    exit(1)

client = Groq(api_key=groq_api_key)

user = User.objects.filter(is_superuser=True).first()
if not user:
    user = User.objects.first()

problems_data = """July 25	Two Sum	Arrays	Easy
July 25	Remove Linked List Elements	Linked List	Easy
July 26	Group Anagrams	Strings	Medium
July 26	Same Tree	Trees	Easy
July 27	Top K Frequent Elements	Heap	Medium
July 27	Invert Binary Tree	Trees	Easy
July 28	Best Time to Buy and Sell Stock	Arrays	Easy
July 28	Min Stack	Stack	Medium
July 29	Merge Intervals	Arrays	Medium
July 29	Maximum Depth of Binary Tree	Trees	Easy
July 30	Maximum Subarray	Arrays	Easy
July 30	Reverse Linked List	Linked List	Easy
Jul 31	Watermelon	Implementation	Easy
Jul 31	Way Too Long Words	Strings	Easy
Aug 1	Next Round	Sorting	Easy
Aug 1	Beautiful Matrix	Math	Easy
Aug 2	Petya and Strings	Strings	Easy
Aug 2	Team	Brute Force	Easy
Aug 3	Nearly Lucky Number	Implementation	Easy
Aug 3	Helpful Maths	Sorting	Easy
Aug 4	George and Accommodation	Greedy	Easy
Aug 4	Word	Strings	Easy
Aug 5	Boy or Girl	Sets & Strings	Easy-Medium
Aug 5	Stones on the Table	Greedy	Easy-Medium
Aug 6	Drinks	Math	Easy-Medium
Aug 6	Football	Strings	Easy-Medium
Aug 7	Dubstep	Strings	Easy-Medium
Aug 7	Presents	Simulation	Easy-Medium
Aug 8	Horseshoe	Sets	Easy-Medium
Aug 8	Queue at the School	Simulation	Easy-Medium
Aug 9	Xenia and Ringroad	Implementation	Easy-Medium
Aug 9	I Wanna Be the Guy	Sets	Easy-Medium
Aug 10	Sereja and Dima	Greedy	Medium
Aug 10	Cheap Travel	Greedy / Math	Medium
Aug 11	Arrival of the General	Greedy	Medium
Aug 11	Word Capitalization	Strings	Medium
Aug 12	Night at the Museum	Math	Medium
Aug 12	Soft Drinking	Implementation	Medium
Aug 13	Park Lighting	Math	Medium
Aug 13	Young Physicist	Math / Implementation	Medium
Aug 14	Even Odds	Math	Medium
Aug 14	Bit++	Implementation	Medium
Aug 15	Kefa and First Steps	Greedy / DP	Easy-Hard
Aug 15	Valera and Plates	Greedy	Easy-Hard
Aug 16	Kyoya and Photobooks	Combinatorics	Easy-Hard
Aug 16	GukiZ and Contest	Sorting	Easy-Hard
Aug 17	Jzzhu and Children	Queue	Easy-Hard
Aug 17	Xenia and Divisors	Math	Easy-Hard
Aug 18	Tavas and SaDDas	Bit Manipulation	Easy-Hard
Aug 18	Fox And Snake	Implementation	Easy-Hard
Aug 19	BerSU Ball	Two Pointers	Hard
Aug 19	Soldier and Cards	Simulation	Hard
Aug 20	Lucky Sum of Digits	Greedy / Math	Hard
Aug 20	Pashmak and Flowers	Greedy	Hard
Aug 21	Little Elephant and Bits	Greedy	Hard
Aug 21	Magic Numbers	Strings / Greedy	Hard
Aug 22	Puzzle Pieces	Greedy	Hard
Aug 22	Two Round Dances	Combinatorics	Hard
Aug 23	Special Permutation	Constructive	Hard
Aug 23	Captain Flint and Crew Recruitment	Math / Brute Force	Hard
Aug 24	Hit the Lottery	DP / Greedy	Medium
Aug 24	Registration System	Hashing / DS	Easy-Hard
Aug 25	Constructing the Array	DS / Greedy	Medium
Aug 25	Gravity Flip	Greedy / Sorting	Easy-Medium
Aug 26	Vanya and Lanterns	Greedy / Binary Search	Medium
Aug 26	Divisibility Problem	Math	Easy-Medium
Aug 27	Spy Detected!	Implementation	Easy-Medium
Aug 27	Hit the Lottery	DP / Greedy	Medium
Aug 28	Kefa and First Steps	Greedy / DP	Easy-Hard
Aug 28	BerSU Ball	Two Pointers	Hard
Aug 29	Soldier and Cards	Simulation	Hard
Aug 29	Pashmak and Flowers	Greedy	Hard
Aug 30	Special Permutation	Constructive	Hard
Aug 30	Captain Flint...	Math / Brute Force	Hard
Aug 31	Registration System	Hashing / DS	Easy-Hard
Aug 31	Constructing the Array	Greedy / DS	Medium
Sep 1	T-Primes	Number Theory / Binary Search	Easy-Hard
Sep 1	Vanya and Lanterns	Greedy / Binary Search	Medium
Sep 2	Cheap Travel	Greedy / DP	Medium
Sep 2	Divisibility Problem	Math	Easy-Medium
Sep 3	Spy Detected!	Implementation	Easy-Medium
Sep 3	Constructing the Array	Greedy / DS	Medium
Sep 4	Kefa and First Steps	Greedy / DP	Easy-Hard
Sep 4	BerSU Ball	Two Pointers	Hard
Sep 5	Pashmak and Flowers	Greedy	Hard
Sep 5	Magic Numbers	Strings / Greedy	Hard"""

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
        # Remove any potential markdown json blocks if the model failed to follow instructions perfectly
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        return json.loads(content.strip())
    except Exception as e:
        print(f"Error generating details for {title}: {e}")
        return None

count = 0
lines = [l for l in problems_data.strip().split('\n') if l.strip()]

print(f"Starting to add {len(lines)} problems. This will take a few minutes as it generates real descriptions and test cases via Groq AI...")

for i, line in enumerate(lines, 1):
    parts = line.split('\t')
    if len(parts) >= 4:
        title = parts[1].strip()
        topic = parts[2].strip()
        difficulty = parts[3].strip()
        db_difficulty = map_difficulty(difficulty)
        
        # Check if already exists
        if Problem.objects.filter(title=title).exists():
            print(f"[{i}/{len(lines)}] Skipped: {title} (Already exists)")
            continue
            
        print(f"[{i}/{len(lines)}] Generating & Adding: {title}...")
        
        details = generate_problem_details(title, topic)
        
        if details:
            # Fallback for test_cases if it wasn't returned properly
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
            print(f"    -> Failed to generate details for {title}")
            
        time.sleep(1) # Prevent rate limiting

print(f"\nSuccessfully generated and added {count} problems!")
