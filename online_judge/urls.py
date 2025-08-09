# main_project/urls.py - FIXED VERSION
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # This includes ALL your core URLs
]

# Media files configuration for development and production
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Alternative approach if you prefer:
# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('', include('core.urls')),
# ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)