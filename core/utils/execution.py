#!/usr/bin/env python3
"""
Secure Code Executor for Online Judge
Implements security measures directly in code to prevent malicious submissions
"""

import sys
import os
import resource
import signal
import subprocess
import tempfile
import threading
import time
import psutil
import gc
from contextlib import contextmanager
from io import StringIO
import ast
import builtins

class SecureCodeExecutor:
    def __init__(self, 
                 memory_limit_mb=128, 
                 time_limit_seconds=5, 
                 cpu_limit_seconds=3):
        self.memory_limit = memory_limit_mb * 1024 * 1024  # Convert to bytes
        self.time_limit = time_limit_seconds
        self.cpu_limit = cpu_limit_seconds
        self.start_time = None
        self.process = None
        
        # Blocked modules and functions
        self.blocked_modules = {
            'os', 'subprocess', 'sys', 'socket', 'urllib', 'requests',
            'multiprocessing', 'threading', 'asyncio', 'ctypes',
            'importlib', 'marshal', 'pickle', '__builtin__', '__builtins__'
        }
        
        self.blocked_functions = {
            'eval', 'exec', 'compile', '__import__', 'open', 'file',
            'input', 'raw_input', 'reload', 'vars', 'locals', 'globals',
            'dir', 'hasattr', 'getattr', 'setattr', 'delattr'
        }
        
    def set_resource_limits(self):
        """Set system resource limits"""
        try:
            # Memory limit (virtual memory)
            resource.setrlimit(resource.RLIMIT_AS, (self.memory_limit, self.memory_limit))
            
            # CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.cpu_limit, self.cpu_limit))
            
            # No core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            
            # Limit number of processes
            resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
            
            # Limit file size
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024*1024, 1024*1024))  # 1MB
            
            print(f"✅ Resource limits set: {self.memory_limit//1024//1024}MB memory, {self.cpu_limit}s CPU")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not set resource limits: {e}")
    
    def timeout_handler(self, signum, frame):
        """Handle timeout signal"""
        raise TimeoutError("Code execution timed out")
    
    def check_code_safety(self, code):
        """Static analysis to check for dangerous code patterns"""
        dangerous_patterns = [
            'import os', 'import sys', 'import subprocess', 'import socket',
            'import urllib', 'import requests', 'import threading',
            'import multiprocessing', '__import__', 'eval(', 'exec(',
            'open(', 'file(', 'input(', 'raw_input(', 'while True:',
            'for i in range(999', 'range(10000', '*' * 100
        ]
        
        code_lower = code.lower()
        detected_patterns = []
        
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                detected_patterns.append(pattern)
        
        if detected_patterns:
            return False, f"Dangerous patterns detected: {', '.join(detected_patterns)}"
        
        # Check for potential infinite loops
        if 'while' in code_lower and 'break' not in code_lower:
            return False, "Potential infinite loop detected (while without break)"
            
        # Check for large allocations
        if any(num in code for num in ['9999', '99999', '999999']):
            return False, "Large number detected - potential resource exhaustion"
            
        return True, "Code appears safe"
    
    def create_safe_environment(self):
        """Create a restricted execution environment"""
        safe_builtins = {
            'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod',
            'enumerate', 'filter', 'float', 'format', 'frozenset', 'hex',
            'int', 'len', 'list', 'map', 'max', 'min', 'oct', 'ord',
            'pow', 'print', 'range', 'repr', 'reversed', 'round', 'set',
            'slice', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip'
        }
        
        # Create restricted builtins
        restricted_builtins = {}
        for name in safe_builtins:
            if hasattr(builtins, name):
                restricted_builtins[name] = getattr(builtins, name)
        
        # Add safe modules
        safe_globals = {
            '__builtins__': restricted_builtins,
            'math': __import__('math'),
            'random': __import__('random'),
            'string': __import__('string'),
            'collections': __import__('collections'),
            'itertools': __import__('itertools'),
            'functools': __import__('functools'),
            're': __import__('re')
        }
        
        return safe_globals
    
    def monitor_memory_usage(self, stop_event):
        """Monitor memory usage in a separate thread"""
        try:
            process = psutil.Process()
            while not stop_event.is_set():
                memory_info = process.memory_info()
                if memory_info.rss > self.memory_limit:
                    print(f"🚨 Memory limit exceeded: {memory_info.rss // 1024 // 1024}MB")
                    os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(0.1)
        except Exception:
            pass
    
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
    
    def execute_python_code(self, code, inputs=None):
        """Execute Python code with security measures"""
        print("🔒 Executing Python code with security measures...")
        
        # Set resource limits
        self.set_resource_limits()
        
        # Set timeout
        signal.signal(signal.SIGALRM, self.timeout_handler)
        signal.alarm(self.time_limit)
        
        # Start memory monitor
        stop_monitor = threading.Event()
        monitor_thread = threading.Thread(target=self.monitor_memory_usage, args=(stop_monitor,))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        self.start_time = time.time()
        
        try:
            # Static code analysis
            is_safe, message = self.check_code_safety(code)
            if not is_safe:
                return {
                    'success': False,
                    'error': f"Code rejected: {message}",
                    'stdout': '',
                    'stderr': '',
                    'execution_time': 0
                }
            
            # Create safe execution environment
            safe_globals = self.create_safe_environment()
            safe_locals = {}
            
            # Capture output
            with self.capture_output() as (stdout_capture, stderr_capture):
                try:
                    # Handle inputs if provided
                    if inputs:
                        input_lines = inputs.strip().split('\n')
                        input_iter = iter(input_lines)
                        safe_globals['input'] = lambda prompt='': next(input_iter, '')
                    
                    # Execute the code
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
                    
                except MemoryError:
                    return {
                        'success': False,
                        'error': 'Memory limit exceeded',
                        'stdout': stdout_capture.getvalue(),
                        'stderr': stderr_capture.getvalue(),
                        'execution_time': time.time() - self.start_time
                    }
                except TimeoutError as e:
                    return {
                        'success': False,
                        'error': str(e),
                        'stdout': stdout_capture.getvalue(),
                        'stderr': stderr_capture.getvalue(),
                        'execution_time': self.time_limit
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': str(e),
                        'stdout': stdout_capture.getvalue(),
                        'stderr': stderr_capture.getvalue(),
                        'execution_time': time.time() - self.start_time
                    }
        
        finally:
            # Cleanup
            signal.alarm(0)  # Cancel timeout
            stop_monitor.set()  # Stop memory monitor
            gc.collect()  # Force garbage collection
    
    def execute_c_code(self, code, inputs=None):
        """Execute C code with security measures"""
        print("🔒 Executing C code with security measures...")
        
        # Check for dangerous C patterns
        dangerous_c_patterns = [
            'system(', 'exec(', 'fork(', 'clone(', 'mmap(',
            'socket(', 'connect(', 'bind(', 'listen(', 'accept(',
            'fopen("/etc', 'fopen("/usr', 'fopen("/var',
            '#include <sys/socket.h>', '#include <unistd.h>',
            'while(1)', 'for(;;)', 'malloc(999999'
        ]
        
        for pattern in dangerous_c_patterns:
            if pattern in code:
                return {
                    'success': False,
                    'error': f'Dangerous C pattern detected: {pattern}',
                    'stdout': '',
                    'stderr': '',
                    'execution_time': 0
                }
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
                f.write(code)
                source_file = f.name
            
            executable = source_file.replace('.c', '')
            
            # Compile with security flags
            compile_cmd = [
                'gcc', 
                '-Wall', '-Wextra', '-O2',
                '-fstack-protector-strong',
                '-D_FORTIFY_SOURCE=2',
                source_file, '-o', executable
            ]
            
            compile_result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if compile_result.returncode != 0:
                os.unlink(source_file)
                return {
                    'success': False,
                    'error': f'Compilation failed: {compile_result.stderr}',
                    'stdout': '',
                    'stderr': compile_result.stderr,
                    'execution_time': 0
                }
            
            # Execute with limits
            start_time = time.time()
            
            execute_cmd = [
                'timeout', str(self.time_limit),
                'ulimit', '-v', str(self.memory_limit // 1024),  # KB
                '&&', executable
            ]
            
            # Use shell to apply ulimit
            cmd = f"ulimit -v {self.memory_limit // 1024} && timeout {self.time_limit} {executable}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                input=inputs,
                capture_output=True,
                text=True,
                timeout=self.time_limit + 1
            )
            
            execution_time = time.time() - start_time
            
            # Cleanup
            os.unlink(source_file)
            if os.path.exists(executable):
                os.unlink(executable)
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'execution_time': execution_time,
                'error': 'Execution failed' if result.returncode != 0 else None
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Time limit exceeded',
                'stdout': '',
                'stderr': '',
                'execution_time': self.time_limit
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'stdout': '',
                'stderr': '',
                'execution_time': 0
            }

