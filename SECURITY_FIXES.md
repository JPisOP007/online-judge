# 🛡️ Security Architecture & Validation

This document details the security architecture of the Online Judge platform and the measures taken to safely execute untrusted code in a production environment.

## 1. Code Execution Sandboxing

Executing arbitrary user code requires extreme caution. Our sandbox utilizes a multi-layered defense strategy:

### A. Python Static Analysis (AST Parsing) & Import Proxy
Before any Python code is executed, it is parsed into an Abstract Syntax Tree (AST). We employ a custom `SecurityVisitor` to statically block:
- **Dangerous Imports:** Forbids importing modules like `os`, `subprocess`, `socket`, `urllib`, etc.
- **Dangerous Functions:** Blocks execution of functions like `eval()`, `exec()`, `compile()`, and `__import__()`.
- **Reflection & Introspection:** Blocks attributes like `getattr`, `setattr`, `vars`, `globals`, `locals`, and format-string dunder exploits to prevent sandbox escapes.
- **Restricted `sys` Proxy:** We supply a safe proxy of the `sys` module to user scripts (allowing `stdin/stdout` and `setrecursionlimit`) while completely blocking access to `sys.modules` or `sys._getframe` which could be used to bypass AST filters. Standard library imports remain unhindered.

### B. OS-Level Isolation (`nsjail`)
For true robust containment of C++, Java, Node.js, and Python, we utilize Google's `nsjail` leveraging Linux namespaces (PID, mount, network, user, IPC) and `cgroups`:
- **Network Isolation:** The sandbox runs without `CLONE_NEWNET` disabled for outbound egress. Untrusted code has absolutely no network access (`--disable_clone_newnet`, `--iface_no_lo`).
- **Filesystem Isolation:** The sandbox is executed in a chroot with empty `tmpfs` overlays mounted over `/tmp`, `/etc`, `/var`, `/home`, and `/root`. This ensures world-readable host files (like `/etc/hostname`) or application canaries are invisible and inaccessible.
- **Resource Constraints:** `nsjail` rigorously enforces limits on Memory (`RLIMIT_AS`), CPU time (`RLIMIT_CPU`), and File output size (`RLIMIT_FSIZE`).
- **Identity Masking:** Code runs under the unprivileged `sandboxuser` (`UID/GID 65534`).

### C. Environment Scrubbing
Before launching a subprocess for any language, the environment variables are explicitly wiped. The subprocess receives a clean, minimal environment (e.g., `{'PATH': '/usr/bin:/bin'}`). This ensures that application secrets (like `MONGODB_URI` and `DJANGO_SECRET_KEY`) injected into the container are never leaked to user-submitted code.

## 2. Container Security

The application runs in a hardened Docker environment:
- **Non-Root Execution:** The web server and celery workers run as `appuser` (UID 1000). The untrusted execution happens within `nsjail`, which drops privileges to `sandboxuser` (UID 65534).
- **Privileged Engine:** To enable `nsjail` to create new namespaces and pivot_root, the Docker container itself runs with privileges, but untrusted code is securely jailed inside it.
- **Read-Only Considerations:** While the code needs to write to a temporary sandbox directory, access to the rest of the application filesystem is restricted by standard UNIX file permissions and `nsjail`'s read-only bind mounts.

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

While the application is heavily fortified, it is important to acknowledge the limitations of a software-level sandbox:
- **Container Escapes:** We rely on Linux namespaces and standard Docker isolation. We do not currently use hypervisor-level microVMs (like Firecracker).
- **Side-Channel Attacks:** CPU-level vulnerabilities (e.g., Spectre) are not mitigated by this sandbox.

*For any security reports or vulnerabilities, please contact the repository maintainer directly rather than opening a public issue.*