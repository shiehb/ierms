"""
Management command to migrate help data from JavaScript files to JSON.
"""
import json
import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from help.utils import (
    save_help_topics,
    save_help_categories,
    HELP_DATA_DIR,
)


class Command(BaseCommand):
    help = 'Migrates help data from src/data/helpData.js and src/data/helpCategories.js to JSON files in media/help/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing JSON files',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting help data migration...'))
        
        # Get base directory (project root)
        base_dir = settings.BASE_DIR.parent  # Go up from server/ to project root
        
        help_data_path = base_dir / 'src' / 'data' / 'helpData.js'
        help_categories_path = base_dir / 'src' / 'data' / 'helpCategories.js'
        
        # Check if files exist
        if not help_data_path.exists():
            self.stdout.write(self.style.ERROR(f'File not found: {help_data_path}'))
            return
        
        if not help_categories_path.exists():
            self.stdout.write(self.style.ERROR(f'File not found: {help_categories_path}'))
            return
        
        # Check if JSON files already exist
        topics_json_path = os.path.join(HELP_DATA_DIR, 'help_topics.json')
        categories_json_path = os.path.join(HELP_DATA_DIR, 'help_categories.json')
        
        if os.path.exists(topics_json_path) and not options['force']:
            self.stdout.write(
                self.style.WARNING(
                    f'help_topics.json already exists. Use --force to overwrite.'
                )
            )
            return
        
        if os.path.exists(categories_json_path) and not options['force']:
            self.stdout.write(
                self.style.WARNING(
                    f'help_categories.json already exists. Use --force to overwrite.'
                )
            )
            return
        
        try:
            # Read and parse helpData.js
            self.stdout.write('Reading helpData.js...')
            with open(help_data_path, 'r', encoding='utf-8') as f:
                help_data_content = f.read()
            
            # Extract the helpTopics array using regex
            # Find the content between export const helpTopics = [ and ];
            match = re.search(r'export const helpTopics = (\[.*?\]);', help_data_content, re.DOTALL)
            if not match:
                self.stdout.write(self.style.ERROR('Could not find helpTopics array in helpData.js'))
                return
            
            topics_str = match.group(1)
            
            # Convert JavaScript to JSON
            # Replace JS comments and fix common issues
            topics_str = re.sub(r'//.*?$', '', topics_str, flags=re.MULTILINE)  # Remove single-line comments
            topics_str = re.sub(r'/\*.*?\*/', '', topics_str, flags=re.DOTALL)  # Remove multi-line comments
            
            # Try to parse as JSON
            try:
                topics = json.loads(topics_str)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to use eval (less safe but works for migration)
                self.stdout.write(self.style.WARNING('JSON parsing failed, using eval (less safe)...'))
                try:
                    # Create a safe context for eval
                    topics = eval(topics_str)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Failed to parse topics: {e}'))
                    return
            
            # Read and parse helpCategories.js
            self.stdout.write('Reading helpCategories.js...')
            with open(help_categories_path, 'r', encoding='utf-8') as f:
                categories_content = f.read()
            
            # Extract the helpCategories array
            match = re.search(r'export const helpCategories = (\[.*?\]);', categories_content, re.DOTALL)
            if not match:
                self.stdout.write(self.style.ERROR('Could not find helpCategories array in helpCategories.js'))
                return
            
            categories_str = match.group(1)
            
            # Remove comments
            categories_str = re.sub(r'//.*?$', '', categories_str, flags=re.MULTILINE)
            categories_str = re.sub(r'/\*.*?\*/', '', categories_str, flags=re.DOTALL)
            
            try:
                categories = json.loads(categories_str)
            except json.JSONDecodeError:
                self.stdout.write(self.style.WARNING('JSON parsing failed for categories, using eval...'))
                try:
                    categories = eval(categories_str)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Failed to parse categories: {e}'))
                    return
            
            # Add timestamps to topics if not present
            from datetime import datetime
            for topic in topics:
                if 'created_at' not in topic:
                    topic['created_at'] = datetime.now().isoformat()
                if 'updated_at' not in topic:
                    topic['updated_at'] = datetime.now().isoformat()
            
            # Save to JSON files
            self.stdout.write('Saving help topics...')
            save_help_topics(topics)
            self.stdout.write(self.style.SUCCESS(f'✓ Saved {len(topics)} topics'))
            
            self.stdout.write('Saving help categories...')
            save_help_categories(categories)
            self.stdout.write(self.style.SUCCESS(f'✓ Saved {len(categories)} categories'))
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nMigration completed successfully!\n'
                    f'Files saved to: {HELP_DATA_DIR}'
                )
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during migration: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())

