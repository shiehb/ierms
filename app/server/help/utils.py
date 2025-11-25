"""
Utility functions for help content management.
"""
import json
import os
import zipfile
import tempfile
import shutil
from datetime import datetime
from django.conf import settings
from pathlib import Path


# Help directory configuration
HELP_DATA_DIR = os.path.join(settings.MEDIA_ROOT, 'help')
HELP_BACKUPS_DIR = os.path.join(HELP_DATA_DIR, 'backups')
HELP_TOPICS_FILE = os.path.join(HELP_DATA_DIR, 'help_topics.json')
HELP_CATEGORIES_FILE = os.path.join(HELP_DATA_DIR, 'help_categories.json')

# Ensure directories exist
os.makedirs(HELP_DATA_DIR, exist_ok=True)
os.makedirs(HELP_BACKUPS_DIR, exist_ok=True)


def get_help_topics():
    """Read help topics from JSON file."""
    try:
        if os.path.exists(HELP_TOPICS_FILE):
            with open(HELP_TOPICS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except (json.JSONDecodeError, IOError) as e:
        raise ValueError(f"Error reading help topics: {str(e)}")


def get_help_categories():
    """Read help categories from JSON file."""
    try:
        if os.path.exists(HELP_CATEGORIES_FILE):
            with open(HELP_CATEGORIES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except (json.JSONDecodeError, IOError) as e:
        raise ValueError(f"Error reading help categories: {str(e)}")


def rename_help_images(topics):
    """Rename help images to meaningful names based on topic and step info.
    
    Args:
        topics: List of topic dictionaries
    
    Returns:
        Tuple of (updated_topics, rename_count) where rename_count is number of images renamed
    """
    import re
    
    help_images_dir = os.path.join(settings.MEDIA_ROOT, 'help', 'images')
    if not os.path.exists(help_images_dir):
        return topics, 0
    
    def slugify(text):
        """Convert text to URL-friendly slug."""
        if not text:
            return 'untitled'
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        text = text.strip('-')
        if len(text) > 50:
            text = text[:50].rstrip('-')
        return text or 'untitled'
    
    def extract_filename_from_url(url):
        """Extract filename from image URL."""
        if not url:
            return None
        url = url.split('?')[0]
        if '/media/help/images/' in url:
            return url.split('/media/help/images/')[-1]
        elif '/help/images/' in url:
            return url.split('/help/images/')[-1]
        elif '/' in url:
            return url.split('/')[-1]
        return url
    
    updated_topics = []
    rename_count = 0
    used_new_names = set()
    
    for topic in topics:
        updated_topic = topic.copy()
        topic_id = topic.get('id', 'unknown')
        topic_title = topic.get('title', 'untitled')
        topic_slug = slugify(topic_title)
        
        if 'steps' in updated_topic and isinstance(updated_topic['steps'], list):
            updated_steps = []
            
            for step_index, step in enumerate(updated_topic['steps'], 1):
                updated_step = step.copy()
                
                if 'image' in updated_step and updated_step['image']:
                    old_filename = extract_filename_from_url(updated_step['image'])
                    
                    if old_filename:
                        # Generate new filename
                        ext = os.path.splitext(old_filename)[1].lower()
                        new_filename = f"{topic_id}-{topic_slug}-step-{step_index}{ext}"
                        
                        # Check if already correctly named
                        expected_pattern = f"{topic_id}-{topic_slug}-step-{step_index}{ext}"
                        if old_filename == expected_pattern:
                            # Already correctly named
                            used_new_names.add(old_filename)
                            updated_steps.append(updated_step)
                            continue
                        
                        # Handle duplicates
                        if new_filename in used_new_names:
                            counter = 2
                            base_name = f"{topic_id}-{topic_slug}-step-{step_index}"
                            while f"{base_name}-{counter}{ext}" in used_new_names:
                                counter += 1
                            new_filename = f"{base_name}-{counter}{ext}"
                        
                        # Rename the file if it exists and name is different
                        old_path = os.path.join(help_images_dir, old_filename)
                        new_path = os.path.join(help_images_dir, new_filename)
                        
                        if old_filename != new_filename and os.path.exists(old_path):
                            try:
                                # Check if new filename already exists (shouldn't happen, but safety check)
                                if not os.path.exists(new_path):
                                    os.rename(old_path, new_path)
                                    rename_count += 1
                                    
                                    # Update image URL in step
                                    if updated_step['image'].startswith('/media/'):
                                        updated_step['image'] = f"/media/help/images/{new_filename}"
                                    elif '/media/help/images/' in updated_step['image']:
                                        updated_step['image'] = updated_step['image'].replace(
                                            old_filename, new_filename
                                        )
                                    else:
                                        updated_step['image'] = f"/media/help/images/{new_filename}"
                                    
                                    used_new_names.add(new_filename)
                                else:
                                    # New filename exists, keep old name but log warning
                                    print(f"Warning: Target filename {new_filename} already exists, keeping {old_filename}")
                            except (OSError, IOError) as e:
                                print(f"Warning: Could not rename {old_filename} to {new_filename}: {e}")
                        
                updated_steps.append(updated_step)
            
            updated_topic['steps'] = updated_steps
        
        updated_topics.append(updated_topic)
    
    return updated_topics, rename_count


def _extract_image_filenames_from_topics(topics):
    """Extract all image filenames referenced in topics."""
    import re
    
    def extract_filename_from_url(url):
        """Extract filename from image URL."""
        if not url:
            return None
        url = url.split('?')[0]
        if '/media/help/images/' in url:
            return url.split('/media/help/images/')[-1]
        elif '/help/images/' in url:
            return url.split('/help/images/')[-1]
        elif '/' in url:
            return url.split('/')[-1]
        return url
    
    image_files = set()
    
    for topic in topics:
        if 'steps' in topic and isinstance(topic['steps'], list):
            for step in topic['steps']:
                if 'image' in step and step['image']:
                    filename = extract_filename_from_url(step['image'])
                    if filename:
                        image_files.add(filename)
    
    return image_files


def _delete_unused_images(old_image_files, new_image_files):
    """Delete image files that are no longer referenced.
    
    Args:
        old_image_files: Set of old image filenames
        new_image_files: Set of new image filenames
    
    Returns:
        Number of images deleted
    """
    help_images_dir = os.path.join(settings.MEDIA_ROOT, 'help', 'images')
    if not os.path.exists(help_images_dir):
        return 0
    
    # Find images that were removed (in old but not in new)
    removed_images = old_image_files - new_image_files
    
    deleted_count = 0
    for filename in removed_images:
        file_path = os.path.join(help_images_dir, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                deleted_count += 1
                print(f"Deleted unused image: {filename}")
            except (OSError, IOError) as e:
                print(f"Warning: Could not delete image {filename}: {e}")
    
    return deleted_count


def save_help_topics(topics):
    """Save help topics to JSON file with backup."""
    # Validate JSON structure
    if not isinstance(topics, list):
        raise ValueError("Topics must be a list")
    
    # Validate each topic has required fields
    required_fields = ['id', 'title', 'description', 'category']
    for topic in topics:
        if not isinstance(topic, dict):
            raise ValueError("Each topic must be a dictionary")
        for field in required_fields:
            if field not in topic:
                raise ValueError(f"Topic missing required field: {field}")
    
    # Load old topics to compare images
    old_topics = []
    old_image_files = set()
    if os.path.exists(HELP_TOPICS_FILE):
        try:
            old_topics = get_help_topics()
            old_image_files = _extract_image_filenames_from_topics(old_topics)
        except Exception as e:
            print(f"Warning: Could not load old topics for image comparison: {e}")
    
    # Auto-rename images before saving
    topics, renamed_count = rename_help_images(topics)
    if renamed_count > 0:
        print(f"Auto-renamed {renamed_count} image(s) to meaningful names")
    
    # Extract new image filenames
    new_image_files = _extract_image_filenames_from_topics(topics)
    
    # Delete unused images (images that were removed or replaced)
    deleted_count = _delete_unused_images(old_image_files, new_image_files)
    if deleted_count > 0:
        print(f"Deleted {deleted_count} unused image(s)")
    
    # Create backup before saving
    if os.path.exists(HELP_TOPICS_FILE):
        backup_file = os.path.join(
            HELP_BACKUPS_DIR,
            f"help_topics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        try:
            with open(HELP_TOPICS_FILE, 'r', encoding='utf-8') as src:
                with open(backup_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
        except IOError as e:
            # Log error but continue with save
            print(f"Warning: Failed to create backup: {e}")
    
    # Clean up old backups (keep last 3)
    cleanup_old_backups(HELP_BACKUPS_DIR, 'help_topics_', 3)
    
    # Save new data
    try:
        with open(HELP_TOPICS_FILE, 'w', encoding='utf-8') as f:
            json.dump(topics, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        raise ValueError(f"Error saving help topics: {str(e)}")


def save_help_categories(categories):
    """Save help categories to JSON file with backup."""
    # Validate JSON structure
    if not isinstance(categories, list):
        raise ValueError("Categories must be a list")
    
    # Validate each category has required fields
    required_fields = ['key', 'name']
    for category in categories:
        if not isinstance(category, dict):
            raise ValueError("Each category must be a dictionary")
        for field in required_fields:
            if field not in category:
                raise ValueError(f"Category missing required field: {field}")
    
    # Create backup before saving
    if os.path.exists(HELP_CATEGORIES_FILE):
        backup_file = os.path.join(
            HELP_BACKUPS_DIR,
            f"help_categories_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        try:
            with open(HELP_CATEGORIES_FILE, 'r', encoding='utf-8') as src:
                with open(backup_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
        except IOError as e:
            print(f"Warning: Failed to create backup: {e}")
    
    # Clean up old backups (keep last 3)
    cleanup_old_backups(HELP_BACKUPS_DIR, 'help_categories_', 3)
    
    # Save new data
    try:
        with open(HELP_CATEGORIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(categories, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        raise ValueError(f"Error saving help categories: {str(e)}")


def cleanup_old_backups(backup_dir, prefix, keep_count=3):
    """Remove old backup files, keeping only the most recent ones.
    
    Args:
        backup_dir: Directory containing backup files
        prefix: Prefix to match backup files (e.g., 'help_topics_')
        keep_count: Number of most recent backups to keep (default: 3)
    
    Returns:
        Number of backups deleted
    """
    try:
        if not os.path.exists(backup_dir):
            return 0
            
        backup_files = [
            f for f in os.listdir(backup_dir)
            if f.startswith(prefix) and f.endswith('.json')
        ]
        
        if len(backup_files) <= keep_count:
            return 0
        
        # Sort by modification time (newest first)
        backup_files_with_path = [
            (f, os.path.join(backup_dir, f))
            for f in backup_files
        ]
        backup_files_with_path.sort(
            key=lambda x: os.path.getmtime(x[1]),
            reverse=True
        )
        
        # Delete oldest backups
        deleted_count = 0
        for old_file, old_path in backup_files_with_path[keep_count:]:
            try:
                os.remove(old_path)
                deleted_count += 1
            except (IOError, OSError) as e:
                # Log error but continue
                print(f"Warning: Could not delete backup {old_file}: {e}")
        
        return deleted_count
    except (IOError, OSError) as e:
        print(f"Warning: Error during backup cleanup: {e}")
        return 0


def export_help_data(include_images=True):
    """Export all help data as a single JSON object or ZIP archive with images.
    
    Args:
        include_images: If True, returns ZIP bytes with JSON and images. If False, returns dict.
    
    Returns:
        If include_images=True: (zip_bytes, filename)
        If include_images=False: dict with topics, categories, exported_at
    """
    topics = get_help_topics()
    categories = get_help_categories()
    data = {
        'topics': topics,
        'categories': categories,
        'exported_at': datetime.now().isoformat()
    }
    
    if not include_images:
        return data
    
    # Create ZIP archive with images
    help_images_dir = os.path.join(settings.MEDIA_ROOT, 'help', 'images')
    
    # Create temporary ZIP file
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_zip_path = temp_zip.name
    temp_zip.close()
    
    try:
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add JSON data
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            zipf.writestr('help_data.json', json_str.encode('utf-8'))
            
            # Extract and add all referenced images
            image_files = _extract_image_filenames_from_topics(topics)
            images_added = 0
            
            for filename in image_files:
                image_path = os.path.join(help_images_dir, filename)
                if os.path.exists(image_path):
                    # Add to images/ folder in ZIP
                    zipf.write(image_path, f'images/{filename}')
                    images_added += 1
            
            print(f"Exported {len(topics)} topics, {len(categories)} categories, and {images_added} images")
        
        # Read ZIP file as bytes
        with open(temp_zip_path, 'rb') as f:
            zip_bytes = f.read()
        
        # Generate filename
        zip_filename = f"help_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        return zip_bytes, zip_filename
    finally:
        # Clean up temporary file
        if os.path.exists(temp_zip_path):
            os.remove(temp_zip_path)


def import_help_data(data, zip_file_path=None):
    """Import help data from JSON object or ZIP archive.
    
    Args:
        data: Dictionary with topics and categories (if importing from JSON)
        zip_file_path: Path to ZIP file (if importing from ZIP)
    
    Returns:
        dict with import statistics
    """
    topics = []
    categories = []
    images_imported = 0
    
    # If ZIP file provided, extract it
    if zip_file_path and os.path.exists(zip_file_path):
        help_images_dir = os.path.join(settings.MEDIA_ROOT, 'help', 'images')
        os.makedirs(help_images_dir, exist_ok=True)
        
        temp_extract_dir = tempfile.mkdtemp()
        
        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zipf:
                # Extract all files
                zipf.extractall(temp_extract_dir)
                
                # Read JSON data
                json_path = os.path.join(temp_extract_dir, 'help_data.json')
                if not os.path.exists(json_path):
                    raise ValueError("ZIP file missing help_data.json")
                
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                topics = data.get('topics', [])
                categories = data.get('categories', [])
                
                # Extract and copy images
                images_dir_in_zip = os.path.join(temp_extract_dir, 'images')
                if os.path.exists(images_dir_in_zip):
                    for filename in os.listdir(images_dir_in_zip):
                        src_path = os.path.join(images_dir_in_zip, filename)
                        if os.path.isfile(src_path):
                            # Check if image already exists (skip if same)
                            dst_path = os.path.join(help_images_dir, filename)
                            if not os.path.exists(dst_path):
                                shutil.copy2(src_path, dst_path)
                                images_imported += 1
                            else:
                                # File exists, check if different
                                if os.path.getsize(src_path) != os.path.getsize(dst_path):
                                    shutil.copy2(src_path, dst_path)
                                    images_imported += 1
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir)
    else:
        # Import from JSON dict
        if not isinstance(data, dict):
            raise ValueError("Import data must be a dictionary")
        
        topics = data.get('topics', [])
        categories = data.get('categories', [])
    
    # Save topics and categories
    if topics:
        save_help_topics(topics)
    
    if categories:
        save_help_categories(categories)
    
    return {
        'topics_imported': len(topics),
        'categories_imported': len(categories),
        'images_imported': images_imported,
        'success': True
    }

