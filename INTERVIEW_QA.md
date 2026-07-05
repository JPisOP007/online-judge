# 🎯 Online Judge — Interview Questions & Answers

> **Complete interview preparation guide for the Online Judge project.**
> Every answer references the actual codebase, architecture decisions, and real challenges faced during development.

---

## Table of Contents

1. [Project Overview & Architecture](#1-project-overview--architecture)
2. [Challenges Faced](#2-challenges-faced)
3. [Why Docker?](#3-why-docker)
4. [Why Queues? (And Why We Don't Use Them Yet)](#4-why-queues-and-why-we-dont-use-them-yet)
5. [Why Polling?](#5-why-polling)
6. [Why Not Execute Directly?](#6-why-not-execute-directly)
7. [How Do You Prevent Fork Bombs?](#7-how-do-you-prevent-fork-bombs)
8. [How Do You Kill Infinite Loops?](#8-how-do-you-kill-infinite-loops)
9. [How Do You Isolate Containers?](#9-how-do-you-isolate-containers)
10. [How Is Timeout Handled?](#10-how-is-timeout-handled)
11. [How Is Memory Monitored?](#11-how-is-memory-monitored)
12. [Security Deep-Dive](#12-security-deep-dive)
13. [Database & Data Modeling](#13-database--data-modeling)
14. [API Design & REST Architecture](#14-api-design--rest-architecture)
15. [Authentication & Authorization](#15-authentication--authorization)
16. [AI Code Review Integration](#16-ai-code-review-integration)
17. [Contest System Design](#17-contest-system-design)
18. [Deployment & DevOps](#18-deployment--devops)
19. [Performance & Scalability](#19-performance--scalability)
20. [Testing Strategy](#20-testing-strategy)
21. [What Would You Improve?](#21-what-would-you-improve)
22. [Behavioral / Soft-Skill Questions](#22-behavioral--soft-skill-questions)

---

## 1. Project Overview & Architecture

### Q: Walk me through the architecture of your Online Judge.

**A:** The Online Judge is a full-stack web application built on **Django 6.0** with **MongoDB** as the database (via `django-mongodb-backend`). Here's the high-level architecture:

```
┌──────────────────────────────────────────────────────────┐
│                     CLIENT (Browser)                     │
│   HTML Templates + JavaScript + CodeMirror 6 Editor      │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTPS (TLS 1.2/1.3)
                       ▼
┌──────────────────────────────────────────────────────────┐
│                   NGINX (Reverse Proxy)                  │
│   • SSL termination     • Static/media file serving      │
│   • Gzip compression    • Security headers               │
│   • Rate limiting       • HTTP→HTTPS redirect            │
└──────────────────────┬───────────────────────────────────┘
                       │ proxy_pass http://web:8000
                       ▼
┌──────────────────────────────────────────────────────────┐
│              DJANGO APP (Gunicorn WSGI)                  │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Views     │  │  REST API    │  │  Middleware     │  │
│  │  (SSR HTML) │  │ (DRF + JWT)  │  │  (Security)    │  │
│  └──────┬──────┘  └──────┬───────┘  └────────────────┘  │
│         │                │                               │
│  ┌──────▼────────────────▼───────┐                       │
│  │        Business Logic          │                       │
│  │  • Code Execution Engine       │                       │
│  │  • Contest Management          │                       │
│  │  • AI Review (Groq LLaMA 3.3) │                       │
│  └───────────────┬───────────────┘                       │
│                  │                                        │
│  ┌───────────────▼───────────────┐                       │
│  │     Secure Execution Layer     │                       │
│  │  • AST-based code analysis     │                       │
│  │  • Import whitelisting         │                       │
│  │  • subprocess with limits      │                       │
│  │  • Temp dir isolation          │                       │
│  └───────────────────────────────┘                       │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│                   MongoDB (Atlas)                         │
│   Collections: users, problems, solutions, contests,     │
│   contest_participants, contest_submissions, etc.        │
└──────────────────────────────────────────────────────────┘
```

**Key components:**
- **Frontend**: Server-side rendered Django templates with CodeMirror 6 for the code editor, AJAX for async submissions
- **Backend**: Django with DRF (Django REST Framework) for API endpoints, JWT authentication for API access
- **Code Execution**: Custom sandboxed execution engine using `subprocess` with resource limits, AST analysis, and import whitelisting
- **Database**: MongoDB via `django-mongodb-backend` with `ObjectIdAutoField` as default PK
- **Deployment**: Docker + Docker Compose + Nginx with Let's Encrypt SSL on a custom domain (`myoj.work.gd`)
- **AI Integration**: Groq API with LLaMA 3.3-70b for automated code review

### Q: Why Django and not Node.js / Go / FastAPI?

**A:**
1. **Rapid development**: Django's "batteries included" philosophy — ORM, admin panel, auth system, form validation — let me ship features fast as a solo developer.
2. **Mature ecosystem**: DRF for REST APIs, SimpleJWT for token auth, `drf-spectacular` for OpenAPI docs — all production-tested.
3. **Template engine**: Server-side rendering with Django templates was simpler than building a separate React/Vue frontend for this scope.
4. **Security built-in**: CSRF protection, SQL injection prevention via ORM, XSS protection, clickjacking protection — all out of the box.
5. **Python synergy**: Since the code execution engine already needed Python's `subprocess`, `ast`, and `resource` modules, staying in Python avoided cross-language complexity.

**Trade-off acknowledged**: Django's synchronous nature means code execution blocks the request thread. In a production system at scale, I'd use Celery + Redis for async task processing (discussed in the queues section).

---

## 2. Challenges Faced

### Q: What were the biggest challenges you faced building this?

**A:** Here are the major challenges, in order of difficulty:

#### Challenge 1: Secure Code Execution (Hardest)
**Problem**: Allowing users to run arbitrary code on your server is inherently dangerous. Users can attempt:
- File system access (`import os; os.system('rm -rf /')`)
- Network calls (`import socket; socket.connect(...)`)
- Fork bombs (`os.fork()` in a loop)
- Infinite loops / memory bombs (`while True: x.append([0]*10**8)`)
- Import-based escapes (`__import__('os').system('whoami')`)

**Solution**: I built a multi-layered security system:
1. **Static Analysis Layer (AST)**: Parse the code's Abstract Syntax Tree before execution to detect forbidden imports, function calls, and attribute access. This catches attacks *before* any code runs.
2. **Runtime Sandbox**: Replace Python's `__import__` function with a custom `safe_import()` that enforces a whitelist at runtime.
3. **OS-Level Limits**: Use `resource.setrlimit()` on Linux to cap CPU time, memory, file size, and process count.
4. **Process Isolation**: Execute in a temporary directory with `0o700` permissions, destroyed after execution.
5. **Subprocess Timeout**: `process.communicate(timeout=5)` kills processes that exceed the time limit.

The challenge was balancing security with usability — I needed to allow legitimate competitive programming imports (`collections`, `heapq`, `itertools`, `math`) while blocking dangerous ones. I solved this with a **smart whitelist system** in `secure_execution.py` that allows specific functions from specific modules.

#### Challenge 2: Cross-Platform Development
**Problem**: I developed on Windows but deployed to Linux (Docker). Python's `resource` module doesn't exist on Windows, and compiler paths differ.

**Solution**: Platform detection at the top of `secure_execution.py`:
```python
import platform
IS_WINDOWS = platform.system() == 'Windows'

if not IS_WINDOWS:
    import resource
    HAS_RESOURCE = True
else:
    HAS_RESOURCE = False
```
On Windows, resource limits are skipped (acceptable for development). On Linux (production Docker), they're enforced.

#### Challenge 3: MongoDB with Django
**Problem**: Django was historically built for SQL databases. Using MongoDB required `django-mongodb-backend`, which had compatibility quirks:
- No auto-incrementing integer IDs → had to use `ObjectIdAutoField`
- Some Django ORM features (like complex JOINs) behave differently
- Admin panel needed custom `MongoAdminConfig`, `MongoAuthConfig`, `MongoContentTypesConfig` instead of defaults

**Solution**: Custom app configurations in settings:
```python
INSTALLED_APPS = [
    'online_judge.apps.MongoAdminConfig',  # instead of django.contrib.admin
    'online_judge.apps.MongoAuthConfig',    # instead of django.contrib.auth
    'online_judge.apps.MongoContentTypesConfig',  # instead of contenttypes
    ...
]
DEFAULT_AUTO_FIELD = 'django_mongodb_backend.fields.ObjectIdAutoField'
```

#### Challenge 4: Contest Real-Time Features
**Problem**: Contests need real-time countdowns, live standings, and time-synchronized start/end. JavaScript timers drift; timezone handling across server (IST) and client is tricky.

**Solution**:
- Server-side `status` property on the Contest model that computes state from `timezone.now()` vs `start_time`/`end_time`
- A dedicated API endpoint (`contest_timer_api`) that returns remaining seconds, called by client-side JavaScript
- `USE_TZ = True` in Django settings with `TIME_ZONE = 'Asia/Kolkata'` for consistent timezone handling

#### Challenge 5: Profile Photo Upload Security
**Problem**: File uploads are a classic attack vector. Users could upload:
- Executable files disguised as images
- Files with directory traversal in filenames (`../../etc/passwd`)
- Extremely large files to DoS the server

**Solution**: Created `file_validators.py` with multiple layers:
- **MIME type validation** using `python-magic` (checks actual file bytes, not just extension)
- **PIL image validation** (opens the image to verify it's a real image)
- **Size limits** (5MB max for profile photos)
- **Sanitized filenames** with user-specific directories (`media/profile_photos/{user_id}/`)
- **Extension whitelist** (only `.jpg`, `.png`, `.gif`, `.webp`)

#### Challenge 6: AI Review Response Parsing
**Problem**: The Groq LLaMA model doesn't always return perfectly formatted JSON. Sometimes it adds markdown code fences, extra text, or uses slightly different key names.

**Solution**: Multi-strategy parsing in `ai_review.py`:
1. First, try regex extraction of JSON from response: `re.search(r'\{.*\}', response_text, re.DOTALL)`
2. If JSON parsing fails, fall back to text-based section parsing with multiple strategies (numbered sections, keyword headers, line-by-line analysis)
3. Robust retry mechanism with `generate_code_review_robust()` that retries up to 2 times with 1-second delays

---

## 3. Why Docker?

### Q: Why did you use Docker for this project?

**A:** Docker solves several critical problems for an online judge:

#### 1. **Environment Consistency ("Works on my machine" problem)**
The online judge needs specific compilers/interpreters: `g++`, `javac`, `java`, `node`, `python3`. Docker guarantees the exact same versions are available in development, testing, and production.

From our `Dockerfile`:
```dockerfile
FROM python:3.13-slim
RUN apt-get update && apt-get install -y \
    g++ \
    default-jdk \
    nodejs \
    npm \
    gcc \
    ...
```

Without Docker, I'd need to install and maintain these on every server, deal with version conflicts, and debug "why does g++14 work on my laptop but the server has g++12?"

#### 2. **Security Isolation**
Docker provides **namespace isolation** — the code execution happens inside a container that's isolated from the host OS. Even if a user breaks out of my Python-level sandbox, they're still inside a Docker container with:
- A non-root user (`appuser`)
- Limited process counts (`nproc 100/200`)
- Limited file descriptors (`nofile 1024/2048`)
- No access to host filesystem (except mounted volumes)

#### 3. **Reproducible Deployments**
One command deploys everything:
```bash
docker-compose up -d
```
This spins up the Django app with all dependencies, compilers, and configurations. No "install Python 3.13, then install g++, then install JDK..." manual steps.

#### 4. **Resource Control**
Docker lets you set memory limits, CPU limits, and network restrictions at the container level — an additional layer beyond what my application code enforces.

#### 5. **Easy Horizontal Scaling**
When traffic grows, I can spin up multiple container replicas behind a load balancer without changing any application code.

### Q: What are the downsides of Docker in your project?

**A:**
1. **Image size**: Our image includes g++, JDK, Node.js, and Python — it's ~800MB+. I mitigate this with `python:3.13-slim` as the base and cleaning apt cache (`rm -rf /var/lib/apt/lists/*`).
2. **Build time**: Cold builds take 3-5 minutes because of apt package installation and pip installs.
3. **Development overhead**: Docker adds complexity to the dev workflow (rebuilding images for dependency changes). I use volume mounts (`- .:/app`) in docker-compose to avoid rebuilds for code changes.
4. **Resource usage**: Docker daemon uses memory. On a small VPS (1GB RAM), this matters.

### Q: Why `python:3.13-slim` and not `alpine`?

**A:** Alpine uses `musl libc` instead of `glibc`. Many Python packages with C extensions (like `Pillow`) have compatibility issues on Alpine, requiring extra build dependencies. `slim` is based on Debian with `glibc`, so pip wheels "just work" while still being ~60% smaller than the full `python:3.13` image.

---

## 4. Why Queues? (And Why We Don't Use Them Yet)

### Q: Why would you use a message queue for code execution?

**A:** In our current architecture, code execution is **synchronous** — when a user submits code, the Django view calls `secure_execute_code()`, which blocks the HTTP request thread until execution completes (up to 5 seconds). This has serious problems at scale:

```
Current Flow (Synchronous):
User → HTTP Request → Django View → secure_execute_code() → [BLOCKS 5 sec] → Response

With Queue (Asynchronous):
User → HTTP Request → Enqueue Job → Immediate Response (202 Accepted)
                            ↓
                     Worker picks up job → Execute code → Store result in DB
                            ↓
User polls /status/{id} → Gets result when ready
```

#### Why queues are needed:
1. **Thread exhaustion**: Gunicorn runs 2 workers (see our `Dockerfile` CMD). If 2 users submit code simultaneously, the 3rd user has to wait. With queues, the web server returns immediately and a separate worker pool handles execution.

2. **Timeout control**: Queue workers (like Celery) have their own timeout mechanisms independent of HTTP timeouts. If a task hangs, the worker can kill it without affecting the web server.

3. **Retry logic**: If execution fails due to a transient error (disk full, compiler crash), a queue can automatically retry.

4. **Priority handling**: Contest submissions could be given higher priority than practice submissions.

5. **Rate limiting per user**: A queue makes it trivial to say "max 3 concurrent submissions per user."

6. **Horizontal scaling**: You can add more workers without adding more web servers.

#### What I'd use:
- **Celery** as the task framework (Python-native, works perfectly with Django)
- **Redis** as the message broker (fast, supports pub/sub for real-time results)
- Or **RabbitMQ** if I needed guaranteed delivery

#### Why I haven't implemented it yet:
This is a project with low concurrent users. The synchronous approach works fine for the current scale. Adding Celery + Redis adds operational complexity (another service to deploy, monitor, and debug). I'd add it when:
- Concurrent submissions exceed worker count
- Average response times cross 3 seconds consistently
- Contest events cause traffic spikes

### Q: What queue would you choose and why?

**A:** **Celery with Redis** for this project:
- **Celery** because it's the de facto standard for Django async tasks, with built-in support for retries, task chaining, result backends, and monitoring (Flower)
- **Redis** as broker because it's lightweight, fast, and I can also use it for caching (replacing our current `LocMemCache`) and session storage — getting 3 benefits from 1 service
- I'd avoid RabbitMQ here because it's heavier to operate and the guaranteed delivery semantics aren't critical for code execution (if a submission is lost, the user just resubmits)

---

## 5. Why Polling?

### Q: How does the client get code execution results? Why polling?

**A:** Currently, our system uses **AJAX requests** (not true polling) — the client sends a POST request and waits for the response:

```javascript
// From the frontend JavaScript (problem_detail.html)
fetch(url, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    body: formData
})
.then(response => response.json())
.then(data => {
    // Display verdict, output, etc.
});
```

The Django view detects AJAX via `request.headers.get('X-Requested-With') == 'XMLHttpRequest'` and returns `JsonResponse` instead of a full HTML page.

#### If we moved to async execution (queues), we'd need polling:

```
Option 1: Short Polling
Client → POST /submit → 202 {job_id: "abc123"}
Client → GET /status/abc123 → {"status": "pending"} (every 2 sec)
Client → GET /status/abc123 → {"status": "pending"}
Client → GET /status/abc123 → {"status": "completed", "verdict": "AC"}
```

**Pros**: Simple to implement, works through all firewalls/proxies, stateless.
**Cons**: Wastes bandwidth on empty responses, 2-second delay between completion and notification.

```
Option 2: Long Polling
Client → GET /status/abc123 → [Server holds connection until result is ready] → {"verdict": "AC"}
```

**Pros**: Near-instant response, no wasted requests.
**Cons**: Ties up server connections, timeout handling is tricky, load balancers may kill idle connections.

```
Option 3: WebSockets
Client ↔ ws://server/submissions → Real-time bidirectional communication
```

**Pros**: True real-time, bidirectional (could stream compilation output line by line).
**Cons**: Requires Django Channels + ASGI (significant architecture change), WebSocket connections are stateful (harder to scale horizontally).

```
Option 4: Server-Sent Events (SSE)
Client → GET /stream/abc123 → Server pushes events as they happen
```

**Pros**: Simpler than WebSockets, built on HTTP, auto-reconnect.
**Cons**: Unidirectional only, requires ASGI or async views.

#### For the contest timer, we DO use polling:
```python
# views.py - contest_timer_api
@login_required
def contest_timer_api(request, contest_uuid):
    contest = get_object_or_404(Contest, uuid=contest_uuid)
    time_data = {
        'status': contest.status,
        'time_remaining': int(contest.time_remaining.total_seconds()) if contest.time_remaining else None,
        'time_until_start': int(contest.time_until_start.total_seconds()) if contest.time_until_start else None,
    }
    return JsonResponse(time_data)
```

The client JavaScript calls this every few seconds to keep the countdown synchronized with the server clock.

### Q: If you were redesigning, what would you choose?

**A:** **Server-Sent Events (SSE)** for code execution results and **WebSockets** (via Django Channels) for contest features (live leaderboard, announcements). SSE is simpler for the one-way "server pushes result to client" pattern, while WebSockets are justified for the bidirectional nature of live contest interactions.

---

## 6. Why Not Execute Directly?

### Q: Why can't you just run user code directly with `exec()` or `eval()`?

**A:** Running user code in the same Python process as the Django server is **catastrophically dangerous**. Here's why:

#### Risk 1: Full Server Access
```python
# If you used exec() in your Django view:
exec(user_code)  # This runs in the SAME process as your Django app

# User submits:
import django.conf
print(django.conf.settings.SECRET_KEY)  # Steals your secret key
print(django.conf.settings.DATABASES)    # Steals your DB credentials
```

The user's code would have access to **everything** Django has access to: database credentials, secret keys, environment variables, the entire filesystem.

#### Risk 2: No Resource Limits
`exec()` runs in the same thread. There's no way to:
- Kill it after 5 seconds (no timeout mechanism)
- Limit its memory usage
- Limit its CPU usage
- Limit its file access

An infinite loop would hang your entire web server:
```python
while True: pass  # Your Django server is now frozen
```

#### Risk 3: State Pollution
`exec()` can modify global state, corrupt variables, monkey-patch modules, and affect subsequent requests from other users.

#### Risk 4: No Process Isolation
With `exec()`, if the user's code crashes (segfault, stack overflow), it crashes your **entire Django process**, affecting all users.

#### What We Do Instead: `subprocess.Popen()`

We execute user code in a **completely separate process**:

```python
# From secure_execution.py
process = subprocess.Popen(
    cmd,                          # ['python3', '/tmp/secure_exec_xxx/main.py']
    stdin=subprocess.PIPE,        # We control the input
    stdout=subprocess.PIPE,       # We capture the output
    stderr=subprocess.PIPE,       # We capture errors
    text=True,
    cwd=temp_dir,                 # Isolated working directory
    preexec_fn=set_resource_limits  # OS-level limits (Linux only)
)

out, err = process.communicate(
    input=normalized_input,
    timeout=MAX_EXECUTION_TIME     # Kill if exceeds 5 seconds
)
```

This gives us:
- **Process isolation**: User code runs in a separate process with its own memory space
- **Timeout control**: `communicate(timeout=5)` automatically kills the process
- **Resource limits**: `preexec_fn=set_resource_limits` sets OS-level constraints
- **I/O control**: We control stdin/stdout/stderr pipes
- **Clean termination**: `process.kill()` if anything goes wrong

#### Additional Layer: Code Rewriting

Before `subprocess.Popen()` runs the code, we **rewrite the user's code** inside a restricted environment:

```python
# From secure_execution.py - create_simple_secure_environment()
restricted_code = f"""
import sys
import builtins

original_import = builtins.__import__

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in ABSOLUTELY_FORBIDDEN:
        raise ImportError(f"Module '{name}' is not allowed")
    if name not in ALLOWED_IMPORTS:
        raise ImportError(f"Module '{name}' is not in the allowed imports list")
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = safe_import

try:
    {user_code_indented}
except Exception as e:
    print(f"Runtime Error: {e}", file=sys.stderr)
    sys.exit(1)
"""
```

The user's code is wrapped inside a try-except block with a hijacked import system. Even if they try `import os`, the `safe_import` function blocks it.

---

## 7. How Do You Prevent Fork Bombs?

### Q: What is a fork bomb and how does your system prevent it?

**A:** A **fork bomb** is a process that recursively creates copies of itself, exponentially consuming all system resources until the OS crashes.

Classic fork bomb:
```python
import os
while True:
    os.fork()  # Each child also runs this loop
```
```bash
:(){ :|:& };:  # Bash fork bomb
```

#### Our Multi-Layer Defense:

**Layer 1: Static Analysis (AST) — Catches before execution**
```python
# secure_execution.py - ABSOLUTELY_FORBIDDEN list
ABSOLUTELY_FORBIDDEN = [
    'os', 'subprocess', 'multiprocessing', 'threading', 'concurrent', 'asyncio',
    ...
]
```
The AST visitor checks every `import` and `import from` statement. If a user writes `import os`, it's blocked at the **parsing stage** — the code never executes.

```python
# secure_execution.py - analyze_python_code_security()
def visit_Import(self, node):
    for alias in node.names:
        if alias.name in ABSOLUTELY_FORBIDDEN:
            self.violations.append(f"Forbidden import: {alias.name}")
```

**Layer 2: Runtime Import Hook — Catches dynamic imports**
```python
# The safe_import function replaces builtins.__import__
def safe_import(name, ...):
    if name in ABSOLUTELY_FORBIDDEN:
        raise ImportError(f"Module '{name}' is not allowed")
```
This catches sneaky attempts like:
```python
__builtins__.__import__('os')  # Blocked by AST (visit_Call checks for __import__)
importlib.import_module('os')  # Blocked because 'importlib' is in ABSOLUTELY_FORBIDDEN
```

**Layer 3: OS-Level Process Limit (Linux) — Hard kill switch**
```python
# secure_execution.py - set_resource_limits()
def set_resource_limits():
    if HAS_RESOURCE and not IS_WINDOWS:
        resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))  # Max 1 process!
```
`RLIMIT_NPROC` limits the number of processes the user can create. Set to `(1, 1)`, it means the code can only run as a **single process** — any attempt to fork will get an `OSError: [Errno 11] Resource temporarily unavailable`.

**Layer 4: Container-Level Process Limits**
```dockerfile
# Dockerfile
RUN echo "appuser soft nproc 100" >> /etc/security/limits.conf \
    && echo "appuser hard nproc 200" >> /etc/security/limits.conf
```
Even if a process somehow escapes the `resource.setrlimit`, the container-level `nproc` limit caps the `appuser` to 200 processes max.

**Layer 5: Docker itself**
Docker namespaces provide PID isolation — processes inside the container can't see or affect processes on the host. Even a successful fork bomb would only impact the container, not the host OS.

#### For C++/Java (compiled languages):
Fork bombs in C++ (`fork()` syscall) are harder to catch statically. The defense relies on:
- `RLIMIT_NPROC` (Layer 3) — this works at the OS level regardless of language
- Container-level limits (Layer 4)
- Timeout (Layer 5) — even if forking succeeds, the 5-second timeout kills the parent process, and all children inherit the resource limits

---

## 8. How Do You Kill Infinite Loops?

### Q: What happens when a user submits code with `while True: pass`?

**A:** The system handles infinite loops through **multiple timeout mechanisms**:

#### Mechanism 1: `subprocess.communicate(timeout=5)` — Primary defense

```python
# secure_execution.py - run_with_limits()
try:
    out, err = process.communicate(input=normalized_input, timeout=MAX_EXECUTION_TIME)
except subprocess.TimeoutExpired:
    process.kill()  # Sends SIGKILL to the process
    return {'verdict': 'TLE', 'error': f'Time Limit Exceeded ({MAX_EXECUTION_TIME} seconds)'}
```

**How it works:**
1. `process.communicate()` starts a timer
2. If the process doesn't finish within `MAX_EXECUTION_TIME` (5 seconds), Python raises `subprocess.TimeoutExpired`
3. We catch this exception and call `process.kill()` which sends `SIGKILL` (signal 9) — this is **uncatchable** by the user's code. The process is terminated immediately by the kernel.
4. We return a `TLE` (Time Limit Exceeded) verdict to the user

**Why `process.kill()` and not `process.terminate()`?**
- `process.terminate()` sends `SIGTERM` (signal 15) — the process can catch this and ignore it!
  ```python
  import signal
  signal.signal(signal.SIGTERM, lambda s, f: None)  # Ignores SIGTERM
  while True: pass
  ```
- `process.kill()` sends `SIGKILL` (signal 9) — **cannot be caught, blocked, or ignored**. The kernel forcefully terminates the process.

#### Mechanism 2: `RLIMIT_CPU` — OS-level CPU time limit

```python
# secure_execution.py - set_resource_limits()
resource.setrlimit(resource.RLIMIT_CPU, (MAX_EXECUTION_TIME, MAX_EXECUTION_TIME))
```

This is a **kernel-level** timer that counts actual CPU time consumed. Even if `subprocess.communicate()` somehow fails to kill the process:
- After 5 seconds of CPU time, the kernel sends `SIGXCPU` to the process
- If the process catches `SIGXCPU` (soft limit), the kernel sends `SIGKILL` when the hard limit is hit

**Difference from wall-clock timeout:**
- `subprocess.communicate(timeout=5)` measures wall-clock time (includes I/O wait, sleep)
- `RLIMIT_CPU` measures actual CPU time (only counts when the CPU is executing this process's instructions)

An infinite loop like `while True: pass` hits both. But a sneaky attack like `time.sleep(100)` would hit the wall-clock timeout but NOT the CPU limit.

#### Mechanism 3: Gunicorn Worker Timeout — Last resort

```dockerfile
CMD ["gunicorn", ..., "--timeout", "120", ...]
```

If a request takes longer than 120 seconds (shouldn't happen since code execution is 5s), Gunicorn kills the worker and spawns a new one. This prevents a stuck worker from permanently consuming resources.

#### For CPU-intensive but finite loops:
What about code that's not infinite but just slow?
```python
# This technically terminates, but takes O(2^n) time
def fib(n):
    if n <= 1: return n
    return fib(n-1) + fib(n-2)
print(fib(50))  # Would take years
```

Same answer — the 5-second timeout kills it. The verdict is `TLE`, which tells the user their algorithm is too slow (common in competitive programming — the whole point is to write efficient algorithms).

---

## 9. How Do You Isolate Containers?

### Q: How do you ensure one user's code execution doesn't affect another user's or the system?

**A:** Isolation is implemented at 5 levels:

#### Level 1: Filesystem Isolation (Temp Directories)
```python
# secure_execution.py
def create_secure_temp_directory():
    temp_dir = tempfile.mkdtemp(prefix='secure_exec_')
    os.chmod(temp_dir, 0o700)  # Only owner (the execution user) can access
    return temp_dir
```

Each code execution:
1. Creates a unique temp directory (e.g., `/tmp/secure_exec_a1b2c3d4/`)
2. Writes the user's code into it
3. Executes in that directory (`cwd=temp_dir`)
4. **Deletes the directory** after execution (in a `finally` block):
   ```python
   try:
       if language == 'python':
           return execute_python_secure(code, input_data, expected_output, temp_dir)
   finally:
       try:
           shutil.rmtree(temp_dir)  # Clean up no matter what
       except:
           pass
   ```

User A's code **cannot see or access** User B's temp directory because:
- Different random directory names
- `0o700` permissions (owner-only access)
- `filesystem` modules (`os`, `shutil`) are blocked by the import whitelist

#### Level 2: Process Isolation (subprocess)
Each execution runs in a separate OS process via `subprocess.Popen()`. This means:
- Separate memory space (one user's variables can't leak to another)
- Separate file descriptor table
- Independent resource limits
- If one crashes, others are unaffected

#### Level 3: Import System Isolation
The `builtins.__import__` replacement ensures each execution has its own restricted import environment. Even if User A somehow modifies the import system, it only affects their process — not the Django server or other users' processes.

#### Level 4: Docker Container Isolation
All executions happen inside the Docker container, which provides:
- **PID namespace**: Processes inside can't see host processes
- **Network namespace**: Can be restricted to prevent outbound connections
- **Mount namespace**: Only sees mounted volumes, not the host filesystem
- **User namespace**: Runs as `appuser`, not root

```dockerfile
# Dockerfile
RUN groupadd -r appuser && useradd -r -g appuser -m appuser
# ... (setup)
USER appuser  # All subsequent commands run as this non-root user
```

#### Level 5: Non-Root Execution
```dockerfile
USER appuser
```
Even inside the container, code runs as `appuser` (not root). This means:
- Can't modify system files
- Can't install packages
- Can't change network configuration
- Can't access other users' data
- Limited to 100-200 processes (`limits.conf`)

#### What about concurrent executions?
If User A and User B submit code at the same time:
- Gunicorn worker 1 handles User A → creates `/tmp/secure_exec_xxx/` → subprocess A
- Gunicorn worker 2 handles User B → creates `/tmp/secure_exec_yyy/` → subprocess B
- Completely independent processes, directories, and resource limits
- No shared state between them

---

## 10. How Is Timeout Handled?

### Q: Walk through the complete timeout flow from user submission to TLE verdict.

**A:** Here's the exact sequence:

```
1. User clicks "Submit" → POST request to Django view
2. Django view calls secure_execute_code(language, code, input, expected_output)
3. validate_code_security() checks code statically (AST analysis)
4. create_secure_temp_directory() → /tmp/secure_exec_abc123/
5. User code is wrapped in restricted environment → written to main.py
6. subprocess.Popen() spawns a new OS process:
   - preexec_fn=set_resource_limits  (sets RLIMIT_CPU=5, RLIMIT_AS=128MB)
   - cwd=/tmp/secure_exec_abc123/
7. process.communicate(input=test_input, timeout=5) starts
   ├── Timer starts (5 seconds wall clock)
   ├── If process finishes → compare output → return AC/WA
   └── If timer expires → TimeoutExpired exception:
       ├── process.kill() → SIGKILL sent to process
       ├── return {'verdict': 'TLE', 'error': 'Time Limit Exceeded (5 seconds)'}
       └── finally: shutil.rmtree(temp_dir)  # Cleanup
```

#### Multiple timeout layers:

| Layer | Mechanism | Timeout | What it catches |
|-------|-----------|---------|-----------------|
| 1 | `subprocess.communicate(timeout=5)` | 5 seconds (wall clock) | Infinite loops, slow algorithms, sleep() calls |
| 2 | `resource.RLIMIT_CPU = 5` | 5 seconds (CPU time) | CPU-intensive infinite loops |
| 3 | Gunicorn `--timeout 120` | 120 seconds | Stuck workers (safety net) |
| 4 | Nginx `proxy_read_timeout 300` | 300 seconds | Hung upstream connections |

#### Why is the wall-clock timeout set to 5 seconds?

5 seconds is the standard in competitive programming (Codeforces uses 1-3 seconds). Most correctly-implemented algorithms finish in <1 second for typical input sizes. 5 seconds gives generous headroom while preventing abuse.

The value is configurable:
```python
# settings.py
CODE_EXECUTION = {
    'TIME_LIMIT': 5,  # seconds
    ...
}

# secure_execution.py
MAX_EXECUTION_TIME = 5  # seconds
```

#### What about compilation timeout?
For compiled languages (C++, Java), compilation itself has a separate timeout:
```python
# execution.py
compile_proc = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=10)
```
Compilation gets 10 seconds (JDK startup is slow). If compilation times out, the verdict is `CE` (Compilation Error), not `TLE`.

---

## 11. How Is Memory Monitored?

### Q: How do you prevent a user from consuming all server memory?

**A:** Memory is controlled at multiple levels:

#### Level 1: `RLIMIT_AS` — Virtual Address Space Limit
```python
# secure_execution.py
MAX_MEMORY_MB = 128  # MB

def set_resource_limits():
    memory_limit = MAX_MEMORY_MB * 1024 * 1024  # Convert to bytes
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
```

`RLIMIT_AS` limits the **total virtual address space** of the process. If the user's code tries to allocate more than 128MB:
```python
x = [0] * (10**9)  # Tries to allocate ~8GB
# Raises: MemoryError (Python) or malloc returns NULL (C++)
```

The kernel refuses the memory allocation. In Python, this raises `MemoryError`. In C/C++, `malloc()` returns `NULL`. The process crashes, and we return verdict `RE` (Runtime Error) or `MLE` (Memory Limit Exceeded).

#### Level 2: `RLIMIT_FSIZE` — File Size Limit
```python
resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_SIZE, MAX_FILE_SIZE))  # 1MB
```
This prevents a user from filling up disk space:
```python
with open('huge_file', 'w') as f:
    f.write('x' * 10**9)  # Blocked! Can't write more than 1MB
```
Note: This attack is also blocked by the import whitelist (can't use `open()`), but `RLIMIT_FSIZE` is a defense-in-depth measure.

#### Level 3: Output Size Limit
```python
# secure_execution.py - run_with_limits()
if len(out) > MAX_OUTPUT_SIZE:  # 1MB
    return {'verdict': 'RE', 'error': 'Output too large'}
```
If the program produces excessive output (e.g., printing in an infinite loop that happens to be slow enough to not hit the timeout), we cap the output at 1MB.

#### Level 4: Docker Container Memory Limits
Docker Compose can set container-level memory limits:
```yaml
# docker-compose.yml (could be added)
services:
  web:
    deploy:
      resources:
        limits:
          memory: 512M
```
This is a hard cap — if the container exceeds 512MB total (including all concurrent executions), the OOM killer terminates processes.

#### Level 5: Code Size Limit
```python
# secure_execution.py - validate_code_security()
if len(code) > MAX_FILE_SIZE:  # 1MB
    return False, "Code too long"
```
We reject code that's larger than 1MB before even trying to execute it. This prevents "zip bomb" style attacks where a small-looking code string expands to enormous size.

#### Why 128MB?
- Most competitive programming problems can be solved with <64MB
- 128MB gives headroom for language runtime overhead (Python itself uses ~20-30MB)
- It's the standard limit on platforms like Codeforces and LeetCode
- For Java, this needs to be higher because the JVM itself uses ~50-100MB

#### Memory bomb attacks and defenses:

| Attack | Defense |
|--------|---------|
| `x = [0] * 10**9` (huge list) | `RLIMIT_AS` → `MemoryError` |
| `x = 'a' * 10**9` (huge string) | `RLIMIT_AS` → `MemoryError` |
| `x = {}; while True: x[i] = [0]*1000` (gradual fill) | `RLIMIT_AS` → `MemoryError` when limit reached |
| Recursive calls (stack overflow) | `RLIMIT_AS` + Python's default recursion limit (1000) |
| Writing huge files to disk | `RLIMIT_FSIZE` + import whitelist blocks `open()` |
| Fork + allocate in each child | `RLIMIT_NPROC` prevents forking |

---

## 12. Security Deep-Dive

### Q: Walk me through all the security layers in your system.

**A:** Security is implemented as **defense in depth** — multiple independent layers so that if one fails, others catch the attack.

```
┌─────────────────────────────────────────────────────────┐
│                  SECURITY LAYERS                         │
│                                                          │
│  Layer 6: Docker Container (PID/Net/Mount namespace)     │
│  ┌──────────────────────────────────────────────────┐    │
│  │ Layer 5: Non-Root User (appuser, nproc limits)    │    │
│  │ ┌──────────────────────────────────────────────┐  │    │
│  │ │ Layer 4: OS Resource Limits (RLIMIT_*)       │  │    │
│  │ │ ┌──────────────────────────────────────────┐ │  │    │
│  │ │ │ Layer 3: Process Isolation (subprocess)   │ │  │    │
│  │ │ │ ┌──────────────────────────────────────┐  │ │  │    │
│  │ │ │ │ Layer 2: Runtime Sandbox              │  │ │  │    │
│  │ │ │ │ (safe_import, restricted builtins)    │  │ │  │    │
│  │ │ │ │ ┌──────────────────────────────────┐  │  │ │  │    │
│  │ │ │ │ │ Layer 1: Static Analysis (AST)   │  │  │ │  │    │
│  │ │ │ │ │ (import check, function check)   │  │  │ │  │    │
│  │ │ │ │ └──────────────────────────────────┘  │  │ │  │    │
│  │ │ │ └──────────────────────────────────────┘  │ │  │    │
│  │ │ └──────────────────────────────────────────┘ │  │    │
│  │ └──────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Q: What attacks can bypass your AST analysis?

**A:** Good question — AST analysis is the first line of defense but has known bypass vectors:

#### Bypass attempt 1: String-based import
```python
x = '__imp' + 'ort__'
getattr(__builtins__, x)('os')
```
**Defense**: The `FORBIDDEN_FUNCTIONS` list blocks `__import__`, and the `visit_Attribute` method blocks direct `__builtins__` access. The runtime `safe_import` hook would also catch this.

#### Bypass attempt 2: `exec` with encoded strings
```python
exec(bytes([105,109,112,111,114,116,32,111,115]).decode())  # "import os"
```
**Defense**: `exec` is in `FORBIDDEN_FUNCTIONS` — blocked by AST analysis.

#### Bypass attempt 3: Metaclass tricks
```python
class Evil(type):
    def __new__(cls, name, bases, attrs):
        # Do something evil in the metaclass
        pass
```
**Defense**: Even if a metaclass is created, it can't import forbidden modules because the runtime import hook is active.

#### Bypass attempt 4: Decorator-based code execution
```python
@(lambda f: __import__('os').system('whoami'))
def x(): pass
```
**Defense**: `__import__` is in `FORBIDDEN_FUNCTIONS` (caught by AST), and the runtime import hook blocks `os`.

#### Acknowledged weaknesses:
1. **C++ code** is harder to sandbox statically — we rely primarily on OS-level limits and Docker isolation for compiled languages
2. **Python's `ctypes`** could potentially bypass restrictions if it weren't in `ABSOLUTELY_FORBIDDEN`
3. **Resource exhaustion** within limits (e.g., using exactly 128MB in a legitimate algorithm) — this is by design; the limits are the contract

### Q: How do you handle injection in form inputs?

**A:**
- Django's ORM uses **parameterized queries** by default — prevents SQL injection (or in our case, MongoDB injection)
- Django templates **auto-escape** HTML by default — prevents XSS
- CSRF middleware generates and validates tokens on all POST requests
- `CodeExecutionSecurityMiddleware` logs suspicious code submission patterns
- `SecurityMiddleware` adds security headers (X-Frame-Options, X-Content-Type-Options, HSTS)

### Q: How is rate limiting implemented?

**A:** Two levels:

1. **Custom middleware** (`SecurityMiddleware`):
```python
def is_rate_limited(self, request):
    ip = self.get_client_ip(request)
    cache_key = f"rate_limit_{ip}"
    current_requests = cache.get(cache_key, 0)
    if current_requests >= 100:  # 100 requests per minute per IP
        return True
    cache.set(cache_key, current_requests + 1, 60)
    return False
```

2. **DRF throttling** for API endpoints:
```python
# settings.py
'DEFAULT_THROTTLE_RATES': {
    'anon': '100/hour',
    'user': '1000/hour'
}
```

---

## 13. Database & Data Modeling

### Q: Why MongoDB instead of PostgreSQL?

**A:**
1. **Flexible schema for test cases**: Problems have `test_cases_json` as a text field containing variable-length JSON arrays. MongoDB's document model handles this more naturally than relational tables.
2. **Learning objective**: I wanted to demonstrate proficiency with NoSQL databases and the `django-mongodb-backend` integration.
3. **Cloud-ready**: MongoDB Atlas provides a free tier with 512MB storage, sufficient for this project.

**Trade-off**: Django's ORM is primarily designed for SQL. Some features (complex aggregations, multi-table JOINs) are less mature with MongoDB backend. I mitigated this by keeping queries simple and using Django's ORM abstraction.

### Q: Explain your data model.

**A:**
```
UserProfile (1:1 with Django User)
├── role: setter | participant | admin
├── photo: ImageField with validators
└── user: OneToOneField → User

Problem
├── uuid: UUID4 (used in URLs instead of sequential IDs)
├── title, description, constraints, input_format, output_format
├── sample_input, sample_output (displayed to users)
├── test_cases_json: JSON array of {input, output} (hidden, used for judging)
├── difficulty: easy | medium | hard
├── tags: comma-separated string
└── created_by: ForeignKey → User

Solution
├── problem: ForeignKey → Problem
├── user: ForeignKey → User
├── code: TextField
├── language: python | cpp | java
├── verdict: AC | WA | TLE | CE | RE
├── execution_time: Float (seconds)
└── submitted_at: DateTimeField

Contest
├── uuid: UUID4
├── title, description
├── contest_type: rated | unrated | practice
├── start_time, end_time, duration
├── max_participants, is_public, registration_required, password
├── participants: ManyToMany → User (through ContestParticipant)
└── created_by: ForeignKey → User

ContestProblem (M2M bridge between Contest and Problem)
├── contest, problem
├── order: PositiveInteger (display order)
└── points: PositiveInteger (max score)

ContestParticipant (M2M bridge with extra fields)
├── contest, user
├── registered_at
└── start_time (for individual start times in virtual contests)

ContestSubmission
├── contest, participant, problem, solution
├── verdict, score, points_awarded
└── submitted_at

ContestAnnouncement
├── contest, title, content
├── created_by, created_at
└── is_important: Boolean
```

### Q: Why UUIDs instead of auto-increment IDs?

**A:**
1. **Security**: Sequential IDs leak information (total number of problems, rate of submissions). With UUIDs, you can't guess `/problem/abc-def-123/` by iterating.
2. **MongoDB compatibility**: MongoDB's `ObjectId` is already non-sequential. UUIDs are a natural fit.
3. **Merge-safe**: If you ever need to merge databases (dev + prod), UUIDs won't collide.

### Q: Why is `test_cases_json` a TextField and not a separate model?

**A:** Design decision with trade-offs:

**Why TextField (current approach):**
- Test cases are always loaded together (you need ALL of them to judge a submission)
- Fewer database queries (no JOIN/sub-query needed)
- Simpler to export/import problems (single JSON blob)
- MongoDB already stores documents natively as JSON

**Why a separate TestCase model might be better:**
- Individual test case CRUD (add/edit/delete one without touching others)
- Querying capabilities (find all test cases with specific input patterns)
- Referential integrity (no orphaned test cases)
- Better for very large test suites (hundreds of test cases per problem)

For the current scale (5-20 test cases per problem), TextField is simpler and sufficient.

---

## 14. API Design & REST Architecture

### Q: Tell me about your REST API design.

**A:** We use **Django REST Framework** with the following design:

#### ViewSets (Resource-based routing):
```python
# api_urls.py - URL patterns map to ViewSets
router.register(r'users', UserViewSet)
router.register(r'profiles', UserProfileViewSet)
router.register(r'problems', ProblemViewSet)
router.register(r'solutions', SolutionViewSet)
router.register(r'contests', ContestViewSet)
router.register(r'contest-problems', ContestProblemViewSet)
router.register(r'contest-participants', ContestParticipantViewSet)
router.register(r'contest-submissions', ContestSubmissionViewSet)
router.register(r'contest-announcements', ContestAnnouncementViewSet)
router.register(r'admin-settings', AdminSettingsViewSet)
```

#### Authentication:
- **JWT (JSON Web Tokens)** via `djangorestframework-simplejwt`
  - Access token: 1 hour lifetime
  - Refresh token: 7 days lifetime
  - Token rotation enabled (refresh token is rotated on each use)
- **Session authentication** as fallback for browser-based access

#### Custom Actions:
```python
# ContestViewSet has custom actions:
POST /api/contests/{id}/join/          # Join a contest
GET  /api/contests/{id}/standings/     # Get leaderboard
GET  /api/contests/{id}/my_submissions/ # User's contest submissions
GET  /api/contests/upcoming/           # Filter upcoming contests
GET  /api/contests/running/            # Filter running contests
GET  /api/contests/ended/              # Filter ended contests
```

#### Permission Model:
```python
def get_permissions(self):
    if self.action in ['list', 'retrieve']:  # Read operations
        permission_classes = [AllowAny]       # Public access
    else:                                     # Write operations
        permission_classes = [IsAuthenticated] # Require login
    return [permission() for permission in permission_classes]
```

#### Pagination:
```python
# StandardResultsSetPagination - 20 items per page
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
```

#### API Documentation:
Using `drf-spectacular` for automatic OpenAPI/Swagger documentation generation.

### Q: How do you prevent unauthorized API access?

**A:**
1. **JWT required** for write operations
2. **User-scoped queries**: Non-admin users can only see their own solutions:
   ```python
   def get_queryset(self):
       if not self.request.user.is_staff:
           queryset = queryset.filter(user=self.request.user)
   ```
3. **Throttling**: 100 requests/hour for anonymous, 1000/hour for authenticated
4. **CORS restrictions**: Only allowed origins can make cross-origin requests

---

## 15. Authentication & Authorization

### Q: Explain your role-based access control system.

**A:** Three roles with a custom decorator:

| Role | Permissions |
|------|------------|
| `participant` | View/solve problems, submit solutions, join contests |
| `setter` | All participant perms + create/edit problems |
| `admin` | All perms + manage roles, create contests, admin settings |

The `role_required` decorator:
```python
def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            user_profile = UserProfile.objects.get(user=request.user)
            if user_profile.role not in allowed_roles:
                return render(request, 'core/forbidden.html', status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

Usage:
```python
@role_required(['setter', 'admin'])  # Only setters and admins can add problems
def add_problem(request): ...

@role_required(['participant', 'setter', 'admin'])  # All roles can view problems
def problem_list(request): ...

@staff_member_required  # Django's built-in — only superusers/staff
def manage_roles(request): ...
```

### Q: Why not use Django's built-in groups/permissions?

**A:** Django's permission system is powerful but designed for CRUD operations on models (add_problem, change_problem, delete_problem). My requirements were simpler — three role tiers with clear hierarchy. A custom decorator is:
1. More readable (you see `@role_required(['admin'])` and immediately understand)
2. Fewer database queries (one UserProfile lookup vs. many permission checks)
3. Easier to extend (e.g., add "moderator" role without touching Django admin)

For a larger team, I'd migrate to Django's groups + object-level permissions (using `django-guardian`).

---

## 16. AI Code Review Integration

### Q: How does the AI code review feature work?

**A:** The system uses **Groq's API** with the **LLaMA 3.3-70b-versatile** model to generate structured code reviews.

#### Flow:
1. User clicks "AI Review" button → AJAX POST with the code
2. Backend checks if AI is enabled (`AdminSettings.ai_review_enabled`)
3. If enabled, sends code to Groq API with a structured prompt:
   ```python
   prompt = """
   Review this code and return JSON with keys:
   logic, efficiency, clarity, best_practices
   """
   ```
4. Parses the response (JSON or text fallback)
5. Returns structured feedback to the frontend

#### Challenges & Solutions:

**Challenge: LLM output is non-deterministic**
The model sometimes returns markdown-wrapped JSON, extra text, or malformed JSON.

**Solution: Multi-strategy parser**
```python
# Strategy 1: Regex extract JSON
json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

# Strategy 2: Section-based text parsing
sections = re.split(r'\d+\.\s*(Logic|Efficiency|Clarity|Best Practices)', text)

# Strategy 3: Line-by-line keyword extraction
for line in lines:
    if 'logic' in line.lower():
        current_section = 'logic'
```

**Challenge: API failures**
Groq API can timeout, rate limit, or return errors.

**Solution: Retry with fallback**
```python
def generate_code_review_robust(code):
    for attempt in range(2):  # Max 2 attempts
        result = generate_code_review(code)
        if result['success']:
            return result
        time.sleep(1)  # Brief delay before retry
    return fallback_response
```

#### Admin Control:
AI review can be toggled globally by admins:
```python
class AdminSettings(models.Model):
    ai_review_enabled = models.BooleanField(default=True)
```
This is checked before every AI review request. If disabled, users see "AI review is currently disabled by administrator."

---

## 17. Contest System Design

### Q: How does the contest system work?

**A:** The contest system supports three types: **rated**, **unrated**, and **practice** contests.

#### Contest Lifecycle:
```
UPCOMING → RUNNING → ENDED
(registration)  (submissions)  (results frozen)
```

The status is computed dynamically:
```python
@property
def status(self):
    now = timezone.now()
    if now < self.start_time:
        return 'upcoming'
    elif now <= self.end_time:
        return 'running'
    else:
        return 'ended'
```

#### Scoring:
- Each problem has configurable points (default: 100)
- Partial scoring based on test cases passed: `score = (passed / total) * 100`
- Standings sorted by total points (descending), then by submission count (ascending, as tiebreaker)

#### Registration:
- Optional password-protected contests
- Maximum participant limit
- Registration required flag

#### Real-Time Features:
- Timer API endpoint for countdown synchronization
- Live standings page with rank calculation
- Contest announcements with importance flags

### Q: How do you handle ties in contest standings?

**A:** Current tiebreaker: fewer total submissions = higher rank.
```python
standings.sort(key=lambda x: (-x['total_points'], x['submissions_count']))
```
This encourages clean submissions over brute-force trial-and-error. In a production system, I'd add:
- Submission time as a secondary tiebreaker (earlier = better)
- Penalty time for wrong submissions (like Codeforces's system)

---

## 18. Deployment & DevOps

### Q: Walk me through your deployment pipeline.

**A:**

#### Infrastructure:
- **Server**: VPS/Cloud instance
- **Domain**: `myoj.work.gd` with Let's Encrypt SSL
- **Architecture**: Docker Compose with 2 services (web + optional nginx)

#### Deployment Script (`deploy.sh`):
```bash
#!/bin/bash
docker-compose down          # Stop existing containers
docker-compose build         # Build new images
docker-compose up -d         # Start in detached mode
sleep 10                     # Wait for services
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py fix_media_permissions
docker-compose exec web python manage.py collectstatic --noinput
docker-compose restart nginx
```

#### Nginx Configuration:
- HTTP → HTTPS redirect
- SSL with TLS 1.2/1.3, strong cipher suite
- Static file serving with 1-year cache
- Media file serving with type restrictions
- Security headers (HSTS, X-Frame-Options, X-Content-Type-Options)
- Gzip compression
- Reverse proxy to Gunicorn

#### Gunicorn Configuration:
```dockerfile
CMD ["gunicorn", "online_judge.wsgi:application",
     "--bind", "0.0.0.0:8000",
     "--workers", "2",              # 2 worker processes
     "--max-requests", "1000",       # Restart worker after 1000 requests (prevent memory leaks)
     "--max-requests-jitter", "100", # Randomize restart to avoid all workers restarting simultaneously
     "--timeout", "120",             # Kill worker if request takes >120s
     "--keep-alive", "2"]            # Keep-alive timeout
```

### Q: Why Gunicorn and not Daphne/Uvicorn?

**A:** Gunicorn is a **WSGI** server (synchronous). Daphne and Uvicorn are **ASGI** servers (async). Since Django's views are synchronous and I don't use WebSockets or async views, Gunicorn is simpler and more mature. If I added Django Channels for real-time features, I'd switch to Daphne or use Uvicorn with `--interface wsgi` mode.

### Q: How do you handle static files in production?

**A:**
1. `python manage.py collectstatic` gathers all static files into `/app/staticfiles/`
2. **WhiteNoise** serves them directly from Django in simple deployments:
   ```python
   STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
   ```
3. In the full production setup, **Nginx** serves static files directly (bypassing Django entirely):
   ```nginx
   location /static/ {
       alias /app/staticfiles/;
       expires 1y;
       add_header Cache-Control "public, immutable";
   }
   ```
   This is faster because Nginx serves files without Python overhead.

---

## 19. Performance & Scalability

### Q: What are the performance bottlenecks in your system?

**A:**

| Bottleneck | Current Impact | Solution |
|-----------|---------------|----------|
| Synchronous code execution | Blocks worker for 5 seconds | Celery + Redis async queue |
| N+1 queries in standings | Slow leaderboard for large contests | `select_related()` / `prefetch_related()` (partially done) |
| In-memory cache (LocMemCache) | Not shared between workers, lost on restart | Redis cache |
| No CDN for static files | Higher latency for global users | CloudFlare / AWS CloudFront |
| Single database | MongoDB Atlas free tier limits | Sharding / read replicas |
| Two Gunicorn workers | Max 2 concurrent requests | Increase workers or use async |

### Q: How would you scale this to 10,000 concurrent users?

**A:**
1. **Code execution**: Move to a **microservice architecture** — separate "Judge Service" with its own container pool, auto-scaling based on queue depth. Each container handles one execution, gets destroyed and recreated (like AWS Lambda).

2. **Database**: 
   - Read replicas for problem listings, standings, user profiles
   - Write to primary for submissions
   - Redis cache for hot data (active contest standings, problem metadata)

3. **Web tier**:
   - Horizontal scaling with multiple Django instances behind a load balancer
   - Sticky sessions or JWT (already have JWT) for stateless scaling
   - CDN for static/media files

4. **Queue**: 
   - Celery with Redis broker, multiple worker pools
   - Priority queues: contest submissions > practice submissions > AI reviews
   - Dead letter queue for failed executions

5. **Real-time**: 
   - Django Channels with Redis channel layer for WebSocket support
   - Live leaderboard updates via pub/sub

---

## 20. Testing Strategy

### Q: How is the project tested?

**A:** The project has API tests in `tests_api.py`:

```python
# tests_api.py - Tests REST API endpoints
class APITestCase(TestCase):
    def test_problem_list(self): ...
    def test_problem_create(self): ...
    def test_solution_submit(self): ...
    def test_contest_join(self): ...
```

#### What I'd add for production:

1. **Unit tests** for `secure_execution.py`:
   - Test that `import os` is blocked
   - Test that `while True: pass` returns TLE
   - Test that `[0]*10**9` returns MLE/RE
   - Test that valid competitive programming code returns AC

2. **Integration tests**:
   - Submit code through the full Django view → check database → verify verdict
   - Contest workflow: create → register → submit → check standings

3. **Security tests**:
   - Fuzz the code input with known attack payloads
   - Test all import bypass attempts
   - Test path traversal in file uploads

4. **Load tests** (using Locust or k6):
   - 100 concurrent submissions
   - Contest start thundering herd
   - API rate limit verification

---

## 21. What Would You Improve?

### Q: If you had more time, what would you change?

**A:**

#### Must-Have Improvements:
1. **Async code execution** with Celery + Redis — the single biggest architectural improvement
2. **Docker-in-Docker** or **gVisor** for code execution — running each submission in its own disposable container for true isolation
3. **WebSocket support** for real-time contest features (live leaderboard, instant verdict notifications)
4. **Comprehensive test suite** — unit, integration, security, and load tests

#### Nice-to-Have Improvements:
5. **Language support**: Currently only Python execution works end-to-end with security sandboxing. C++/Java execution exists but without AST-level security analysis.
6. **Plagiarism detection**: Compare submissions using MOSS or Dolos for contest integrity
7. **Editorial system**: Problem setters can add solution explanations after contests
8. **Rating system**: Elo-based rating for rated contests (like Codeforces)
9. **Virtual contests**: Allow users to participate in past contests as if they were live
10. **Custom test cases**: Let users run code against their own input (not just sample cases)
11. **Split frontend**: React/Vue SPA consuming the REST API for a richer UX
12. **Monitoring & alerting**: Prometheus + Grafana for system metrics, PagerDuty for incidents

#### Architecture Changes:
13. **Microservices**: Split into Auth Service, Problem Service, Judge Service, Contest Service
14. **Event-driven**: Use events (submission.created → judge → verdict.updated → notify) instead of synchronous calls
15. **Kubernetes**: Replace Docker Compose with K8s for auto-scaling, self-healing, rolling deployments

---

## 22. Behavioral / Soft-Skill Questions

### Q: Why did you build this project?

**A:** I built this to solve a real problem I experienced as a competitive programming enthusiast — most online judges are either too complex to self-host (like DOMjudge) or too basic (no contests, no AI review). I wanted to build a platform that:
1. Demonstrates full-stack development skills (Django, REST API, Docker, MongoDB, AI integration)
2. Solves the hardest problem in competitive programming platforms: **secure code execution**
3. Includes production-ready features: SSL, rate limiting, security headers, deployment pipeline

### Q: What was the hardest bug you fixed?

**A:** Profile photos not showing on the deployed site. The images uploaded correctly to the Django media directory, but Nginx couldn't serve them because:
1. The Docker volume wasn't mounted correctly for the media directory
2. Nginx didn't have the right alias for the media path
3. File permissions were wrong (uploaded as root, Nginx ran as nginx user)

I had to:
- Fix the Docker volume mounts
- Update Nginx config with correct alias paths and file type restrictions
- Create a management command (`fix_media_permissions`) to fix existing files
- Add proper `chown` and `chmod` in the Dockerfile

### Q: How do you approach debugging?

**A:** My approach:
1. **Reproduce**: Can I consistently trigger the bug?
2. **Isolate**: Is it frontend, backend, database, or infrastructure?
3. **Logs**: Check Django logs, Nginx logs, Docker logs
4. **Simplify**: Remove complexity until the bug disappears, then add back
5. **Fix & verify**: Fix the root cause (not symptoms), write a test to prevent regression

### Q: How do you handle security vs. usability trade-offs?

**A:** Example: My initial import whitelist was too restrictive — it blocked `collections.defaultdict` which is essential for competitive programming. Users couldn't solve graph problems.

My approach:
1. Start restrictive (block everything)
2. Collect user feedback on what's blocked
3. Audit each request — is this module genuinely safe?
4. Add to whitelist with specific function-level granularity
5. Monitor for abuse

The result is the `ALLOWED_IMPORTS` dictionary in `secure_execution.py` — it allows 15+ modules with specific safe functions, while blocking 30+ dangerous modules.

### Q: What did you learn from this project?

**A:**
1. **Security is hard**: There's always another attack vector. Defense in depth is the only strategy.
2. **Trade-offs are everywhere**: MongoDB vs. PostgreSQL, sync vs. async, security vs. usability — every choice has costs.
3. **DevOps matters**: Getting the app running locally is 20% of the work. Deploying securely with Docker, Nginx, SSL, and proper monitoring is 80%.
4. **AI integration is messy**: LLM outputs are non-deterministic. You need robust parsing, fallbacks, and error handling.
5. **Start simple, then iterate**: My first version used `exec()` (terrible idea). The current version has 6 security layers. Each iteration was driven by identifying a real vulnerability.

---

## Bonus: Rapid-Fire Questions

| Question | Short Answer |
|----------|-------------|
| What's your tech stack? | Django 6.0, MongoDB, DRF, Docker, Nginx, Gunicorn, Groq AI |
| How many languages do you support? | Python (full sandbox), C++/Java/JS (basic execution) |
| What's the time limit for code? | 5 seconds wall-clock, 5 seconds CPU |
| What's the memory limit? | 128MB |
| How do you store test cases? | JSON array in a TextField on the Problem model |
| How do you serve static files? | WhiteNoise + Nginx |
| What database do you use? | MongoDB (via django-mongodb-backend) hosted on Atlas |
| How do you handle authentication? | Session-based (web) + JWT (API) |
| How many concurrent users can you handle? | ~2 (Gunicorn workers), scalable to more with async |
| What AI model do you use? | LLaMA 3.3-70b-versatile via Groq API |
| How do you deploy? | Docker Compose on VPS with deploy.sh |
| How is SSL configured? | Let's Encrypt with auto-renewal via Certbot |
| What's the biggest security risk? | Code execution — mitigated with 6 security layers |
| What would you add first? | Celery + Redis for async code execution |
| What's your primary key type? | MongoDB ObjectId (ObjectIdAutoField) |

---

> **Last updated**: July 2026
> **Project**: Online Judge (myoj.work.gd)
> **Author**: Built as a full-stack portfolio project demonstrating secure code execution, contest management, REST API design, AI integration, and production deployment.
