import os
import json
import uuid
import re
import logging
from flask import Blueprint, request, jsonify, session, redirect, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import threading
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

drive_bp = Blueprint('drive', __name__)

# OAuth 2.0 configuration with embedded credentials
CLIENT_SECRETS = {
    "web": {
        "client_id": "942837702801-j94s5e2vp0r3vo9oud03vil0623imtog.apps.googleusercontent.com",
        "client_secret": "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",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [
            "https://google-drive-cloner-render-production.up.railway.app/api/auth/callback"
        ]
    }
}

SCOPES = ['https://www.googleapis.com/auth/drive']

# Store for tracking clone progress
clone_progress = {}

def extract_file_id_from_url(url):
    """Extract Google Drive file/folder ID from various URL formats"""
    patterns = [
        r'/folders/([a-zA-Z0-9-_]+)',
        r'/file/d/([a-zA-Z0-9-_]+)',
        r'id=([a-zA-Z0-9-_]+)',
        r'/drive/folders/([a-zA-Z0-9-_]+)',
        r'/open\\?id=([a-zA-Z0-9-_]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_drive_service(credentials):
    """Create Google Drive service instance"""
    try:
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        logger.error(f"Error creating Drive service: {e}")
        raise

def clone_file(service, file_id, parent_id=None, progress_tracker=None, task_id=None):
    """Clone a single file"""
    try:
        # Get file metadata
        file_metadata = service.files().get(fileId=file_id).execute()
        
        # Prepare copy request
        copy_metadata = {
            'name': f"Copy of {file_metadata['name']}"
        }
        if parent_id:
            copy_metadata['parents'] = [parent_id]
        
        # Copy the file
        copied_file = service.files().copy(fileId=file_id, body=copy_metadata).execute()
        
        if progress_tracker and task_id:
            progress_tracker[task_id]['completed'] += 1
            progress_tracker[task_id]['current_file'] = file_metadata['name']
        
        logger.info(f"Successfully copied file: {file_metadata['name']}")
        return copied_file
    except HttpError as error:
        error_msg = f"Error copying file {file_id}: {error}"
        logger.error(error_msg)
        if progress_tracker and task_id:
            progress_tracker[task_id]['errors'].append(error_msg)
        return None
    except Exception as e:
        error_msg = f"Unexpected error copying file {file_id}: {e}"
        logger.error(error_msg)
        if progress_tracker and task_id:
            progress_tracker[task_id]['errors'].append(error_msg)
        return None

def clone_folder_recursive(service, folder_id, parent_id=None, progress_tracker=None, task_id=None):
    """Recursively clone a folder and its contents"""
    try:
        # Get folder metadata
        folder_metadata = service.files().get(fileId=folder_id).execute()
        
        # Create new folder
        new_folder_metadata = {
            'name': f"Copy of {folder_metadata['name']}",
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            new_folder_metadata['parents'] = [parent_id]
        
        new_folder = service.files().create(body=new_folder_metadata).execute()
        new_folder_id = new_folder['id']
        
        if progress_tracker and task_id:
            progress_tracker[task_id]['completed'] += 1
            progress_tracker[task_id]['current_file'] = folder_metadata['name']
        
        # List all items in the folder
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType)"
        ).execute()
        
        items = results.get('files', [])
        
        for item in items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                # Recursively clone subfolder
                clone_folder_recursive(service, item['id'], new_folder_id, progress_tracker, task_id)
            else:
                # Clone file
                clone_file(service, item['id'], new_folder_id, progress_tracker, task_id)
        
        logger.info(f"Successfully cloned folder: {folder_metadata['name']}")
        return new_folder
    except HttpError as error:
        error_msg = f"Error cloning folder {folder_id}: {error}"
        logger.error(error_msg)
        if progress_tracker and task_id:
            progress_tracker[task_id]['errors'].append(error_msg)
        return None
    except Exception as e:
        error_msg = f"Unexpected error cloning folder {folder_id}: {e}"
        logger.error(error_msg)
        if progress_tracker and task_id:
            progress_tracker[task_id]['errors'].append(error_msg)
        return None

def count_items_recursive(service, folder_id):
    """Count total items in a folder recursively"""
    try:
        count = 1  # Count the folder itself
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, mimeType)"
        ).execute()
        
        items = results.get('files', [])
        
        for item in items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                count += count_items_recursive(service, item['id'])
            else:
                count += 1
        
        return count
    except HttpError as error:
        logger.error(f"Error counting items in folder {folder_id}: {error}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error counting items in folder {folder_id}: {e}")
        return 1

@drive_bp.route('/auth/login')
def login():
    """Initiate OAuth flow"""
    try:
        flow = Flow.from_client_config(CLIENT_SECRETS, SCOPES)
        flow.redirect_uri = url_for('drive.callback', _external=True)
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        session['state'] = state
        logger.info("OAuth flow initiated successfully")
        return jsonify({'auth_url': authorization_url})
    except Exception as e:
        logger.error(f"Error initiating OAuth flow: {e}")
        return jsonify({'error': f'Failed to initiate OAuth flow: {str(e)}'}), 500

