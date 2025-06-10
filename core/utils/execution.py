import subprocess
import tempfile
import os
import shutil
import json

def find_compiler(compiler_name):
    """Find the full path of a compiler/interpreter"""
    # Try using shutil.which first
    path = shutil.which(compiler_name)
    if path:
        return path
    
    # Common locations to check
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

def execute_code(language, code, input_data, expected_output):
    
    try:
        suffix_map = {
            'python': '.py',
            'cpp': '.cpp',
            'java': '.java',
            'javascript': '.js'  
        }

        if language not in suffix_map:
            print(f"[DEBUG] Unsupported language: {language}")
            return {'verdict': 'CE', 'error': f'Unsupported language: {language}'}

        suffix = suffix_map[language]

        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"[DEBUG] Created temp directory: {temp_dir}")
            
            filename = 'main' + suffix
            if language == 'java':
                # Java needs the class name to match filename
                filename = 'Main.java'
            
            filepath = os.path.join(temp_dir, filename)
            
            print(f"[DEBUG] Writing code to: {filepath}")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)

            # Prepare run command based on language
            if language == 'python':
                python_path = find_compiler('python3') or find_compiler('python')
                if not python_path:
                    return {'verdict': 'CE', 'error': 'Python interpreter not found'}
                run_cmd = [python_path, filepath]

            elif language == 'cpp':
                # Find g++ compiler
                gpp_path = find_compiler('g++')
                if not gpp_path:
                    return {'verdict': 'CE', 'error': 'g++ compiler not found. Please install: sudo apt install g++'}
                
                exe_path = os.path.join(temp_dir, 'main.exe' if os.name == 'nt' else 'main.out')
                compile_cmd = [gpp_path, filepath, '-o', exe_path]
                
                print(f"[DEBUG] Compiling C++ with: {gpp_path}")
                print(f"[DEBUG] Compile command: {' '.join(compile_cmd)}")
                
                compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=10)
                
                if compile_proc.returncode != 0:
                    error_msg = compile_proc.stderr or "Compilation failed"
                    print(f"[DEBUG] C++ compilation failed: {error_msg}")
                    return {'verdict': 'CE', 'error': error_msg}
                
                run_cmd = [exe_path]

            elif language == 'java':
                # Find javac and java
                javac_path = find_compiler('javac')
                java_path = find_compiler('java')
                
                if not javac_path:
                    return {'verdict': 'CE', 'error': 'javac compiler not found. Please install: sudo apt install default-jdk'}
                if not java_path:
                    return {'verdict': 'CE', 'error': 'java runtime not found. Please install: sudo apt install default-jdk'}
                
                # Compile Java
                compile_cmd = [javac_path, filepath]
                print(f"[DEBUG] Compiling Java with: {javac_path}")
                print(f"[DEBUG] Compile command: {' '.join(compile_cmd)}")
                
                compile_proc = subprocess.run(compile_cmd, cwd=temp_dir, capture_output=True, text=True, timeout=10)
                
                if compile_proc.returncode != 0:
                    error_msg = compile_proc.stderr or "Java compilation failed"
                    print(f"[DEBUG] Java compilation failed: {error_msg}")
                    return {'verdict': 'CE', 'error': error_msg}
                
                run_cmd = [java_path, '-cp', temp_dir, 'Main']

            elif language == 'javascript':
                node_path = find_compiler('node')
                if not node_path:
                    return {'verdict': 'CE', 'error': 'Node.js not found. Please install: sudo apt install nodejs'}
                run_cmd = [node_path, filepath]

            else:
                return {'verdict': 'CE', 'error': f'Execution not implemented for {language}'}

            print(f"[DEBUG] Running command: {' '.join(run_cmd)}")
            
            # Execute the code
            process = subprocess.Popen(
                run_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=temp_dir
            )

            try:
                out, err = process.communicate(input=input_data, timeout=5)
                print(f"[DEBUG] Process completed with return code: {process.returncode}")
                print(f"[DEBUG] stdout: '{out}'")
                print(f"[DEBUG] stderr: '{err}'")
                
            except subprocess.TimeoutExpired:
                print("[DEBUG] Process timed out")
                process.kill()
                return {'verdict': 'TLE', 'error': 'Time Limit Exceeded (5 seconds)'}

            # Check for runtime errors
            if process.returncode != 0 or err.strip():
                error_msg = err.strip() or f"Process exited with code {process.returncode}"
                print(f"[DEBUG] Runtime error: {error_msg}")
                return {'verdict': 'RE', 'error': error_msg, 'output': out.strip()}

            # Normalize output for comparison
            actual_output = out.strip().replace('\r\n', '\n').replace('\r', '\n')
            expected_clean = expected_output.strip().replace('\r\n', '\n').replace('\r', '\n')
            
            print(f"[DEBUG] Normalized actual output: '{actual_output}'")
            print(f"[DEBUG] Normalized expected output: '{expected_clean}'")

            # Compare outputs
            if actual_output == expected_clean:
                print("[DEBUG] Output matches - AC")
                return {'verdict': 'AC', 'output': actual_output}
            else:
                print("[DEBUG] Output doesn't match - WA")
                return {
                    'verdict': 'WA', 
                    'output': actual_output,
                    'error': f"Expected: '{expected_clean}'\nGot: '{actual_output}'"
                }

    except FileNotFoundError as e:
        error_msg = f"Required compiler/interpreter not found: {str(e)}"
        print(f"[DEBUG] FileNotFoundError: {error_msg}")
        return {'verdict': 'CE', 'error': error_msg}
    
    except Exception as e:
        error_msg = f"Execution error: {str(e)}"
        print(f"[DEBUG] Exception: {error_msg}")
        return {'verdict': 'RE', 'error': error_msg}


def evaluate_submission(language, code, problem):
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
        result = execute_code(language, code, input_data, expected_output)

        print(f"[DEBUG] Test case {i}: Verdict: {result['verdict']}")

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