"""
Simple but effective secure code execution module
Focus on core functionality with minimal complexity
"""
import subprocess
import tempfile
import os
import shutil
import time
import ast
from django.conf import settings

# Platform detection
import platform
IS_WINDOWS = platform.system() == 'Windows'

if not IS_WINDOWS:
    try:
        import resource
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
    'itertools': ['*'],  # All itertools functions are generally safe
    'math': ['*'],  # Math is generally safe
    'heapq': ['*'],  # Essential for algorithms
    'bisect': ['*'],  # Binary search utilities
    're': ['compile', 'match', 'search', 'findall', 'finditer', 'sub', 'subn', 'split', 'escape'],
    'functools': ['lru_cache', 'reduce', 'partial', 'wraps', 'singledispatch',
                  'cache', 'cmp_to_key', 'total_ordering'],
    'operator': ['*'],  # Safe operator functions
    'string': ['*'],  # String constants and utilities
    'random': ['randint', 'choice', 'shuffle', 'sample', 'random', 'uniform', 'seed',
               'randrange', 'choices', 'gauss'],
    'decimal': ['*'],  # For precise decimal arithmetic
    'fractions': ['*'],  # For rational number arithmetic
    'copy': ['copy', 'deepcopy'],  # Safe copying utilities
    'typing': ['*'],  # Type hints (safe)
    'dataclasses': ['dataclass', 'field', 'fields', 'asdict', 'astuple'],
    'enum': ['*'],  # Enumerations
    'datetime': ['datetime', 'date', 'time', 'timedelta', 'timezone'],
    'json': ['loads', 'dumps'],  # Safe JSON operations
    'keyword': ['*'],  # Python keywords (safe, used internally by collections)
    'reprlib': ['*'],  # Representation library (safe, used internally by collections)
    # Competitive programming essentials
    'sys': ['stdin', 'stdout', 'stderr', 'setrecursionlimit', 'maxsize', 'version_info'],
    'io': ['StringIO', 'BytesIO'],
    'queue': ['Queue', 'PriorityQueue', 'LifoQueue', 'SimpleQueue'],
    'statistics': ['*'],
    'cmath': ['*'],
    'abc': ['ABC', 'abstractmethod'],
    'array': ['array'],
    'struct': ['pack', 'unpack', 'calcsize'],
    'pprint': ['pprint', 'pformat'],
    'textwrap': ['*'],
    'collections.abc': ['*'],
    'numbers': ['*'],
}

# Absolutely forbidden modules
ABSOLUTELY_FORBIDDEN = [
    'os', 'subprocess', 'socket', 'urllib', 'urllib2', 'urllib3', 'requests',
    'shutil', 'tempfile', 'importlib', 'pickle', 'dill', 'marshal', 'shelve',
    'dbm', 'sqlite3', 'mysql', 'psycopg2', 'pymongo',
    'ftplib', 'smtplib', 'poplib', 'imaplib', 'nntplib',
    'threading', 'multiprocessing', 'concurrent', 'asyncio',
    'ctypes', 'cffi', 'cython',
    'webbrowser', 'tkinter', 'turtle',
    '__builtin__', '__builtins__',
    'code', 'codeop',
]

# Modules that are allowed but with restrictions
RESTRICTED_MODULES = {
    'builtins': ['*'],  # Allow all builtins access (we control the dangerous ones in our wrapper)
}

# Forbidden function calls
FORBIDDEN_FUNCTIONS = [
    'eval', 'exec', 'compile', '__import__',
    'open', 'file', 'raw_input',
    'getattr', 'setattr', 'delattr',        # reflection — blocks scripted class-hierarchy walks
    'vars', 'dir', 'globals', 'locals',      # introspection
    'breakpoint',                             # debugger
    'exit', 'quit', 'help', 'copyright', 'credits', 'license',
]

