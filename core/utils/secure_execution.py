"""
Secure code execution module with sandboxing and resource limits
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

# Smart whitelist system for imports
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
    'code', 'codeop', 'compile', 'exec', 'eval',  # Code execution
]

# Forbidden function calls (these will be blocked by AST analysis)
FORBIDDEN_FUNCTIONS = [
    'eval', 'exec', 'compile', '__import__',
    'open', 'file', 'raw_input',  # I/O functions (input() will be handled specially)
    'exit', 'quit', 'help', 'copyright', 'credits', 'license',
    # Note: globals, locals, vars, dir, getattr, setattr are needed by import system
    # but we'll monitor their usage through AST analysis if needed
]

# Java-specific dangerous patterns
JAVA_DANGEROUS_PATTERNS = [
    r'java\.io\.File',
    r'java\.io\.FileInputStream',
    r'java\.io\.FileOutputStream',
    r'java\.lang\.Runtime',
    r'java\.lang\.ProcessBuilder',
    r'java\.lang\.System\.exit',
    r'java\.net\.Socket',
    r'java\.net\.URL',
    r'java\.nio\.file',
    r'javax\.script',
    r'sun\.',
    r'com\.sun\.',
]

# C++ dangerous patterns
CPP_DANGEROUS_PATTERNS = [
    r'#include\s*<\s*fstream\s*>',
    r'#include\s*<\s*filesystem\s*>',
    r'#include\s*<\s*cstdlib\s*>',
    r'#include\s*<\s*unistd\.h\s*>',
    r'#include\s*<\s*sys/',
    r'system\s*\(',
    r'popen\s*\(',
    r'fork\s*\(',
    r'exec\w*\s*\(',
    r'std::system',
    r'std::filesystem',
    r'ofstream',
    r'ifstream',
    r'fstream',
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
    
    # For other languages, use pattern matching (can be improved later)
    elif language == 'java':
        patterns_to_check = JAVA_DANGEROUS_PATTERNS
        for pattern in patterns_to_check:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Potentially dangerous Java code detected: {pattern}"
    
    elif language == 'cpp':
        patterns_to_check = CPP_DANGEROUS_PATTERNS
        for pattern in patterns_to_check:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Potentially dangerous C++ code detected: {pattern}"
    
    elif language == 'javascript':
        # Basic JavaScript security checks
        js_dangerous_patterns = [
            r'require\s*\(\s*[\'"]fs[\'"]',
            r'require\s*\(\s*[\'"]child_process[\'"]',
            r'require\s*\(\s*[\'"]os[\'"]',
            r'require\s*\(\s*[\'"]path[\'"]',
            r'process\.exit',
            r'process\.env',
            r'global\.',
            r'Buffer\.',
        ]
        for pattern in js_dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Potentially dangerous JavaScript code detected: {pattern}"
    
    return True, "Code validation passed"

def create_secure_temp_directory():
    """
    Create a secure temporary directory with restricted permissions
    """
    temp_dir = tempfile.mkdtemp(prefix='secure_exec_')
    
    # Set restrictive permissions
    os.chmod(temp_dir, 0o700)
    
    return temp_dir

def set_resource_limits():
    """
    Set resource limits for the execution process (Unix only)
    """
    if HAS_RESOURCE and not IS_WINDOWS:
        try:
            # Set memory limit
            memory_limit = MAX_MEMORY_MB * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            
            # Set CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (MAX_EXECUTION_TIME, MAX_EXECUTION_TIME))
            
            # Set file size limit
            resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_SIZE, MAX_FILE_SIZE))
            
            # Set number of processes limit
            resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
        except (OSError, ValueError):
            # Resource limits not available or failed to set
            pass

def find_compiler(compiler_name):
    """Find the full path of a compiler/interpreter with security checks"""
    if IS_WINDOWS:
        # Windows paths
        allowed_compilers = {
            'python3': ['python', 'python3'],
            'python': ['python', 'python3'],
            'g++': ['g++', 'gcc'],
            'javac': ['javac'],
            'java': ['java'],
            'node': ['node'],
        }
    else:
        # Unix paths
        allowed_compilers = {
            'python3': ['/usr/bin/python3'],
            'python': ['/usr/bin/python3', '/usr/bin/python'],
            'g++': ['/usr/bin/g++'],
            'javac': ['/usr/bin/javac'],
            'java': ['/usr/bin/java'],
            'node': ['/usr/bin/node'],
        }
    
    if compiler_name not in allowed_compilers:
        return None
    
    for path in allowed_compilers[compiler_name]:
        if IS_WINDOWS:
            # On Windows, just return the command name and let PATH resolve it
            return path
        else:
            # On Unix, check the full path
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    
    return None

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

def create_safe_python_environment(code):
    """Create a more permissive but still safe Python environment"""
    
    # Safe builtins that are allowed
    safe_builtins = {
        'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'chr', 'dict',
        'divmod', 'enumerate', 'filter', 'float', 'format', 'frozenset',
        'hash', 'hex', 'id', 'int', 'isinstance', 'issubclass', 'iter', 
        'len', 'list', 'map', 'max', 'min', 'next', 'oct', 'ord', 'pow', 
        'print', 'range', 'repr', 'reversed', 'round', 'set', 'slice', 
        'sorted', 'str', 'sum', 'tuple', 'type', 'zip', 'input',
        # Additional builtin types needed by Python internals
        'bytes', 'bytearray', 'memoryview', 'complex', 'property',
        # Additional safe builtins
        'callable', 'classmethod', 'staticmethod', 'property', 'super',
        'object', 'Exception', 'ValueError', 'TypeError', 'IndexError',
        'KeyError', 'AttributeError', 'RuntimeError', 'StopIteration',
        # Exception types needed for proper error handling
        'ImportError', 'ModuleNotFoundError', 'NameError', 'SyntaxError',
        'IndentationError', 'TabError', 'SystemError', 'MemoryError',
        'RecursionError', 'NotImplementedError', 'ZeroDivisionError',
        'OverflowError', 'FloatingPointError', 'ArithmeticError',
        'LookupError', 'AssertionError', 'EOFError', 'KeyboardInterrupt',
        'OSError', 'IOError', 'FileNotFoundError', 'PermissionError',
        'IsADirectoryError', 'NotADirectoryError', 'InterruptedError',
        'BlockingIOError', 'ChildProcessError', 'ConnectionError',
        'BrokenPipeError', 'ConnectionAbortedError', 'ConnectionRefusedError',
        'ConnectionResetError', 'TimeoutError', 'ProcessLookupError',
        # Built-in functions needed by import system
        'locals', 'globals', 'vars', 'dir',  # Needed by import machinery
        'getattr', 'setattr', 'hasattr',  # Needed for attribute access
    }
    
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
    if name and (name.startswith('_') or name in ['traceback', 'warnings', 'linecache']):
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

# Remove dangerous builtins explicitly (but keep delattr for our own use)
dangerous_builtins = ['eval', 'exec', 'compile', 'open', 'file']
for name in dangerous_builtins:
    if hasattr(builtins, name):
        try:
            delattr(builtins, name)
        except (AttributeError, TypeError):
            pass

# Now restrict builtins to safe subset (after we've used delattr)
safe_builtins_set = {safe_builtins}
for name in list(builtins.__dict__.keys()):
    if name not in safe_builtins_set and not name.startswith('__') and name not in ['delattr']:
        try:
            delattr(builtins, name)
        except (AttributeError, TypeError):
            pass  # Some builtins can't be deleted

# Finally remove delattr itself
try:
    delattr(builtins, 'delattr')
except (AttributeError, TypeError):
    pass

# Execution starts here
try:
{indented_code}
except Exception as e:
    import traceback
    print(f"Runtime Error: {{e}}", file=sys.stderr)
    # Print a simplified traceback for debugging
    tb_lines = traceback.format_exc().split('\\n')
    # Filter out our wrapper code from traceback
    filtered_tb = [line for line in tb_lines if 'main.py' in line or 'Error:' in line or 'Exception:' in line]
    if len(filtered_tb) > 1:
        print('\\n'.join(filtered_tb[-3:]), file=sys.stderr)
    sys.exit(1)
"""
    
    return restricted_code

