from django.contrib import admin
from django.urls import path , include 
from core import views
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', include('core.urls')),  
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
