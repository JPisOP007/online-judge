#!/usr/bin/env python3
"""
Test script for the simple secure execution system
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_judge.settings')
django.setup()

from core.utils.secure_execution_simple import validate_code_security, secure_execute_code

def test_simple_system():
    """Test the simple system"""
    print("🧪 Simple Enhanced Security System Test")
    print("=" * 50)
    
    test_cases = [
        {
            'code': 'print("Hello World")',
            'input': '',
            'expected': 'Hello World',
            'description': 'Basic print statement'
        },
        {
            'code': '''
from collections import deque
d = deque([1, 2, 3])
d.appendleft(0)
print(' '.join(map(str, d)))
''',
            'input': '',
            'expected': '0 1 2 3',
            'description': 'Collections deque usage'
        },
        {
            'code': '''
import math
print(int(math.sqrt(16)))
print(math.gcd(12, 8))
''',
            'input': '',
            'expected': '4\n4',
            'description': 'Math module usage'
        },
        {
            'code': '''
line = input().strip()
parts = line.split()
a, b = map(int, parts)
print(a + b)
''',
            'input': '5 4\r',
            'expected': '9',
            'description': 'Input parsing with carriage return'
        },
        {
            'code': '''
import heapq
nums = [3, 1, 4, 1, 5]
heapq.heapify(nums)
result = []
while nums:
    result.append(heapq.heappop(nums))
print(' '.join(map(str, result)))
''',
            'input': '',
            'expected': '1 1 3 4 5',
            'description': 'Heapq usage for sorting'
        },
        {
            'code': '''
from itertools import permutations
perms = list(permutations([1, 2, 3], 2))
print(len(perms))
''',
            'input': '',
            'expected': '6',
            'description': 'Itertools permutations'
        }
    ]
    
    passed = 0
    total = len(test_cases)
    
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
        execution_time = result.get('execution_time', 0)
        
        if verdict == 'AC':
            print(f"  ✅ ACCEPTED")
            if execution_time:
                print(f"     ⏱️ Time: {execution_time:.3f}s")
            passed += 1
        else:
            print(f"  ❌ {verdict}")
            if error:
                print(f"     Error: {error}")
            print(f"     Expected: '{test_case['expected']}'")
            print(f"     Got: '{output}'")
        
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    
    # Security tests
    print("\n🚨 Security Tests")
    print("=" * 30)
    
    security_tests = [
        ('import os\nprint(os.getcwd())', 'OS module import'),
        ('eval("print(1)")', 'Eval function call'),
        ('from collections import abc\nprint("test")', 'Disallowed function from allowed module'),
    ]
    
    security_passed = 0
    for code, desc in security_tests:
        is_valid, message = validate_code_security(code, 'python')
        if not is_valid:
            print(f"✅ {desc}: BLOCKED")
            security_passed += 1
        else:
            print(f"❌ {desc}: ALLOWED (should be blocked!)")
    
    print(f"\nSecurity Results: {security_passed}/{len(security_tests)} tests passed")
    
    # Overall results
    print("\n" + "=" * 50)
    if passed == total and security_passed == len(security_tests):
        print("🎉 ALL TESTS PASSED!")
        print("The simple enhanced security system is working perfectly.")
    else:
        print(f"⚠️ Some tests failed:")
        print(f"   Functionality: {passed}/{total}")
        print(f"   Security: {security_passed}/{len(security_tests)}")

if __name__ == "__main__":
    test_simple_system()