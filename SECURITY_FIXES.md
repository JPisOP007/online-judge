# 🛡️ Security Architecture & Validation

This document details the security architecture of the Online Judge platform and the measures taken to safely execute untrusted code in a production environment.

## 1. Code Execution Sandboxing

Executing arbitrary user code requires extreme caution. Our sandbox utilizes a multi-layered defense strategy:

### A. Python Static Analysis (AST Parsing)
Before any Python code is executed, it is parsed into an Abstract Syntax Tree (AST). We employ a custom `SecurityVisitor` to statically block:
- **Dangerous Imports:** Completely forbids importing modules like `os`, `subprocess`, `sys`, `socket`, `urllib`, etc.
- **Dangerous Functions:** Blocks execution of functions like `eval()`, `exec()`, `compile()`, and `__import__()`.
- **System Calls:** Prevents unauthorized file system or network access originating from user code.

### B. OS-Level Resource Limitations
To protect the host container from resource exhaustion (Denial of Service):
- **Address Space (Memory):** Subprocesses are bounded using `resource.setrlimit(resource.RLIMIT_AS)`.
- **Process Count (Fork Bombs):** Capped using `RLIMIT_NPROC` to prevent fork bombing.
- **CPU Time:** Bound by strict execution timeouts (`RLIMIT_CPU`).
- **File Output:** Maximum file output sizes are enforced to prevent disk-fill attacks.

### C. Environment Scrubbing
Before launching a subprocess for any language (Python, C++, Java, Node.js), the environment variables are explicitly wiped. The subprocess receives a clean, minimal environment (e.g., `{'PATH': '/usr/bin:/bin'}`). This ensures that application secrets (like `MONGODB_URI` and `DJANGO_SECRET_KEY`) injected into the container are never leaked to user-submitted code.

## 2. Container Security

The application runs in a hardened Docker environment:
- **Non-Root Execution:** The Dockerfile explicitly creates and utilizes an `appuser` (UID 1000). The web server and code execution engines do not run as root.
- **PAM Limits:** OS-level limits are hardcoded via `/etc/security/limits.conf` inside the container.
- **Read-Only Considerations:** While the code needs to write to a temporary sandbox directory, access to the rest of the application filesystem is restricted by standard UNIX file permissions.

## 3. Web Application & API Security

- **Rate Limiting:** IP-based throttling is enforced via Django REST Framework (100 requests/hour for anonymous, 1000/hour for authenticated users) to prevent API abuse.
- **JWT Authentication:** Secure access token generation with short lifespans (1 hour) and rotating refresh tokens (7 days).
- **CORS Policies:** Cross-Origin Resource Sharing is strictly limited to allowed frontend domains specified in the environment variables.
- **Security Headers:** The application enforces XSS filtering, content-type sniffing protection, and strict X-Frame-Options (`DENY`).

## 4. File Upload Validation

To protect against malicious payloads disguised as profile photos:
- **MIME Validation:** We use `python-magic` to inspect the actual file signature (magic bytes) rather than trusting the file extension.
- **Image Integrity Checks:** Uploaded images are passed through the `Pillow` (PIL) library to verify they are structurally valid images.
- **Size Restrictions:** Strict limits (max 5MB) on all media uploads.

## 5. Known Threat Model Exclusions

While the application is heavily fortified, it is important to acknowledge the limitations of a user-level sandbox in a PaaS environment:
- **Container Escapes:** We rely on standard Docker isolation. We do not currently use hypervisor-level microVMs (like Firecracker).
- **Network Exfiltration:** Because we run in unprivileged containers (lacking `CAP_NET_ADMIN`), we cannot create isolated network namespaces for subprocesses. Malicious C++/Java code could theoretically make outbound network requests.
- **Side-Channel Attacks:** CPU-level vulnerabilities (e.g., Spectre) are not mitigated by this sandbox.

*For any security reports or vulnerabilities, please contact the repository maintainer directly rather than opening a public issue.*