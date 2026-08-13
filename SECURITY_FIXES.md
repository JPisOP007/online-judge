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

### B. Static Analysis for C++, Java and JavaScript
These languages have no equivalent to Python's import hook, so submissions are matched against per-language denylists covering process creation, file I/O, sockets, reflection, inline assembly and environment access. Matching runs on source with comments and string literals blanked out, so a payload cannot be hidden in a comment and a benign `printf("system(x)")` does not trigger a false positive.

JavaScript additionally runs inside a harness that pre-reads stdin and exposes `readline()` / `readAll()`, then executes user code in a scope where `require`, `process`, `module` and `globalThis` are shadowed — `require('child_process')` would otherwise be a one-line escape.

**Lexical shadowing alone proved insufficient**, and it is worth recording why. The Function constructor compiles code in *global* scope, outside those shadowed bindings, and is reachable without ever naming `Function`:

```javascript
(()=>{}).constructor("return this")().process   // the real process object
```

This was confirmed working against the harness — an escape to arbitrary code execution. It is closed at two levels:

- Node is launched with `--disallow-code-generation-from-strings`, which makes V8 refuse `eval`, `Function()`, `.constructor()` and the async and generator function constructors outright. This is an engine-level control, not a shim, and it does not depend on the denylist being complete.
- The denylist additionally rejects `.constructor`, `Reflect`, `Proxy`, `WebAssembly`, `Atomics` and `SharedArrayBuffer` before execution.

**Residual risk.** JavaScript is offered on all deployments, including those without OS-level isolation. The specific escape above is closed at the engine level, but shadowing intrinsics inside a shared process is not a containment boundary: another route to global scope would again mean immediate arbitrary code execution, with no OS boundary behind it on PaaS. This is an accepted risk for this deployment, not a solved problem — see the exclusions in section 5.

**These are denylists, and denylists are incomplete by construction.** They reject known-dangerous constructs rather than permitting only known-safe ones. They raise the cost of an attack and stop opportunistic attempts; they are not a containment boundary. That role belongs to the OS-level isolation below.

### C. OS-Level Isolation (`nsjail`) — Docker deployments only
Where the container has the necessary capabilities, Google's `nsjail` provides containment using Linux namespaces:
- **Filesystem Isolation:** Executed in a chroot with empty `tmpfs` overlays mounted over `/tmp`, `/etc`, `/var`, `/home`, and `/root`, so world-readable host files and application canaries are invisible.
- **Resource Constraints:** Limits on memory (`RLIMIT_AS`), CPU time (`RLIMIT_CPU`) and output size (`RLIMIT_FSIZE`).
- **Identity Masking:** Code runs as the unprivileged `sandboxuser` (`UID/GID 65534`).
- **Network:** *Not* isolated. Creating a network namespace requires `CAP_NET_ADMIN`, which is unavailable in our PaaS environment, so the sandbox is launched with `--disable_clone_newnet` and shares the host network. Untrusted code can therefore make outbound network requests. This is a known gap, not a mitigation.

**On the live deployment (Render), none of this applies.** Render runs unprivileged containers, so neither `nsjail` nor `sudo -u sandboxuser` is available and submissions execute as the application user with only `setrlimit` caps and the static analysis above. The isolation described in this section covers the Docker deployment.

### D. Environment Scrubbing
Subprocesses are launched with a minimal environment — only `PATH` — so application secrets such as `MONGODB_URI` and `DJANGO_SECRET_KEY` are not inherited.

Note the limit of this control: where user code runs as the same OS user as the application, which is the case on Render, a process that got past the static analysis could still read the parent's environment through `/proc/<pid>/environ`. Scrubbing raises the bar; it is not a boundary.

## 2. Container Security

The application runs in a hardened Docker environment:
- **Non-Root Execution:** The web server and celery workers run as `appuser` (UID 1000). The untrusted execution happens within `nsjail`, which drops privileges to `sandboxuser` (UID 65534).
- **Privileged Engine:** To enable `nsjail` to create new namespaces and pivot_root, the Docker container itself runs with privileges, but untrusted code is securely jailed inside it.
- **Read-Only Considerations:** While the code needs to write to a temporary sandbox directory, access to the rest of the application filesystem is restricted by standard UNIX file permissions and `nsjail`'s read-only bind mounts.

## 3. Web Application & API Security

- **Rate Limiting:** Two layers. Django REST Framework throttles the API (100/hour anonymous, 1000/hour authenticated), and a custom middleware applies a site-wide per-minute budget backed by Redis so the counter is shared across workers. Authenticated callers are keyed by user id rather than by `X-Forwarded-For`, which a client can forge; anonymous callers fall back to IP, which is best-effort.
- **Role-Based Access Control:** API writes are gated by profile role. Problems, contests and announcements require `setter` or `admin`; accounts and profiles are editable only by their owner or staff; `role` itself is writable only by staff; contest submissions and participants are read-only, so scores cannot be supplied by a client.
- **Content Security Policy:** Restricts script, style, image and font sources to the CDNs actually in use, and sets `connect-src 'self'`, `form-action 'self'`, `object-src 'none'` and `frame-ancestors 'none'`. `'unsafe-inline'` is currently required for scripts and styles because the templates rely on inline blocks and attributes.
- **Markdown Sanitisation:** Problem statements are rendered client-side with `marked` and scrubbed through DOMPurify before insertion, since `marked` has not sanitised by default since v5.
- **JWT Authentication:** Secure access token generation with short lifespans (1 hour) and rotating refresh tokens (7 days).
- **CORS Policies:** Cross-Origin Resource Sharing is strictly limited to allowed frontend domains specified in the environment variables.
- **Security Headers:** The application enforces XSS filtering, content-type sniffing protection, and strict X-Frame-Options (`DENY`).

## 4. File Upload Validation

To protect against malicious payloads disguised as profile photos:
- **MIME Validation:** We use `python-magic` to inspect the actual file signature (magic bytes) rather than trusting the file extension.
- **Image Integrity Checks:** Uploaded images are passed through the `Pillow` (PIL) library to verify they are structurally valid images.
- **Size Restrictions:** Profile photos are capped at 20MB and 4096x4096 pixels by the validator; Django buffers uploads over 5MB to disk rather than memory.

## 5. Known Threat Model Exclusions

It is worth being explicit about what this design does *not* stop:
- **Denylists are incomplete by construction.** For C++, Java and JavaScript the application-level control rejects known-dangerous constructs rather than permitting only known-safe ones. A determined attacker who finds a construct the list does not name will get past it. This is not hypothetical: probing these lists found a working JavaScript escape (section B) and three quieter holes in the C++ and Java lists, all since closed.
- **In-process JavaScript sandboxing.** Shadowing `require` and `process` inside the same Node process is hardening, not containment. Where a deployment has no OS-level isolation, a successful escape has nothing behind it.
- **Reduced isolation on PaaS.** On Render, unprivileged containers mean no `nsjail` and no separate sandbox user, so submissions run as the application user under `setrlimit` alone.
- **Network access.** No network namespace is created (see section C), so untrusted code can make outbound requests.
- **Filesystem reads.** Where code runs as the application user, it can read application source. Secrets are supplied by environment rather than committed, but see the note on `/proc/<pid>/environ` in section D.
- **Container Escapes:** We rely on Linux namespaces and standard Docker isolation, not hypervisor-level microVMs such as Firecracker.
- **Side-Channel Attacks:** CPU-level vulnerabilities (e.g., Spectre) are not mitigated by this sandbox.

*For any security reports or vulnerabilities, please contact the repository maintainer directly rather than opening a public issue.*