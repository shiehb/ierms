"""
Image optimization utilities for user avatars
"""
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone


def optimize_avatar(image_file, user_id):
    """
    Optimize avatar image for web performance:
    - Resize to 256x256px (crop center if needed)
    - Convert to WebP (fallback to JPEG if unsupported)
    - Compress to 75% quality, reduce further if needed to reach ~150KB max
    - Return optimized image file object
    
    Args:
        image_file: Django uploaded file object
        user_id: User ID for filename generation
        
    Returns:
        InMemoryUploadedFile: Optimized image file ready for saving
        
    Raises:
        ValueError: If image processing fails
    """
    try:
        # Open and process image
        img = Image.open(image_file)
        
        # Convert RGBA to RGB if necessary (removes alpha channel)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize to 256x256 maintaining aspect ratio, crop center if needed
        target_size = (256, 256)
        
        # Calculate resize maintaining aspect ratio
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Create 256x256 image with white background (for non-square images)
        final_img = Image.new('RGB', target_size, (255, 255, 255))
        
        # Paste resized image centered
        paste_x = (target_size[0] - img.size[0]) // 2
        paste_y = (target_size[1] - img.size[1]) // 2
        final_img.paste(img, (paste_x, paste_y))
        
        # Try WebP first, fallback to JPEG
        output_format = 'WEBP'
        file_ext = 'webp'
        
        # Prepare output buffer
        output = BytesIO()
        
        # Start with 75% quality
        quality = 75
        max_size_bytes = 150 * 1024  # 150KB
        
        # Try WebP first
        try:
            final_img.save(output, format=output_format, quality=quality, method=6)
            
            # If file is too large, reduce quality iteratively
            while output.tell() > max_size_bytes and quality > 20:
                quality -= 5
                output.seek(0)
                output.truncate(0)
                final_img.save(output, format=output_format, quality=quality, method=6)
            
            # If still too large or WebP failed, try JPEG
            if output.tell() > max_size_bytes:
                output_format = 'JPEG'
                file_ext = 'jpg'
                quality = 75
                output.seek(0)
                output.truncate(0)
                final_img.save(output, format=output_format, quality=quality, optimize=True)
                
                # Reduce JPEG quality if still too large
                while output.tell() > max_size_bytes and quality > 20:
                    quality -= 5
                    output.seek(0)
                    output.truncate(0)
                    final_img.save(output, format=output_format, quality=quality, optimize=True)
        
        except Exception:
            # Fallback to JPEG if WebP not supported
            output_format = 'JPEG'
            file_ext = 'jpg'
            quality = 75
            output.seek(0)
            output.truncate(0)
            final_img.save(output, format=output_format, quality=quality, optimize=True)
            
            # Reduce quality if too large
            while output.tell() > max_size_bytes and quality > 20:
                quality -= 5
                output.seek(0)
                output.truncate(0)
                final_img.save(output, format=output_format, quality=quality, optimize=True)
        
        # Reset buffer position
        output.seek(0)
        
        # Generate filename with timestamp for uniqueness
        timestamp = int(timezone.now().timestamp())
        filename = f"{user_id}-{timestamp}.{file_ext}"
        
        # Get file size
        file_size = output.tell()
        output.seek(0)
        
        # Create InMemoryUploadedFile
        optimized_file = InMemoryUploadedFile(
            output,
            'avatar',
            filename,
            f'image/{file_ext}',
            file_size,
            None
        )
        
        return optimized_file
        
    except Exception as e:
        raise ValueError(f"Failed to optimize avatar image: {str(e)}")

