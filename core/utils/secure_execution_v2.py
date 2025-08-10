"""
Enhanced secure code execution module - Simplified approach
Balances security with functionality for competitive programming
"""
import subprocess
import tempfile
import os
import shutil
import json
import signal
import platform
from pathlib import Path
import re
import hashlib
import time
import ast
import threading
from django.conf import settings

# Platform-specific imports
IS_WINDOWS = platform.system() == 'Windows'

if not IS_WINDOWS:
    try:
        import resource
        import pwd
        import grp
        HAS_RESOURCE = True
    except ImportError:
        HAS_RESOURCE = False
else:
    HAS_RESOURCE = False

# Security constants
MAX_EXECUTION_TIME = 5  # seconds
MAX_MEMORY_MB = 128  # MB
MAX_FILE_SIZE = 1024 * 1024  # 1MB
MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB
ALLOWED_LANGUAGES = ['python', 'cpp', 'java', 'javascript']

# Smart whitelist system for imports - more permissive for competitive programming
ALLOWED_IMPORTS = {
    'collections': ['deque', 'defaultdict', 'Counter', 'OrderedDict', 'namedtuple', 'ChainMap'],
    'itertools': ['permutations', 'combinations', 'combinations_with_replacement', 'product', 'chain', 'cycle', 'repeat', 'count', 'islice', 'takewhile', 'dropwhile', 'filterfalse', 'compress', 'groupby', 'accumulate'],
    'math': ['*'],  # Math is generally safe for competitive programming
    'heapq': ['*'],  # Essential for algorithms
    'bisect': ['*'],  # Binary search utilities
    're': ['compile', 'match', 'search', 'findall', 'finditer', 'sub', 'subn', 'split', 'escape'],
    'functools': ['lru_cache', 'reduce', 'partial', 'wraps', 'singledispatch'],
    'operator': ['*'],  # Safe operator functions
    'string': ['*'],  # String constants and utilities
    'random': ['randint', 'choice', 'shuffle', 'sample', 'random', 'uniform', 'seed'],
    'decimal': ['*'],  # For precise decimal arithmetic
    'fractions': ['*'],  # For rational number arithmetic
    'copy': ['copy', 'deepcopy'],  # Safe copying utilities
    'typing': ['*'],  # Type hints (safe)
    'dataclasses': ['dataclass', 'field', 'fields', 'asdict', 'astuple'],
    'enum': ['*'],  # Enumerations
    'datetime': ['datetime', 'date', 'time', 'timedelta', 'timezone'],  # Limited datetime functionality
    'json': ['loads', 'dumps'],  # Safe JSON operations (no file I/O)
}

# Absolutely forbidden modules - these should never be allowed
ABSOLUTELY_FORBIDDEN = [
    'os', 'subprocess', 'sys', 'socket', 'urllib', 'urllib2', 'urllib3', 'requests',
    'shutil', 'tempfile', 'importlib', 'pickle', 'dill', 'marshal', 'shelve',
    'dbm', 'sqlite3', 'mysql', 'psycopg2', 'pymongo',  # Database modules
    'ftplib', 'smtplib', 'poplib', 'imaplib', 'nntplib',  # Network modules
    'threading', 'multiprocessing', 'concurrent', 'asyncio',  # Concurrency modules
    'ctypes', 'cffi', 'cython',  # Low-level modules
    'webbrowser', 'tkinter', 'turtle',  # GUI modules
    '__builtin__', '__builtins__', 'builtins',  # Builtin manipulation
    'code', 'codeop',  # Code execution
]

# Forbidden function calls (these will be blocked by AST analysis)
FORBIDDEN_FUNCTIONS = [
    'eval', 'exec', 'compile', '__import__',
    'open', 'file', 'raw_input',  # I/O functions (input() will be handled specially)
    'exit', 'quit', 'help', 'copyright', 'credits', 'license',
]

