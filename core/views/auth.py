from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.conf import settings
from functools import wraps
from django.db import IntegrityError
from core.models import (
    UserProfile, Problem, Solution, Contest, ContestParticipant,
    ContestProblem, ContestSubmission, ContestAnnouncement
)
from core.forms import (
    SubmitSolutionForm, ProblemForm, UserProfileForm, ContestForm,
    ContestRegistrationForm, AnnouncementForm
)
from core.utils.secure_execution import secure_execute_code, secure_evaluate_submission
import json

def role_required(allowed_roles):
    """
    Decorator to check if user has required role
    Fixed version with proper authentication handling
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # First check if user is authenticated
            if not request.user.is_authenticated:
                messages.error(request, 'Please login to access this page.')
                return redirect('login')
            
            # Get or create user profile
            try:
                user_profile = UserProfile.objects.get(user=request.user)
                user_role = user_profile.role
            except UserProfile.DoesNotExist:
                # Create default profile if it doesn't exist
                user_profile = UserProfile.objects.create(
                    user=request.user, 
                    role='participant'
                )
                user_role = 'participant'
            
            # Check if user has required role
            if user_role not in allowed_roles:
                messages.error(request, f'Access denied. Required roles: {", ".join(allowed_roles)}')
                return render(request, 'core/forbidden.html', {'required_roles': allowed_roles}, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def home(request):
    return render(request, 'core/home.html')

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email', '')  # Optional

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'core/register.html')

        try:
            user = User.objects.create_user(username=username, password=password, email=email)

            # Safe profile creation
            UserProfile.objects.get_or_create(user=user, defaults={'role': 'participant'})

            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')

        except IntegrityError as e:
            messages.error(request, f'Registration failed: {str(e)}')

    return render(request, 'core/register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            # Create profile if it doesn't exist
            UserProfile.objects.get_or_create(user=user, defaults={'role': 'participant'})
            messages.success(request, f'Welcome back, {user.username}!')
            
            # Redirect to next page if specified
            next_page = request.GET.get('next', 'home')
            return redirect(next_page)
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')

