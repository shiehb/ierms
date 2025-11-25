"""
Management command to clean up and rename help images.

This command will:
1. Delete unused images (not referenced in any help topic)
2. Rename images with meaningful names based on topic and step
3. Update topic references to use new image names

Usage:
    python manage.py cleanup_help_images
    python manage.py cleanup_help_images --dry-run  # Preview changes
    python manage.py cleanup_help_images --no-backup  # Skip backup
"""
import os
import re
import json
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from help.utils import (
    get_help_topics,
    save_help_topics,
    HELP_TOPICS_FILE,
    HELP_BACKUPS_DIR
)
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up unused help images and rename them with meaningful names'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without making them',
        )
        parser.add_argument(
            '--no-backup',
            action='store_true',
            help='Skip creating backup of topics file',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        no_backup = options.get('no_backup', False)
        force = options.get('force', False)

        self.stdout.write(self.style.SUCCESS('\n=== Help Images Cleanup Tool ===\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))

        # Get paths
        help_images_dir = os.path.join(settings.MEDIA_ROOT, 'help', 'images')
        os.makedirs(help_images_dir, exist_ok=True)

        # Load topics
        try:
            topics = get_help_topics()
            self.stdout.write(f'Loaded {len(topics)} help topics')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error loading topics: {e}'))
            return

        # Extract all image references from topics
        used_images = self._extract_image_references(topics)
        self.stdout.write(f'Found {len(used_images)} image references in topics')

        # Get all image files in directory
        all_images = self._get_all_image_files(help_images_dir)
        self.stdout.write(f'Found {len(all_images)} image files in directory\n')

        # Identify unused images
        unused_images = [img for img in all_images if img not in used_images]
        
        if unused_images:
            self.stdout.write(self.style.WARNING(f'Found {len(unused_images)} unused images:'))
            for img in unused_images:
                self.stdout.write(f'  - {img}')
        else:
            self.stdout.write(self.style.SUCCESS('No unused images found'))

        # Plan renaming
        rename_plan = self._plan_renames(topics, used_images, help_images_dir)
        
        if rename_plan:
            self.stdout.write(f'\n{len(rename_plan)} images will be renamed:')
            for old_name, new_name in rename_plan.items():
                self.stdout.write(f'  {old_name} -> {new_name}')
        else:
            self.stdout.write('\nNo images need renaming')

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write('SUMMARY:')
        self.stdout.write(f'  Unused images to delete: {len(unused_images)}')
        self.stdout.write(f'  Images to rename: {len(rename_plan)}')
        self.stdout.write('='*50 + '\n')

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run complete. Use without --dry-run to apply changes.'))
            return

        # Confirm before proceeding
        if not force:
            confirm = input('Do you want to proceed? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled.'))
                return

        # Create backup
        if not no_backup:
            self._create_backup()

        # Delete unused images
        deleted_count = 0
        for img_name in unused_images:
            img_path = os.path.join(help_images_dir, img_name)
            try:
                os.remove(img_path)
                deleted_count += 1
                self.stdout.write(f'Deleted: {img_name}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error deleting {img_name}: {e}'))

        # Rename images and update topics
        if rename_plan:
            updated_topics = self._rename_images_and_update_topics(
                topics, rename_plan, help_images_dir
            )
            
            # Save updated topics
            try:
                save_help_topics(updated_topics)
                self.stdout.write(self.style.SUCCESS(f'\nSuccessfully updated {len(rename_plan)} images'))
                self.stdout.write(self.style.SUCCESS('Topics file updated with new image references'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error saving topics: {e}'))
                return

        self.stdout.write(self.style.SUCCESS(f'\n✓ Cleanup complete!'))
        self.stdout.write(f'  - Deleted {deleted_count} unused images')
        self.stdout.write(f'  - Renamed {len(rename_plan)} images')

    def _extract_image_references(self, topics):
        """Extract all image filenames referenced in topics."""
        used_images = set()
        
        for topic in topics:
            if 'steps' in topic and isinstance(topic['steps'], list):
                for step in topic['steps']:
                    if 'image' in step and step['image']:
                        img_url = step['image']
                        # Extract filename from URL
                        filename = self._extract_filename_from_url(img_url)
                        if filename:
                            used_images.add(filename)
        
        return used_images

    def _extract_filename_from_url(self, url):
        """Extract filename from image URL."""
        if not url:
            return None
        
        # Handle different URL formats
        # /media/help/images/filename.jpg
        # http://example.com/media/help/images/filename.jpg
        # filename.jpg
        
        # Remove query parameters if any
        url = url.split('?')[0]
        
        # Extract filename
        if '/media/help/images/' in url:
            filename = url.split('/media/help/images/')[-1]
        elif '/help/images/' in url:
            filename = url.split('/help/images/')[-1]
        elif '/' in url:
            filename = url.split('/')[-1]
        else:
            filename = url
        
        return filename if filename else None

    def _get_all_image_files(self, directory):
        """Get all image files in directory."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        files = []
        
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in image_extensions:
                        files.append(filename)
        
        return files

    def _plan_renames(self, topics, used_images, help_images_dir):
        """Plan image renames based on topic and step information."""
        rename_plan = {}
        used_new_names = set()  # Track names we've already assigned
        
        for topic in topics:
            topic_id = topic.get('id', 'unknown')
            topic_title = topic.get('title', 'untitled')
            topic_slug = self._slugify(topic_title)
            
            if 'steps' in topic and isinstance(topic['steps'], list):
                for step_index, step in enumerate(topic['steps'], 1):
                    if 'image' in step and step['image']:
                        old_filename = self._extract_filename_from_url(step['image'])
                        
                        if old_filename and old_filename in used_images:
                            # Get file extension
                            ext = os.path.splitext(old_filename)[1].lower()
                            
                            # Generate new filename
                            new_filename = f"{topic_id}-{topic_slug}-step-{step_index}{ext}"
                            
                            # Check if image already has the correct name format
                            # Pattern: {id}-{slug}-step-{number}.{ext}
                            expected_pattern = f"{topic_id}-{topic_slug}-step-{step_index}{ext}"
                            if old_filename == expected_pattern:
                                # Already correctly named, skip
                                used_new_names.add(old_filename)
                                continue
                            
                            # Handle duplicates (if same topic has multiple steps with same name pattern)
                            if new_filename in used_new_names or new_filename in rename_plan.values():
                                counter = 2
                                base_name = f"{topic_id}-{topic_slug}-step-{step_index}"
                                while (f"{base_name}-{counter}{ext}" in used_new_names or 
                                       f"{base_name}-{counter}{ext}" in rename_plan.values()):
                                    counter += 1
                                new_filename = f"{base_name}-{counter}{ext}"
                            
                            # Only rename if different
                            if old_filename != new_filename:
                                rename_plan[old_filename] = new_filename
                                used_new_names.add(new_filename)
        
        return rename_plan

    def _slugify(self, text):
        """Convert text to URL-friendly slug."""
        if not text:
            return 'untitled'
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace spaces and special chars with hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        
        # Remove leading/trailing hyphens
        text = text.strip('-')
        
        # Limit length
        if len(text) > 50:
            text = text[:50].rstrip('-')
        
        return text or 'untitled'

    def _rename_images_and_update_topics(self, topics, rename_plan, help_images_dir):
        """Rename images and update topic references."""
        updated_topics = []
        
        # Create reverse mapping (old -> new)
        old_to_new = rename_plan
        
        for topic in topics:
            updated_topic = topic.copy()
            
            if 'steps' in updated_topic and isinstance(updated_topic['steps'], list):
                updated_steps = []
                
                for step in updated_topic['steps']:
                    updated_step = step.copy()
                    
                    if 'image' in updated_step and updated_step['image']:
                        old_filename = self._extract_filename_from_url(updated_step['image'])
                        
                        if old_filename in old_to_new:
                            new_filename = old_to_new[old_filename]
                            
                            # Rename the actual file
                            old_path = os.path.join(help_images_dir, old_filename)
                            new_path = os.path.join(help_images_dir, new_filename)
                            
                            if os.path.exists(old_path):
                                try:
                                    os.rename(old_path, new_path)
                                    self.stdout.write(f'Renamed: {old_filename} -> {new_filename}')
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f'Error renaming {old_filename}: {e}'))
                                    continue
                            
                            # Update image URL in step
                            # Preserve the URL format (keep /media/help/images/ prefix)
                            if updated_step['image'].startswith('/media/'):
                                updated_step['image'] = f"/media/help/images/{new_filename}"
                            elif '/media/help/images/' in updated_step['image']:
                                updated_step['image'] = updated_step['image'].replace(
                                    old_filename, new_filename
                                )
                            else:
                                updated_step['image'] = f"/media/help/images/{new_filename}"
                    
                    updated_steps.append(updated_step)
                
                updated_topic['steps'] = updated_steps
            
            updated_topics.append(updated_topic)
        
        return updated_topics

    def _create_backup(self):
        """Create backup of topics file."""
        if not os.path.exists(HELP_TOPICS_FILE):
            return
        
        backup_file = os.path.join(
            HELP_BACKUPS_DIR,
            f"help_topics_before_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        os.makedirs(HELP_BACKUPS_DIR, exist_ok=True)
        
        try:
            shutil.copy2(HELP_TOPICS_FILE, backup_file)
            self.stdout.write(self.style.SUCCESS(f'Backup created: {backup_file}'))
            
            # Clean up old cleanup backups (keep only 3)
            from help.utils import cleanup_old_backups
            deleted = cleanup_old_backups(HELP_BACKUPS_DIR, 'help_topics_before_cleanup_', 3)
            if deleted > 0:
                self.stdout.write(f'Cleaned up {deleted} old cleanup backup(s)')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Warning: Could not create backup: {e}'))