def analyze_python_code_security(code):
    """Use AST to detect dangerous operations more accurately for Python"""
    try:
        tree = ast.parse(code)
        
        class SecurityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.violations = []
            
            def visit_Import(self, node):
                for alias in node.names:
                    if alias.name in ABSOLUTELY_FORBIDDEN:
                        self.violations.append(f"Forbidden import: {alias.name}")
                    elif alias.name not in ALLOWED_IMPORTS:
                        self.violations.append(f"Import not in whitelist: {alias.name}. Try using built-in alternatives or allowed modules like collections, itertools, math, heapq, bisect.")
                self.generic_visit(node)
            
            def visit_ImportFrom(self, node):
                if node.module in ABSOLUTELY_FORBIDDEN:
                    self.violations.append(f"Forbidden import from: {node.module}")
                elif node.module and node.module not in ALLOWED_IMPORTS:
                    self.violations.append(f"Import from module not in whitelist: {node.module}")
                elif node.module in ALLOWED_IMPORTS:
                    # Check specific imports from allowed modules
                    allowed_items = ALLOWED_IMPORTS[node.module]
                    if allowed_items != ['*']:  # If not all items are allowed
                        for alias in node.names:
                            if alias.name != '*' and alias.name not in allowed_items:
                                self.violations.append(f"Function '{alias.name}' not allowed from module '{node.module}'. Allowed: {', '.join(allowed_items)}")
                self.generic_visit(node)
            
            def visit_Call(self, node):
                # Check for dangerous function calls
                if isinstance(node.func, ast.Name):
                    if node.func.id in FORBIDDEN_FUNCTIONS:
                        if node.func.id == 'input':
                            # input() is handled specially in our restricted environment
                            pass
                        else:
                            self.violations.append(f"Forbidden function: {node.func.id}")
                
                # Check for attribute access to dangerous functions
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['system', 'popen', 'exec', 'eval']:
                        self.violations.append(f"Forbidden method call: {node.func.attr}")
                
                self.generic_visit(node)
            
            def visit_Attribute(self, node):
                # Check for dangerous attribute access
                if isinstance(node.value, ast.Name):
                    if node.value.id == '__builtins__' or node.value.id == 'builtins':
                        self.violations.append("Direct access to builtins is not allowed")
                self.generic_visit(node)
        
        visitor = SecurityVisitor()
        visitor.visit(tree)
        return len(visitor.violations) == 0, visitor.violations
        
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

def validate_code_security(code, language):
    """
    Validate code for security vulnerabilities using improved methods
    """
    if not code or not language:
        return False, "Empty code or language"
    
    if language not in ALLOWED_LANGUAGES:
        return False, f"Language {language} not allowed"
    
    # Check code length
    if len(code) > MAX_FILE_SIZE:
        return False, "Code too long"
    
    # Use AST analysis for Python
    if language == 'python':
        is_safe, violations = analyze_python_code_security(code)
        if not is_safe:
            return False, f"Security violations detected:\n" + "\n".join(f"• {v}" for v in violations)
    
    # For other languages, use basic pattern matching
    elif language in ['java', 'cpp', 'javascript']:
        # Basic security patterns for non-Python languages
        dangerous_patterns = {
            'java': [
                r'java\.io\.File', r'java\.io\.FileInputStream', r'java\.io\.FileOutputStream',
                r'java\.lang\.Runtime', r'java\.lang\.ProcessBuilder', r'java\.lang\.System\.exit',
                r'java\.net\.Socket', r'java\.net\.URL', r'java\.nio\.file', r'javax\.script',
            ],
            'cpp': [
                r'#include\s*<\s*fstream\s*>', r'#include\s*<\s*filesystem\s*>',
                r'#include\s*<\s*cstdlib\s*>', r'#include\s*<\s*unistd\.h\s*>',
                r'system\s*\(', r'popen\s*\(', r'fork\s*\(',
            ],
            'javascript': [
                r'require\s*\(\s*[\'"]fs[\'"]', r'require\s*\(\s*[\'"]child_process[\'"]',
                r'require\s*\(\s*[\'"]os[\'"]', r'process\.exit', r'process\.env',
            ]
        }
        
        patterns = dangerous_patterns.get(language, [])
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Potentially dangerous {language} code detected: {pattern}"
    
    return True, "Code validation passed"

