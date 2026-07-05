from django.urls import path
from core.views import auth, problems, profiles, contests

urlpatterns = [
    # Authentication and Basic Views
    path('', auth.home, name='home'),  # Homepage
    path('register/', auth.register, name='register'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    
    # Problem Management
    path('add-problem/', problems.add_problem, name='add_problem'),
    path('problems/', problems.problem_list, name='problem_list'),  
    path('problem/<uuid:problem_id>/', problems.problem_detail, name='problem_detail'),  
    path('submit/<uuid:problem_id>/', problems.submit_solution, name='submit_solution'),
    path('submission/<str:submission_id>/', problems.submission_detail, name='submission_detail'),
    
    # User Management and Profile
    path('manage-roles/', profiles.manage_roles, name='manage_roles'),
    path('profile/', profiles.profile_view, name='profile'),
    
    # Contest Management
    path('contests/', contests.contest_list, name='contest_list'),  
    path('contest/<uuid:contest_uuid>/', contests.contest_detail, name='contest_detail'),  
    path('contest/<uuid:contest_uuid>/problems/', contests.contest_problems, name='contest_problems'),  
    path('contest/<uuid:contest_uuid>/problem/<uuid:problem_uuid>/', contests.contest_problem_detail, name='contest_problem_detail'),  
    path('contest/<uuid:contest_uuid>/standings/', contests.contest_standings, name='contest_standings'),  
    # Contest announcements
    path('contest/<uuid:contest_uuid>/announcements/', contests.contest_announcements, name='contest_announcements'),
    path('contest/<uuid:contest_uuid>/announcements/create/', contests.create_announcement, name='create_announcement'),
    path('contest/<uuid:contest_uuid>/announcements/<str:announcement_id>/edit/', contests.edit_announcement, name='edit_announcement'),
    path('contest/<uuid:contest_uuid>/announcements/<str:announcement_id>/delete/', contests.delete_announcement, name='delete_announcement'),
    # Contest Administration (Staff Only)
    path('create-contest/', contests.create_contest, name='create_contest'),  
    path('contest/<uuid:contest_uuid>/edit/', contests.edit_contest, name='edit_contest'),  
    
    # API Endpoints
    path('api/submission/<str:submission_id>/status/', problems.submission_status_api, name='submission_status_api'),
    path('api/contest/<uuid:contest_uuid>/timer/', contests.contest_timer_api, name='contest_timer_api'),  
]