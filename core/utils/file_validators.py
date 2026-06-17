"""
Secure file upload validators
"""
import os
from PIL import Image
from django.core.exceptions import ValidationError
from django.conf import settings

# Try to import magic, fallback if not available
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

# File size limits
MAX_PROFILE_PHOTO_SIZE = 20 * 1024 * 1024  # 20MB
MAX_PROFILE_PHOTO_DIMENSIONS = (4096, 4096)  # 4096x4096 pixels

# Allowed file types
ALLOWED_IMAGE_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'image/webp': ['.webp']
}

ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

def validate_image_file(file):
    """
    Comprehensive image file validation
    """
    # Check file size
    if file.size > MAX_PROFILE_PHOTO_SIZE:
        raise ValidationError(f'File size must be less than {MAX_PROFILE_PHOTO_SIZE // (1024*1024)}MB')
    
    # Check file extension
    file_extension = os.path.splitext(file.name)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}')
    
    # Reset file pointer
    file.seek(0)
    
    # Check MIME type using python-magic (if available)
    if HAS_MAGIC:
        try:
            mime_type = magic.from_buffer(file.read(1024), mime=True)
            file.seek(0)
            
            if mime_type not in ALLOWED_IMAGE_TYPES:
                raise ValidationError(f'Invalid file type. Detected: {mime_type}')
            
            # Verify extension matches MIME type
            expected_extensions = ALLOWED_IMAGE_TYPES[mime_type]
            if file_extension not in expected_extensions:
                raise ValidationError('File extension does not match file content')
        
        except Exception as e:
            raise ValidationError(f'Could not validate file type: {str(e)}')
    else:
        # Fallback validation without magic
        if file_extension not in ALLOWED_EXTENSIONS:
            raise ValidationError(f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}')
    
    # Validate image using PIL
    try:
        file.seek(0)
        with Image.open(file) as img:
            # Verify it's a valid image
            img.verify()
            
            # Check dimensions
            if img.size[0] > MAX_PROFILE_PHOTO_DIMENSIONS[0] or img.size[1] > MAX_PROFILE_PHOTO_DIMENSIONS[1]:
                raise ValidationError(f'Image dimensions too large. Maximum: {MAX_PROFILE_PHOTO_DIMENSIONS[0]}x{MAX_PROFILE_PHOTO_DIMENSIONS[1]}')
            
            # Check for potential malicious content
            if hasattr(img, 'format') and img.format not in ['JPEG', 'PNG', 'GIF', 'WEBP']:
                raise ValidationError('Unsupported image format')
    
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f'Invalid image file: {str(e)}')
    
    # Reset file pointer for further processing
    file.seek(0)
    
    return True

def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and other attacks
    """
    # Remove directory separators and other dangerous characters
    dangerous_chars = ['/', '\\', '..', '~', '$', '&', '|', ';', '`', "'", '"', '<', '>', '?', '*']
    
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Limit filename length
    name, ext = os.path.splitext(filename)
    if len(name) > 50:
        name = name[:50]
    
    return f"{name}{ext}"

def get_upload_path(instance, filename):
    """
    Generate secure upload path for profile photos
    """
    # Sanitize filename
    filename = sanitize_filename(filename)
    
    # Create user-specific directory
    user_id = instance.user.id
    return f'profile_photos/user_{user_id}/{filename}'