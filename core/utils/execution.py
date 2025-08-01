import subprocess
import tempfile
import os
import shutil
import json
import re
import resource
import pwd
import grp
from pathlib import Path

class SecurityError(Exception):
    """Custom exception for security violations"""
    pass

class SecureCodeExecutor:
    def __init__(self):
        # Security configurations
        self.MAX_FILE_SIZE = 50 * 1024  # 50KB max file size
        self.MAX_OUTPUT_SIZE = 10 * 1024  # 10KB max output
        self.EXECUTION_TIMEOUT = 5  # 5 seconds max execution time
        self.MAX_MEMORY_MB = 128  # 128MB memory limit
        
        # Allowed languages and their configurations
        self.LANGUAGE_CONFIG = {
            'python': {
                'extension': '.py',
                'compile_cmd': None,
                'run_cmd': ['python3', '-u'],  # -u for unbuffered output
                'compiler_name': 'python3'
            },
            'cpp': {
                'extension': '.cpp',
                'compile_cmd': ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra'],
                'run_cmd': None,  # Will be set to executable path
                'compiler_name': 'g++'
            },
            'java': {
                'extension': '.java',
                'compile_cmd': ['javac'],
                'run_cmd': ['java', '-Xmx128m'],  # Limit heap to 128MB
                'compiler_name': 'javac'
            },
            'javascript': {
                'extension': '.js',
                'compile_cmd': None,
                'run_cmd': ['node', '--max-old-space-size=128'],  # Limit memory
                'compiler_name': 'node'
            }
        }
        
        # Dangerous patterns that should be blocked
        self.DANGEROUS_PATTERNS = {
            'python': [
                r'import\s+os',
                r'import\s+subprocess',
                r'import\s+sys',
                r'import\s+socket',
                r'import\s+urllib',
                r'import\s+requests',
                r'import\s+ctypes',
                r'import\s+multiprocessing',
                r'import\s+threading',
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
                r'input\s*\(',  # Prevent interactive input
                r'raw_input\s*\(',
            ],
            'cpp': [
                r'#include\s*<fstream>',
                r'#include\s*<filesystem>',
                r'#include\s*<cstdlib>',
                r'system\s*\(',
                r'popen\s*\(',
                r'fork\s*\(',
                r'exec[lv]',
                r'asm\s*\(',
                r'__asm__',
            ],
            'java': [
                r'import\s+java\.io\.',
                r'import\s+java\.nio\.',
                r'import\s+java\.net\.',
                r'import\s+java\.lang\.Runtime',
                r'import\s+java\.lang\.ProcessBuilder',
                r'Runtime\.getRuntime',
                r'ProcessBuilder',
                r'System\.exit',
                r'Thread\.',
                r'Runnable',
            ],
            'javascript': [
                r'require\s*\(',
                r'import\s+.*from',
                r'process\.',
                r'fs\.',
                r'child_process',
                r'eval\s*\(',
                r'Function\s*\(',
                r'setTimeout',
                r'setInterval',
                r'XMLHttpRequest',
                r'fetch\s*\(',
            ]
        }

    def find_compiler(self, compiler_name):
        """Safely find compiler path"""
        try:
            path = shutil.which(compiler_name)
            if path and os.access(path, os.X_OK):
                return path
        except Exception:
            pass
        return None

    def validate_code_security(self, language, code):
        """Check code for dangerous patterns"""
        if len(code) > self.MAX_FILE_SIZE:
            raise SecurityError(f"Code exceeds maximum size limit ({self.MAX_FILE_SIZE} bytes)")
        
        if language not in self.DANGEROUS_PATTERNS:
            return  # No patterns defined for this language
        
        patterns = self.DANGEROUS_PATTERNS[language]
        
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                raise SecurityError(f"Code contains prohibited pattern: {pattern}")
        
        # Additional checks
        if len(code.splitlines()) > 1000:
            raise SecurityError("Code has too many lines (max 1000)")
        
        # Check for suspicious long strings that might contain encoded malicious code
        for line in code.splitlines():
            if len(line) > 1000:
                raise SecurityError("Code contains suspiciously long line")

    def set_resource_limits(self):
        """Set resource limits for the subprocess"""
        try:
            # Set memory limit (in bytes)
            resource.setrlimit(resource.RLIMIT_AS, (self.MAX_MEMORY_MB * 1024 * 1024, 
                                                   self.MAX_MEMORY_MB * 1024 * 1024))
            
            # Set CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.EXECUTION_TIMEOUT, 
                                                    self.EXECUTION_TIMEOUT))
            
            # Limit number of processes
            resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
            
            # Disable core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except Exception as e:
            print(f"[WARNING] Could not set resource limits: {e}")

    def create_secure_environment(self):
        """Create a secure execution environment"""
        env = os.environ.copy()
        
        # Remove potentially dangerous environment variables
        dangerous_env_vars = [
            'LD_PRELOAD', 'LD_LIBRARY_PATH', 'PYTHONPATH', 
            'PATH', 'HOME', 'USER', 'SHELL'
        ]
        
        for var in dangerous_env_vars:
            env.pop(var, None)
        
        # Set minimal safe environment
        env['PATH'] = '/usr/bin:/bin'
        env['HOME'] = '/tmp'
        env['USER'] = 'nobody'
        
        return env

    def execute_code(self, language, code, input_data, expected_output):
        """Execute code securely"""
        try:
            # Validate language
            if language not in self.LANGUAGE_CONFIG:
                return {'verdict': 'CE', 'error': f'Unsupported language: {language}'}
            
            config = self.LANGUAGE_CONFIG[language]
            
            # Security validation
            self.validate_code_security(language, code)
            
            # Check if required compiler/interpreter exists
            compiler_path = self.find_compiler(config['compiler_name'])
            if not compiler_path:
                return {'verdict': 'CE', 'error': f'{config["compiler_name"]} not found'}
            
            # Validate input data size
            if len(input_data) > self.MAX_OUTPUT_SIZE:
                return {'verdict': 'IE', 'error': 'Input data too large'}

            with tempfile.TemporaryDirectory() as temp_dir:
                # Create secure temporary directory
                os.chmod(temp_dir, 0o700)
                
                # Write code to file
                if language == 'java':
                    filename = 'Main.java'
                else:
                    filename = f'main{config["extension"]}'
                
                filepath = os.path.join(temp_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                os.chmod(filepath, 0o600)  # Read-write for owner only
                
                # Compilation step (if needed)
                if config['compile_cmd']:
                    if language == 'cpp':
                        exe_path = os.path.join(temp_dir, 'main.out')
                        compile_cmd = config['compile_cmd'] + [filepath, '-o', exe_path]
                        run_cmd = [exe_path]
                    elif language == 'java':
                        compile_cmd = config['compile_cmd'] + [filepath]
                        run_cmd = config['run_cmd'] + ['-cp', temp_dir, 'Main']
                    
                    # Compile with security measures
                    try:
                        compile_proc = subprocess.run(
                            compile_cmd,
                            cwd=temp_dir,
                            capture_output=True,
                            text=True,
                            timeout=10,
                            env=self.create_secure_environment(),
                            preexec_fn=self.set_resource_limits
                        )
                        
                        if compile_proc.returncode != 0:
                            error_msg = compile_proc.stderr[:1000]  # Limit error message size
                            return {'verdict': 'CE', 'error': f'Compilation failed: {error_msg}'}
                    
                    except subprocess.TimeoutExpired:
                        return {'verdict': 'CE', 'error': 'Compilation timeout'}
                    
                    if language == 'cpp':
                        os.chmod(exe_path, 0o700)  # Executable for owner only
                else:
                    # Interpreted language
                    run_cmd = config['run_cmd'] + [filepath]
                
                # Execute the code
                try:
                    process = subprocess.Popen(
                        run_cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=temp_dir,
                        env=self.create_secure_environment(),
                        preexec_fn=self.set_resource_limits
                    )
                    
                    # Communicate with timeout and size limits
                    try:
                        out, err = process.communicate(
                            input=input_data, 
                            timeout=self.EXECUTION_TIMEOUT
                        )
                        
                        # Limit output size
                        if len(out) > self.MAX_OUTPUT_SIZE:
                            out = out[:self.MAX_OUTPUT_SIZE] + "\n[Output truncated]"
                        
                        if len(err) > self.MAX_OUTPUT_SIZE:
                            err = err[:self.MAX_OUTPUT_SIZE] + "\n[Error truncated]"
                        
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        return {'verdict': 'TLE', 'error': 'Time Limit Exceeded'}
                
                except Exception as e:
                    return {'verdict': 'RE', 'error': f'Execution failed: {str(e)[:500]}'}
                
                # Check for runtime errors
                if process.returncode != 0:
                    error_msg = err.strip()[:1000] if err.strip() else f"Process exited with code {process.returncode}"
                    return {'verdict': 'RE', 'error': error_msg, 'output': out.strip()[:1000]}
                
                # If there's stderr output but return code is 0, it might be warnings
                if err.strip():
                    print(f"[DEBUG] Warning/Info from stderr: {err.strip()}")
                
                # Normalize and compare output
                actual_output = out.strip().replace('\r\n', '\n').replace('\r', '\n')
                expected_clean = expected_output.strip().replace('\r\n', '\n').replace('\r', '\n')
                
                if actual_output == expected_clean:
                    return {'verdict': 'AC', 'output': actual_output}
                else:
                    return {
                        'verdict': 'WA',
                        'output': actual_output,
                        'error': f"Expected: '{expected_clean[:500]}'\nGot: '{actual_output[:500]}'"
                    }
        
        except SecurityError as e:
            return {'verdict': 'SE', 'error': f'Security violation: {str(e)}'}
        
        except Exception as e:
            return {'verdict': 'IE', 'error': f'Internal error: {str(e)[:500]}'}

    def evaluate_submission(self, language, code, problem):
        """Evaluate a submission against test cases"""
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
            
            result = self.execute_code(language, code, input_data, expected_output)

            print(f"[DEBUG] Test case {i}: Verdict: {result['verdict']}")

            if result['verdict'] == 'SE':  # Security error - fail immediately
                return result
            
            if result['verdict'] != 'AC':
                all_passed = False
                last_error = result.get('error', '')
                last_output = result.get('output', '')
                
                # Stop on first compilation error or security violation
                if result['verdict'] in ['CE', 'SE', 'IE']:
                    return result
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


# Usage example and testing
if __name__ == "__main__":
    executor = SecureCodeExecutor()
    
    print("Checking available compilers/interpreters:")
    for lang, config in executor.LANGUAGE_CONFIG.items():
        compiler_name = config['compiler_name']
        path = executor.find_compiler(compiler_name)
        if path:
            print(f"✓ {compiler_name}: {path}")
        else:
            print(f"✗ {compiler_name}: Not found")
    
    # Test with safe code
    print("\n--- Testing safe code ---")
    safe_python_code = """
n = int(input())
print(n * 2)
"""
    
    result = executor.execute_code('python', safe_python_code, '5', '10')
    print(f"Safe code result: {result}")
    
    # Test with malicious code
    print("\n--- Testing malicious code ---")
    malicious_code = """
import os
os.system('ls -la /')
"""
    
    result = executor.execute_code('python', malicious_code, '', '')
    print(f"Malicious code result: {result}")