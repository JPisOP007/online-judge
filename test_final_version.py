#!/usr/bin/env python3
"""
Test script for the final secure execution system
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_judge.settings')
django.setup()

from core.utils.secure_execution_final import validate_code_security, secure_execute_code

def test_comprehensive():
    """Comprehensive test of the final system"""
    print("🧪 Final Enhanced Security System Test")
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
        
        # Input handling with carriage returns
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
    
    # Test security violations
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
        print("The final enhanced security system is working perfectly.")
    else:
        print(f"⚠️ Some tests failed:")
        print(f"   Functionality: {passed}/{total}")
        print(f"   Security: {security_passed}/{len(security_tests)}")

if __name__ == "__main__":
    test_comprehensive()