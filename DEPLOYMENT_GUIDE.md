# 🚀 Secure Deployment Guide

This guide outlines how to deploy the Online Judge platform securely using Docker, Nginx, and Cloudinary.

## 🏗️ Architecture Overview

- **Web Server:** Gunicorn serving the Django application
- **Reverse Proxy:** Nginx for request routing and rate-limiting
- **Database:** MongoDB (via django-mongodb-backend)
- **Media Storage:** Cloudinary (Production) or Local Volume (Development)
- **Static Files:** WhiteNoise

## 🔧 Prerequisites

- Docker and Docker Compose installed
- A MongoDB instance (e.g., MongoDB Atlas)
- A Cloudinary account (optional, for media storage)
- A Groq API key (optional, for AI features)

## 🚀 Production Deployment (Docker)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/JPisOP007/online-judge.git
   cd online-judge
   ```

2. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and configure the following:
   ```env
   # Security
   DJANGO_SECRET_KEY=generate-a-very-long-secure-key
   DEBUG=False
   DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

   # Database
   MONGODB_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/online_judge?retryWrites=true&w=majority

   # Media (Cloudinary)
   CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>
   ```

3. **Build and Start Services:**
   ```bash
   docker-compose down
   docker-compose build
   docker-compose up -d
   ```

4. **Initialize the Database:**
   ```bash
   # Run migrations
   docker-compose exec web python manage.py migrate
   
   # Collect static files
   docker-compose exec web python manage.py collectstatic --noinput
   ```

## ☁️ Note on PaaS Deployment (Render)

The public instance runs on Render from this repository's `Dockerfile`, not via
`docker-compose`. Two differences matter:

- Render runs **unprivileged containers**, so `nsjail` and `sudo -u sandboxuser`
  are unavailable and submissions execute as the application user under
  `setrlimit` alone. See `SECURITY_FIXES.md` for what that means for the threat
  model.
- There is **no Nginx layer**; Gunicorn is addressed directly and static files
  are served by WhiteNoise.

Set `REDIS_URL` on the service. It backs both Celery and the cache used for
rate limiting; without it the cache silently falls back to per-process memory
and the rate limit is enforced per worker rather than globally.

---

## 🛡️ Security Configuration Checklist

Before exposing the application to the public, verify the following:

- [ ] `DEBUG` is set to `False` in `.env`.
- [ ] `DJANGO_SECRET_KEY` is a strong, unique value and not the default.
- [ ] Nginx is configured to enforce HTTPS (if using custom domains).
- [ ] MongoDB connection strings are secure and the database restricts IP access.
- [ ] The `appuser` in the Dockerfile is correctly utilized (running without root privileges).

## 📁 Media Storage (Local vs. Cloudinary)

If you do NOT provide a `CLOUDINARY_URL`, the application falls back to storing profile photos on the local disk.

**For Local Media (Development only):**
- Media files are stored in `media/profile_photos/`.
- You must ensure the Nginx container has access to the shared `media` volume.
- Run `docker-compose exec web python manage.py fix_media_permissions` if you encounter permission issues reading uploaded photos.

**For Cloudinary (Recommended for Production):**
- The app automatically uploads and serves profile photos via the Cloudinary CDN.
- No local media volume synchronization is required.

## 🔍 Monitoring and Logs

To monitor the health and security of your deployment:

```bash
# View all logs
docker-compose logs -f

# View specifically web application errors
docker-compose logs -f web

# View Nginx access and error logs
docker-compose logs -f nginx
```

Security events (blocked code executions, rate-limit trips) are written to stdout under the `core.security` logger, so they appear in `docker-compose logs` and in your platform's log stream. There is no log file: container disks are ephemeral.