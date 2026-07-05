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
- **AST-Based Static Analysis (Python):** Python submissions are parsed using the `ast` module to statically analyze and block malicious imports (e.g., `os`, `subprocess`) and built-in functions before execution.
- **Environment Scrubbing (Secrets Protection):** Untrusted code is executed in a highly sanitized environment. We explicitly wipe the entire OS environment variables before the subprocess runs, ensuring that application secrets (like database credentials or API Keys) cannot be leaked.
- **Resource Exhaustion (Defense-in-Depth):**
  - **Process Limits:** Subprocesses are wrapped with Python's `resource.setrlimit` to cap maximum memory address space (`RLIMIT_AS`) and maximum child processes (`RLIMIT_NPROC`).
  - **Time Limits:** Strict CPU time limits to prevent infinite loop DoS attacks.
  - **OS-Level Limits:** Hardcoded PAM limits (`/etc/security/limits.conf`) in the Dockerfile prevent excessive file descriptor or process consumption.
- **Shell Injection Prevention:** User code is strictly written to a temporary file in the sandbox and executed via strict argument lists (`subprocess.run(..., shell=False)`). No code is ever interpolated into shell command strings.
- **File Upload Security:** Strict MIME-type validation (using `python-magic`) and image integrity checks (via `Pillow`) to prevent malicious file uploads.

### Known Threat Model Exclusions
- **Filesystem Traversal:** The code executes as the primary application user within the container. A malicious program can read the unencrypted source code, but because all secrets are injected via environment variables (which are scrubbed at execution time), this yields no sensitive data.
- **Container Escapes (Kernel Exploits):** This sandbox relies on standard kernel boundaries within an unprivileged Docker container. It does *not* defend against kernel-level 0-day privilege escalation exploits (which would require microVMs like AWS Firecracker or strict `seccomp` profiles).
- **Network Access Restriction:** Without `CAP_NET_ADMIN` in our PaaS environment, we cannot create isolated network namespaces. Malicious code could theoretically make outbound network requests.
- **Side-Channel Attacks:** CPU-level side-channel attacks (e.g., Spectre, Meltdown) across shared hardware are not mitigated by this user-level sandbox.

## 🚀 Local Development & Deployment

The platform is designed to be easily deployable using Docker.

```bash
# Clone the repository
git clone https://github.com/yourusername/online-judge.git
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
- [System Design & Interview Q&A](INTERVIEW_QA.md)

---
*Built with Django & Docker.*
