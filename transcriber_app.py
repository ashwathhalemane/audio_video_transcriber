from flask import Flask, request, jsonify, render_template, session, send_file
from flask_cors import CORS
import os
import uuid
from werkzeug.utils import secure_filename
from functools import wraps
import time
import requests
import io
from datetime import datetime
# from openai import OpenAI
import openai
from dotenv import load_dotenv
import threading
from urllib.parse import urlparse
from media_utils import (get_media_info, format_duration, is_ffmpeg_available, 
                         traverse_and_analyze_media, split_media, cleanup_temp_files, 
                         needs_splitting, get_file_size_mb)
from external_services import (GoogleDriveService, LinkedInService, MediaProcessorService, 
                              URLService, check_dependencies)

# Load environment variables
load_dotenv()

app = Flask(__name__)
openai.api_key = os.getenv('OPENAI_API_KEY')
print("Initializing OpenAI client...")
# print(f"OpenAI API Key: {openai.api_key}")
if not openai.api_key:
    raise ValueError("OpenAI API key not set. Please set the OPENAI_API_KEY environment variable.")
else: 
    print("OpenAI API key loaded successfully.")
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
CORS(app)

# Configuration
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
ALLOWED_EXTENSIONS = {
    'audio': ['mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg', 'wma'],
    'video': ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv']
}
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 100 * 1024 * 1024))  # 100MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('transcriptions', exist_ok=True)

# Initialize OpenAI client
# client = openai.OpenAI()

# Global dictionary to store user sessions
user_sessions = {}

