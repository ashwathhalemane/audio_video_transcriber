from openai import OpenAI
import requests
import io 

client = OpenAI()

def basic_example():
    try:
        response = client.models.list()
        print("API Request Successful!")

        for model in response:
            print(f"- {model.id}")

    except Exception as e:
        print(f"API Request Failed: {e}")

def basic_chat():
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            # TODO: Configure system and user prompts below
            messages=[
                {"role": "system", "content": ""},
                {"role": "user", "content": ""},
            ]
        )
        print("API Request Successful!")
        print(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"API Request Failed: {e}")

def transcribe_audio(file_path):
    
    """
    Transcribe an audio file using OpenAI's Whisper API.
    """
    try:
        with open(file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                timeout=60
            )

            return transcript.text

    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")
    
def transcribe_remote(url):
    """
    Transcribe a remote video file from a URL using OpenAI's Whisper API.
    """
    try:
        # TODO: Download the content using the `requests` library
        response = requests.get(url, stream = True)
        # TODO: Send the content to OpenAI API
        
        # # mp4 downloaded from URL: not necessary as whisper takes in stream of data, which avoids processing bytes in memory by storing it in a file
        # if response.status_code == 200:
        #     with open(filename, 'wb') as f:
        #         for chunk in response.iter_content(chunk_size=8192):
        #             f.write(chunk)
            
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=('video.mp4', response.content)
        )
        return transcript.text
            
    except Exception as e:
        return f"Error: {str(e)}"
    
def transcribe_audio_from_url(url):
    # TODO: Download the mp3 file from the URL
    response = requests.get(url, stream = True)
    # TODO: Open the audio file in binary mode

    #  Whisper API needs a file-like object, not just a tuple of filename and bytes. Passing ('audio.mp3', response.content) won’t work as expected. 
    # if response.status_code == 200:
    #     with open('output.mp3', 'wb') as f:
    #         f.write(response.content)
    #     print("Saved MP3 successfully!")
    # else:
    #     print(f"Failed to download MP3. Status code: {response.status_code}")


    # passing file-like object to OpenAI API
    audio_byte = io.BytesIO(response.content)
    audio_byte.name = 'audio.mp3'  # Set a name for the BytesIO object to mimic a file

    # TODO: Create a transcription request with a timeout and specific model
    transcript = client.audio.transcriptions.create(
            model = "whisper-1",
            file  = audio_byte
        )
    return transcript.text
    # TODO: Print the transcribed text

if __name__ == "__main__":
    result = transcribe_audio("resources/sample_audio.mp3")
    print("Transcription:", result)

    remote_video_url = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4"
    print(transcribe_remote(remote_video_url))

    remote_audio_url = "https://dare.wisc.edu/wp-content/uploads/sites/1051/2008/04/Arthur.mp3"
    print(transcribe_audio_from_url(remote_audio_url))