from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    UserProfile, Problem, Solution, Contest, 
    ContestProblem, ContestParticipant, ContestSubmission, ContestAnnouncement,
    AdminSettings
)


class ObjectIdPrimaryKeyMixin(serializers.Serializer):
    """Expose MongoDB ObjectId primary keys as strings.

    Without this, DRF infers a field type from ObjectIdAutoField and fails to
    represent the value, which is what made every list endpoint return a 500.
    """
    id = serializers.CharField(read_only=True)


class UserSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'is_active']
        read_only_fields = ['date_joined']


class UserProfileSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    user = UserSerializer(read_only=True)
    user_id = serializers.CharField(write_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'user_id', 'role', 'photo', 'photo_url']
        read_only_fields = ['user']

    def get_photo_url(self, obj):
        """Return absolute URL of profile photo"""
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None

    def create(self, validated_data):
        """Create UserProfile with associated user"""
        user_id = validated_data.pop('user_id')
        try:
            user = User.objects.get(id=user_id)
            validated_data['user'] = user
            return super().create(validated_data)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")


class ProblemSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for Problem model"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    test_cases = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = [
            'id', 'uuid', 'title', 'difficulty', 'description', 
            'constraints', 'input_format', 'output_format', 
            'sample_input', 'sample_output', 'tags', 'test_cases',
            'created_by_username', 'created_at'
        ]
        read_only_fields = ['uuid', 'created_at']

    def get_test_cases(self, obj):
        """Parse and return test cases from JSON"""
        import json
        if obj.test_cases_json:
            try:
                return json.loads(obj.test_cases_json)
            except json.JSONDecodeError:
                return []
        return []


class SolutionSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for Solution model"""
    problem_title = serializers.CharField(source='problem.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Solution
        fields = [
            'id', 'problem', 'problem_title', 'user', 'user_username',
            'code', 'language', 'submitted_at', 'output', 'error',
            'verdict', 'execution_time', 'status'
        ]
        read_only_fields = ['submitted_at', 'output', 'error', 'verdict', 'execution_time', 'status', 'user']


class ContestProblemSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for ContestProblem model"""
    problem_details = ProblemSerializer(source='problem', read_only=True)

    class Meta:
        model = ContestProblem
        fields = ['id', 'contest', 'problem', 'problem_details', 'order', 'points']


class ContestParticipantSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for ContestParticipant model"""
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = ContestParticipant
        fields = ['id', 'contest', 'user', 'user_details', 'registered_at', 'start_time']
        read_only_fields = ['registered_at']


class ContestSubmissionSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for ContestSubmission model"""
    user_username = serializers.CharField(source='participant.user.username', read_only=True)
    problem_title = serializers.CharField(source='problem.title', read_only=True)
    
    class Meta:
        model = ContestSubmission
        fields = [
            'id', 'contest', 'participant', 'problem', 'problem_title',
            'solution', 'user_username', 'submitted_at', 'points_awarded',
            'verdict', 'score'
        ]
        read_only_fields = ['submitted_at']


class ContestAnnouncementSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for ContestAnnouncement model"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = ContestAnnouncement
        fields = [
            'id', 'contest', 'title', 'content', 'created_by_username',
            'created_at', 'is_important'
        ]
        read_only_fields = ['created_at']


class ContestListSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Simplified serializer for listing contests"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    participant_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = Contest
        fields = [
            'id', 'uuid', 'title', 'description', 'contest_type',
            'start_time', 'end_time', 'duration', 'is_public',
            'created_by_username', 'created_at', 'participant_count', 'status'
        ]
        read_only_fields = ['uuid', 'created_at']
    
    def get_participant_count(self, obj):
        return obj.participants.count()
    
    def get_status(self, obj):
        return obj.status


class ContestDetailSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Detailed serializer for contest with nested data"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    participant_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    problems = ContestProblemSerializer(source='contest_problems', many=True, read_only=True)
    announcements = ContestAnnouncementSerializer(many=True, read_only=True)
    
    class Meta:
        model = Contest
        fields = [
            'id', 'uuid', 'title', 'description', 'contest_type',
            'start_time', 'end_time', 'duration', 'max_participants',
            'is_public', 'registration_required', 'created_by_username',
            'created_at', 'updated_at', 'participant_count', 'status',
            'problems', 'announcements'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class AdminSettingsSerializer(ObjectIdPrimaryKeyMixin, serializers.ModelSerializer):
    """Serializer for AdminSettings model"""
    
    class Meta:
        model = AdminSettings
        fields = ['id', 'ai_review_enabled', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