@drive_bp.route('/auth/callback')
def callback():
    """Handle OAuth callback"""
    try:
        state = session.get('state')
        
        flow = Flow.from_client_config(CLIENT_SECRETS, SCOPES, state=state)
        flow.redirect_uri = url_for('drive.callback', _external=True)
        
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        session['credentials'] = credentials_to_dict(credentials)
        
        logger.info("OAuth callback processed successfully")
        return redirect('/')
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return f"Authentication failed: {str(e)}", 500

@drive_bp.route('/auth/status')
def auth_status():
    """Check authentication status"""
    try:
        if 'credentials' not in session:
            return jsonify({'authenticated': False})
        
        credentials = Credentials(**session['credentials'])
        
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                session['credentials'] = credentials_to_dict(credentials)
            else:
                return jsonify({'authenticated': False})
        
        return jsonify({'authenticated': True})
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return jsonify({'authenticated': False, 'error': str(e)})

@drive_bp.route('/parse-url', methods=['POST'])
def parse_url():
    """Parse Google Drive URL and get file/folder metadata"""
    try:
        if 'credentials' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        file_id = extract_file_id_from_url(url)
        if not file_id:
            return jsonify({'error': 'Invalid Google Drive URL'}), 400
        
        credentials = Credentials(**session['credentials'])
        service = get_drive_service(credentials)
        
        file_metadata = service.files().get(fileId=file_id, fields='id,name,mimeType,size,parents').execute()
        
        # Check if it's a folder
        is_folder = file_metadata['mimeType'] == 'application/vnd.google-apps.folder'
        
        response = {
            'id': file_metadata['id'],
            'name': file_metadata['name'],
            'type': 'folder' if is_folder else 'file',
            'size': file_metadata.get('size', 'Unknown')
        }
        
        if is_folder:
            # Count items in folder
            item_count = count_items_recursive(service, file_id)
            response['item_count'] = item_count
        
        logger.info(f"Successfully parsed URL for: {file_metadata['name']}")
        return jsonify(response)
    except HttpError as error:
        logger.error(f"HTTP error parsing URL: {error}")
        return jsonify({'error': f'Failed to access file: {str(error)}'}), 400
    except Exception as e:
        logger.error(f"Unexpected error parsing URL: {e}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@drive_bp.route('/clone', methods=['POST'])
def start_clone():
    """Start cloning process"""
    try:
        if 'credentials' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        file_id = data.get('file_id')
        
        if not file_id:
            return jsonify({'error': 'File ID is required'}), 400
        
        credentials = Credentials(**session['credentials'])
        service = get_drive_service(credentials)
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Initialize progress tracking
        clone_progress[task_id] = {
            'status': 'starting',
            'total': 0,
            'completed': 0,
            'current_file': '',
            'errors': []
        }
        
        def clone_task():
            try:
                # Get file metadata to determine if it's a file or folder
                file_metadata = service.files().get(fileId=file_id).execute()
                is_folder = file_metadata['mimeType'] == 'application/vnd.google-apps.folder'
                
                if is_folder:
                    # Count total items
                    total_items = count_items_recursive(service, file_id)
                    clone_progress[task_id]['total'] = total_items
                    clone_progress[task_id]['status'] = 'cloning'
                    
                    # Clone folder
                    result = clone_folder_recursive(service, file_id, None, clone_progress, task_id)
                else:
                    clone_progress[task_id]['total'] = 1
                    clone_progress[task_id]['status'] = 'cloning'
                    
                    # Clone single file
                    result = clone_file(service, file_id, None, clone_progress, task_id)
                
                if result:
                    clone_progress[task_id]['status'] = 'completed'
                    clone_progress[task_id]['result'] = {
                        'id': result['id'],
                        'name': result['name']
                    }
                    logger.info(f"Clone task completed successfully: {task_id}")
                else:
                    clone_progress[task_id]['status'] = 'failed'
                    logger.error(f"Clone task failed: {task_id}")
            except Exception as e:
                clone_progress[task_id]['status'] = 'failed'
                clone_progress[task_id]['errors'].append(str(e))
                logger.error(f"Clone task error: {task_id} - {e}")
        
        # Start cloning in background thread
        thread = threading.Thread(target=clone_task)
        thread.daemon = True
        thread.start()
        
        logger.info(f"Clone task started: {task_id}")
        return jsonify({'task_id': task_id})
    except Exception as e:
        logger.error(f"Error starting clone: {e}")
        return jsonify({'error': f'Failed to start clone: {str(e)}'}), 500

@drive_bp.route('/progress/<task_id>')
def get_progress(task_id):
    """Get cloning progress"""
    try:
        if task_id not in clone_progress:
            return jsonify({'error': 'Task not found'}), 404
        
        progress = clone_progress[task_id].copy()
        
        # Calculate percentage
        if progress['total'] > 0:
            progress['percentage'] = (progress['completed'] / progress['total']) * 100
        else:
            progress['percentage'] = 0
        
        return jsonify(progress)
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({'error': str(e)}), 500

def credentials_to_dict(credentials):
    """Convert credentials to dictionary"""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


