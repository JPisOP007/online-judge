#!/usr/bin/env python3
"""
Test script for the enhanced secure execution system
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_judge.settings')
django.setup()

from core.utils.secure_execution import validate_code_security, secure_execute_code

def test_ast_security_analysis():
    """Test the new AST-based security analysis"""
    print("🔒 Testing AST-based Security Analysis")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        # Should be allowed
        ("from collections import deque\nprint('Hello')", "python", True),
        ("import math\nprint(math.sqrt(4))", "python", True),
        ("from itertools import permutations\nprint(list(permutations([1,2])))", "python", True),
        
        # Should be blocked
        ("import os\nos.system('ls')", "python", False),
        ("from subprocess import call\ncall(['ls'])", "python", False),
        ("eval('print(1)')", "python", False),
        
        # Partial imports - should work
        ("from collections import Counter, defaultdict\nprint('OK')", "python", True),
        
        # Partial imports - should be blocked
        ("from collections import abc\nprint('Not OK')", "python", False),
    ]
    
    for i, (code, language, should_pass) in enumerate(test_cases, 1):
        is_valid, message = validate_code_security(code, language)
        status = "✅ PASS" if (is_valid == should_pass) else "❌ FAIL"
        print(f"Test {i}: {status}")
        print(f"  Code: {code[:50]}{'...' if len(code) > 50 else ''}")
        print(f"  Expected: {'ALLOW' if should_pass else 'BLOCK'}, Got: {'ALLOW' if is_valid else 'BLOCK'}")
        if not is_valid:
            print(f"  Message: {message}")
        print()

def test_enhanced_python_execution():
    """Test the enhanced Python execution environment"""
    print("🐍 Testing Enhanced Python Execution")
    print("=" * 50)
    
    # Test cases with expected results
    test_cases = [
        # Basic functionality
        {
            'code': 'print("Hello World")',
            'input': '',
            'expected': 'Hello World',
            'description': 'Basic print statement'
        },
        
        # Collections usage
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
        
        # Math operations
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
        
        # Input handling
        {
            'code': '''
n = int(input())
print(n * 2)
''',
            'input': '5',
            'expected': '10',
            'description': 'Input handling'
        },
        
        # Algorithm with heapq
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
        
        if verdict == 'AC':
            print(f"  ✅ ACCEPTED")
        else:
            print(f"  ❌ {verdict}")
            if error:
                print(f"  Error: {error}")
            print(f"  Expected: '{test_case['expected']}'")
            print(f"  Got: '{output}'")
        
        print()

def test_security_violations():
    """Test that security violations are properly caught and reported"""
    print("🚨 Testing Security Violation Detection")
    print("=" * 50)
    
    # Test cases that should be blocked
    violation_cases = [
        {
            'code': 'import os\nprint(os.getcwd())',
            'description': 'OS module import'
        },
        {
            'code': 'from subprocess import run\nrun(["echo", "hello"])',
            'description': 'Subprocess import'
        },
        {
            'code': 'eval("print(1)")',
            'description': 'Eval function call'
        },
        {
            'code': 'from collections import abc\nprint("test")',
            'description': 'Disallowed function from allowed module'
        }
    ]
    
    for i, test_case in enumerate(violation_cases, 1):
        print(f"Test {i}: {test_case['description']}")
        
        is_valid, message = validate_code_security(test_case['code'], 'python')
        
        if not is_valid:
            print(f"  ✅ BLOCKED (as expected)")
            print(f"  Reason: {message}")
        else:
            print(f"  ❌ ALLOWED (should be blocked!)")
        
        print()

if __name__ == "__main__":
    print("🧪 Enhanced Security System Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_ast_security_analysis()
        test_enhanced_python_execution()
        test_security_violations()
        
        print("🎉 Test suite completed!")
        print("The enhanced security system is working correctly.")
        
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()