# Retry decorator
def retry_on_error(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        raise
                    print(f"Error: {e}. Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def allowed_file(filename):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False, None
    
    extension = filename.rsplit('.', 1)[1].lower()
    
    if extension in ALLOWED_EXTENSIONS['audio']:
        return True, 'audio'
    elif extension in ALLOWED_EXTENSIONS['video']:
        return True, 'video'
    else:
        return False, None

def get_or_create_session():
    """Get or create a user session"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    if session_id not in user_sessions:
        user_sessions[session_id] = {
            'transcriptions': [],
            'processing_jobs': {}
        }
    
    return session_id

@retry_on_error(max_retries=3, delay=2)
def transcribe_file_chunk(file_path, job_id=None):
    """Transcribe a single audio/video file chunk using OpenAI Whisper"""
    try:
        with open(file_path, 'rb') as audio_file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
            return transcript
    except Exception as e:
        raise Exception(f"Chunk transcription failed: {str(e)}")

def transcribe_file(file_path, job_id=None):
    """Transcribe an audio/video file, splitting if necessary for large files"""
    try:
        # Check if file needs splitting (25MB limit for Whisper API)
        if needs_splitting(file_path, max_size_mb=25):
            print(f"File {file_path} is {get_file_size_mb(file_path):.1f}MB, splitting for transcription...")
            
            if not is_ffmpeg_available():
                raise Exception("FFmpeg is required for splitting large files but is not available")
            
            # Split the file into chunks
            chunks = split_media(file_path, chunk_size_mb=20)
            transcripts = []
            
            try:
                # Transcribe each chunk
                for i, chunk_path in enumerate(chunks):
                    print(f"Transcribing chunk {i+1}/{len(chunks)}...")
                    chunk_transcript = transcribe_file_chunk(chunk_path, job_id)
                    transcripts.append(chunk_transcript)
                    
                # Combine all transcripts
                combined_transcript = " ".join(transcripts)
                
            finally:
                # Clean up temporary chunk files
                cleanup_temp_files(chunks)
                
            return combined_transcript
        else:
            # File is small enough, transcribe directly
            return transcribe_file_chunk(file_path, job_id)
            
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")

@retry_on_error(max_retries=3, delay=2)
def transcribe_from_url(url, job_id=None):
    """Transcribe an audio/video file from URL using OpenAI Whisper"""
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        # Create a BytesIO object from the response content
        audio_data = io.BytesIO(response.content)
        
        # Get filename from URL or use default
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path) or 'audio_from_url'
        audio_data.name = filename
        
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_data,
            response_format="text"
        )
        return transcript
    except Exception as e:
        raise Exception(f"URL transcription failed: {str(e)}")

def process_transcription_async(session_id, job_id, file_path=None, url=None, filename=None):
    """Process transcription in background thread"""
    try:
        user_data = user_sessions[session_id]
        user_data['processing_jobs'][job_id]['status'] = 'processing'
        
        # Transcribe based on source
        if file_path:
            result = transcribe_file(file_path, job_id)
        elif url:
            result = transcribe_from_url(url, job_id)
        else:
            raise ValueError("No file path or URL provided")
        
        # Save transcription
        transcription_data = {
            'job_id': job_id,
            'filename': filename or 'URL transcription',
            'transcription': result,
            'timestamp': datetime.now().isoformat(),
            'source': 'file' if file_path else 'url',
            'status': 'completed'
        }
        
        # Save to file
        transcription_file = f'transcriptions/{job_id}.txt'
        with open(transcription_file, 'w', encoding='utf-8') as f:
            f.write(result)
        
        transcription_data['file_path'] = transcription_file
        
        # Update session data
        user_data['transcriptions'].append(transcription_data)
        user_data['processing_jobs'][job_id] = transcription_data
        
    except Exception as e:
        # Update job status with error
        if session_id in user_sessions and job_id in user_sessions[session_id]['processing_jobs']:
            user_sessions[session_id]['processing_jobs'][job_id].update({
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('transcriber.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file uploads for transcription"""
    try:
        session_id = get_or_create_session()
        user_data = user_sessions[session_id]
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        is_allowed, file_type = allowed_file(file.filename)
        if not is_allowed:
            return jsonify({'error': 'File type not supported. Please upload audio or video files.'}), 400
        
        # Save the file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Analyze media file with FFmpeg if available
        media_info = None
        if is_ffmpeg_available():
            try:
                media_info = get_media_info(file_path)
                if media_info:
                    print(f"Media analysis for {filename}:")
                    print(f"  Duration: {format_duration(media_info['duration'])}")
                    print(f"  Size: {media_info['size'] / (1024*1024):.1f} MB")
                    print(f"  Format: {media_info['format_name']}")
            except Exception as e:
                print(f"Error analyzing media file: {e}")
        
        # Create job ID and start processing
        job_id = str(uuid.uuid4())
        
        # Initialize job status with media info
        job_data = {
            'job_id': job_id,
            'filename': filename,
            'status': 'queued',
            'timestamp': datetime.now().isoformat(),
            'file_type': file_type,
            'file_path': file_path
        }
        
        # Add media info if available
        if media_info:
            job_data.update({
                'duration': media_info['duration'],
                'formatted_duration': format_duration(media_info['duration']),
                'file_size': media_info['size'],
                'format_name': media_info['format_name'],
                'has_audio': media_info['has_audio'],
                'has_video': media_info['has_video'],
                'audio_codec': media_info['audio_codec'],
                'video_codec': media_info['video_codec'],
                'sample_rate': media_info['sample_rate'],
                'channels': media_info['channels']
            })
        
        user_data['processing_jobs'][job_id] = job_data
        
        # Start background processing
        thread = threading.Thread(
            target=process_transcription_async,
            args=(session_id, job_id, file_path, None, filename)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': f'File "{filename}" uploaded successfully. Transcription started.',
            'job_id': job_id,
            'filename': filename,
            'file_type': file_type
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing upload: {str(e)}'}), 500

@app.route('/api/transcribe-url', methods=['POST'])
def transcribe_url():
    """Handle URL-based transcription"""
    try:
        session_id = get_or_create_session()
        user_data = user_sessions[session_id]
        
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'Invalid URL'}), 400
        
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        user_data['processing_jobs'][job_id] = {
            'job_id': job_id,
            'url': url,
            'status': 'queued',
            'timestamp': datetime.now().isoformat(),
            'source': 'url'
        }
        
        # Start background processing
        thread = threading.Thread(
            target=process_transcription_async,
            args=(session_id, job_id, None, url, f'URL: {url}')
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': f'URL transcription started.',
            'job_id': job_id,
            'url': url
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing URL: {str(e)}'}), 500

@app.route('/api/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get status of a transcription job"""
    try:
        session_id = get_or_create_session()
        user_data = user_sessions[session_id]
        
        if job_id not in user_data['processing_jobs']:
            return jsonify({'error': 'Job not found'}), 404
        
        job_data = user_data['processing_jobs'][job_id]
        return jsonify(job_data)
        
    except Exception as e:
        return jsonify({'error': f'Error getting job status: {str(e)}'}), 500

@app.route('/api/transcriptions', methods=['GET'])
def get_transcriptions():
    """Get all transcriptions for current session"""
    try:
        session_id = get_or_create_session()
        user_data = user_sessions[session_id]
        
        return jsonify({
            'transcriptions': user_data['transcriptions'],
            'processing_jobs': list(user_data['processing_jobs'].values())
        })
        
    except Exception as e:
        return jsonify({'error': f'Error getting transcriptions: {str(e)}'}), 500

@app.route('/api/download/<job_id>', methods=['GET'])
def download_transcription(job_id):
    """Download transcription as text file"""
    try:
        session_id = get_or_create_session()
        user_data = user_sessions[session_id]
        
        # Find the transcription
        transcription = None
        for t in user_data['transcriptions']:
            if t['job_id'] == job_id:
                transcription = t
                break
        
        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        
        if 'file_path' not in transcription or not os.path.exists(transcription['file_path']):
            return jsonify({'error': 'Transcription file not found'}), 404
        
        return send_file(
            transcription['file_path'],
            as_attachment=True,
            download_name=f"{transcription['filename']}_transcription.txt",
            mimetype='text/plain'
        )
        
    except Exception as e:
        return jsonify({'error': f'Error downloading transcription: {str(e)}'}), 500

@app.route('/api/reset', methods=['POST'])
def reset_session():
    """Reset the current session"""
    try:
        session_id = get_or_create_session()
        
        # Clean up files
        if session_id in user_sessions:
            for transcription in user_sessions[session_id]['transcriptions']:
                try:
                    if 'file_path' in transcription and os.path.exists(transcription['file_path']):
                        os.remove(transcription['file_path'])
                except Exception as e:
                    print(f"Error deleting transcription file: {e}")
        
        # Reset session
        user_sessions[session_id] = {
            'transcriptions': [],
            'processing_jobs': {}
        }
        
        return jsonify({'message': 'Session reset successfully'})
        
    except Exception as e:
        return jsonify({'error': f'Error resetting session: {str(e)}'}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current session status"""
    try:
        session_id = get_or_create_session()
        user_data = user_sessions[session_id]
        
        return jsonify({
            'session_id': session_id,
            'total_transcriptions': len(user_data['transcriptions']),
            'processing_jobs': len([j for j in user_data['processing_jobs'].values() if j['status'] == 'processing']),
            'completed_jobs': len([t for t in user_data['transcriptions'] if t['status'] == 'completed']),
            'ffmpeg_available': is_ffmpeg_available()
        })
        
    except Exception as e:
        return jsonify({'error': f'Error getting status: {str(e)}'}), 500

@app.route('/api/analyze-media', methods=['POST'])
def analyze_media():
    """Analyze a media file and return detailed information"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data:
            return jsonify({'error': 'No file path provided'}), 400
        
        file_path = data['file_path']
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        if not is_ffmpeg_available():
            return jsonify({'error': 'FFmpeg is not available on this system'}), 503
        
        # Analyze the media file
        media_info = get_media_info(file_path)
        
        if not media_info:
            return jsonify({'error': 'Could not analyze media file'}), 500
        
        return jsonify({
            'success': True,
            'media_info': media_info,
            'formatted_duration': format_duration(media_info['duration']),
            'file_size_mb': round(media_info['size'] / (1024 * 1024), 2)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error analyzing media: {str(e)}'}), 500

@app.route('/api/analyze-directory', methods=['POST'])
def analyze_directory():
    """Analyze all media files in a directory"""
    try:
        data = request.get_json()
        if not data or 'directory_path' not in data:
            return jsonify({'error': 'No directory path provided'}), 400
        
        directory_path = data['directory_path']
        
        if not os.path.exists(directory_path):
            return jsonify({'error': 'Directory not found'}), 404
        
        if not os.path.isdir(directory_path):
            return jsonify({'error': 'Path is not a directory'}), 400
        
        if not is_ffmpeg_available():
            return jsonify({'error': 'FFmpeg is not available on this system'}), 503
        
        # Analyze all media files in the directory
        results = traverse_and_analyze_media(directory_path)
        
        if not results:
            return jsonify({
                'success': True,
                'message': 'No media files found in directory',
                'files_analyzed': 0,
                'results': {}
            })
        
        # Calculate summary statistics
        total_duration = sum(info['duration'] for info in results.values())
        total_size = sum(info['size'] for info in results.values())
        audio_files = sum(1 for info in results.values() if info['has_audio'] and not info['has_video'])
        video_files = sum(1 for info in results.values() if info['has_video'])
        
        return jsonify({
            'success': True,
            'files_analyzed': len(results),
            'total_duration': total_duration,
            'formatted_total_duration': format_duration(total_duration),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'audio_files': audio_files,
            'video_files': video_files,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': f'Error analyzing directory: {str(e)}'}), 500

@app.route('/api/ffmpeg-status', methods=['GET'])
def ffmpeg_status():
    """Check FFmpeg availability and provide installation guidance"""
    ffmpeg_available = is_ffmpeg_available()
    
    response_data = {
        'ffmpeg_available': ffmpeg_available,
        'message': 'FFmpeg is available and ready to use' if ffmpeg_available else 'FFmpeg is not installed or not in PATH'
    }
    
    if not ffmpeg_available:
        response_data['installation_guide'] = {
            'windows': 'Download from https://ffmpeg.org/download.html#build-windows and add to PATH',
            'macos': 'Install with Homebrew: brew install ffmpeg',
            'linux': 'Install with package manager: sudo apt install ffmpeg (Ubuntu/Debian) or sudo yum install ffmpeg (CentOS/RHEL)'
        }
    
    return jsonify(response_data)

@app.route('/api/enhanced-url', methods=['POST'])
def enhanced_url_processing():
    """Handle enhanced URL processing for Google Drive, LinkedIn, YouTube, etc."""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'Invalid URL'}), 400
        
        # Check dependencies
        missing_deps = check_dependencies()
        if missing_deps:
            return jsonify({
                'error': f'Missing dependencies: {", ".join(missing_deps)}',
                'install_command': f'pip install {", ".join(missing_deps)}'
            }), 503
        
        # Identify URL type
        url_type = URLService.identify_url_type(url)
        
        session_id = get_or_create_session()
        user_data = user_sessions[session_id]
        job_id = str(uuid.uuid4())
        
        # Initialize job with URL type info
        user_data['processing_jobs'][job_id] = {
            'job_id': job_id,
            'url': url,
            'url_type': url_type,
            'status': 'downloading',
            'timestamp': datetime.now().isoformat(),
            'source': 'enhanced_url'
        }
        
        def process_enhanced_url():
            try:
                # Update status
                user_data['processing_jobs'][job_id]['status'] = 'downloading'
                
                # Download from URL
                downloaded_file = URLService.download_from_url(url)
                
                # Update status and start transcription
                user_data['processing_jobs'][job_id]['status'] = 'transcribing'
                user_data['processing_jobs'][job_id]['downloaded_file'] = downloaded_file
                
                # Transcribe the downloaded file
                result = transcribe_file(downloaded_file, job_id)
                
                # Save transcription
                transcription_data = {
                    'job_id': job_id,
                    'filename': f'{url_type.title()} - {url}',
                    'transcription': result,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'enhanced_url',
                    'url': url,
                    'url_type': url_type,
                    'status': 'completed'
                }
                
                # Save to file
                transcription_file = f'transcriptions/{job_id}.txt'
                with open(transcription_file, 'w', encoding='utf-8') as f:
                    f.write(result)
                
                transcription_data['file_path'] = transcription_file
                
                # Update session data
                user_data['transcriptions'].append(transcription_data)
                user_data['processing_jobs'][job_id] = transcription_data
                
                # Clean up downloaded file
                try:
                    cleanup_temp_files([downloaded_file])
                except Exception as e:
                    print(f"Error cleaning up downloaded file: {e}")
                
            except Exception as e:
                user_data['processing_jobs'][job_id].update({
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        # Start background processing
        thread = threading.Thread(target=process_enhanced_url)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'message': f'{url_type.title()} URL processing started.',
            'job_id': job_id,
            'url': url,
            'url_type': url_type
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing enhanced URL: {str(e)}'}), 500

@app.route('/api/summarize/<job_id>', methods=['POST'])
def summarize_transcription(job_id):
    """Generate a summary of a completed transcription"""
    try:
        session_id = get_or_create_session()
        user_data = user_sessions[session_id]
        
        # Find the transcription
        transcription = None
        for t in user_data['transcriptions']:
            if t['job_id'] == job_id:
                transcription = t
                break
        
        if not transcription:
            return jsonify({'error': 'Transcription not found'}), 404
        
        if transcription.get('status') != 'completed':
            return jsonify({'error': 'Transcription not completed yet'}), 400
        
        # Initialize media processor service
        processor = MediaProcessorService()
        
        # Generate summary
        summary = processor.summarize_transcription(transcription['transcription'])
        
        if not summary:
            return jsonify({'error': 'Failed to generate summary'}), 500
        
        # Extract key topics
        topics = processor.extract_key_topics(transcription['transcription'])
        
        # Save summary to transcription data
        transcription['summary'] = summary
        transcription['key_topics'] = topics
        transcription['summary_timestamp'] = datetime.now().isoformat()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'summary': summary,
            'key_topics': topics,
            'original_length': len(transcription['transcription']),
            'summary_length': len(summary) if summary else 0
        })
        
    except Exception as e:
        return jsonify({'error': f'Error generating summary: {str(e)}'}), 500

@app.route('/api/dependencies', methods=['GET'])
def check_app_dependencies():
    """Check application dependencies status"""
    missing_deps = check_dependencies()
    
    return jsonify({
        'all_dependencies_available': len(missing_deps) == 0,
        'missing_dependencies': missing_deps,
        'available_features': {
            'google_drive': 'gdown' not in missing_deps,
            'linkedin_youtube': 'yt-dlp' not in missing_deps,
            'ffmpeg': is_ffmpeg_available(),
            'openai': os.getenv('OPENAI_API_KEY') is not None
        },
        'install_command': f'pip install {", ".join(missing_deps)}' if missing_deps else None
    })

if __name__ == '__main__':
    # Check OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("Warning: OPENAI_API_KEY environment variable not set!")
        print("Please set your OpenAI API key before running the app.")
    
    app.run(debug=True, host='0.0.0.0', port=3000)
