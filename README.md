# 🚀 Online Judge Platform

A fully-featured, highly secure algorithmic coding platform (similar to LeetCode or HackerRank) built with Django, Docker, and a custom code-execution sandbox.

This platform allows users to solve programming challenges, participate in competitive programming contests, and receive immediate, secure evaluations of their code.

## ✨ Core Features

- **Multi-Language Code Execution:** Supports secure execution for Python, C++, Java, and Node.js.
- **Custom Sandbox Architecture:** Safely executes untrusted user-submitted code in an isolated environment.
- **Competitive Programming Contests:** Support for rated/unrated contests, leaderboards, and time-bound challenges.
- **AI Code Review:** Integrated AI-driven code review and feedback system for users.
- **Role-Based Access Control:** Separate dashboards and permissions for Admins, Problem Setters, and Participants.
- **Scalable Infrastructure:** Dockerized environment using Nginx for routing, WhiteNoise for static file serving, and Cloudinary for media storage.

## 🛡️ Security Architecture & Threat Model

Executing untrusted user code in a production environment is inherently dangerous. This application implements strict, multi-layered security measures to run submissions safely:

### What is Protected
- **AST-Based Static Analysis (Python):** Python submissions are parsed using the `ast` module to statically analyze and block malicious imports (e.g., `os`, `subprocess`) and built-in functions before execution. A runtime `__import__` hook and a restricted `sys` proxy enforce the same whitelist during execution.
- **Per-Language Static Analysis (C++ / Java / JavaScript):** These languages have no equivalent runtime hook, so submissions are matched against per-language denylists covering process creation, file I/O, raw file descriptors, sockets, reflection, inline assembly and environment access. Matching is done on word boundaries against source with comments and string literals removed, so a payload cannot hide in a comment and ordinary output strings do not trigger false positives.
- **Isolation-Gated Languages:** JavaScript is only offered where OS-level isolation is available behind the denylist. On PaaS deployments without it, JavaScript submissions are refused rather than run. In-process shadowing of `require`/`process` is not a containment boundary — the Function constructor reaches global scope without naming `Function` — so where JavaScript does run, Node is launched with `--disallow-code-generation-from-strings` to refuse that class of escape at the engine level.
- **Environment Scrubbing (Secrets Protection):** Untrusted code is executed with a minimal environment — only `PATH` is passed through — so application secrets such as database credentials and API keys are not inherited by the subprocess. Note the limit of this control: where the sandbox runs as the same OS user as the application (see exclusions below), a process that escapes the language-level checks can still read the parent's environment via `/proc/<pid>/environ`. Scrubbing raises the bar; it is not a boundary.
- **Resource Exhaustion (Defense-in-Depth):**
  - **Process Limits:** Subprocesses are wrapped with Python's `resource.setrlimit` to cap maximum memory address space (`RLIMIT_AS`) and maximum child processes (`RLIMIT_NPROC`).
  - **Time Limits:** Strict CPU time limits to prevent infinite loop DoS attacks.
  - **OS-Level Limits:** Hardcoded PAM limits (`/etc/security/limits.conf`) in the Dockerfile prevent excessive file descriptor or process consumption.
- **Shell Injection Prevention:** User code is strictly written to a temporary file in the sandbox and executed via strict argument lists (`subprocess.run(..., shell=False)`). No code is ever interpolated into shell command strings.
- **File Upload Security:** Strict MIME-type validation (using `python-magic`) and image integrity checks (via `Pillow`) to prevent malicious file uploads.

### Known Threat Model Exclusions
- **Denylists Are Not Sandboxes:** For C++, Java and JavaScript the application-level control is static pattern matching, which is inherently incomplete — it rejects known-dangerous constructs rather than permitting only known-safe ones. It raises the cost of an attack and catches opportunistic attempts; it does not stop a determined attacker who finds a construct the list does not name. OS-level isolation is what actually contains untrusted code, which is why its absence on PaaS (below) matters.
- **Reduced Isolation on PaaS:** On Render, containers run unprivileged, so neither `nsjail` nor `sudo -u sandboxuser` is available and submissions execute as the application user with only `setrlimit` caps. The full isolation described above applies to the Docker deployment, not to that environment.
- **Filesystem Traversal:** The code executes as the primary application user within the container. A malicious program can read the unencrypted source code, but because all secrets are injected via environment variables (which are scrubbed at execution time), this yields no sensitive data.
- **Container Escapes (Kernel Exploits):** This sandbox relies on standard kernel boundaries within an unprivileged Docker container. It does *not* defend against kernel-level 0-day privilege escalation exploits (which would require microVMs like AWS Firecracker or strict `seccomp` profiles).
- **Network Access Restriction:** Without `CAP_NET_ADMIN` in our PaaS environment, we cannot create isolated network namespaces. Malicious code could theoretically make outbound network requests.
- **Side-Channel Attacks:** CPU-level side-channel attacks (e.g., Spectre, Meltdown) across shared hardware are not mitigated by this user-level sandbox.

## 🚀 Local Development & Deployment

The platform is designed to be easily deployable using Docker.

```bash
# Clone the repository
git clone https://github.com/JPisOP007/online-judge.git
cd online-judge

# Set up environment variables
cp .env.example .env
# Edit .env with your Cloudinary and Database credentials

# Build and run the containers
docker-compose up -d --build
```

For more detailed deployment instructions, please refer to the [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## 📚 Documentation

For a deeper dive into the architecture, API, and engineering decisions:
- [API Documentation](API_DOCUMENTATION.md)
- [Security Fixes & Architecture](SECURITY_FIXES.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)

---
*Built with Django & Docker.*
