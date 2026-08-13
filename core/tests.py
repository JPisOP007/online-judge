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

    def test_cpp_suspicious_patterns(self):
        suspicious = [
            'system("rm -rf /");',
            'std::system ("id");',           # space before paren defeated the old check
            'auto f = &system; f("id");',    # so did taking a function pointer
            '#include <fstream>\nstd::ifstream f("/etc/passwd");',
            '#include <unistd.h>\nexecl("/bin/sh", "sh", 0);',
            'getenv("DJANGO_SECRET_KEY");',
            'popen("id", "r");',
        ]
        for code in suspicious:
            is_valid, msg = validate_code_security(code, "cpp")
            self.assertFalse(is_valid, f"Failed to catch: {code}")
            self.assertIn("Security violations detected", msg)

    def test_java_suspicious_patterns(self):
        suspicious = [
            'Runtime.getRuntime().exec("ls");',
            'ProcessBuilder pb = new ProcessBuilder();',
            'Class.forName("java.lang.Runtime");',
            'new java.io.File("/").listFiles();',
            'System.getenv("MONGODB_URI");',
            'Files.readAllBytes(Paths.get("/etc/passwd"));',
        ]
        for code in suspicious:
            is_valid, msg = validate_code_security(code, "java")
            self.assertFalse(is_valid, f"Failed to catch: {code}")
            self.assertIn("Security violations detected", msg)

    def test_javascript_suspicious_patterns(self):
        """require() was not checked at all before, making Node a one-line escape."""
        suspicious = [
            "require('child_process').execSync('id')",
            "const cp = require ( 'child_process' );",
            "process.binding('spawn_sync')",
            "globalThis.process.mainModule.require('fs')",
            "eval('require(\"fs\")')",
            "new Function('return process')()",
        ]
        for code in suspicious:
            is_valid, msg = validate_code_security(code, "javascript")
            self.assertFalse(is_valid, f"Failed to catch: {code}")
            self.assertIn("Security violations detected", msg)

    def test_legitimate_solutions_are_not_flagged(self):
        """Guard against the denylists becoming so broad they reject real code."""
        legitimate = [
            ("cpp", "#include <bits/stdc++.h>\nusing namespace std;\n"
                    "int main(){int n;cin>>n;cout<<n*2<<endl;}"),
            # <cstdlib> is allowed: it is needed for abs()/atoi(). The dangerous
            # symbols it also declares are blocked by name instead.
            ("cpp", "#include <cstdlib>\nint main(){ int x = abs(-5); printf(\"%d\", x); }"),
            ("cpp", '#include <iostream>\nint main(){ std::cout << "call system(x)"; }'),
            ("cpp", "// a comment mentioning system( and fork(\n"
                    "#include <iostream>\nint main(){std::cout<<1;}"),
            ("java", "import java.util.*;\npublic class Main{public static void main(String[] a){"
                     "Scanner s=new Scanner(System.in);System.out.println(s.nextInt()*2);}}"),
            # The deep-recursion idiom: a big-stack Thread must keep working.
            ("java", "public class Main{public static void main(String[] a){"
                     "new Thread(null, () -> System.out.println(1), \"m\", 1<<26).start();}}"),
            ("javascript", "const n = parseInt(readline()); console.log(n*2);"),
        ]
        for language, code in legitimate:
            is_valid, msg = validate_code_security(code, language)
            self.assertTrue(is_valid, f"False positive on {language}: {msg}")

    def test_known_sandbox_escapes_stay_closed(self):
        """Payloads that were confirmed to bypass an earlier version of the
        denylists. The JavaScript one reached the real `process` object at
        runtime inside the harness, which is arbitrary code execution."""
        escapes = [
            ('javascript', 'const g=(()=>{}).constructor("return this")(); console.log(g);'),
            ('javascript', 'const g=(()=>{}).constructor("return this")(); console.log(g["pro"+"cess"]);'),
            ('javascript', 'console.log(Reflect.ownKeys(globalThis));'),
            ('java', 'public class Main{public static void main(String[] a){'
                     'System.out.println(System.getProperty("user.home"));}}'),
            ('java', 'public class Main{public static void main(String[] a){'
                     'System.out.println(new Main().getClass().getProtectionDomain());}}'),
            ('java', 'import java.io.*;\nimport java.util.*;\npublic class Main{'
                     'public static void main(String[] a)throws Exception{'
                     'Scanner s=new Scanner(new File("/etc/passwd"));}}'),
            ('cpp', '#include <fcntl.h>\nint main(){ int fd=open("/etc/passwd",0); return fd; }'),
            ('cpp', '#include <sys/mman.h>\nint main(){ mmap(0,0,0,0,0,0); }'),
        ]
        for language, code in escapes:
            is_valid, msg = validate_code_security(code, language)
            self.assertFalse(is_valid, f"Escape no longer caught ({language}): {code[:60]}")

    def test_javascript_requires_os_isolation(self):
        """JavaScript is refused where nothing contains it but the denylist."""
        from .utils.secure_execution import language_is_available, get_isolation_level
        if get_isolation_level() == 'none':
            self.assertFalse(language_is_available('javascript'))
            result = secure_execute_code('javascript', 'console.log(1);', '', '')
            self.assertEqual(result.get('verdict'), 'CE')
            self.assertIn('unavailable', result.get('error', ''))
        else:
            self.assertTrue(language_is_available('javascript'))
        # The other three are never gated on isolation.
        for language in ('python', 'cpp', 'java'):
            self.assertTrue(language_is_available(language))

    def test_comments_and_strings_are_stripped(self):
        from .utils.secure_execution import strip_comments_and_strings
        scrubbed = strip_comments_and_strings('int x; // system(1)\n/* fork() */ char* s = "popen";')
        self.assertNotIn('system', scrubbed)
        self.assertNotIn('fork', scrubbed)
        self.assertNotIn('popen', scrubbed)
        self.assertIn('int x;', scrubbed)


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
