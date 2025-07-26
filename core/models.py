from django.contrib.auth.models import User
from django.db import models
import uuid
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('setter', 'Problem Setter'),
        ('participant', 'Participant'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

class Problem(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    difficulty = models.CharField(max_length=50, choices=DIFFICULTY_CHOICES, default='easy')
    description = models.TextField()
    constraints = models.TextField(blank=True)
    input_format = models.TextField(blank=True)
    output_format = models.TextField(blank=True)
    sample_input = models.TextField(blank=True)
    sample_output = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True, null=True)  
    test_cases_json = models.TextField(blank=True) 
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title


class Solution(models.Model):
    VERDICT_CHOICES = [
        ('AC', 'Accepted'),
        ('WA', 'Wrong Answer'),
        ('TLE', 'Time Limit Exceeded'),
        ('CE', 'Compilation Error'),
        ('RE', 'Runtime Error')
    ]

    LANGUAGE_CHOICES = [
        ('python', 'Python'),
        ('cpp', 'C++'),
        ('java', 'Java')
    ]

    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='solutions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.TextField()
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES)
    submitted_at = models.DateTimeField(auto_now_add=True)
    output = models.TextField(blank=True, null=True)
    error = models.TextField(blank=True, null=True)
    verdict = models.CharField(max_length=5, choices=VERDICT_CHOICES, blank=True, null=True)
    execution_time = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=50, default='Pending')


    def __str__(self):
        return f"{self.user.username}'s {self.language} solution for {self.problem.title}"



import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils import timezone



class Contest(models.Model):
    CONTEST_TYPES = [
        ('rated', 'Rated Contest'),
        ('unrated', 'Unrated Contest'),
        ('practice', 'Practice Contest'),
    ]
    
    CONTEST_STATUS = [
        ('upcoming', 'Upcoming'),
        ('running', 'Running'),
        ('ended', 'Ended'),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    contest_type = models.CharField(max_length=20, choices=CONTEST_TYPES, default='rated')
    
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    duration = models.DurationField(
        null=True, 
        blank=True, 
        help_text="Contest duration (e.g., 2:00:00 for 2 hours)"
    )
    
   
    max_participants = models.PositiveIntegerField(null=True, blank=True, help_text="Leave empty for unlimited")
    is_public = models.BooleanField(default=True)
    registration_required = models.BooleanField(default=True)
    password = models.CharField(max_length=50, blank=True, help_text="Leave empty for public contest")
    
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_contests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    
    participants = models.ManyToManyField(User, through='ContestParticipant', related_name='contests')
    
    def __str__(self):
        return self.title
    
    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time")
    
    @property
    def status(self):
        now = timezone.now()
        if now < self.start_time:
            return 'upcoming'
        elif now <= self.end_time:
            return 'running'
        else:
            return 'ended'
    
    @property
    def is_running(self):
        return self.status == 'running'
    
    @property
    def is_ended(self):
        return self.status == 'ended'
    
    @property
    def is_upcoming(self):
        return self.status == 'upcoming'
    
    @property
    def time_remaining(self):
        if self.is_running:
            return self.end_time - timezone.now()
        return None
    
    @property
    def time_until_start(self):
        if self.is_upcoming:
            return self.start_time - timezone.now()
        return None
    
    @property
    def status(self):
        """Get current contest status with proper timezone handling"""
        now = timezone.now()
        print(f"[DEBUG] Current time: {now}")
        print(f"[DEBUG] Contest start: {self.start_time}")
        print(f"[DEBUG] Contest end: {self.end_time}")
        
        if now < self.start_time:
            return 'upcoming'
        elif now <= self.end_time:
            return 'running'
        else:
            return 'ended'
    
    @property
    def time_remaining(self):
        """Get time remaining in contest"""
        if self.is_running:
            remaining = self.end_time - timezone.now()
            return remaining if remaining.total_seconds() > 0 else None
        return None
    
    @property
    def time_until_start(self):
        """Get time until contest starts"""
        if self.is_upcoming:
            until_start = self.start_time - timezone.now()
            return until_start if until_start.total_seconds() > 0 else None
        return None

class ContestProblem(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='contest_problems')
    problem = models.ForeignKey('Problem', on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=1)
    points = models.PositiveIntegerField(default=100)
    
    class Meta:
        unique_together = ['contest', 'problem']
        ordering = ['order']
    
    def __str__(self):
        return f"{self.contest.title} - {self.problem.title}"

class ContestParticipant(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    registered_at = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['contest', 'user']
    
    def __str__(self):
        return f"{self.user.username} in {self.contest.title}"

class ContestSubmission(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='contest_submissions')
    participant = models.ForeignKey(ContestParticipant, on_delete=models.CASCADE)
    problem = models.ForeignKey('Problem', on_delete=models.CASCADE)
    solution = models.ForeignKey('Solution', on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    points_awarded = models.PositiveIntegerField(default=0)
    verdict = models.CharField(max_length=10, blank=True, null=True)
    score = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.participant.user.username} - {self.problem.title}"

class ContestAnnouncement(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_important = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.contest.title} - {self.title}"