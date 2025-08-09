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

class SecurityMiddleware(MiddlewareMixin):
    """
    Custom security middleware for rate limiting and request validation
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Rate limiting
        if self.is_rate_limited(request):
            logger.warning(f"Rate limit exceeded for IP: {self.get_client_ip(request)}")
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
    
    def is_rate_limited(self, request):
        """Simple rate limiting implementation"""
        ip = self.get_client_ip(request)
        cache_key = f"rate_limit_{ip}"
        
        # Get current request count
        current_requests = cache.get(cache_key, 0)
        
        # Rate limit: 100 requests per minute
        if current_requests >= 100:
            return True
        
        # Increment counter
        cache.set(cache_key, current_requests + 1, 60)  # 60 seconds timeout
        
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