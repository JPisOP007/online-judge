# 🛠️ API & Architecture Enhancements

This document highlights the recent architectural enhancements made to the Online Judge backend to ensure it is production-ready, well-documented, and easily integrable with external frontend clients.

## 1. Environment Configuration & Secrets Management

To adhere to Twelve-Factor App principles, all configuration and secrets have been decoupled from the codebase:
- **`.env` Integration:** The application utilizes `python-dotenv` to load secrets from a local `.env` file (which is `git-ignored`).
- **Dynamic Configuration:** Variables such as `DJANGO_SECRET_KEY`, `MONGODB_URI`, `GROQ_API_KEY`, and `CORS_ALLOWED_ORIGINS` are dynamically loaded at runtime.
- **Docker Integration:** The `docker-compose.yml` file is configured to pass through environment variables to the containers, ensuring that secrets are never baked into Docker images.

## 2. Interactive API Documentation (OpenAPI/Swagger)

To facilitate frontend integration and third-party API usage, we have integrated `drf-spectacular` to automatically generate OpenAPI 3.0 schemas.

- **Auto-Syncing:** The documentation is generated directly from the Django REST Framework serializers and views, ensuring it never goes out of date.
- **Interactive UI:** Available at `/api/schema/swagger-ui/`, developers can authenticate via JWT and test endpoints directly from the browser.
- **ReDoc Support:** An alternative, clean reading view is available at `/api/schema/redoc/`.

## 3. Cross-Origin Resource Sharing (CORS)

To support decoupled frontend architectures (e.g., React, Vue, or Next.js applications hosted on different domains), we have implemented strict but flexible CORS policies.

- **`django-cors-headers` Integration:** Configured to intercept and validate preflight requests.
- **Environment-Based Origins:** Allowed origins are not hardcoded. They are read from the `CORS_ALLOWED_ORIGINS` environment variable, allowing different rules for development, staging, and production environments.
- **Credential Support:** `CORS_ALLOW_CREDENTIALS` is enabled to support cookie-based sessions if JWT is not used.

## 4. Scalable Media & Static File Serving

- **WhiteNoise Integration:** Static files (CSS, JS, Admin UI assets) are collected and served directly by the Gunicorn application using WhiteNoise, complete with compression and far-future caching headers.
- **Cloudinary Storage:** Media files (like User Profile Photos) can be automatically uploaded to and served from Cloudinary CDN by setting the `CLOUDINARY_URL` variable, bypassing the need for shared persistent volumes across container replicas.

## Next Steps for Frontend Integrators
If you are building a frontend for this platform:
1. Check the interactive Swagger UI at `/api/schema/swagger-ui/` for request/response payloads.
2. Ensure your frontend domain is added to the `CORS_ALLOWED_ORIGINS` environment variable on the server.
3. Authenticate using the `/api/auth/token/` endpoint and pass the resulting token in the `Authorization: Bearer <token>` header for subsequent requests.
