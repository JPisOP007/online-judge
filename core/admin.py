from django.contrib import admin
from .models import UserProfile, Problem

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')

admin.site.register(Problem)
