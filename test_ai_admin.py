#!/usr/bin/env python
"""
Test script to verify AI review and admin settings
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'online_judge.settings')
django.setup()

from core.models import AdminSettings, UserProfile, User

def test_admin_settings():
    """Test admin settings functionality"""
    print("🔧 Testing Admin Settings...")
    
    # Get or create admin settings
    settings = AdminSettings.get_settings()
    print(f"✅ Admin settings created/retrieved: AI Review = {settings.ai_review_enabled}")
    
    # Test toggle functionality
    original_state = settings.ai_review_enabled
    settings.ai_review_enabled = not original_state
    settings.save()
    
    # Verify change
    settings.refresh_from_db()
    print(f"✅ Admin settings toggled: AI Review = {settings.ai_review_enabled}")
    
    # Restore original state
    settings.ai_review_enabled = original_state
    settings.save()
    print(f"✅ Admin settings restored: AI Review = {settings.ai_review_enabled}")

def test_user_profiles():
    """Test user profile photo paths"""
    print("\n👤 Testing User Profiles...")
    
    profiles_with_photos = UserProfile.objects.exclude(photo='').exclude(photo__isnull=True)
    
    for profile in profiles_with_photos:
        print(f"✅ User {profile.user.username}: {profile.photo}")
        
        # Check if file exists
        if profile.photo and hasattr(profile.photo, 'path'):
            if os.path.exists(profile.photo.path):
                print(f"   📁 File exists: {profile.photo.path}")
            else:
                print(f"   ❌ File missing: {profile.photo.path}")
        
        # Check URL
        if profile.photo:
            print(f"   🔗 URL: {profile.photo.url}")

def test_ai_review_import():
    """Test AI review functionality"""
    print("\n🤖 Testing AI Review Import...")
    
    try:
        from core.utils.ai_review import generate_code_review
        print("✅ AI review module imported successfully")
        
        # Test with simple code
        test_code = "print('Hello World')"
        result = generate_code_review(test_code)
        
        if result['success']:
            print("✅ AI review generation successful")
            print(f"   Logic: {result['review']['logic'][:50]}...")
        else:
            print(f"⚠️  AI review failed: {result['error']}")
            
    except Exception as e:
        print(f"❌ AI review import failed: {e}")

if __name__ == "__main__":
    print("🧪 Testing AI Review and Admin Settings...\n")
    
    try:
        test_admin_settings()
        test_user_profiles()
        test_ai_review_import()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)