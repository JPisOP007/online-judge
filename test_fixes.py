#!/usr/bin/env python3
"""
Test script to verify the fixes for input() function and submission issues
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_judge.settings')
django.setup()

from core.utils.secure_execution import validate_code_security, secure_execute_code

def test_input_function_allowed():
    """Test that input() function is now allowed in code validation"""
    print("🧪 Testing input() function validation...")
    
    # Test code with input() function
    test_code = """
n = int(input())
print(n * 2)
"""
    
    is_valid, message = validate_code_security(test_code, 'python')
    
    if is_valid:
        print("✅ input() function is now allowed in code validation")
        return True
    else:
        print(f"❌ input() function is still blocked: {message}")
        return False

def test_input_execution():
    """Test that input() function works in code execution"""
    print("🧪 Testing input() function execution...")
    
    # Simple code that uses input()
    test_code = """
n = int(input())
print(n * 2)
"""
    
    # Test input and expected output
    test_input = "5"
    expected_output = "10"
    
    try:
        result = secure_execute_code('python', test_code, test_input, expected_output)
        
        if result.get('verdict') == 'AC':
            print("✅ input() function works correctly in execution")
            return True
        else:
            print(f"❌ input() function execution failed: {result}")
            return False
    except Exception as e:
        print(f"❌ input() function execution error: {e}")
        return False

def test_multiple_inputs():
    """Test code with multiple input() calls"""
    print("🧪 Testing multiple input() calls...")
    
    test_code = """
a = int(input())
b = int(input())
print(a + b)
"""
    
    test_input = "3\n7"
    expected_output = "10"
    
    try:
        result = secure_execute_code('python', test_code, test_input, expected_output)
        
        if result.get('verdict') == 'AC':
            print("✅ Multiple input() calls work correctly")
            return True
        else:
            print(f"❌ Multiple input() calls failed: {result}")
            return False
    except Exception as e:
        print(f"❌ Multiple input() calls error: {e}")
        return False

def test_string_input():
    """Test input() with string data"""
    print("🧪 Testing string input()...")
    
    test_code = """
name = input().strip()
print(f"Hello, {name}!")
"""
    
    test_input = "World"
    expected_output = "Hello, World!"
    
    try:
        result = secure_execute_code('python', test_code, test_input, expected_output)
        
        if result.get('verdict') == 'AC':
            print("✅ String input() works correctly")
            return True
        else:
            print(f"❌ String input() failed: {result}")
            print(f"   Expected: '{expected_output}'")
            print(f"   Got: '{result.get('output', '')}'")
            return False
    except Exception as e:
        print(f"❌ String input() error: {e}")
        return False

def main():
    print("🔧 Testing Input Function Fixes\n")
    
    tests = [
        test_input_function_allowed,
        test_input_execution,
        test_multiple_inputs,
        test_string_input
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"❌ Test failed with exception: {e}\n")
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The input() function fixes are working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)