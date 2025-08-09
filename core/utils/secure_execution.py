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

# Blacklisted patterns for code injection prevention
DANGEROUS_PATTERNS = [
    r'import\s+os',
    r'import\s+subprocess',
    r'import\s+sys',
    r'import\s+socket',
    r'import\s+urllib',
    r'import\s+requests',
    r'import\s+shutil',
    r'import\s+tempfile',
    r'from\s+os\s+import',
    r'from\s+subprocess\s+import',
    r'from\s+sys\s+import',
    r'from\s+socket\s+import',
    r'__import__',
    r'eval\s*\(',
    r'exec\s*\(',
    r'compile\s*\(',
    r'open\s*\(',
    r'file\s*\(',
    r'input\s*\(',
    r'raw_input\s*\(',
    r'System\.exit',
    r'System\.getProperty',
    r'Runtime\.getRuntime',
    r'ProcessBuilder',
    r'Class\.forName',
    r'#include\s*<\s*stdlib\.h\s*>',
    r'#include\s*<\s*unistd\.h\s*>',
    r'system\s*\(',
    r'popen\s*\(',
    r'fork\s*\(',
    r'require\s*\(\s*[\'"]fs[\'"]',
    r'require\s*\(\s*[\'"]child_process[\'"]',
    r'require\s*\(\s*[\'"]os[\'"]',
    r'require\s*\(\s*[\'"]path[\'"]',
    r'process\.exit',
    r'process\.env',
    r'global\.',
    r'Buffer\.',
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

def validate_code_security(code, language):
    """
    Validate code for security vulnerabilities
    """
    if not code or not language:
        return False, "Empty code or language"
    
    if language not in ALLOWED_LANGUAGES:
        return False, f"Language {language} not allowed"
    
    # Check for dangerous patterns
    patterns_to_check = DANGEROUS_PATTERNS.copy()
    
    if language == 'java':
        patterns_to_check.extend(JAVA_DANGEROUS_PATTERNS)
    elif language == 'cpp':
        patterns_to_check.extend(CPP_DANGEROUS_PATTERNS)
    
    for pattern in patterns_to_check:
        if re.search(pattern, code, re.IGNORECASE):
            return False, f"Potentially dangerous code detected: {pattern}"
    
    # Check code length
    if len(code) > MAX_FILE_SIZE:
        return False, "Code too long"
    
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

def execute_python_secure(code, input_data, expected_output, temp_dir):
    """Securely execute Python code"""
    python_path = find_compiler('python3')
    if not python_path:
        return {'verdict': 'CE', 'error': 'Python interpreter not found'}
    
    # Create restricted Python code with proper indentation
    indented_code = '\n'.join('    ' + line for line in code.split('\n'))
    
    restricted_code = f"""import sys

# Disable dangerous builtins
import builtins
original_import = builtins.__import__

def restricted_import(name, *args, **kwargs):
    forbidden_modules = {{
        'os', 'subprocess', 'sys', 'socket', 'urllib', 'requests',
        'shutil', 'tempfile', 'importlib', 'pkgutil', 'imp'
    }}
    if name in forbidden_modules:
        raise ImportError(f"Module '{{name}}' is not allowed")
    return original_import(name, *args, **kwargs)

builtins.__import__ = restricted_import
builtins.open = None
builtins.input = None
builtins.eval = None
builtins.exec = None
builtins.compile = None

try:
{indented_code}
except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
    
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

def run_with_limits(cmd, input_data, expected_output, temp_dir):
    """Run command with resource limits and security restrictions"""
    try:
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
            out, err = process.communicate(
                input=input_data,
                timeout=MAX_EXECUTION_TIME
            )
            
            # Check output size
            if len(out) > MAX_OUTPUT_SIZE:
                return {'verdict': 'RE', 'error': 'Output too large'}
            
            if process.returncode != 0 or err.strip():
                error_msg = err.strip() or f"Process exited with code {process.returncode}"
                return {'verdict': 'RE', 'error': error_msg, 'output': out.strip()}
            
            # Normalize output for comparison
            actual_output = out.strip().replace('\r\n', '\n').replace('\r', '\n')
            expected_clean = expected_output.strip().replace('\r\n', '\n').replace('\r', '\n')
            
            if actual_output == expected_clean:
                return {'verdict': 'AC', 'output': actual_output}
            else:
                return {
                    'verdict': 'WA',
                    'output': actual_output,
                    'error': f"Expected: '{expected_clean}'\nGot: '{actual_output}'"
                }
        
        except subprocess.TimeoutExpired:
            process.kill()
            return {'verdict': 'TLE', 'error': f'Time Limit Exceeded ({MAX_EXECUTION_TIME} seconds)'}
    
    except Exception as e:
        return {'verdict': 'RE', 'error': f'Execution error: {str(e)}'}

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