# Video/Audio Transcriber Web Application

A full-stack web application that transcribes audio and video files using OpenAI's Whisper API. Built with Flask backend and a modern HTML/CSS/JavaScript frontend.

## Features

- **File Upload**: Drag-and-drop or browse to upload audio/video files
- **URL Transcription**: Transcribe audio/video files directly from URLs
- **Multiple Formats**: Supports MP3, WAV, FLAC, MP4, AVI, MOV, and many more
- **Background Processing**: Asynchronous transcription with real-time status updates
- **Download Results**: Download transcriptions as text files
- **Session Management**: Maintains separate sessions for multiple users
- **Error Handling**: Robust retry mechanism with automatic error recovery
- **Progress Tracking**: Real-time status updates during processing

## Supported Formats

**Audio**: MP3, WAV, FLAC, M4A, AAC, OGG, WMA  
**Video**: MP4, AVI, MOV, WMV, FLV, WebM, MKV

## Tech Stack

- **Backend**: Flask, OpenAI Whisper API
- **Frontend**: HTML5, CSS3, JavaScript (jQuery), Bootstrap
- **Processing**: Background threading for async transcription
- **AI**: OpenAI Whisper-1 model

## Setup Instructions

### Prerequisites

1. Python 3.8 or higher
2. OpenAI API key
3. Git (optional)

### Installation

1. **Clone or download the project**:
   ```bash
   git clone <repository-url>
   cd video_transcriber
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   
   **Option A: Use the setup script (recommended)**:
   ```bash
   python setup_env.py
   ```
   
   **Option B: Manual setup**:
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env and add your OpenAI API key
   ```

5. **Run the application**:
   ```bash
   python transcriber_app.py
   ```

6. **Open your browser** and navigate to:
   ```
   http://localhost:5000
   ```

## Usage

### File Upload Transcription

1. **Drag and Drop**: Simply drag an audio/video file onto the upload area
2. **Browse**: Click "Browse Files" to select a file from your computer
3. **Processing**: The file will be uploaded and transcription will start automatically
4. **Results**: View and download transcription results in real-time

### URL Transcription

1. **Enter URL**: Paste the direct URL to an audio/video file
2. **Submit**: Click "Transcribe URL" to start processing
3. **Processing**: The app will download and transcribe the remote file
4. **Results**: View and download the transcription when complete

### Managing Results

- **View Transcriptions**: All completed transcriptions appear in the results section
- **Download**: Click the "Download" button to save transcription as a text file
- **Auto-Refresh**: The interface automatically updates every 10 seconds

## API Endpoints

- `GET /` - Main application page
- `POST /api/upload` - Upload files for transcription
- `POST /api/transcribe-url` - Start URL-based transcription
- `GET /api/job-status/<job_id>` - Get transcription job status
- `GET /api/transcriptions` - Get all transcriptions for current session
- `GET /api/download/<job_id>` - Download transcription as text file
- `POST /api/reset` - Reset current session
- `GET /api/status` - Get current session statistics

## Configuration

Customize the application by editing the `.env` file:

```env
# OpenAI API Configuration
OPENAI_API_KEY=your_actual_api_key_here

# Flask Configuration
SECRET_KEY=your-secret-key-change-this-in-production

# Upload Configuration
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=104857600  # 100MB

# Processing Configuration
MAX_RETRIES=3
RETRY_DELAY=2
```

## Error Handling

The application includes robust error handling:

- **Automatic Retries**: Failed transcriptions are automatically retried up to 3 times
- **Timeout Handling**: Long-running requests have appropriate timeouts
- **File Validation**: Only supported file types are accepted
- **Size Limits**: Files larger than 100MB are rejected
- **Network Errors**: URL transcriptions handle network issues gracefully

## Troubleshooting

### Common Issues

1. **"No OpenAI API key" error**:
   - Ensure your `.env` file exists and contains a valid `OPENAI_API_KEY`
   - Run `python setup_env.py` to set up your environment

2. **"File type not supported" error**:
   - Check that your file has a supported extension
   - Rename the file if it has an unusual extension but is actually a supported format

3. **"Upload failed" error**:
   - Check that the file size is under 100MB
   - Ensure the file isn't corrupted
   - Try a different file format

4. **Transcription takes a long time**:
   - Large files naturally take longer to process
   - The Whisper API has processing limits
   - Check your internet connection for URL-based transcriptions

5. **"ModuleNotFoundError" errors**:
   - Activate your virtual environment
   - Run `pip install -r requirements.txt`

### Development Mode

```bash
# Set Flask environment to development
export FLASK_ENV=development  # On Windows: set FLASK_ENV=development
python transcriber_app.py
```

## File Structure

```
video_transcriber/
├── transcriber_app.py      # Main Flask application
├── requirements.txt        # Python dependencies
├── setup_env.py           # Environment setup script
├── .env.example           # Environment variables template
├── .env                   # Your environment variables (created by setup)
├── README.md              # This file
├── templates/
│   └── transcriber.html   # Frontend HTML template
├── uploads/               # Directory for uploaded files (created automatically)
├── transcriptions/        # Directory for transcription results (created automatically)
└── resources/             # Sample files for testing
    └── sample_audio.mp3   # Sample audio file
```

## Legacy Files

The following files are from the original command-line version:
- `app.py` - Original transcription script with decorators
- `main.py` - CLI version with URL support
- `decorators/` - Retry decorator implementations

These are kept for reference but the new web application (`transcriber_app.py`) is recommended.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License.

## Support

If you encounter any issues:

1. Check the troubleshooting section above
2. Review error messages in the browser console and terminal
3. Ensure all dependencies are correctly installed
4. Verify your OpenAI API key is valid and has sufficient credits