def execute_python_secure(code, input_data, expected_output, temp_dir):
    """Securely execute Python code with improved safety measures"""
    python_path = find_compiler('python3')
    if not python_path:
        return {'verdict': 'CE', 'error': 'Python interpreter not found'}
    
    # Create the safe Python environment
    restricted_code = create_safe_python_environment(code)
    
    filepath = os.path.join(temp_dir, 'main.py')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(restricted_code)
    
    return run_with_limits(
        [python_path, filepath],
        input_data,
        expected_output,
        temp_dir
    )

def execute_cpp_secure(code, input_data, expected_output, temp_dir):
    """Securely execute C++ code"""
    gpp_path = find_compiler('g++')
    if not gpp_path:
        return {'verdict': 'CE', 'error': 'g++ compiler not found'}
    
    filepath = os.path.join(temp_dir, 'main.cpp')
    exe_path = os.path.join(temp_dir, 'main.out')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)
    
    # Compile with security flags
    compile_cmd = [
        gpp_path, filepath, '-o', exe_path,
        '-std=c++17',
        '-O2',
        '-Wall',
        '-Wextra',
        '-DONLINE_JUDGE',
        '-fno-asm',
        '-fno-builtin-system'
    ]
    
    try:
        compile_proc = subprocess.run(
            compile_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=temp_dir
        )
        
        if compile_proc.returncode != 0:
            return {'verdict': 'CE', 'error': compile_proc.stderr}
        
        return run_with_limits([exe_path], input_data, expected_output, temp_dir)
    
    except subprocess.TimeoutExpired:
        return {'verdict': 'CE', 'error': 'Compilation timeout'}