def analyze_python_code_security(code):
    """Use AST to detect dangerous operations"""
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
                        self.violations.append(f"Import not in whitelist: {alias.name}")
                self.generic_visit(node)
            
            def visit_ImportFrom(self, node):
                if node.module in ABSOLUTELY_FORBIDDEN:
                    self.violations.append(f"Forbidden import from: {node.module}")
                elif node.module and node.module not in ALLOWED_IMPORTS:
                    self.violations.append(f"Import from module not in whitelist: {node.module}")
                elif node.module in ALLOWED_IMPORTS:
                    allowed_items = ALLOWED_IMPORTS[node.module]
                    if allowed_items != ['*']:
                        for alias in node.names:
                            if alias.name != '*' and alias.name not in allowed_items:
                                self.violations.append(f"Function '{alias.name}' not allowed from module '{node.module}'")
                self.generic_visit(node)
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    if node.func.id in FORBIDDEN_FUNCTIONS:
                        if node.func.id != 'input':  # input() is allowed
                            self.violations.append(f"Forbidden function: {node.func.id}")
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['system', 'popen', 'exec', 'eval']:
                        self.violations.append(f"Forbidden method call: {node.func.attr}")
                    # Detect format-string dunder exploits: "{0.__class__}".format(...)
                    if node.func.attr == 'format':
                        if isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str):
                            fmt_str = node.func.value.value
                            if '__' in fmt_str:
                                self.violations.append(f"Format string contains dunder access")
                self.generic_visit(node)
            
            def visit_Attribute(self, node):
                if node.attr.startswith('__') and node.attr.endswith('__'):
                    self.violations.append(f"Access to dunder attributes is not allowed: {node.attr}")
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
    """Validate code for security vulnerabilities"""
    if not code or not language:
        return False, "Empty code or language"
    
    if language not in ALLOWED_LANGUAGES:
        return False, f"Language {language} not allowed"
    
    if len(code) > MAX_FILE_SIZE:
        return False, "Code too long"
    
    if language == 'python':
        is_safe, violations = analyze_python_code_security(code)
        if not is_safe:
            return False, "Security violations detected: " + "; ".join(violations)
    else:
        # Basic check for other languages
        suspicious_patterns = [
            'system(', 'popen(', 'exec(', 'ProcessBuilder', 'Runtime.getRuntime',
            'fork(', 'execvp(', 'execve(', 'syscall('
        ]
        code_lower = code.lower()
        for pattern in suspicious_patterns:
            if pattern.lower() in code_lower:
                return False, f"Suspicious pattern detected: {pattern}"
    
    return True, "Code validation passed"

def create_secure_temp_directory():
    """Create a secure temporary directory for execution"""
    # Use /sandbox if it exists (Docker environment), otherwise use system temp
    base_dir = '/sandbox' if os.path.exists('/sandbox') else None
    temp_dir = tempfile.mkdtemp(prefix='secure_exec_', dir=base_dir)
    # Give full permissions so sandboxuser can write to it
    os.chmod(temp_dir, 0o777)
    return temp_dir

def set_resource_limits():
    """Set resource limits (Unix only)"""
    if HAS_RESOURCE and not IS_WINDOWS:
        try:
            memory_limit = MAX_MEMORY_MB * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            resource.setrlimit(resource.RLIMIT_CPU, (MAX_EXECUTION_TIME, MAX_EXECUTION_TIME))
            resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_SIZE, MAX_FILE_SIZE))
            resource.setrlimit(resource.RLIMIT_NPROC, (15, 15))
        except (OSError, ValueError):
            pass

def find_compiler(compiler_name):
    """Find the full path of a compiler/interpreter"""
    if compiler_name in ['python', 'python3']:
        import sys
        return sys.executable
        
    path = shutil.which(compiler_name)
    if path:
        return path
    
    if IS_WINDOWS:
        return None
        
    common_paths = [
        f'/usr/bin/{compiler_name}',
        f'/bin/{compiler_name}',
        f'/usr/local/bin/{compiler_name}',
        f'/opt/bin/{compiler_name}'
    ]
    
    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    return None