def format_error_message(verdict, error, language, execution_time=None, memory_used=None):
    """Provide educational error messages with suggestions"""
    
    error_suggestions = {
        'CE': {
            'python': {
                'import': "💡 Try using built-in data structures or allowed modules like collections, itertools, math, heapq, bisect instead of restricted imports.",
                'syntax': "💡 Check your indentation, brackets, and syntax. Python is sensitive to whitespace.",
                'module': "💡 This module is not allowed for security reasons. Use built-in alternatives or check the allowed modules list.",
            },
            'cpp': {
                'compilation': "💡 Check for missing headers (#include), syntax errors, or type mismatches. Make sure your main function returns int.",
                'undefined': "💡 Make sure all variables and functions are declared before use.",
            },
            'java': {
                'compilation': "💡 Check your class name matches 'Main', syntax errors, and import statements.",
                'access': "💡 Make sure your main method is 'public static void main(String[] args)'.",
            },
            'javascript': {
                'syntax': "💡 Check for missing semicolons, brackets, or syntax errors in your JavaScript code.",
            }
        },
        'TLE': "⏱️ Your solution is too slow. Consider optimizing your algorithm's time complexity. Look for nested loops that can be reduced or use more efficient data structures.",
        'MLE': "💾 Your solution uses too much memory. Try using more memory-efficient data structures or algorithms that don't store unnecessary data.",
        'WA': "❌ Your output doesn't match the expected output. Check your logic, edge cases, and make sure you're reading input correctly.",
        'RE': {
            'python': {
                'indexerror': "💡 Array/list index out of bounds. Check your loop conditions and array access.",
                'keyerror': "💡 Dictionary key not found. Use .get() method or check if key exists first.",
                'valueerror': "💡 Invalid value conversion. Check your input parsing and data types.",
                'zerodivisionerror': "💡 Division by zero. Add checks to ensure denominators are not zero.",
            },
            'general': "💥 Your program crashed during execution. Check for array bounds, null pointers, or invalid operations."
        }
    }
    
    base_message = error
    
    # Add performance info if available
    if execution_time is not None:
        base_message += f"\n⏱️ Execution time: {execution_time:.3f}s"
    if memory_used is not None:
        base_message += f"\n💾 Memory used: {memory_used / (1024*1024):.1f}MB"
    
    # Add educational suggestions
    if verdict in error_suggestions:
        suggestions = error_suggestions[verdict]
        
        if isinstance(suggestions, dict):
            if language in suggestions:
                lang_suggestions = suggestions[language]
                if isinstance(lang_suggestions, dict):
                    # Check for specific error patterns
                    error_lower = error.lower()
                    for pattern, suggestion in lang_suggestions.items():
                        if pattern in error_lower:
                            base_message += f"\n{suggestion}"
                            break
                else:
                    base_message += f"\n{lang_suggestions}"
            elif 'general' in suggestions:
                base_message += f"\n{suggestions['general']}"
        else:
            base_message += f"\n{suggestions}"
    
    return base_message