def execute_java_secure(code, input_data, expected_output, temp_dir):
    """Securely execute Java code"""
    javac_path = find_compiler('javac')
    java_path = find_compiler('java')
    
    if not javac_path or not java_path:
        return {'verdict': 'CE', 'error': 'Java compiler/runtime not found'}
    
    filepath = os.path.join(temp_dir, 'Main.java')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)
    
    # Compile Java
    compile_cmd = [javac_path, filepath]
    
    try:
        compile_proc = subprocess.run(
            compile_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=temp_dir
        )
        
        if compile_proc.returncode != 0:
            return {'verdict': 'CE', 'error': compile_proc.stderr}
        
        # Run with security manager
        run_cmd = [
            java_path,
            '-Djava.security.manager',
            '-Djava.security.policy=all.policy',
            '-Xmx128m',
            '-cp', temp_dir,
            'Main'
        ]
        
        # Create restrictive security policy
        policy_content = """
grant {
    permission java.lang.RuntimePermission "exitVM";
    permission java.io.FilePermission "<<ALL FILES>>", "read";
};
"""
        policy_path = os.path.join(temp_dir, 'all.policy')
        with open(policy_path, 'w') as f:
            f.write(policy_content)
        
        return run_with_limits(run_cmd, input_data, expected_output, temp_dir)
    
    except subprocess.TimeoutExpired:
        return {'verdict': 'CE', 'error': 'Compilation timeout'}

def execute_javascript_secure(code, input_data, expected_output, temp_dir):
    """Securely execute JavaScript code"""
    node_path = find_compiler('node')
    if not node_path:
        return {'verdict': 'CE', 'error': 'Node.js not found'}
    
    # Create restricted JavaScript code
    restricted_code = f"""
// Disable dangerous globals
delete global.process;
delete global.require;
delete global.Buffer;
delete global.__dirname;
delete global.__filename;

// Set timeout
setTimeout(() => {{
    process.exit(1);
}}, {MAX_EXECUTION_TIME * 1000});

try {{
{code}
}} catch (e) {{
    console.error('Error:', e.message);
    process.exit(1);
}}
"""
    
    filepath = os.path.join(temp_dir, 'main.js')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(restricted_code)
    
    return run_with_limits([node_path, filepath], input_data, expected_output, temp_dir)

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

def secure_evaluate_submission(language, code, problem):
    """
    Securely evaluate a submission against test cases
    """
    try:
        test_cases = json.loads(problem.test_cases_json or "[]")
    except json.JSONDecodeError:
        return {'verdict': 'IE', 'error': 'Invalid test case format', 'score': 0}

    if not test_cases:
        return {'verdict': 'IE', 'error': 'No test cases found', 'score': 0}

    all_passed = True
    total_cases = len(test_cases)
    passed_cases = 0
    last_output = ''
    last_error = ''

    for i, case in enumerate(test_cases, start=1):
        input_data = case.get("input", "")
        expected_output = case.get("output", "")
        result = secure_execute_code(language, code, input_data, expected_output)

        if result['verdict'] != 'AC':
            all_passed = False
            last_error = result.get('error', '')
            last_output = result.get('output', '')
        else:
            passed_cases += 1

    if all_passed:
        return {'verdict': 'AC', 'score': 100, 'output': last_output}
    else:
        partial_score = int((passed_cases / total_cases) * 100)
        return {
            'verdict': 'WA',
            'score': partial_score,
            'output': last_output,
            'error': last_error
        }