import os
import tempfile
import subprocess
from urllib.parse import urlparse, parse_qs
from openai import OpenAI

class GoogleDriveService:
    """Service for handling Google Drive video downloads"""
    
    @staticmethod
    def is_google_drive_url(url):
        """Check if URL is a Google Drive URL"""
        parsed = urlparse(url)
        return 'drive.google.com' in parsed.netloc
    
    @staticmethod
    def get_file_id(url):
        """Extract file ID from Google Drive URL"""
        if '/file/d/' in url:
            return url.split('/file/d/')[1].split('/')[0]
        elif 'id=' in url:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            return query_params.get('id', [None])[0]
        return None
    
    @staticmethod
    def download_file(url):
        """Download file from Google Drive using gdown"""
        try:
            import gdown
        except ImportError:
            raise ImportError("gdown is required for Google Drive downloads. Install with: pip install gdown")
        
        file_id = GoogleDriveService.get_file_id(url)
        if not file_id:
            raise ValueError("Invalid Google Drive URL")
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        output = temp_file.name
        temp_file.close()
        
        # Download using gdown
        download_url = f"https://drive.google.com/uc?id={file_id}"
        try:
            gdown.download(download_url, output, quiet=False)
        except Exception as e:
            # Try alternative download method
            try:
                gdown.download(download_url, output, quiet=False, fuzzy=True)
            except Exception as e2:
                raise ValueError(f"Failed to download from Google Drive: {str(e2)}")
        
        # Verify file was downloaded
        if not os.path.exists(output) or os.path.getsize(output) == 0:
            if os.path.exists(output):
                os.remove(output)
            raise ValueError("Downloaded file is empty or failed to download")
        
        return output


class LinkedInService:
    """Service for handling LinkedIn video downloads"""
    
    @staticmethod
    def is_linkedin_url(url):
        """Check if URL is a LinkedIn URL"""
        parsed = urlparse(url)
        valid_paths = [
            '/feed/update/urn:li:activity:',  # Existing format
            '/posts/'  # New format to support
        ]
        return 'linkedin.com' in parsed.netloc and any(path in parsed.path for path in valid_paths)
    
    @staticmethod
    def download_video(url):
        """Download video from LinkedIn using yt-dlp"""
        try:
            import yt_dlp
        except ImportError:
            raise ImportError("yt-dlp is required for LinkedIn downloads. Install with: pip install yt-dlp")
        
        print("Downloading LinkedIn video...")
        
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        try:
            ydl_opts = {
                'format': 'mp4/best[ext=mp4]',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'extractaudio': False,
                'audioformat': 'mp3',
                'progress_hooks': [lambda d: print(f"Status: {d['status']}")],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find downloaded file
            files = os.listdir(temp_dir)
            if not files:
                raise Exception("No file downloaded")
            
            downloaded_file = os.path.join(temp_dir, files[0])
            
            # Verify file exists and is not empty
            if not os.path.exists(downloaded_file) or os.path.getsize(downloaded_file) == 0:
                raise Exception("Downloaded file is empty")
            
            return downloaded_file
            
        except Exception as e:
            # Clean up temp directory on error
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass
            raise ValueError(f"Failed to download LinkedIn video: {str(e)}")


class MediaProcessorService:
    """Service for processing and summarizing media transcriptions"""
    
    def __init__(self):
        try:
            self.client = OpenAI()
        except Exception as e:
            print(f"Warning: OpenAI client initialization failed: {e}")
            self.client = None
    
    def transcribe_small_media(self, file_path):
        """Transcribe small media files using OpenAI Whisper"""
        if not self.client:
            raise Exception("OpenAI client not available")
        
        try:
            with open(file_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                return transcript
        except Exception as e:
            print(f"Error transcribing {file_path}: {e}")
            return None
    
    def transcribe(self, file_path):
        """Transcribe a large media file by splitting it into chunks"""
        from media_utils import split_media, cleanup_temp_files
        
        chunks = []
        try:
            # Split media into 1MB chunks for testing (you can adjust this)
            chunks = split_media(file_path, 1)
            transcriptions = []
            
            for chunk in chunks:
                # Transcribe each chunk
                text = self.transcribe_small_media(chunk)
                if text:
                    transcriptions.append(text)
            
            return ' '.join(transcriptions)
            
        except Exception as e:
            print(f"Error processing large file: {e}")
            return None
        finally:
            # Clean up all chunks in the finally block
            if chunks:
                cleanup_temp_files(chunks)
    
    def summarize_transcription(self, text):
        """Generate a structured summary of transcription using OpenAI GPT-4"""
        if not self.client:
            raise Exception("OpenAI client not available")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using gpt-4o-mini for cost efficiency
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert content analyst and summarizer with these capabilities:\n"
                            "- Extracting key points while maintaining context\n"
                            "- Identifying main themes and core messages\n"
                            "- Preserving critical details while reducing length\n"
                            "- Maintaining the original tone and intent\n"
                            "- Organizing information hierarchically\n\n"
                            "Format your summaries with:\n"
                            "1. A one-sentence overview\n"
                            "2. 2-3 key takeaways\n"
                            "3. Important details or quotes (if any)"
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Create a structured summary of this transcription. "
                            f"Focus on the core message and key points while maintaining "
                            f"context and critical details.\n\n"
                            f"Transcription:\n{text}"
                        )
                    }
                ],
                max_tokens=1000,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating summary: {e}")
            return None
    
    def extract_key_topics(self, text):
        """Extract key topics and themes from transcription"""
        if not self.client:
            raise Exception("OpenAI client not available")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert at extracting key topics and themes from content. "
                            "Analyze the provided transcription and extract:\n"
                            "- Main topics discussed\n"
                            "- Key themes and concepts\n"
                            "- Important keywords and phrases\n"
                            "Format as a bulleted list with categories."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Extract key topics and themes from this transcription:\n\n{text}"
                    }
                ],
                max_tokens=500,
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error extracting topics: {e}")
            return None


