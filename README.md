# Online Judge

A fully-featured, secure online judge platform built with Django, MongoDB, and Docker. 

## Features
- Code execution for Python, C++, Java, and Node.js.
- Cloudinary integration for scalable media storage.
- WhiteNoise for high-performance static file serving in production.
- Token-based JWT authentication and CORS for API integrations.

## Security Architecture & Threat Model

This application implements strict security measures to safely execute untrusted user code in a production Docker environment. 

### What is Protected
- **Environment Scrubbing (Secrets Protection)**: Untrusted code submitted by users is executed in a highly sanitized environment. Because Render's infrastructure prevents `sudo` (via the `no-new-privileges` flag), we execute the code as the standard application user, but explicitly wipe the entire OS environment (passing a highly restrictive dictionary like `env={'PATH': '/usr/bin:/bin'}`). The application's secrets (like MongoDB credentials, Cloudinary keys, and Django Secret Key) are injected by Render at runtime and DO NOT exist in any `.env` file on disk. Since the environment variables are wiped before execution, malicious code has no path to access these secrets.
- **Shell Injection Prevention**: The command array is executed using strict argument lists (e.g. `subprocess.run(..., shell=False)`). User-supplied code is strictly written to a temporary file in the sandbox directory and never interpolated into the shell command string, making shell injection impossible.
- **Resource Exhaustion (Fork Bombs & OOM)**: We implement defense-in-depth against Denial of Service attacks:
  - Subprocesses are wrapped with Python's `resource.setrlimit` inside `preexec_fn` to cap the maximum address space (`RLIMIT_AS`) and maximum child processes (`RLIMIT_NPROC=15`).
  - OS-level PAM limits (`/etc/security/limits.conf`) are hardcoded in the Dockerfile to prevent excessive file descriptor or process consumption across the entire container.

### What is NOT Protected (Known Threat Model Exclusions)
- **Filesystem Traversal**: Since the code executes as the primary application user, a malicious program can read the unencrypted source code of the application (e.g., viewing `settings.py`). However, because the production configuration relies on environment variables rather than hardcoded secrets, reading the source code does not yield access to sensitive data or the database.
- **Container Escapes (Kernel Exploits)**: This sandbox relies on standard kernel boundaries within an unprivileged Docker container. It does *not* defend against kernel-level 0-day privilege escalation exploits. For absolute multi-tenant isolation, the infrastructure would require hypervisor-level microVMs (e.g., AWS Firecracker) or strict `seccomp` profiles (e.g., gVisor).
- **Network Access Restriction**: Because the application runs in an unprivileged Docker container (common on PaaS providers like Render), we do not have the `CAP_NET_ADMIN` capability required to create isolated network namespaces. Consequently, malicious code can make outbound network requests (e.g., downloading external payloads or participating in outbound DDoS activity).
- **Side-Channel Attacks**: CPU-level side-channel attacks (e.g., Spectre, Meltdown) or timing attacks across shared hardware are not mitigated by this user-level sandbox.
