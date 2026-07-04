from django.test import TestCase
from .utils.secure_execution import (
    analyze_python_code_security,
    validate_code_security,
    secure_execute_code
)

class SecurityAnalysisTests(TestCase):
    def test_safe_imports_allowed(self):
        safe_code = """
import collections
import math
from itertools import chain
from heapq import heappush
"""
        is_safe, violations = analyze_python_code_security(safe_code)
        self.assertTrue(is_safe, f"Safe code was flagged: {violations}")

    def test_forbidden_imports_caught(self):
        forbidden_codes = [
            "import os",
            "import subprocess",
            "import socket",
            "from os import system",
            "__import__('os')"
        ]
        for code in forbidden_codes:
            is_safe, violations = analyze_python_code_security(code)
            self.assertFalse(is_safe, f"Forbidden code was not flagged: {code}")
            self.assertTrue(len(violations) > 0)

    def test_forbidden_functions_caught(self):
        forbidden_codes = [
            "eval('1 + 1')",
            "exec('a = 1')",
            "open('test.txt', 'w')",
            "exit(1)"
        ]
        for code in forbidden_codes:
            is_safe, violations = analyze_python_code_security(code)
            self.assertFalse(is_safe, f"Forbidden function was not flagged: {code}")

    def test_dangerous_attributes_caught(self):
        dangerous_code = "obj.system('ls')"
        is_safe, violations = analyze_python_code_security(dangerous_code)
        self.assertFalse(is_safe, "Dangerous attribute (system) was not flagged")

    def test_syntax_error_handled(self):
        bad_code = "for i in range(10) print(i)" # missing colon
        is_safe, violations = analyze_python_code_security(bad_code)
        self.assertFalse(is_safe)
        self.assertTrue(any("Syntax error" in v for v in violations))


class ValidationTests(TestCase):
    def test_empty_code(self):
        is_valid, msg = validate_code_security("", "python")
        self.assertFalse(is_valid)
        self.assertEqual(msg, "Empty code or language")

    def test_unsupported_language(self):
        is_valid, msg = validate_code_security("print(1)", "ruby")
        self.assertFalse(is_valid)
        self.assertTrue("not allowed" in msg)

    def test_oversized_code(self):
        large_code = "x = 1\n" * 2000000
        is_valid, msg = validate_code_security(large_code, "python")
        self.assertFalse(is_valid)
        self.assertEqual(msg, "Code too long")

    def test_cpp_java_suspicious_patterns(self):
        suspicious = [
            "system('rm -rf /');",
            "Runtime.getRuntime().exec(\"ls\");",
            "ProcessBuilder pb = new ProcessBuilder();"
        ]
        for code in suspicious:
            is_valid, msg = validate_code_security(code, "cpp")
            self.assertFalse(is_valid, f"Failed to catch: {code}")
            self.assertTrue("Suspicious pattern" in msg)


class ExecutionTests(TestCase):
    def test_python_ac(self):
        code = "name = input()\nprint(f'Hello {name}')"
        result = secure_execute_code('python', code, "Alice", "Hello Alice")
        if result.get('verdict') != 'AC':
            print("AC test failed. Result:", result)
        self.assertEqual(result.get('verdict'), 'AC')
        self.assertEqual(result.get('output'), 'Hello Alice')

    def test_python_wa(self):
        code = "name = input()\nprint('Wrong')"
        result = secure_execute_code('python', code, "Alice", "Hello Alice")
        self.assertEqual(result.get('verdict'), 'WA')
        self.assertEqual(result.get('output'), 'Wrong')

    def test_python_re(self):
        code = "print(1 / 0)"
        result = secure_execute_code('python', code, "", "")
        self.assertEqual(result.get('verdict'), 'RE')
        self.assertTrue("division by zero" in result.get('error', ''))

    def test_python_tle(self):
        # We run an infinite loop and it should time out (takes ~5s)
        code = "while True:\n    pass"
        result = secure_execute_code('python', code, "", "")
        self.assertEqual(result.get('verdict'), 'TLE')

    def test_python_security_violation_in_execution(self):
        code = "import os\nos.system('echo hacked')"
        result = secure_execute_code('python', code, "", "")
        self.assertEqual(result.get('verdict'), 'CE')
        self.assertTrue('Security violation' in result.get('error', ''))