class URLService:
    """Service for handling various URL types and downloads"""
    
    @staticmethod
    def identify_url_type(url):
        """Identify the type of URL"""
        if GoogleDriveService.is_google_drive_url(url):
            return "google_drive"
        elif LinkedInService.is_linkedin_url(url):
            return "linkedin"
        elif any(domain in url.lower() for domain in ['youtube.com', 'youtu.be']):
            return "youtube"
        elif any(ext in url.lower() for ext in ['.mp3', '.mp4', '.wav', '.m4a', '.flac']):
            return "direct_media"
        else:
            return "unknown"
    
    @staticmethod
    def download_from_url(url):
        """Download media from various URL types"""
        url_type = URLService.identify_url_type(url)
        
        if url_type == "google_drive":
            return GoogleDriveService.download_file(url)
        elif url_type == "linkedin":
            return LinkedInService.download_video(url)
        elif url_type == "youtube":
            return URLService.download_youtube_video(url)
        elif url_type == "direct_media":
            return URLService.download_direct_media(url)
        else:
            raise ValueError(f"Unsupported URL type: {url_type}")
    
    @staticmethod
    def download_youtube_video(url):
        """Download video from YouTube using yt-dlp"""
        try:
            import yt_dlp
        except ImportError:
            raise ImportError("yt-dlp is required for YouTube downloads. Install with: pip install yt-dlp")
        
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        try:
            ydl_opts = {
                'format': 'bestaudio/best[ext=mp4]',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            files = os.listdir(temp_dir)
            if not files:
                raise Exception("No file downloaded")
            
            return os.path.join(temp_dir, files[0])
            
        except Exception as e:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise ValueError(f"Failed to download YouTube video: {str(e)}")
    
    @staticmethod
    def download_direct_media(url):
        """Download media file directly from URL"""
        import requests
        
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Get file extension from URL or Content-Type
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or '.' not in filename:
                content_type = response.headers.get('content-type', '')
                if 'audio' in content_type:
                    filename = 'audio_file.mp3'
                elif 'video' in content_type:
                    filename = 'video_file.mp4'
                else:
                    filename = 'media_file.mp4'
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1])
            
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            
            temp_file.close()
            return temp_file.name
            
        except Exception as e:
            raise ValueError(f"Failed to download media from URL: {str(e)}")


# Helper function to check if required packages are available
def check_dependencies():
    """Check if required packages are installed"""
    missing_packages = []
    
    try:
        import gdown
    except ImportError:
        missing_packages.append("gdown")
    
    try:
        import yt_dlp
    except ImportError:
        missing_packages.append("yt-dlp")
    
    return missing_packages


if __name__ == "__main__":
    # Test the services
    missing = check_dependencies()
    if missing:
        print(f"Missing packages: {missing}")
        print("Install with: pip install " + " ".join(missing))
    else:
        print("All dependencies are available!")