def create_simple_secure_environment(code):
    """Create a simple secure Python environment"""
    
    # Convert dictionaries to strings for the restricted environment
    allowed_imports_str = str(ALLOWED_IMPORTS)  # Don't replace '*', keep it as is
    absolutely_forbidden_str = str(ABSOLUTELY_FORBIDDEN)
    restricted_modules_str = str(RESTRICTED_MODULES)
    
    # Indent the user code
    indented_code = '\n'.join('    ' + line for line in code.split('\n'))
    
    restricted_code = f"""import sys
import builtins
import types

# Store original import function
original_import = builtins.__import__

# Define security lists
ALLOWED_IMPORTS = {allowed_imports_str}
ABSOLUTELY_FORBIDDEN = {absolutely_forbidden_str}
RESTRICTED_MODULES = {restricted_modules_str}

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    # Allow internal Python modules
    if name and name.startswith('_'):
        return original_import(name, globals, locals, fromlist, level)
    
    # Check forbidden modules
    if name in ABSOLUTELY_FORBIDDEN:
        raise ImportError(f"Module '{{name}}' is not allowed for security reasons")
    
    # Handle restricted modules
    if name in RESTRICTED_MODULES:
        module = original_import(name, globals, locals, fromlist, level)
        if fromlist:
            allowed_items = RESTRICTED_MODULES[name]
            if allowed_items != ['*']:  # Only check if not allowing all
                for item in fromlist:
                    if item not in allowed_items:
                        raise ImportError(f"Attribute '{{item}}' from module '{{name}}' is not allowed")
        return module
    
    # Check whitelist
    if name not in ALLOWED_IMPORTS:
        raise ImportError(f"Module '{{name}}' is not in the allowed imports list")
    
    # Import the module
    module = original_import(name, globals, locals, fromlist, level)
    
    # Check specific imports (only if not '*')
    allowed_items = ALLOWED_IMPORTS[name]
    if allowed_items != ['*'] and fromlist:
        for item in fromlist:
            if item not in allowed_items:
                raise ImportError(f"Function '{{item}}' from module '{{name}}' is not allowed")
    
    return module

# Replace import function
builtins.__import__ = safe_import

# Cap sys.setrecursionlimit to prevent C-stack overflow
_orig_sys = sys
_orig_setrecursionlimit = _orig_sys.setrecursionlimit
def _safe_setrecursionlimit(n):
    if n > 1000000:
        n = 1000000
    _orig_setrecursionlimit(n)

# Create a safe sys proxy for user code
_user_sys = types.ModuleType('sys')
_SYS_ALLOWED = ['stdin', 'stdout', 'stderr', 'maxsize', 'version_info', 
                'version', 'platform', 'byteorder', 'exit', 'hexversion',
                'float_info', 'int_info', 'hash_info']
for attr in _SYS_ALLOWED:
    if hasattr(_orig_sys, attr):
        setattr(_user_sys, attr, getattr(_orig_sys, attr))
_user_sys.setrecursionlimit = _safe_setrecursionlimit

# Patch __import__ to enforce security ONLY for user script imports.
# Standard library modules (like collections) must be able to import their own internal dependencies.
def _user_aware_safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    is_user_script = globals is not None and globals.get('__name__') == '__main__'
    
    if not is_user_script:
        # Let internal standard library modules import whatever they need
        return original_import(name, globals, locals, fromlist, level)
        
    # For user script, enforce security checks
    module = safe_import(name, globals, locals, fromlist, level)
    
    # Return proxy for sys
    if name == 'sys':
        return _user_sys
        
    return module

builtins.__import__ = _user_aware_safe_import

# Execute user code
try:
{indented_code}
except Exception as e:
    print(f"Runtime Error: {{e}}", file=_orig_sys.stderr)
    _orig_sys.exit(1)
"""
    
    return restricted_code

def execute_python_secure(code, input_data, expected_output, temp_dir):
    """Securely execute Python code"""
    python_path = find_compiler('python3') or find_compiler('python')
    if not python_path:
        return {'verdict': 'CE', 'error': 'Python interpreter not found'}
    
    # Create secure environment
    restricted_code = create_simple_secure_environment(code)
    
    filepath = os.path.join(temp_dir, 'main.py')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(restricted_code)
    
    return run_with_limits([python_path, filepath], input_data, expected_output, temp_dir)

