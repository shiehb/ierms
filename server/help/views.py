"""
API views for help content management.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse, FileResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from audit.utils import log_activity
from audit.constants import AUDIT_ACTIONS, AUDIT_MODULES
from .utils import (
    get_help_topics,
    get_help_categories,
    save_help_topics,
    save_help_categories,
    export_help_data,
    import_help_data,
    HELP_TOPICS_FILE,
    HELP_CATEGORIES_FILE,
)
import json
import os
import uuid


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_topics(request):
    """Get all help topics."""
    try:
        topics = get_help_topics()
        return Response(topics, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_categories(request):
    """Get all help categories."""
    try:
        categories = get_help_categories()
        return Response(categories, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def save_topics(request):
    """Save help topics (admin only)."""
    try:
        topics = request.data
        
        if not isinstance(topics, list):
            return Response(
                {'error': 'Topics must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get old topics for comparison
        old_topics = get_help_topics()
        old_topic_ids = {t.get('id') for t in old_topics if t.get('id')}
        new_topic_ids = {t.get('id') for t in topics if t.get('id')}
        
        # Identify created, updated, and deleted topics
        created_ids = new_topic_ids - old_topic_ids
        deleted_ids = old_topic_ids - new_topic_ids
        updated_ids = new_topic_ids & old_topic_ids
        
        # Create a map of old topics by ID for comparison
        old_topics_map = {t.get('id'): t for t in old_topics if t.get('id')}
        
        # Save topics
        save_help_topics(topics)
        
        # Log created topics
        for topic_id in created_ids:
            topic = next((t for t in topics if t.get('id') == topic_id), None)
            if topic:
                log_activity(
                    user=request.user,
                    action=AUDIT_ACTIONS["CREATE"],
                    module=AUDIT_MODULES["HELP"],
                    description=f"Created help topic: {topic.get('title', 'Untitled')}",
                    message=f"Created help topic '{topic.get('title', 'Untitled')}' (ID: {topic_id})",
                    metadata={
                        "topic_id": topic_id,
                        "topic_title": topic.get('title', 'Untitled'),
                        "category": topic.get('category', ''),
                        "steps_count": len(topic.get('steps', [])),
                        "status": "success"
                    },
                    request=request
                )
        
        # Log updated topics
        for topic_id in updated_ids:
            topic = next((t for t in topics if t.get('id') == topic_id), None)
            old_topic = old_topics_map.get(topic_id)
            if topic and old_topic:
                # Check if there were actual changes
                if topic != old_topic:
                    log_activity(
                        user=request.user,
                        action=AUDIT_ACTIONS["UPDATE"],
                        module=AUDIT_MODULES["HELP"],
                        description=f"Updated help topic: {topic.get('title', 'Untitled')}",
                        message=f"Updated help topic '{topic.get('title', 'Untitled')}' (ID: {topic_id})",
                        metadata={
                            "topic_id": topic_id,
                            "topic_title": topic.get('title', 'Untitled'),
                            "category": topic.get('category', ''),
                            "steps_count": len(topic.get('steps', [])),
                            "status": "success"
                        },
                        before=old_topic,
                        after=topic,
                        request=request
                    )
        
        # Log deleted topics
        for topic_id in deleted_ids:
            old_topic = old_topics_map.get(topic_id)
            if old_topic:
                log_activity(
                    user=request.user,
                    action=AUDIT_ACTIONS["DELETE"],
                    module=AUDIT_MODULES["HELP"],
                    description=f"Deleted help topic: {old_topic.get('title', 'Untitled')}",
                    message=f"Deleted help topic '{old_topic.get('title', 'Untitled')}' (ID: {topic_id})",
                    metadata={
                        "topic_id": topic_id,
                        "topic_title": old_topic.get('title', 'Untitled'),
                        "status": "success"
                    },
                    before=old_topic,
                    request=request
                )
        
        return Response(
            {'success': True, 'message': 'Help topics saved successfully'},
            status=status.HTTP_200_OK
        )
    except ValueError as e:
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["UPDATE"],
            module=AUDIT_MODULES["HELP"],
            description="Failed to save help topics",
            message=f"Error saving help topics: {str(e)}",
            metadata={"status": "error", "error": str(e)},
            request=request
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["UPDATE"],
            module=AUDIT_MODULES["HELP"],
            description="Failed to save help topics",
            message=f"Error saving help topics: {str(e)}",
            metadata={"status": "error", "error": str(e)},
            request=request
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def save_categories(request):
    """Save help categories (admin only)."""
    try:
        categories = request.data
        
        if not isinstance(categories, list):
            return Response(
                {'error': 'Categories must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get old categories for comparison
        old_categories = get_help_categories()
        old_category_keys = {c.get('key') for c in old_categories if c.get('key')}
        new_category_keys = {c.get('key') for c in categories if c.get('key')}
        
        # Identify created, updated, and deleted categories
        created_keys = new_category_keys - old_category_keys
        deleted_keys = old_category_keys - new_category_keys
        updated_keys = new_category_keys & old_category_keys
        
        # Create a map of old categories by key for comparison
        old_categories_map = {c.get('key'): c for c in old_categories if c.get('key')}
        
        # Save categories
        save_help_categories(categories)
        
        # Log created categories
        for category_key in created_keys:
            category = next((c for c in categories if c.get('key') == category_key), None)
            if category:
                log_activity(
                    user=request.user,
                    action=AUDIT_ACTIONS["CREATE"],
                    module=AUDIT_MODULES["HELP"],
                    description=f"Created help category: {category.get('name', category_key)}",
                    message=f"Created help category '{category.get('name', category_key)}' (Key: {category_key})",
                    metadata={
                        "category_key": category_key,
                        "category_name": category.get('name', category_key),
                        "status": "success"
                    },
                    request=request
                )
        
        # Log updated categories
        for category_key in updated_keys:
            category = next((c for c in categories if c.get('key') == category_key), None)
            old_category = old_categories_map.get(category_key)
            if category and old_category:
                # Check if there were actual changes
                if category != old_category:
                    log_activity(
                        user=request.user,
                        action=AUDIT_ACTIONS["UPDATE"],
                        module=AUDIT_MODULES["HELP"],
                        description=f"Updated help category: {category.get('name', category_key)}",
                        message=f"Updated help category '{category.get('name', category_key)}' (Key: {category_key})",
                        metadata={
                            "category_key": category_key,
                            "category_name": category.get('name', category_key),
                            "status": "success"
                        },
                        before=old_category,
                        after=category,
                        request=request
                    )
        
        # Log deleted categories
        for category_key in deleted_keys:
            old_category = old_categories_map.get(category_key)
            if old_category:
                log_activity(
                    user=request.user,
                    action=AUDIT_ACTIONS["DELETE"],
                    module=AUDIT_MODULES["HELP"],
                    description=f"Deleted help category: {old_category.get('name', category_key)}",
                    message=f"Deleted help category '{old_category.get('name', category_key)}' (Key: {category_key})",
                    metadata={
                        "category_key": category_key,
                        "category_name": old_category.get('name', category_key),
                        "status": "success"
                    },
                    before=old_category,
                    request=request
                )
        
        return Response(
            {'success': True, 'message': 'Help categories saved successfully'},
            status=status.HTTP_200_OK
        )
    except ValueError as e:
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["UPDATE"],
            module=AUDIT_MODULES["HELP"],
            description="Failed to save help categories",
            message=f"Error saving help categories: {str(e)}",
            metadata={"status": "error", "error": str(e)},
            request=request
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["UPDATE"],
            module=AUDIT_MODULES["HELP"],
            description="Failed to save help categories",
            message=f"Error saving help categories: {str(e)}",
            metadata={"status": "error", "error": str(e)},
            request=request
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def export_backup(request):
    """Export help data as ZIP archive with images (admin only)."""
    try:
        # Check if client wants JSON only (for backward compatibility)
        format_type = request.GET.get('format', 'zip')
        
        if format_type == 'json':
            # Return JSON only (backward compatibility)
            data = export_help_data(include_images=False)
            
            # Log export
            log_activity(
                user=request.user,
                action=AUDIT_ACTIONS["EXPORT"],
                module=AUDIT_MODULES["HELP"],
                description="Exported help data (JSON format)",
                message="Exported help data in JSON format",
                metadata={
                    "format": "json",
                    "topics_count": len(data.get('topics', [])),
                    "categories_count": len(data.get('categories', [])),
                    "status": "success"
                },
                request=request
            )
            
            return Response(data, status=status.HTTP_200_OK)
        else:
            # Return ZIP with images
            zip_bytes, zip_filename = export_help_data(include_images=True)
            
            # Get topic and category counts for logging
            topics = get_help_topics()
            categories = get_help_categories()
            
            # Log export
            log_activity(
                user=request.user,
                action=AUDIT_ACTIONS["EXPORT"],
                module=AUDIT_MODULES["HELP"],
                description="Exported help data (ZIP format with images)",
                message=f"Exported help data as ZIP archive: {zip_filename}",
                metadata={
                    "format": "zip",
                    "filename": zip_filename,
                    "topics_count": len(topics),
                    "categories_count": len(categories),
                    "status": "success"
                },
                request=request
            )
            
            from django.http import HttpResponse
            response = HttpResponse(zip_bytes, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
            return response
    except Exception as e:
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["EXPORT"],
            module=AUDIT_MODULES["HELP"],
            description="Failed to export help data",
            message=f"Error exporting help data: {str(e)}",
            metadata={"status": "error", "error": str(e)},
            request=request
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def restore_backup(request):
    """Import help data from JSON or ZIP archive (admin only)."""
    try:
        import tempfile
        
        # Check if ZIP file was uploaded
        if 'file' in request.FILES:
            zip_file = request.FILES['file']
            
            # Validate file type
            if not zip_file.name.endswith('.zip'):
                return Response(
                    {'error': 'Invalid file type. Please upload a ZIP file.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save uploaded file temporarily
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            for chunk in zip_file.chunks():
                temp_zip.write(chunk)
            temp_zip.close()
            
            try:
                # Import from ZIP
                result = import_help_data(None, zip_file_path=temp_zip.name)
                
                # Log import
                log_activity(
                    user=request.user,
                    action=AUDIT_ACTIONS["IMPORT"],
                    module=AUDIT_MODULES["HELP"],
                    description="Imported help data from ZIP archive",
                    message=f"Imported help data from ZIP file: {zip_file.name}",
                    metadata={
                        "format": "zip",
                        "filename": zip_file.name,
                        "topics_imported": result.get('topics_imported', 0),
                        "categories_imported": result.get('categories_imported', 0),
                        "images_imported": result.get('images_imported', 0),
                        "status": "success"
                    },
                    request=request
                )
                
                return Response(
                    {
                        'success': True,
                        'message': 'Help data restored successfully',
                        'topics_imported': result['topics_imported'],
                        'categories_imported': result['categories_imported'],
                        'images_imported': result['images_imported']
                    },
                    status=status.HTTP_200_OK
                )
            finally:
                # Clean up temporary file
                if os.path.exists(temp_zip.name):
                    os.remove(temp_zip.name)
        else:
            # Import from JSON (backward compatibility)
            data = request.data
            
            if not isinstance(data, dict):
                return Response(
                    {'error': 'Import data must be a dictionary or ZIP file'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            result = import_help_data(data)
            
            # Log import
            log_activity(
                user=request.user,
                action=AUDIT_ACTIONS["IMPORT"],
                module=AUDIT_MODULES["HELP"],
                description="Imported help data from JSON",
                message="Imported help data from JSON format",
                metadata={
                    "format": "json",
                    "topics_imported": result.get('topics_imported', 0),
                    "categories_imported": result.get('categories_imported', 0),
                    "images_imported": result.get('images_imported', 0),
                    "status": "success"
                },
                request=request
            )
            
            return Response(
                {
                    'success': True,
                    'message': 'Help data restored successfully',
                    'topics_imported': result['topics_imported'],
                    'categories_imported': result['categories_imported'],
                    'images_imported': result['images_imported']
                },
                status=status.HTTP_200_OK
            )
    except ValueError as e:
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["IMPORT"],
            module=AUDIT_MODULES["HELP"],
            description="Failed to import help data",
            message=f"Error importing help data: {str(e)}",
            metadata={"status": "error", "error": str(e)},
            request=request
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["IMPORT"],
            module=AUDIT_MODULES["HELP"],
            description="Failed to import help data",
            message=f"Error importing help data: {str(e)}",
            metadata={"status": "error", "error": str(e)},
            request=request
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def upload_help_image(request):
    """Upload an image for help content (admin only)."""
    try:
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif']
        if file.content_type not in allowed_types:
            log_activity(
                user=request.user,
                action=AUDIT_ACTIONS["CREATE"],
                module=AUDIT_MODULES["HELP"],
                description="Failed to upload help image - invalid file type",
                message=f"Attempted to upload invalid file type: {file.content_type}",
                metadata={
                    "filename": file.name,
                    "file_type": file.content_type,
                    "status": "error",
                    "error": "Invalid file type"
                },
                request=request
            )
            return Response(
                {'error': 'Invalid file type. Only images are allowed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file size (max 5MB)
        if file.size > 5 * 1024 * 1024:
            log_activity(
                user=request.user,
                action=AUDIT_ACTIONS["CREATE"],
                module=AUDIT_MODULES["HELP"],
                description="Failed to upload help image - file too large",
                message=f"Attempted to upload file exceeding size limit: {file.name}",
                metadata={
                    "filename": file.name,
                    "file_size": file.size,
                    "status": "error",
                    "error": "File size exceeds 5MB limit"
                },
                request=request
            )
            return Response(
                {'error': 'File size exceeds 5MB limit'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save file to media/help/images/
        help_images_dir = os.path.join(settings.MEDIA_ROOT, 'help', 'images')
        os.makedirs(help_images_dir, exist_ok=True)
        
        # Generate unique filename
        file_ext = os.path.splitext(file.name)[1]
        filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(help_images_dir, filename)
        
        # Save file
        with default_storage.open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        # Return URL
        image_url = f"{settings.MEDIA_URL}help/images/{filename}"
        
        # Log successful upload
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["CREATE"],
            module=AUDIT_MODULES["HELP"],
            description=f"Uploaded help image: {file.name}",
            message=f"Uploaded help image '{file.name}' as {filename}",
            metadata={
                "original_filename": file.name,
                "saved_filename": filename,
                "file_size": file.size,
                "file_type": file.content_type,
                "image_url": image_url,
                "status": "success"
            },
            request=request
        )
        
        return Response({
            'success': True,
            'url': image_url,
            'filename': filename
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        log_activity(
            user=request.user,
            action=AUDIT_ACTIONS["CREATE"],
            module=AUDIT_MODULES["HELP"],
            description="Failed to upload help image",
            message=f"Error uploading help image: {str(e)}",
            metadata={
                "status": "error",
                "error": str(e)
            },
            request=request
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

