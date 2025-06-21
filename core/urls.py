from django.urls import path
from . import views

urlpatterns = [
    # Authentication and Basic Views
    path('', views.home, name='home'),  # Homepage
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Problem Management
    path('add-problem/', views.add_problem, name='add_problem'),
    path('problems/', views.problem_list, name='problem_list'),  
    path('problem/<uuid:problem_id>/', views.problem_detail, name='problem_detail'),  
    path('submit/<uuid:problem_id>/', views.submit_solution, name='submit_solution'),
    
    # User Management and Profile
    path('manage-roles/', views.manage_roles, name='manage_roles'),
    path('profile/', views.profile_view, name='profile'),
    path('submission/<int:submission_id>/', views.submission_detail, name='submission_detail'),
    
    # Contest Management
    path('contests/', views.contest_list, name='contest_list'),  
    path('contest/<uuid:contest_uuid>/', views.contest_detail, name='contest_detail'),  
    path('contest/<uuid:contest_uuid>/problems/', views.contest_problems, name='contest_problems'),  
    path('contest/<uuid:contest_uuid>/problem/<uuid:problem_uuid>/', views.contest_problem_detail, name='contest_problem_detail'),  
    path('contest/<uuid:contest_uuid>/standings/', views.contest_standings, name='contest_standings'),  
  # Contest announcements
    path('contest/<uuid:contest_uuid>/announcements/', views.contest_announcements, name='contest_announcements'),
    path('contest/<uuid:contest_uuid>/announcements/create/', views.create_announcement, name='create_announcement'),
    path('contest/<uuid:contest_uuid>/announcements/<int:announcement_id>/edit/', views.edit_announcement, name='edit_announcement'),
    path('contest/<uuid:contest_uuid>/announcements/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),
    # Contest Administration (Staff Only)
    path('create-contest/', views.create_contest, name='create_contest'),  
    path('contest/<uuid:contest_uuid>/edit/', views.edit_contest, name='edit_contest'),  
    
    # API Endpoints
    path('api/contest/<uuid:contest_uuid>/timer/', views.contest_timer_api, name='contest_timer_api'),  
]