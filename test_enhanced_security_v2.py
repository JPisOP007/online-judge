#!/usr/bin/env python3
"""
Test script for the enhanced secure execution system - Simplified version
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_judge.settings')
django.setup()

from core.utils.secure_execution_v2 import validate_code_security, secure_execute_code

def test_enhanced_python_execution():
    """Test the enhanced Python execution environment"""
    print("🐍 Testing Enhanced Python Execution (Simplified)")
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
        },
        
        # Itertools usage
        {
            'code': '''
from itertools import permutations
perms = list(permutations([1, 2, 3], 2))
print(len(perms))
''',
            'input': '',
            'expected': '6',
            'description': 'Itertools permutations'
        },
        
        # Complex algorithm example
        {
            'code': '''
from collections import defaultdict
from heapq import heappush, heappop

# Dijkstra's algorithm example
def dijkstra():
    graph = defaultdict(list)
    graph[0] = [(1, 4), (2, 1)]
    graph[1] = [(3, 1)]
    graph[2] = [(1, 2), (3, 5)]
    
    dist = defaultdict(lambda: float('inf'))
    dist[0] = 0
    pq = [(0, 0)]
    
    while pq:
        d, u = heappop(pq)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heappush(pq, (dist[v], v))
    
    return dist[3]

print(dijkstra())
''',
            'input': '',
            'expected': '3',
            'description': 'Complex algorithm with multiple modules'
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
        memory_used = result.get('memory_used', 0)
        
        if verdict == 'AC':
            print(f"  ✅ ACCEPTED")
            if execution_time:
                print(f"     ⏱️ Time: {execution_time:.3f}s")
            if memory_used:
                print(f"     💾 Memory: {memory_used / (1024*1024):.1f}MB")
            passed += 1
        else:
            print(f"  ❌ {verdict}")
            if error:
                print(f"     Error: {error}")
            print(f"     Expected: '{test_case['expected']}'")
            print(f"     Got: '{output}'")
        
        print()
    
    print(f"Results: {passed}/{total} tests passed")
    return passed == total

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
        },
        {
            'code': 'open("test.txt", "w").write("hack")',
            'description': 'File operations'
        }
    ]
    
    passed = 0
    total = len(violation_cases)
    
    for i, test_case in enumerate(violation_cases, 1):
        print(f"Test {i}: {test_case['description']}")
        
        is_valid, message = validate_code_security(test_case['code'], 'python')
        
        if not is_valid:
            print(f"  ✅ BLOCKED (as expected)")
            print(f"     Reason: {message}")
            passed += 1
        else:
            print(f"  ❌ ALLOWED (should be blocked!)")
        
        print()
    
    print(f"Results: {passed}/{total} security tests passed")
    return passed == total

def test_educational_error_messages():
    """Test that error messages are educational and helpful"""
    print("📚 Testing Educational Error Messages")
    print("=" * 50)
    
    # Test cases that should produce helpful error messages
    error_cases = [
        {
            'code': '''
arr = [1, 2, 3]
print(arr[5])  # Index error
''',
            'input': '',
            'expected': '',
            'description': 'Index out of bounds error'
        },
        {
            'code': '''
d = {"a": 1}
print(d["b"])  # Key error
''',
            'input': '',
            'expected': '',
            'description': 'Dictionary key error'
        },
        {
            'code': '''
print(10 / 0)  # Division by zero
''',
            'input': '',
            'expected': '',
            'description': 'Division by zero error'
        }
    ]
    
    for i, test_case in enumerate(error_cases, 1):
        print(f"Test {i}: {test_case['description']}")
        
        result = secure_execute_code(
            'python', 
            test_case['code'], 
            test_case['input'], 
            test_case['expected']
        )
        
        verdict = result.get('verdict', 'Unknown')
        error = result.get('error', '')
        
        print(f"  Verdict: {verdict}")
        if error:
            print(f"  Error Message: {error}")
            # Check if error message contains helpful suggestions
            if "💡" in error:
                print(f"  ✅ Contains educational suggestions")
            else:
                print(f"  ⚠️ Could use more educational content")
        
        print()

if __name__ == "__main__":
    print("🧪 Enhanced Security System Test Suite (Simplified)")
    print("=" * 60)
    print()
    
    try:
        # Run all tests
        execution_passed = test_enhanced_python_execution()
        security_passed = test_security_violations()
        test_educational_error_messages()
        
        print("=" * 60)
        if execution_passed and security_passed:
            print("🎉 All critical tests passed!")
            print("The enhanced security system is working correctly.")
        else:
            print("⚠️ Some tests failed. Please review the results above.")
        
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()