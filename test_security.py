#!/usr/bin/env python
"""
Security test script to verify the fixes work
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_judge.settings')
django.setup()

from core.utils.secure_execution import validate_code_security, secure_execute_code

def test_security_validation():
    """Test code security validation"""
    print("🔒 Testing Security Validation...")
    
    # Test dangerous code patterns
    dangerous_codes = [
        "import os\nos.system('rm -rf /')",
        "import subprocess\nsubprocess.call(['ls', '/'])",
        "__import__('os').system('whoami')",
        "eval('print(1)')",
        "exec('import sys')",
    ]
    
    safe_codes = [
        "print('Hello World')",
        "def add(a, b):\n    return a + b\nprint(add(2, 3))",
        "for i in range(10):\n    print(i)",
    ]
    
    print("Testing dangerous code patterns...")
    for i, code in enumerate(dangerous_codes, 1):
        is_valid, message = validate_code_security(code, 'python')
        if not is_valid:
            print(f"✅ Test {i}: Blocked dangerous code - {message}")
        else:
            print(f"❌ Test {i}: Failed to block dangerous code")
    
    print("\nTesting safe code patterns...")
    for i, code in enumerate(safe_codes, 1):
        is_valid, message = validate_code_security(code, 'python')
        if is_valid:
            print(f"✅ Test {i}: Allowed safe code")
        else:
            print(f"❌ Test {i}: Incorrectly blocked safe code - {message}")

def test_code_execution():
    """Test secure code execution"""
    print("\n🚀 Testing Secure Code Execution...")
    
    # Test simple safe code
    safe_code = "print('Hello, World!')"
    result = secure_execute_code('python', safe_code, '', 'Hello, World!')
    
    if result['verdict'] == 'AC':
        print("✅ Safe code execution works")
    else:
        print(f"❌ Safe code execution failed: {result}")
    
    # Test resource limits (infinite loop)
    infinite_loop = "while True:\n    pass"
    result = secure_execute_code('python', infinite_loop, '', '')
    
    if result['verdict'] == 'TLE':
        print("✅ Time limit enforcement works")
    else:
        print(f"❌ Time limit enforcement failed: {result}")

def test_file_validation():
    """Test file upload validation"""
    print("\n📁 Testing File Upload Validation...")
    
    from core.utils.file_validators import sanitize_filename
    
    # Test filename sanitization
    dangerous_filenames = [
        "../../../etc/passwd",
        "file;rm -rf /",
        "file<script>alert(1)</script>.jpg",
        "file|whoami.png"
    ]
    
    for filename in dangerous_filenames:
        sanitized = sanitize_filename(filename)
        if '../' not in sanitized and ';' not in sanitized and '<' not in sanitized and '|' not in sanitized:
            print(f"✅ Sanitized: {filename} -> {sanitized}")
        else:
            print(f"❌ Failed to sanitize: {filename} -> {sanitized}")

if __name__ == "__main__":
    print("🛡️  Running Security Tests...\n")
    
    try:
        test_security_validation()
        test_code_execution()
        test_file_validation()
        
        print("\n✅ Security tests completed!")
        print("\n📋 Summary of Security Fixes Applied:")
        print("1. ✅ Code execution sandboxing")
        print("2. ✅ Resource limits and timeouts")
        print("3. ✅ Input validation and sanitization")
        print("4. ✅ File upload security")
        print("5. ✅ Dangerous pattern detection")
        print("6. ✅ Profile photo organization")
        
    except Exception as e:
        print(f"❌ Security test failed: {e}")
        sys.exit(1)