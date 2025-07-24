import subprocess
import os
import json
import math
import tempfile
from typing import Optional, Dict, Any, List

def get_media_duration(file_path: str) -> Optional[float]:
    """Get the duration of a media file using ffprobe"""
    cmd = [
        'ffprobe', 
        '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        duration = float(output.strip())
        return duration
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
        print(f"Error getting duration for {file_path}: {e}")
        return None

def get_media_info(file_path: str) -> Optional[Dict[str, Any]]:
    """Get comprehensive media file information using ffprobe"""
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        file_path
    ]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        info = json.loads(output)
        
        # Extract useful information
        format_info = info.get('format', {})
        streams = info.get('streams', [])
        
        # Find audio and video streams
        audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
        video_streams = [s for s in streams if s.get('codec_type') == 'video']
        
        result = {
            'duration': float(format_info.get('duration', 0)),
            'size': int(format_info.get('size', 0)),
            'format_name': format_info.get('format_name', ''),
            'bit_rate': int(format_info.get('bit_rate', 0)),
            'has_audio': len(audio_streams) > 0,
            'has_video': len(video_streams) > 0,
            'audio_codec': audio_streams[0].get('codec_name', '') if audio_streams else '',
            'video_codec': video_streams[0].get('codec_name', '') if video_streams else '',
            'sample_rate': int(audio_streams[0].get('sample_rate', 0)) if audio_streams else 0,
            'channels': int(audio_streams[0].get('channels', 0)) if audio_streams else 0
        }
        
        return result
        
    except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error getting media info for {file_path}: {e}")
        return None

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable format"""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{int(minutes)}:{int(remaining_seconds):02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        return f"{int(hours)}:{int(minutes):02d}:{int(remaining_seconds):02d}"

def is_ffmpeg_available() -> bool:
    """Check if FFmpeg is available on the system"""
    try:
        subprocess.run(['ffprobe', '-version'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def traverse_and_analyze_media(directory: str) -> Dict[str, Dict[str, Any]]:
    """Traverse directory and analyze all media files"""
    valid_extensions = ('.mp3', '.mp4', '.wav', '.flac', '.avi', '.mov', '.m4a', '.aac', '.ogg', '.wma', '.wmv', '.flv', '.webm', '.mkv')
    results = {}
    
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist")
        return results
    
    try:
        for file in os.listdir(directory):
            if file.lower().endswith(valid_extensions):
                file_path = os.path.join(directory, file)
                print(f"Analyzing {file}...")
                
                media_info = get_media_info(file_path)
                if media_info:
                    media_info['filename'] = file
                    media_info['file_path'] = file_path
                    media_info['formatted_duration'] = format_duration(media_info['duration'])
                    results[file] = media_info
                    
                    print(f"  Duration: {media_info['formatted_duration']}")
                    print(f"  Size: {media_info['size'] / (1024*1024):.1f} MB")
                    print(f"  Format: {media_info['format_name']}")
                    if media_info['has_audio']:
                        print(f"  Audio: {media_info['audio_codec']}, {media_info['sample_rate']}Hz, {media_info['channels']} channels")
                    if media_info['has_video']:
                        print(f"  Video: {media_info['video_codec']}")
                    print()
                else:
                    print(f"  Could not analyze {file}")
                    
    except Exception as e:
        print(f"Error traversing directory {directory}: {e}")
    
    return results

def run_command_with_output(cmd, desc=None):
    """Run a command and stream its output in real-time"""
    if desc:
        print(f"\n{desc}")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
    
    process.stdout.close()
    return_code = process.wait()
    
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, cmd)

def split_media(file_path: str, chunk_size_mb: int = 20) -> List[str]:
    """Split media file into chunks smaller than the API limit"""
    print("\nSplitting media into chunks...")
    
    duration = get_media_duration(file_path)
    if not duration:
        raise Exception("Could not determine audio duration")
    
    file_size = os.path.getsize(file_path)
    chunk_duration = duration * (chunk_size_mb * 1024 * 1024) / file_size
    num_chunks = math.ceil(duration / chunk_duration)
    
    chunks = []
    for i in range(num_chunks):
        start_time = i * chunk_duration
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(file_path)[1]
        )
        
        cmd = [
            'ffmpeg',
            '-i', file_path,    # Specify the input file to process
            '-ss', str(start_time),  # Set the start time of the chunk
            '-t', str(chunk_duration),  # Define the chunk's duration
            '-c', 'copy',   # Copy streams without re-encoding for efficiency
            '-y',   # Overwrite output files without confirmation
            temp_file.name
        ]
        
        run_command_with_output(
            cmd, 
            f"Extracting chunk {i+1}/{num_chunks}"
        )
        chunks.append(temp_file.name)
    
    print(f"Split media into {len(chunks)} chunk(s): {chunks}")
    return chunks

def cleanup_temp_files(file_paths) -> None:
    """Clean up temporary files and directories"""
    # Handle both single file and list of files
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    elif not isinstance(file_paths, (list, tuple)):
        file_paths = [file_paths]
    
    for file_path in file_paths:
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
                print(f"Cleaned up file: {file_path}")
            elif os.path.isdir(file_path):
                for root, dirs, files in os.walk(file_path, topdown=False):
                    for name in files:
                        os.unlink(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(file_path)
                print(f"Cleaned up directory: {file_path}")
        except Exception as e:
            print(f"Warning: Could not clean up {file_path}: {e}")

def get_file_size_mb(file_path: str) -> float:
    """Get file size in MB"""
    return os.path.getsize(file_path) / (1024 * 1024)

def needs_splitting(file_path: str, max_size_mb: int = 25) -> bool:
    """Check if file needs to be split based on size"""
    return get_file_size_mb(file_path) > max_size_mb

if __name__ == "__main__":
    # Check if FFmpeg is available
    if not is_ffmpeg_available():
        print("FFmpeg/FFprobe is not available on this system.")
        print("Please install FFmpeg to use media analysis features.")
        exit(1)
    
    # Analyze files in resources directory
    print("Analyzing media files in resources directory...")
    print("=" * 50)
    results = traverse_and_analyze_media("resources")
    
    if results:
        print(f"\nAnalyzed {len(results)} media files successfully.")
    else:
        print("\nNo media files found or analyzed.")
