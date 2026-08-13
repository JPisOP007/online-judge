"""
Security middleware for additional protection
"""
import logging
import time
from django.http import HttpResponseForbidden
from django.core.cache import cache
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('core.security')

# Static and media requests should not count against a user's budget. This
# middleware runs before WhiteNoise, so every asset on a page was consuming
# one of the 100 allowed requests - a handful of page loads could lock a
# legitimate visitor out.
RATE_LIMIT_EXEMPT_PREFIXES = ('/static/', '/media/')
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW_SECONDS = 60

# Content-Security-Policy.
#
# 'unsafe-inline' is unavoidable for now: the templates carry inline <style>
# blocks, hundreds of style="" attributes and inline <script> blocks. Removing
# it means nonce-ing every one of them, which is a separate piece of work.
#
# The policy still earns its place without it. Scripts and styles can only be
# fetched from hosts we actually use, connect-src stops a successful injection
# from exfiltrating anywhere, object-src and base-uri close two common
# redirection tricks, and form-action stops a planted form posting credentials
# off-site. Sanitising markdown with DOMPurify remains the primary XSS defence.
#
# Hosts, all verified against the templates:
#   cdn.jsdelivr.net      Bootstrap, Bootstrap Icons (CSS + webfonts), marked, DOMPurify
#   cdnjs.cloudflare.com  CodeMirror
#   fonts.googleapis.com  Google Fonts stylesheet
#   fonts.gstatic.com     the font files that stylesheet references
#   res.cloudinary.com    profile photos, when CLOUDINARY_URL is configured
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
    "https://fonts.googleapis.com",
    "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net",
    # jsdelivr also serves the Swagger UI favicon on /api/schema/swagger-ui/.
    "img-src 'self' data: https://res.cloudinary.com https://cdn.jsdelivr.net",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
])


class SecurityMiddleware(MiddlewareMixin):
    """
    Custom security middleware for rate limiting and request validation
    """

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        # Rate limiting
        if not request.path.startswith(RATE_LIMIT_EXEMPT_PREFIXES) and self.is_rate_limited(request):
            logger.warning(f"Rate limit exceeded for {self.get_rate_limit_key(request)}")
            return HttpResponseForbidden("Rate limit exceeded")

        # Request size validation
        if hasattr(request, 'META') and 'CONTENT_LENGTH' in request.META:
            try:
                content_length = int(request.META['CONTENT_LENGTH'])
                if content_length > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
                    logger.warning(f"Large request from IP: {self.get_client_ip(request)}, size: {content_length}")
                    return HttpResponseForbidden("Request too large")
            except (ValueError, TypeError):
                pass
        
        return None
    
    def process_response(self, request, response):
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.setdefault('Content-Security-Policy', CONTENT_SECURITY_POLICY)

        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        return response
    
    def get_client_ip(self, request):
        """Get the real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_rate_limit_key(self, request):
        """Identify the caller for rate limiting.

        Authenticated users are keyed by primary key, which cannot be spoofed.
        Anonymous callers fall back to IP. Note that X-Forwarded-For is
        client-supplied; behind a proxy that appends rather than replaces it,
        the leftmost entry can be forged, so IP-based limiting is best-effort.
        """
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            return f"user:{user.pk}"
        return f"ip:{self.get_client_ip(request)}"

    def is_rate_limited(self, request):
        """Fixed-window rate limiting, shared across workers via the cache.

        The previous get()/set() pair was not atomic and, on LocMemCache, was
        also per-process: each gunicorn worker kept its own counter and every
        restart reset them. Uses add() then incr(), which Redis performs
        atomically.
        """
        cache_key = f"rate_limit_{self.get_rate_limit_key(request)}"

        try:
            if cache.add(cache_key, 1, RATE_LIMIT_WINDOW_SECONDS):
                return False
            return cache.incr(cache_key) > RATE_LIMIT_REQUESTS
        except ValueError:
            # The key expired between add() and incr(); treat as a new window.
            return False
        except Exception as exc:
            # Never take the site down because the cache backend is unreachable.
            logger.warning(f"Rate limit check skipped, cache unavailable: {exc}")
            return False

class CodeExecutionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to monitor and log code execution attempts
    """
    
    def process_request(self, request):
        # Log code submission attempts
        if request.path.startswith('/problem/') and request.method == 'POST':
            ip = self.get_client_ip(request)
            user = getattr(request, 'user', None)
            username = user.username if user and user.is_authenticated else 'anonymous'
            
            logger.info(f"Code submission attempt - IP: {ip}, User: {username}, Path: {request.path}")
            
            # Additional monitoring for suspicious patterns
            if hasattr(request, 'POST'):
                source_code = request.POST.get('source_code', '')
                if self.contains_suspicious_patterns(source_code):
                    logger.warning(f"Suspicious code submission - IP: {ip}, User: {username}")
        
        return None
    
    def get_client_ip(self, request):
        """Get the real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def contains_suspicious_patterns(self, code):
        """Check for suspicious patterns in code"""
        if not code:
            return False
        
        suspicious_patterns = [
            'import os',
            'import subprocess',
            'import sys',
            '__import__',
            'eval(',
            'exec(',
            'system(',
            'popen(',
            'Runtime.getRuntime',
            'ProcessBuilder',
        ]
        
        code_lower = code.lower()
        for pattern in suspicious_patterns:
            if pattern.lower() in code_lower:
                return True
        
        return False