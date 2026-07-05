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
- **Filesystem Isolation (Secrets Protection)**: Untrusted code submitted by users is executed as a strictly isolated OS-level user (`sandboxuser`). The primary application and its environment variables (including `.env` containing database credentials, Cloudinary keys, and the Django Secret Key) are owned by the `appuser` with `chmod 700`. The Linux kernel fundamentally blocks the sandbox user from reading these files, preventing credential theft even if the application-level sandbox is bypassed.
- **Shell Injection Prevention**: The application transitions to the sandbox user via `sudo -n -u sandboxuser`. The command array is executed using strict argument lists (e.g. `subprocess.run(..., shell=False)`). User-supplied code is strictly written to a temporary file in the sandbox directory and never interpolated into the shell command string, making shell injection impossible.
- **Resource Exhaustion (Fork Bombs & OOM)**: We implement defense-in-depth against Denial of Service attacks:
  - Subprocesses are wrapped with Python's `resource.setrlimit` inside `preexec_fn` to cap the maximum address space (`RLIMIT_AS`) and maximum child processes (`RLIMIT_NPROC=15`).
  - OS-level PAM limits (`/etc/security/limits.conf`) are hardcoded in the Dockerfile for `sandboxuser` to prevent excessive file descriptor or process consumption across the entire container.

### What is NOT Protected (Known Threat Model Exclusions)
- **Container Escapes (Kernel Exploits)**: This sandbox relies on Linux user namespaces and standard kernel boundaries within an unprivileged Docker container. It does *not* defend against kernel-level 0-day privilege escalation exploits. For absolute multi-tenant isolation, the infrastructure would require hypervisor-level microVMs (e.g., AWS Firecracker) or strict `seccomp` profiles (e.g., gVisor).
- **Network Access Restriction**: Because the application runs in an unprivileged Docker container (common on PaaS providers like Render), we do not have the `CAP_NET_ADMIN` capability required to create isolated network namespaces for `sandboxuser`. Consequently, malicious code can make outbound network requests. While data exfiltration of internal `.env` secrets is blocked by filesystem permissions, attackers could theoretically download external payloads or participate in outbound DDoS activity.
- **Side-Channel Attacks**: CPU-level side-channel attacks (e.g., Spectre, Meltdown) or timing attacks across shared hardware are not mitigated by this user-level sandbox.
