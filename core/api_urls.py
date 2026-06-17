from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    UserViewSet, UserProfileViewSet, ProblemViewSet, SolutionViewSet,
    ContestViewSet, ContestProblemViewSet, ContestParticipantViewSet,
    ContestSubmissionViewSet, ContestAnnouncementViewSet, AdminSettingsViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'profiles', UserProfileViewSet, basename='profile')
router.register(r'problems', ProblemViewSet, basename='problem')
router.register(r'solutions', SolutionViewSet, basename='solution')
router.register(r'contests', ContestViewSet, basename='contest')
router.register(r'contest-problems', ContestProblemViewSet, basename='contest-problem')
router.register(r'contest-participants', ContestParticipantViewSet, basename='contest-participant')
router.register(r'contest-submissions', ContestSubmissionViewSet, basename='contest-submission')
router.register(r'announcements', ContestAnnouncementViewSet, basename='announcement')
router.register(r'admin-settings', AdminSettingsViewSet, basename='admin-settings')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls')),
]
