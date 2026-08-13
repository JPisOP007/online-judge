from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from .models import UserProfile, Problem, Contest, ContestAnnouncement
from .utils.file_validators import validate_image_file
import re


# -------------------------------
# Form: SubmitSolutionForm
# -------------------------------
class SubmitSolutionForm(forms.Form):
    language = forms.ChoiceField(
        choices=[
            ('python', 'Python 3'),
            ('cpp', 'C++'),
            ('java', 'Java'),
            ('javascript', 'JavaScript'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    source_code = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 20,
            'placeholder': 'Enter your source code here...',
            'style': 'font-family: monospace;',
            'maxlength': '50000'
        }),
        max_length=50000,
        help_text="Maximum 50,000 characters"
    )

    problem_id = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def clean_source_code(self):
        code = self.cleaned_data.get('source_code')
        if not code or not code.strip():
            raise ValidationError("Source code cannot be empty")
        
        return code


# -------------------------------
# Form: ProblemForm
# -------------------------------
class ProblemForm(forms.ModelForm):
    test_cases = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
        required=False,
        help_text="Enter JSON array of input/output test cases."
    )

    class Meta:
        model = Problem
        fields = ['title', 'description', 'constraints', 'input_format', 'output_format',
                  'sample_input', 'sample_output', 'difficulty', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 10, 'class': 'form-control'}),
            'constraints': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'input_format': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'output_format': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'sample_input': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'sample_output': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'tags': forms.TextInput(attrs={'class': 'form-control'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
  
        test_cases_input = self.cleaned_data.get('test_cases')
        if test_cases_input:
            instance.test_cases_json = test_cases_input
        if commit:
            instance.save()
        return instance


# -------------------------------
# Form: UserProfileForm
# -------------------------------
class UserProfileForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150, 
        label="Username",
        help_text="Letters, digits and @/./+/-/_ only."
    )
    email = forms.EmailField(label="Email")

    class Meta:
        model = UserProfile
        fields = ['photo', 'username', 'email']
        widgets = {
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['username'].initial = user.username
            self.fields['email'].initial = user.email
            self.user = user

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise ValidationError("Username is required")
        
        # Check for valid characters
        if not re.match(r'^[\w.@+-]+$', username):
            raise ValidationError("Username can only contain letters, digits and @/./+/-/_ characters")
        
        # Check if username is taken by another user
        if hasattr(self, 'user'):
            if User.objects.filter(username=username).exclude(id=self.user.id).exists():
                raise ValidationError("This username is already taken")
        
        return username
    
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            # Validate the file
            try:
                validate_image_file(photo)
            except ValidationError as e:
                # Re-raise with more user-friendly message
                raise ValidationError(f"Photo upload failed: {e.message}")
        return photo

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.username = self.cleaned_data['username']
        self.user.email = self.cleaned_data['email']
        if commit:
            self.user.save()
            profile.user = self.user
            profile.save()
        return profile


# -------------------------------
# Form: Contest Forms
# -------------------------------

class ContestForm(forms.ModelForm):
    problems = forms.ModelMultipleChoiceField(
        queryset=Problem.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }
        ),
        help_text="Contest start date and time"
    )
    
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local', 
                'class': 'form-control'
            }
        ),
        help_text="Contest end date and time"
    )
    
    class Meta:
        model = Contest
        fields = [
            'title', 'description', 'contest_type', 'start_time', 'end_time',
            'max_participants', 'is_public', 'registration_required', 'password'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'password': forms.PasswordInput(attrs={'placeholder': 'Leave empty for public contest'}),
        }
    
    def clean_max_participants(self):
        max_participants = self.cleaned_data.get('max_participants')
        if max_participants is not None and max_participants < 1:
            raise forms.ValidationError("Maximum participants must be at least 1")
        return max_participants
    
    def clean(self):
        """Normalise the contest window and derive its duration.

        `duration` is not one of Meta.fields, so it is never present in
        cleaned_data on input - it is always computed from start and end.
        """
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        # datetime-local inputs arrive naive; make them aware before comparing.
        if start_time and timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time)
            cleaned_data['start_time'] = start_time
        if end_time and timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time)
            cleaned_data['end_time'] = end_time

        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError("End time must be after start time")
            cleaned_data['duration'] = end_time - start_time

        return cleaned_data

class ContestRegistrationForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contest Password'}),
        required=False,
        help_text="Enter password if required"
    )

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = ContestAnnouncement
        fields = ['title', 'content', 'is_important']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Announcement Title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Announcement Content'}),
            'is_important': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