def execute_cpp_secure(code, input_data, expected_output, temp_dir):
    gpp_path = find_compiler('g++')
    if not gpp_path:
        return {'verdict': 'CE', 'error': 'g++ compiler not found'}
    
    filepath = os.path.join(temp_dir, 'main.cpp')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)
    
    exe_path = os.path.join(temp_dir, 'main.exe' if IS_WINDOWS else 'main.out')
    compile_cmd = [gpp_path, filepath, '-o', exe_path]
    
    try:
        compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=10)
        if compile_proc.returncode != 0:
            return {'verdict': 'CE', 'error': compile_proc.stderr or "Compilation failed"}
    except subprocess.TimeoutExpired:
        return {'verdict': 'CE', 'error': 'Compilation timed out'}
    
    return run_with_limits([exe_path], input_data, expected_output, temp_dir)

def execute_java_secure(code, input_data, expected_output, temp_dir):
    javac_path = find_compiler('javac')
    java_path = find_compiler('java')
    if not javac_path or not java_path:
        return {'verdict': 'CE', 'error': 'Java JDK not found'}
    
    filepath = os.path.join(temp_dir, 'Main.java')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)
    
    compile_cmd = [javac_path, filepath]
    
    try:
        compile_proc = subprocess.run(compile_cmd, cwd=temp_dir, capture_output=True, text=True, timeout=10)
        if compile_proc.returncode != 0:
            return {'verdict': 'CE', 'error': compile_proc.stderr or "Compilation failed"}
    except subprocess.TimeoutExpired:
        return {'verdict': 'CE', 'error': 'Compilation timed out'}
    
    return run_with_limits([java_path, '-cp', temp_dir, 'Main'], input_data, expected_output, temp_dir)

def execute_javascript_secure(code, input_data, expected_output, temp_dir):
    node_path = find_compiler('node') or find_compiler('nodejs')
    if not node_path:
        return {'verdict': 'CE', 'error': 'Node.js not found'}
    
    filepath = os.path.join(temp_dir, 'main.js')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)
    
    return run_with_limits([node_path, filepath], input_data, expected_output, temp_dir)

def build_execution_command(cmd, temp_dir):
    """Wrap command with appropriate isolation for the environment.
    
    Priority:
    1. nsjail (Docker with SYS_ADMIN capability) - true mount/PID/net namespace isolation
    2. sudo -u sandboxuser (Docker without nsjail) - user-level isolation
    3. bare command (Render / Windows) - no OS-level isolation
    """
    if IS_WINDOWS:
        return cmd
        
    # Render: bare execution (limited isolation — see security docs)
    # Render runs unprivileged containers where nsjail and sudo fail
    if os.environ.get('RENDER'):
        return cmd
    
    # Check if nsjail is available (Docker environment)
    nsjail_path = shutil.which('nsjail')
    if nsjail_path:
        return [
            nsjail_path, '--quiet', '--mode', 'o',
            '--time_limit', str(MAX_EXECUTION_TIME + 2),
            '--rlimit_as', str(MAX_MEMORY_MB),
            '--rlimit_cpu', str(MAX_EXECUTION_TIME),
            '--rlimit_fsize', '1',
            '--disable_clone_newnet',
            '--iface_no_lo',
            '--cwd', temp_dir,
            '--chroot', '/',
            '-m', 'none:/tmp:tmpfs:size=16777216',
            '-m', 'none:/etc:tmpfs:size=1048576',
            '-m', 'none:/var:tmpfs:size=1048576',
            '-m', 'none:/home:tmpfs:size=1048576',
            '-m', 'none:/root:tmpfs:size=1048576',
            '--bindmount_ro', '/usr:/usr',
            '--bindmount_ro', '/lib:/lib',
            '--bindmount_ro', '/lib64:/lib64',
            '--bindmount_ro', '/bin:/bin',
            '--bindmount_ro', '/sbin:/sbin',
            '--bindmount_ro', '/etc/alternatives:/etc/alternatives',
            '--bindmount', f'{temp_dir}:{temp_dir}',
            '--user', '65534',
            '--group', '65534',
            '--',
        ] + cmd
    
    # Fallback: sandboxuser isolation (Docker without nsjail)
    return ['sudo', '-n', '-u', 'sandboxuser'] + cmd


