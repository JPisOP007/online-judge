"""
Management command to fix media file permissions and paths
"""
import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import UserProfile

class Command(BaseCommand):
    help = 'Fix media file permissions and organize profile photos'

    def handle(self, *args, **options):
        media_root = settings.MEDIA_ROOT
        profile_photos_dir = os.path.join(media_root, 'profile_photos')
        
        # Create media directories if they don't exist
        os.makedirs(media_root, exist_ok=True)
        os.makedirs(profile_photos_dir, exist_ok=True)
        
        # Set proper permissions
        try:
            os.chmod(media_root, 0o755)
            os.chmod(profile_photos_dir, 0o755)
            self.stdout.write(self.style.SUCCESS(f'Set permissions for {media_root}'))
        except OSError as e:
            self.stdout.write(self.style.WARNING(f'Could not set permissions: {e}'))
        
        # Organize existing profile photos
        profiles_with_photos = UserProfile.objects.exclude(photo='').exclude(photo__isnull=True)
        
        for profile in profiles_with_photos:
            if profile.photo and hasattr(profile.photo, 'path'):
                try:
                    old_path = profile.photo.path
                    if os.path.exists(old_path):
                        # Create user-specific directory
                        user_dir = os.path.join(profile_photos_dir, f'user_{profile.user.id}')
                        os.makedirs(user_dir, exist_ok=True)
                        
                        # Get filename
                        filename = os.path.basename(old_path)
                        new_path = os.path.join(user_dir, filename)
                        
                        # Move file if it's not already in the right place
                        if old_path != new_path:
                            shutil.move(old_path, new_path)
                            
                            # Update database path
                            profile.photo.name = f'profile_photos/user_{profile.user.id}/{filename}'
                            profile.save()
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Moved photo for user {profile.user.username}: {filename}'
                                )
                            )
                        
                        # Set file permissions
                        os.chmod(new_path, 0o644)
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error processing photo for user {profile.user.username}: {e}'
                        )
                    )
        
        self.stdout.write(self.style.SUCCESS('Media file organization completed'))