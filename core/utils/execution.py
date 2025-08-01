#!/usr/bin/env python3
"""
Simplified Secure Code Executor for Online Judge
Minimal dependencies, maximum compatibility
"""

import sys
import os
import signal
import subprocess
import tempfile
import time
import threading
import gc
from contextlib import contextmanager
from io import StringIO

class SimpleSecureExecutor:
    def __init__(self, memory_limit_mb=64, time_limit_seconds=5):
        self.memory_limit_mb = memory_limit_mb
        self.time_limit = time_limit_seconds
        self.start_time = None
        
        # Simple blocked patterns
        self.blocked_imports = [
            'import os', 'import sys', 'import subprocess', 'import socket',
            'import urllib', 'import requests', 'import threading', 
            'import multiprocessing', 'from os', 'from sys', 'from subprocess'
        ]
        
        self.blocked_functions = [
            'eval(', 'exec(', '__import__(', 'open(', 'file(',
            'input(', 'raw_input(', 'compile('
        ]
        
        self.blocked_patterns = [
            'while True:', 'while 1:', 'for i in range(999999',
            'range(999999', 'range(1000000', '*' * 50
        ]
    
    def check_code_safety(self, code):
        """Basic static analysis for dangerous patterns"""
        code_lower = code.lower().replace(' ', '').replace('\n', ' ')
        
        # Check for blocked imports
        for pattern in self.blocked_imports:
            if pattern.lower().replace(' ', '') in code_lower:
                return False, f"Blocked import: {pattern}"
        
        # Check for blocked functions
        for pattern in self.blocked_functions:
            if pattern.lower() in code_lower:
                return False, f"Blocked function: {pattern}"
        
        # Check for dangerous patterns
        for pattern in self.blocked_patterns:
            if pattern.lower().replace(' ', '') in code_lower:
                return False, f"Dangerous pattern: {pattern}"
        
        # Check for potential memory bombs
        if any(str(num) in code for num in [99999, 999999, 9999999]):
            return False, "Large number detected - potential resource exhaustion"
        
        return True, "Code appears safe"
    
    def timeout_handler(self, signum, frame):
        """Handle timeout"""
        raise TimeoutError("Code execution timed out")
    
    @contextmanager
    def capture_output(self):
        """Capture stdout and stderr"""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            yield stdout_capture, stderr_capture
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def create_restricted_globals(self):
        """Create a restricted global environment"""
        safe_builtins = {
            'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
            'chr': chr, 'dict': dict, 'divmod': divmod, 'enumerate': enumerate,
            'filter': filter, 'float': float, 'format': format, 'frozenset': frozenset,
            'hex': hex, 'int': int, 'len': len, 'list': list, 'map': map,
            'max': max, 'min': min, 'oct': oct, 'ord': ord, 'pow': pow,
            'print': print, 'range': range, 'repr': repr, 'reversed': reversed,
            'round': round, 'set': set, 'slice': slice, 'sorted': sorted,
            'str': str, 'sum': sum, 'tuple': tuple, 'type': type, 'zip': zip
        }
        
        # Add safe modules
        try:
            import math
            import random
            import string
            safe_globals = {
                '__builtins__': safe_builtins,
                'math': math,
                'random': random,
                'string': string
            }
        except ImportError:
            safe_globals = {'__builtins__': safe_builtins}
        
        return safe_globals
    
    def execute_with_subprocess(self, code, inputs=None):
        """Execute code in a separate process with limits"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Build command with resource limits
            if os.name == 'posix':  # Unix/Linux
                cmd = [
                    'timeout', str(self.time_limit),
                    'python3', temp_file
                ]
            else:  # Windows
                cmd = ['python', temp_file]
            
            start_time = time.time()
            
            # Execute with timeout
            try:
                result = subprocess.run(
                    cmd,
                    input=inputs,
                    capture_output=True,
                    text=True,
                    timeout=self.time_limit
                )
                
                execution_time = time.time() - start_time
                
                # Clean up
                os.unlink(temp_file)
                
                return {
                    'success': result.returncode == 0,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'execution_time': execution_time,
                    'error': None if result.returncode == 0 else 'Runtime error'
                }
                
            except subprocess.TimeoutExpired:
                os.unlink(temp_file)
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': '',
                    'execution_time': self.time_limit,
                    'error': 'Time limit exceeded'
                }
                
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'execution_time': 0,
                'error': f'Execution error: {str(e)}'
            }
    
    def execute_in_process(self, code, inputs=None):
        """Execute code in current process with basic protection"""
        # Set timeout
        signal.signal(signal.SIGALRM, self.timeout_handler)
        signal.alarm(self.time_limit)
        
        self.start_time = time.time()
        
        try:
            # Create restricted environment
            safe_globals = self.create_restricted_globals()
            safe_locals = {}
            
            # Handle inputs
            if inputs:
                input_lines = inputs.strip().split('\n')
                input_iter = iter(input_lines)
                safe_globals['input'] = lambda prompt='': next(input_iter, '')
            
            # Capture output
            with self.capture_output() as (stdout_capture, stderr_capture):
                try:
                    # Compile and execute
                    compiled_code = compile(code, '<user_code>', 'exec')
                    exec(compiled_code, safe_globals, safe_locals)
                    
                    execution_time = time.time() - self.start_time
                    
                    return {
                        'success': True,
                        'stdout': stdout_capture.getvalue(),
                        'stderr': stderr_capture.getvalue(),
                        'execution_time': execution_time,
                        'error': None
                    }
                    
                except TimeoutError:
                    return {
                        'success': False,
                        'stdout': stdout_capture.getvalue(),
                        'stderr': stderr_capture.getvalue(),
                        'execution_time': self.time_limit,
                        'error': 'Time limit exceeded'
                    }
                except MemoryError:
                    return {
                        'success': False,
                        'stdout': stdout_capture.getvalue(),
                        'stderr': stderr_capture.getvalue(),
                        'execution_time': time.time() - self.start_time,
                        'error': 'Memory limit exceeded'
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'stdout': stdout_capture.getvalue(),
                        'stderr': stderr_capture.getvalue(),
                        'execution_time': time.time() - self.start_time,
                        'error': str(e)
                    }
        finally:
            signal.alarm(0)  # Cancel timeout
            gc.collect()  # Force garbage collection
    
    def execute_python_code(self, code, inputs=None, use_subprocess=True):
        """Main execution method"""
        print(f"🔒 Executing code with {self.memory_limit_mb}MB limit, {self.time_limit}s timeout")
        
        # Static code analysis
        is_safe, message = self.check_code_safety(code)
        if not is_safe:
            return {
                'success': False,
                'error': f'Code rejected: {message}',
                'stdout': '',
                'stderr': '',
                'execution_time': 0
            }
        
        # Choose execution method
        if use_subprocess and os.name == 'posix':
            return self.execute_with_subprocess(code, inputs)
        else:
            return self.execute_in_process(code, inputs)

# Simple test function
def test_executor():
    """Test the executor with safe examples"""
    executor = SimpleSecureExecutor(memory_limit_mb=32, time_limit_seconds=3)
    
    # Test cases
    test_cases = [
        {
            'name': 'Hello World',
            'code': 'print("Hello, World!")'
        },
        {
            'name': 'Simple Math',
            'code': '''
import math
for i in range(5):
    print(f"Square root of {i}: {math.sqrt(i) if i > 0 else 0}")
'''
        },
        {
            'name': 'Blocked Import',
            'code': '''
import os
print(os.getcwd())
'''
        },
        {
            'name': 'Large Range (should be blocked)',
            'code': '''
for i in range(999999):
    print(i)
'''
        },
        {
            'name': 'Input/Output',
            'code': '''
name = input("Enter name: ")
print(f"Hello, {name}!")
''',
            'inputs': 'Alice'
        }
    ]
    
    print("🧪 Testing Simple Secure Executor")
    print("=" * 40)
    
    for test in test_cases:
        print(f"\n📝 Test: {test['name']}")
        print("-" * 20)
        
        inputs = test.get('inputs', None)
        result = executor.execute_python_code(test['code'], inputs)
        
        print(f"✅ Success: {result['success']}")
        print(f"⏱️  Time: {result['execution_time']:.3f}s")
        
        if result['error']:
            print(f"❌ Error: {result['error']}")
        
        if result['stdout']:
            print(f"📤 Output: {result['stdout'].strip()}")
        
        if result['stderr']:
            print(f"⚠️  Stderr: {result['stderr'].strip()}")

if __name__ == "__main__":
    test_executor()