from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Count, F
from .models import (
    UserProfile, Problem, Solution, Contest,
    ContestProblem, ContestParticipant, ContestSubmission, ContestAnnouncement,
    AdminSettings
)
from .serializers import (
    UserSerializer, UserProfileSerializer, ProblemSerializer, SolutionSerializer,
    ContestListSerializer, ContestDetailSerializer, ContestProblemSerializer,
    ContestParticipantSerializer, ContestSubmissionSerializer, ContestAnnouncementSerializer,
    AdminSettingsSerializer
)
from .pagination import StandardResultsSetPagination
from .permissions import IsSetterOrAdminOrReadOnly, IsSelfOrStaff


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User model
    List: GET /api/users/
    Retrieve: GET /api/users/{id}/
    Update: PUT/PATCH /api/users/{id}/  (own account, or staff)
    Delete: DELETE /api/users/{id}/     (own account, or staff)

    Account creation is deliberately not exposed here: this serializer has no
    password field, so it would mint accounts with an unusable password.
    Registration goes through the site's register view.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsSelfOrStaff]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['id', 'date_joined', 'username']
    ordering = ['-date_joined']
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'put', 'patch', 'delete', 'head', 'options']

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current authenticated user"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def profile(self, request, pk=None):
        """Get user profile"""
        user = self.get_object()
        try:
            profile = user.userprofile
            serializer = UserProfileSerializer(profile, context={'request': request})
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response({'detail': 'User profile not found'}, status=status.HTTP_404_NOT_FOUND)


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UserProfile model
    List: GET /api/profiles/
    Retrieve: GET /api/profiles/{id}/
    Update: PUT/PATCH /api/profiles/{id}/  (own profile, or staff)

    Note that `role` is only writable by staff - see get_serializer(). Without
    that, any participant could PATCH their own profile to role=admin.
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsSelfOrStaff]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'role']
    ordering_fields = ['user__username', 'role']
    ordering = ['user__username']
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'put', 'patch', 'head', 'options']

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if not self.request.user.is_staff and 'role' in serializer.fields:
            serializer.fields['role'].read_only = True
        return serializer

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current user's profile"""
        try:
            profile = request.user.userprofile
            serializer = self.get_serializer(profile, context={'request': request})
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response({'detail': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)


class ProblemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Problem model
    List: GET /api/problems/
    Create: POST /api/problems/
    Retrieve: GET /api/problems/{id}/
    Update: PUT/PATCH /api/problems/{id}/
    Delete: DELETE /api/problems/{id}/
    """
    queryset = Problem.objects.all().order_by('-created_at')
    serializer_class = ProblemSerializer
    permission_classes = [IsSetterOrAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'tags', 'description']
    ordering_fields = ['created_at', 'difficulty', 'title']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def by_difficulty(self, request):
        """Filter problems by difficulty"""
        difficulty = request.query_params.get('difficulty')
        if difficulty:
            queryset = self.get_queryset().filter(difficulty=difficulty)
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return Response({'error': 'difficulty parameter required'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def solutions_count(self, request, pk=None):
        """Get count of solutions for a problem"""
        problem = self.get_object()
        count = problem.solutions.count()
        accepted = problem.solutions.filter(verdict='AC').count()
        return Response({
            'problem_id': problem.id,
            'total_submissions': count,
            'accepted': accepted,
            'acceptance_rate': round((accepted / count * 100) if count > 0 else 0, 2)
        })


class SolutionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Solution model
    List: GET /api/solutions/
    Create: POST /api/solutions/
    Retrieve: GET /api/solutions/{id}/
    Update: PUT/PATCH /api/solutions/{id}/
    Delete: DELETE /api/solutions/{id}/
    """
    queryset = Solution.objects.all().order_by('-submitted_at')
    serializer_class = SolutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['problem__title', 'user__username']
    ordering_fields = ['submitted_at', 'verdict', 'execution_time']
    ordering = ['-submitted_at']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """Filter solutions by user if not admin"""
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        """Set user to current user"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_solutions(self, request):
        """Get current user's solutions"""
        solutions = Solution.objects.filter(user=request.user).order_by('-submitted_at')
        page = self.paginate_queryset(solutions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(solutions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def problem_solutions(self, request):
        """Get the requesting user's solutions for a specific problem.

        This used to query Solution.objects directly, bypassing get_queryset()
        and handing out every user's source code for any problem.
        """
        problem_id = request.query_params.get('problem_id')
        if not problem_id:
            return Response({'error': 'problem_id parameter required'}, status=status.HTTP_400_BAD_REQUEST)

        solutions = self.get_queryset().filter(problem_id=problem_id).order_by('-submitted_at')
        page = self.paginate_queryset(solutions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(solutions, many=True)
        return Response(serializer.data)


class ContestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Contest model with comprehensive filtering and statistics
    """
    queryset = Contest.objects.all().order_by('-start_time')
    permission_classes = [IsSetterOrAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['start_time', 'created_at', 'title']
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        """Use list serializer for list action, detail serializer for retrieve"""
        if self.action == 'retrieve':
            return ContestDetailSerializer
        return ContestListSerializer

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def upcoming(self, request):
        """Get upcoming contests"""
        contests = self.get_queryset().filter(start_time__gt=timezone.now()).order_by('start_time')
        page = self.paginate_queryset(contests)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(contests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def running(self, request):
        """Get running contests"""
        now = timezone.now()
        contests = self.get_queryset().filter(start_time__lte=now, end_time__gte=now)
        page = self.paginate_queryset(contests)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(contests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def ended(self, request):
        """Get ended contests"""
        contests = self.get_queryset().filter(end_time__lt=timezone.now()).order_by('-end_time')
        page = self.paginate_queryset(contests)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(contests, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        """Join a contest"""
        contest = self.get_object()
        
        # Check if contest is full
        if contest.max_participants:
            current_participants = contest.participants.count()
            if current_participants >= contest.max_participants:
                return Response(
                    {'error': 'Contest is full'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create participant record
        participant, created = ContestParticipant.objects.get_or_create(
            contest=contest,
            user=request.user
        )
        
        if created:
            return Response({
                'status': 'joined',
                'message': 'Successfully joined contest'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'status': 'already_joined',
                'message': 'Already joined this contest'
            }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def standings(self, request, pk=None):
        """Get contest standings/leaderboard"""
        contest = self.get_object()
        
        # Get all participants with their scores
        participants = ContestParticipant.objects.filter(contest=contest).select_related('user')
        standings = []
        
        for participant in participants:
            total_score = ContestSubmission.objects.filter(
                participant=participant
            ).aggregate(total=models.Sum('score'))['total'] or 0
            
            standings.append({
                'rank': len(standings) + 1,
                'user': participant.user.username,
                'user_id': participant.user.id,
                'score': total_score,
                'submissions': participant.contestsubmission_set.count()
            })
        
        # Sort by score descending
        standings.sort(key=lambda x: x['score'], reverse=True)
        for i, standing in enumerate(standings):
            standing['rank'] = i + 1
        
        return Response(standings)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def my_submissions(self, request, pk=None):
        """Get current user's submissions in a contest"""
        contest = self.get_object()
        try:
            participant = ContestParticipant.objects.get(contest=contest, user=request.user)
            submissions = ContestSubmission.objects.filter(participant=participant).order_by('-submitted_at')
            page = self.paginate_queryset(submissions)
            if page is not None:
                serializer = ContestSubmissionSerializer(page, many=True, context={'request': request})
                return self.get_paginated_response(serializer.data)
            serializer = ContestSubmissionSerializer(submissions, many=True, context={'request': request})
            return Response(serializer.data)
        except ContestParticipant.DoesNotExist:
            return Response({'error': 'Not a participant in this contest'}, status=status.HTTP_403_FORBIDDEN)


class ContestProblemViewSet(viewsets.ModelViewSet):
    """ViewSet for ContestProblem model"""
    queryset = ContestProblem.objects.all().select_related('contest', 'problem')
    serializer_class = ContestProblemSerializer
    permission_classes = [IsSetterOrAdminOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['order', 'points']
    ordering = ['order']

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def by_contest(self, request):
        """Get problems in a specific contest"""
        contest_id = request.query_params.get('contest_id')
        if not contest_id:
            return Response({'error': 'contest_id parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        problems = self.get_queryset().filter(contest_id=contest_id).order_by('order')
        serializer = self.get_serializer(problems, many=True)
        return Response(serializer.data)


class ContestParticipantViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only view of contest registrations.

    Registration happens through POST /api/contests/{id}/join/, which checks
    capacity. Exposing write methods here let anyone create registrations for
    other users or delete them outright.
    """
    queryset = ContestParticipant.objects.all().select_related('contest', 'user')
    serializer_class = ContestParticipantSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def by_contest(self, request):
        """Get participants in a specific contest"""
        contest_id = request.query_params.get('contest_id')
        if not contest_id:
            return Response({'error': 'contest_id parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        participants = self.get_queryset().filter(contest_id=contest_id)
        page = self.paginate_queryset(participants)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(participants, many=True)
        return Response(serializer.data)


class ContestSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only view of contest submissions.

    This was a full ModelViewSet guarded only by IsAuthenticated, so any user
    could POST or PATCH verdict, score and points_awarded directly and write
    themselves to the top of the standings. Scores are produced by the judge,
    never by the client.
    """
    queryset = ContestSubmission.objects.all().select_related('contest', 'participant', 'problem', 'solution')
    serializer_class = ContestSubmissionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['submitted_at', 'score']
    ordering = ['-submitted_at']
    pagination_class = StandardResultsSetPagination

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def by_contest(self, request):
        """Get submissions for a specific contest"""
        contest_id = request.query_params.get('contest_id')
        if not contest_id:
            return Response({'error': 'contest_id parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        submissions = self.get_queryset().filter(contest_id=contest_id)
        page = self.paginate_queryset(submissions)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(submissions, many=True)
        return Response(serializer.data)


class ContestAnnouncementViewSet(viewsets.ModelViewSet):
    """ViewSet for ContestAnnouncement model"""
    queryset = ContestAnnouncement.objects.all().select_related('contest', 'created_by')
    serializer_class = ContestAnnouncementSerializer
    permission_classes = [IsAuthenticated, IsSetterOrAdminOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'is_important']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def by_contest(self, request):
        """Get announcements for a specific contest"""
        contest_id = request.query_params.get('contest_id')
        if not contest_id:
            return Response({'error': 'contest_id parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        announcements = self.get_queryset().filter(contest_id=contest_id)
        page = self.paginate_queryset(announcements)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(announcements, many=True)
        return Response(serializer.data)


class AdminSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for AdminSettings model"""
    queryset = AdminSettings.objects.all()
    serializer_class = AdminSettingsSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def current(self, request):
        """Get current admin settings"""
        settings = AdminSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)


# Import models for use in views
from django.db import models