def run_with_limits(cmd, input_data, expected_output, temp_dir):
    """Run command with limits"""
    start_time = time.time()
    
    # Environment scrubbing: we explicitly pass a highly restricted environment
    # so the untrusted process does not inherit secrets (like MONGODB_URI)
    secure_env = {
        'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')
    }

    try:
        # Create subprocess
        if IS_WINDOWS:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=temp_dir,
                env=secure_env
            )
        else:
            exec_cmd = build_execution_command(cmd, temp_dir)
                
            process = subprocess.Popen(
                exec_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=temp_dir,
                env=secure_env,
                preexec_fn=set_resource_limits
            )
        
        # Normalize input
        normalized_input = input_data.replace('\r\n', '\n').replace('\r', '\n') if input_data else ''
        
        try:
            out, err = process.communicate(input=normalized_input, timeout=MAX_EXECUTION_TIME)
            execution_time = time.time() - start_time
            
            # Check output size
            if len(out) > MAX_OUTPUT_SIZE:
                return {'verdict': 'RE', 'error': 'Output too large'}
            
            # Check for errors
            # Filter out nsjail internal log lines
            clean_err_lines = [line for line in err.splitlines() if not line.startswith('[W]') and not line.startswith('[E]') and not line.startswith('[I]') and not line.startswith('[F]')]
            clean_err = '\n'.join(clean_err_lines).strip()
            
            if process.returncode != 0 or clean_err:
                error_msg = clean_err or f"Process exited with code {process.returncode}"
                return {'verdict': 'RE', 'error': error_msg, 'output': out.strip()}
            
            # Compare output
            actual_output = out.strip().replace('\r\n', '\n').replace('\r', '\n')
            expected_clean = expected_output.strip().replace('\r\n', '\n').replace('\r', '\n')
            
            if actual_output == expected_clean:
                return {
                    'verdict': 'AC', 
                    'output': actual_output,
                    'execution_time': execution_time
                }
            else:
                return {
                    'verdict': 'WA',
                    'output': actual_output,
                    'execution_time': execution_time
                }
        
        except subprocess.TimeoutExpired:
            process.kill()
            return {'verdict': 'TLE', 'error': f'Time Limit Exceeded ({MAX_EXECUTION_TIME} seconds)'}
    
    except Exception as e:
        return {'verdict': 'RE', 'error': f'Execution error: {str(e)}'}

def secure_execute_code(language, code, input_data, expected_output):
    """Main function to securely execute code"""
    try:
        # Validate security
        is_valid, message = validate_code_security(code, language)
        if not is_valid:
            return {'verdict': 'CE', 'error': f'Security violation: {message}'}
        
        # Create temp directory
        temp_dir = create_secure_temp_directory()
        
        try:
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
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    except Exception as e:
        return {'verdict': 'RE', 'error': f'Execution error: {str(e)}'}

def secure_evaluate_submission(language, code, problem):
    """Securely evaluate a submission against all test cases"""
    import json
    
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
    total_execution_time = 0

    for i, case in enumerate(test_cases, start=1):
        input_data = case.get("input", "")
        expected_output = case.get("output", "")
        result = secure_execute_code(language, code, input_data, expected_output)

        # Track execution time
        if 'execution_time' in result:
            total_execution_time += result['execution_time']

        if result['verdict'] != 'AC':
            all_passed = False
            last_error = result.get('error', '')
            last_output = result.get('output', '')
            # If it's a security violation or compilation error, fail immediately
            if result['verdict'] in ['CE', 'RE', 'TLE']:
                return {
                    'verdict': result['verdict'],
                    'score': 0,
                    'output': last_output,
                    'error': last_error,
                    'execution_time': total_execution_time
                }
        else:
            passed_cases += 1
            last_output = result.get('output', '')

    if all_passed:
        return {
            'verdict': 'AC', 
            'score': 100, 
            'output': last_output,
            'execution_time': total_execution_time
        }
    else:
        partial_score = int((passed_cases / total_cases) * 100)
        return {
            'verdict': 'WA',
            'score': partial_score,
            'output': last_output,
            'error': last_error,
            'execution_time': total_execution_time
        }