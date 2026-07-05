# System Design & Interview Q&A

This document outlines the architectural decisions and system design of the Online Judge platform.

## 1. Code Execution Architecture

**Q: How do you safely execute untrusted user code?**
A: We use a multi-layered sandbox approach:
- **Privilege Separation:** The web application runs as `appuser`. When executing untrusted code, we spawn a subprocess using `sudo -u sandboxuser`. The `sandboxuser` has zero read access to the application directory (`/app`), preventing exfiltration of secrets like `.env`.
- **Resource Limits (OS Level):** We use Python's `resource` module inside `preexec_fn` (or PAM limits on the host) to cap `RLIMIT_AS` (memory), `RLIMIT_NPROC` (fork bombs), and CPU time.
- **Environment Scrubbing:** The execution subprocess is given an empty environment dictionary (`env={'PATH': '/bin:/usr/bin'}`).
- **AST Parsing (Python):** For Python, we statically analyze the Abstract Syntax Tree before execution to block dangerous imports (like `os` and `subprocess`) and built-ins.

## 2. Asynchronous Processing

**Q: What happens when 100 users submit code at the exact same time?**
A: Judging code synchronously inside a Django view blocks the Gunicorn worker for up to 5 seconds per test case. With only a few workers, the site would go down immediately.
To solve this, we use **Celery** and **Redis**.
1. The Django view simply saves a `Solution` object with status `Pending` and pushes a task to the Redis queue.
2. A pool of background Celery workers picks up the tasks and runs the sandbox.
3. The frontend polls the API (or uses WebSockets) to get the final verdict once the Celery task completes.

## 3. Database Choice

**Q: Why use PostgreSQL instead of MongoDB?**
A: An Online Judge is highly relational. A `User` has many `Contests`, which have many `Problems`, which have many `Submissions`.
Initially, the project used MongoDB via `django-mongodb-backend` to learn NoSQL. However, MongoDB lacks native referential integrity (foreign keys) and ACID-compliant multi-table transactions (without replica sets), making it the wrong choice for heavily relational data. Migrating to PostgreSQL resolves this and aligns with standard Django best practices.

## 4. Scalability

**Q: How does the system scale?**
A: 
- **Stateless Web Nodes:** The Django application is stateless. User sessions are stored in JWTs and the cache.
- **Decoupled Workers:** The code execution (Celery workers) is decoupled from the web application. We can scale the worker nodes independently based on the queue depth in Redis.
- **CDN:** Static files are served via WhiteNoise with caching headers, and media (profile photos) are offloaded to Cloudinary CDN, removing the need for a shared persistent volume for user uploads.