def create_simple_python_environment(code):
    """Create a simpler but still secure Python environment"""
    
    # Create the allowed imports dictionary as a string for the restricted environment
    allowed_imports_str = str(ALLOWED_IMPORTS).replace("'*'", "['*']")
    absolutely_forbidden_str = str(ABSOLUTELY_FORBIDDEN)
    
    # Indent the user code
    indented_code = '\n'.join('    ' + line for line in code.split('\n'))
    
    restricted_code = f"""import sys
import builtins

# Store original import function
original_import = builtins.__import__

# Define allowed imports
ALLOWED_IMPORTS = {allowed_imports_str}
ABSOLUTELY_FORBIDDEN = {absolutely_forbidden_str}

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    # Allow internal Python modules (starting with _) that are needed by the import system
    if name and name.startswith('_'):
        return original_import(name, globals, locals, fromlist, level)
    
    # Check if module is absolutely forbidden
    if name in ABSOLUTELY_FORBIDDEN:
        raise ImportError(f"Module '{{name}}' is not allowed for security reasons")
    
    # Check if module is in whitelist
    if name not in ALLOWED_IMPORTS:
        raise ImportError(f"Module '{{name}}' is not in the allowed imports list. Available modules: {{', '.join(ALLOWED_IMPORTS.keys())}}")
    
    # Import the module
    module = original_import(name, globals, locals, fromlist, level)
    
    # If specific functions are whitelisted (not '*'), filter the module
    allowed_items = ALLOWED_IMPORTS[name]
    if allowed_items != ['*'] and fromlist:
        # Check each imported item
        for item in fromlist:
            if item not in allowed_items:
                raise ImportError(f"Function '{{item}}' from module '{{name}}' is not allowed. Allowed items: {{', '.join(allowed_items)}}")
    
    return module

# Replace the import function
builtins.__import__ = safe_import

# Remove only the most dangerous builtins
dangerous_builtins = ['eval', 'exec', 'compile', 'open', 'file']
for name in dangerous_builtins:
    if hasattr(builtins, name):
        try:
            delattr(builtins, name)
        except (AttributeError, TypeError):
            pass

# Execution starts here
try:
{indented_code}
except Exception as e:
    print(f"Runtime Error: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
    
    return restricted_code

# Import the rest of the functions from the original secure_execution module
from .secure_execution import (
    create_secure_temp_directory, set_resource_limits, find_compiler,
    execute_cpp_secure, execute_java_secure, execute_javascript_secure
)

def execute_python_secure(code, input_data, expected_output, temp_dir):
    """Securely execute Python code with simplified but effective safety measures"""
    python_path = find_compiler('python3')
    if not python_path:
        return {'verdict': 'CE', 'error': 'Python interpreter not found'}
    
    # Create the simple Python environment
    restricted_code = create_simple_python_environment(code)
    
    filepath = os.path.join(temp_dir, 'main.py')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(restricted_code)
    
    return run_with_limits(
        [python_path, filepath],
        input_data,
        expected_output,
        temp_dir
    )

def run_with_limits(cmd, input_data, expected_output, temp_dir):
    """Run command with resource limits, security restrictions, and performance monitoring"""
    start_time = time.time()
    memory_peak = 0
    
    try:
        # Determine language from command for better error messages
        language = 'unknown'
        if any('python' in str(c).lower() for c in cmd):
            language = 'python'
        elif any('java' in str(c).lower() for c in cmd):
            language = 'java'
        elif any('.exe' in str(c) or 'g++' in str(c) for c in cmd):
            language = 'cpp'
        elif any('node' in str(c).lower() for c in cmd):
            language = 'javascript'
        
        # Create a subprocess with resource limits
        if IS_WINDOWS:
            # Windows doesn't support preexec_fn
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=temp_dir
            )
        else:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=temp_dir,
                preexec_fn=set_resource_limits
            )
        
        try:
            # Basic memory monitoring (if psutil is available)
            try:
                import psutil
                ps_process = psutil.Process(process.pid)
                
                def monitor_memory():
                    nonlocal memory_peak
                    while process.poll() is None:
                        try:
                            memory_info = ps_process.memory_info()
                            memory_peak = max(memory_peak, memory_info.rss)
                            time.sleep(0.01)  # Check every 10ms
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            break
                
                monitor_thread = threading.Thread(target=monitor_memory, daemon=True)
                monitor_thread.start()
            except ImportError:
                # psutil not available, skip memory monitoring
                pass
            
            out, err = process.communicate(
                input=input_data,
                timeout=MAX_EXECUTION_TIME
            )
            
            execution_time = time.time() - start_time
            
            # Check output size
            if len(out) > MAX_OUTPUT_SIZE:
                error_msg = format_error_message('RE', 'Output too large - your program produced too much output', language, execution_time, memory_peak)
                return {'verdict': 'RE', 'error': error_msg}
            
            if process.returncode != 0 or err.strip():
                error_msg = err.strip() or f"Process exited with code {process.returncode}"
                formatted_error = format_error_message('RE', error_msg, language, execution_time, memory_peak)
                return {'verdict': 'RE', 'error': formatted_error, 'output': out.strip()}
            
            # Normalize output for comparison
            actual_output = out.strip().replace('\r\n', '\n').replace('\r', '\n')
            expected_clean = expected_output.strip().replace('\r\n', '\n').replace('\r', '\n')
            
            if actual_output == expected_clean:
                return {
                    'verdict': 'AC', 
                    'output': actual_output,
                    'execution_time': execution_time,
                    'memory_used': memory_peak
                }
            else:
                error_msg = f"Expected: '{expected_clean}'\nGot: '{actual_output}'"
                formatted_error = format_error_message('WA', error_msg, language, execution_time, memory_peak)
                return {
                    'verdict': 'WA',
                    'output': actual_output,
                    'error': formatted_error,
                    'execution_time': execution_time,
                    'memory_used': memory_peak
                }
        
        except subprocess.TimeoutExpired:
            process.kill()
            execution_time = time.time() - start_time
            error_msg = f'Time Limit Exceeded ({MAX_EXECUTION_TIME} seconds)'
            formatted_error = format_error_message('TLE', error_msg, language, execution_time, memory_peak)
            return {'verdict': 'TLE', 'error': formatted_error}
    
    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f'Execution error: {str(e)}'
        formatted_error = format_error_message('RE', error_msg, language, execution_time, memory_peak)
        return {'verdict': 'RE', 'error': formatted_error}

def secure_execute_code(language, code, input_data, expected_output):
    """
    Securely execute code with sandboxing and resource limits
    """
    try:
        # Validate code security
        is_valid, message = validate_code_security(code, language)
        if not is_valid:
            return {'verdict': 'CE', 'error': f'Security violation: {message}'}
        
        # Create secure temporary directory
        temp_dir = create_secure_temp_directory()
        
        try:
            # Language-specific execution
            if language == 'python':
                return execute_python_secure(code, input_data, expected_output, temp_dir)
            elif language == 'cpp':
                return execute_cpp_secure(code, input_data, expected_output, temp_dir)
            elif language == 'java':
                return execute_java_secure(code, input_data, expected_output, temp_dir)
            elif language == 'javascript':
                return execute_javascript_secure(code, input_data, expected_output, temp_dir)
            else:
                return {'verdict': 'CE', 'error': f'Unsupported language: {language}'}
        
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    except Exception as e:
        return {'verdict': 'RE', 'error': f'Execution error: {str(e)}'}