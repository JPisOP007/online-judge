"""Diagnose why a language fails to execute on this host.

Runs a hello-world through the real pipeline for every supported language and,
for any that fail, re-runs them with the resource limits progressively relaxed
so we can tell a missing toolchain apart from an rlimit that the runtime cannot
start under.

    python manage.py judge_doctor
"""
import os
import platform
import shutil
import subprocess

from django.core.management.base import BaseCommand

from core.utils import secure_execution as se

HELLO = {
    'python': ('print(input()[::-1])', 'hello', 'olleh'),
    'cpp': (
        '#include <bits/stdc++.h>\n'
        'using namespace std;\n'
        'int main(){ string s; getline(cin, s); reverse(s.begin(), s.end()); cout << s << "\\n"; }',
        'hello', 'olleh',
    ),
    'java': (
        'import java.util.*;\n'
        'public class Main {\n'
        '    public static void main(String[] a) {\n'
        '        Scanner sc = new Scanner(System.in);\n'
        '        System.out.println(new StringBuilder(sc.nextLine()).reverse().toString());\n'
        '    }\n'
        '}',
        'hello', 'olleh',
    ),
    'javascript': ('console.log(readline().split("").reverse().join(""));', 'hello', 'olleh'),
}


class Command(BaseCommand):
    help = 'Diagnose per-language execution failures.'

    def handle(self, *args, **options):
        self._environment()
        self._toolchains()
        self._raw_startup()
        self._pipeline()

    def _hr(self, title):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'== {title} '.ljust(72, '=')))

    def _environment(self):
        self._hr('environment')
        self.stdout.write(f'platform          : {platform.platform()}')
        self.stdout.write(f'IS_WINDOWS        : {se.IS_WINDOWS}')
        self.stdout.write(f'HAS_RESOURCE      : {se.HAS_RESOURCE}')
        self.stdout.write(f'RENDER env var    : {os.environ.get("RENDER")!r}')
        self.stdout.write(f'nsjail on PATH    : {shutil.which("nsjail")!r}')
        self.stdout.write(f'MAX_MEMORY_MB     : {se.MAX_MEMORY_MB}')
        self.stdout.write(f'MAX_EXECUTION_TIME: {se.MAX_EXECUTION_TIME}')
        self.stdout.write(f'/sandbox exists   : {os.path.exists("/sandbox")}')

        if se.HAS_RESOURCE:
            import resource
            for name in ['RLIMIT_AS', 'RLIMIT_CPU', 'RLIMIT_NPROC', 'RLIMIT_FSIZE']:
                soft, hard = resource.getrlimit(getattr(resource, name))
                self.stdout.write(f'  current {name:<13}: soft={soft} hard={hard}')

    def _toolchains(self):
        self._hr('toolchains')
        for name, version_flag in [
            ('g++', '--version'), ('javac', '-version'), ('java', '-version'),
            ('node', '--version'), ('nodejs', '--version'),
        ]:
            path = shutil.which(name)
            if not path:
                self.stdout.write(self.style.ERROR(f'{name:<8} NOT FOUND on PATH'))
                continue
            try:
                proc = subprocess.run([path, version_flag], capture_output=True, text=True, timeout=20)
                version = (proc.stdout or proc.stderr).strip().splitlines()
                version = version[0] if version else '?'
            except Exception as exc:
                version = f'error: {exc}'
            self.stdout.write(self.style.SUCCESS(f'{name:<8} {path}  ({version})'))

    def _raw_startup(self):
        """Start each runtime directly, outside the sandbox, then under the rlimits.

        This is the check that separates "not installed" from "installed but
        cannot start under RLIMIT_AS / RLIMIT_NPROC". The JVM and Node both
        reserve a large virtual address space and spawn threads at startup,
        and threads count against RLIMIT_NPROC on Linux.
        """
        self._hr('runtime startup, unrestricted vs sandboxed limits')

        probes = [
            ('java', ['java', '-version']),
            ('node', ['node', '-e', 'console.log(1)']),
        ]
        for label, argv in probes:
            binary = shutil.which(argv[0])
            if not binary:
                self.stdout.write(f'{label:<6} skipped, not installed')
                continue
            cmd = [binary] + argv[1:]

            bare = self._try(cmd, preexec=None)
            self.stdout.write(f'{label:<6} no limits      : {bare}')

            limited = self._try(cmd, preexec=se.make_resource_limiter(label))
            self.stdout.write(f'{label:<6} judge rlimits  : {limited}')

            old = self._try(cmd, preexec=self._limits(128, nproc=15))
            self.stdout.write(f'{label:<6} pre-fix limits : {old}')

            for mb in (512, 2048):
                self.stdout.write(f'{label:<6} RLIMIT_AS {mb}MB : {self._try(cmd, preexec=self._limits(mb))}')

            self.stdout.write(f'{label:<6} no RLIMIT_NPROC: {self._try(cmd, preexec=self._limits(None, nproc=None))}')

    def _limits(self, memory_mb, nproc=15):
        def apply():
            import resource
            if memory_mb:
                cap = memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
            resource.setrlimit(resource.RLIMIT_CPU, (se.MAX_EXECUTION_TIME, se.MAX_EXECUTION_TIME))
            if nproc:
                resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
        return apply

    def _try(self, cmd, preexec):
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=25,
                env={'PATH': os.environ.get('PATH', '/usr/bin:/bin')},
                preexec_fn=preexec,
            )
        except Exception as exc:
            return self.style.ERROR(f'EXCEPTION {exc}')

        if proc.returncode == 0:
            return self.style.SUCCESS('ok')
        detail = (proc.stderr or proc.stdout or '').strip().replace('\n', ' | ')[:160]
        return self.style.ERROR(f'exit {proc.returncode}: {detail}')

    def _pipeline(self):
        self._hr('full pipeline (validation + execution)')
        for language, (code, stdin, expected) in HELLO.items():
            valid, message = se.validate_code_security(code, language)
            if not valid:
                self.stdout.write(self.style.ERROR(f'{language:<11} REJECTED BY VALIDATOR: {message}'))
                continue

            result = se.secure_execute_code(language, code, stdin, expected)
            verdict = result.get('verdict')
            if verdict == 'AC':
                self.stdout.write(self.style.SUCCESS(f'{language:<11} AC'))
            else:
                self.stdout.write(self.style.ERROR(f'{language:<11} {verdict}'))
                self.stdout.write(f'            error : {str(result.get("error"))[:400]}')
                self.stdout.write(f'            output: {str(result.get("output"))[:200]}')