# Example usage and testing
def test_secure_executor():
    """Test the secure executor with various code samples"""
    executor = SecureCodeExecutor(memory_limit_mb=64, time_limit_seconds=3)
    
    test_cases = [
        {
            'name': 'Safe Code',
            'code': '''
for i in range(10):
    print(f"Number: {i}")
print("Sum:", sum(range(10)))
            ''',
            'language': 'python'
        },
        {
            'name': 'Memory Bomb',
            'code': '''
data = []
for i in range(1000000):
    data.append("A" * 1024)
    if i % 1000 == 0:
        print(f"Iteration {i}")
            ''',
            'language': 'python'
        },
        {
            'name': 'Infinite Loop',
            'code': '''
count = 0
while True:
    count += 1
    if count % 1000000 == 0:
        print(f"Count: {count}")
            ''',
            'language': 'python'
        },
        {
            'name': 'System Access',
            'code': '''
import os
os.system("whoami")
            ''',
            'language': 'python'
        },
        {
            'name': 'File Access',
            'code': '''
with open("/etc/passwd", "r") as f:
    print(f.read())
            ''',
            'language': 'python'
        }
    ]
    
    print("🧪 Testing Secure Code Executor")
    print("=" * 50)
    
    for test in test_cases:
        print(f"\n🔍 Testing: {test['name']}")
        print("-" * 30)
        
        if test['language'] == 'python':
            result = executor.execute_python_code(test['code'])
        else:
            result = executor.execute_c_code(test['code'])
        
        print(f"Success: {result['success']}")
        print(f"Execution Time: {result['execution_time']:.2f}s")
        
        if result['error']:
            print(f"Error: {result['error']}")
        
        if result['stdout']:
            print(f"Output: {result['stdout'][:200]}...")
        
        if result['stderr']:
            print(f"Stderr: {result['stderr'][:200]}...")

if __name__ == "__main__":
    # Check if required modules are available
    try:
        import psutil
    except ImportError:
        print("⚠️ psutil not installed. Install with: pip install psutil")
        sys.exit(1)
    
    test_secure_executor()