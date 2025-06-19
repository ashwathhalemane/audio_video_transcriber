from functools import wraps
import time
import random
from openai import OpenAI

client = OpenAI()


# TODO: Implement error handling and retrying decorator
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
# TODO: Apply decorator for the `transcribe` method
# to retry up to 3 times, with a delay of 1 second between retries

@retry_on_error(max_retries=3, delay=1)
def transcribe(file_path):
    """
    Transcribe an audio file using OpenAI's API.
    """
    if random.randint(1, 2) == 1:
        raise ValueError("Unable to process transcription at that point")
    try:
        with open(file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            return transcript.text
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")
        
if __name__ == "__main__":
    print(transcribe("resources/sample_audio.mp3"))