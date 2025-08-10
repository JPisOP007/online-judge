#!/usr/bin/env python3
"""
Simple test to debug the current issue
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_judge.settings')
django.setup()

from core.utils.secure_execution import secure_execute_code

def test_simple_cases():
    """Test simple cases to debug issues"""
    
    test_cases = [
        {
            'code': '''
from collections import deque
d = deque([1, 2, 3])
print("deque created")
''',
            'input': '',
            'expected': 'deque created',
            'description': 'Simple collections test'
        },
        
        {
            'code': '''
import heapq
nums = [3, 1, 4]
print("heapq imported")
''',
            'input': '',
            'expected': 'heapq imported',
            'description': 'Simple heapq test'
        },
        
        {
            'code': '''
# Test input parsing with carriage returns
line = input().strip()
parts = line.split()
a, b = map(int, parts)
print(a + b)
''',
            'input': '5 4\r',
            'expected': '9',
            'description': 'Input parsing with carriage return'
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['description']}")
        
        result = secure_execute_code(
            'python', 
            test_case['code'], 
            test_case['input'], 
            test_case['expected']
        )
        
        verdict = result.get('verdict', 'Unknown')
        output = result.get('output', '')
        error = result.get('error', '')
        
        print(f"  Verdict: {verdict}")
        if error:
            print(f"  Error: {error}")
        print(f"  Expected: '{test_case['expected']}'")
        print(f"  Got: '{output}'")
        print()

if __name__ == "__main__":
    test_simple_cases()