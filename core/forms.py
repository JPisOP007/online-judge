from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Problem


# -------------------------------
# Form: SubmitSolutionForm
# -------------------------------
class SubmitSolutionForm(forms.Form):
    language = forms.ChoiceField(
        choices=[
            ('python', 'Python 3'),
            ('cpp', 'C++'),
            ('java', 'Java'),
            ('c', 'C'),
            ('javascript', 'JavaScript'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    source_code = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 20,
            'placeholder': 'Enter your source code here...',
            'style': 'font-family: monospace;'
        })
    )

    problem_id = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )


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
    username = forms.CharField(max_length=150, label="Username")
    email = forms.EmailField(label="Email")

    class Meta:
        model = UserProfile
        fields = ['photo', 'username', 'email']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['username'].initial = user.username
            self.fields['email'].initial = user.email
            self.user = user

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
# Form: Contest thingies
# -------------------------------


from django import forms
from django.utils import timezone
from .models import Contest, ContestAnnouncement, Problem

from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import Contest, ContestAnnouncement, Problem

from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import Contest, ContestAnnouncement, Problem

from django import forms
from django.utils import timezone
from .models import Contest, Problem

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
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError("End time must be after start time")
            
            # Ensure times are timezone-aware
            if timezone.is_naive(start_time):
                cleaned_data['start_time'] = timezone.make_aware(start_time)
            if timezone.is_naive(end_time):
                cleaned_data['end_time'] = timezone.make_aware(end_time)
        
        return cleaned_data
    
    def clean_duration(self):
        duration_str = self.cleaned_data.get('duration')
        if duration_str:
            try:
               
                parts = duration_str.split(':')
                if len(parts) != 3:
                    raise forms.ValidationError("Duration must be in HH:MM:SS format")
                
                hours, minutes, seconds = map(int, parts)
                if hours < 0 or minutes < 0 or seconds < 0:
                    raise forms.ValidationError("Duration values must be positive")
                if minutes >= 60 or seconds >= 60:
                    raise forms.ValidationError("Minutes and seconds must be less than 60")
                
                duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                if duration < timedelta(minutes=30):
                    raise forms.ValidationError("Contest must be at least 30 minutes long")
                if duration > timedelta(days=7):
                    raise forms.ValidationError("Contest cannot be longer than 7 days")
                
                return duration
            except ValueError:
                raise forms.ValidationError("Invalid duration format. Use HH:MM:SS")
        return duration_str
    
    def clean_max_participants(self):
        max_participants = self.cleaned_data.get('max_participants')
        if max_participants is not None and max_participants < 1:
            raise forms.ValidationError("Maximum participants must be at least 1")
        return max_participants
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        duration = cleaned_data.get('duration')
        
        
        if start_time and end_time and not duration:
            calculated_duration = end_time - start_time
            cleaned_data['duration'] = calculated_duration
            duration = calculated_duration
        
      
        elif start_time and duration and not end_time:
            if isinstance(duration, timedelta):
                cleaned_data['end_time'] = start_time + duration
            else:
                
                try:
                    parts = str(duration).split(':')
                    if len(parts) == 3:
                        hours, minutes, seconds = map(int, parts)
                        duration_obj = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        cleaned_data['end_time'] = start_time + duration_obj
                        cleaned_data['duration'] = duration_obj
                except (ValueError, AttributeError):
                    pass
        
  
        if start_time and end_time and duration:
            calculated_duration = end_time - start_time
            if isinstance(duration, timedelta):
                if abs((calculated_duration - duration).total_seconds()) > 60:
                    
                    raise forms.ValidationError(
                        "Duration doesn't match the time difference between start and end times"
                    )
            else:
                
                try:
                    parts = str(duration).split(':')
                    if len(parts) == 3:
                        hours, minutes, seconds = map(int, parts)
                        duration_obj = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        if abs((calculated_duration - duration_obj).total_seconds()) > 60:
                            raise forms.ValidationError(
                                "Duration doesn't match the time difference between start and end times"
                            )
                        cleaned_data['duration'] = duration_obj
                except (ValueError, AttributeError):
                    pass
        
        return cleaned_data

class ContestRegistrationForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contest Password'}),
        required=False,
        help_text="Enter password if required"
    )

class ContestAnnouncementForm(forms.ModelForm):
    class Meta:
        model = ContestAnnouncement
        fields = ['title', 'content', 'is_important']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Announcement Title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Announcement Content'}),
            'is_important': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }



from django import forms
from .models import ContestAnnouncement

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = ContestAnnouncement
        fields = ['title', 'content', 'is_important']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter announcement title...',
                'maxlength': 200
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter announcement content...',
                'rows': 5
            }),
            'is_important': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].help_text = 'Brief title for the announcement'
        self.fields['content'].help_text = 'Detailed announcement content (supports basic HTML)'
        self.fields['is_important'].help_text = 'Mark as important to highlight this announcement'
