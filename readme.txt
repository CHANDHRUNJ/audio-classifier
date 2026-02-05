# Audio Classifier API

A Flask-based API that classifies audio files based on duration and volume (silence detection).

## Prerequisites
1. **Python 3.8+**
2. **FFmpeg**: Required for audio processing.
   - *Mac*: `brew install ffmpeg`
   - *Linux*: `sudo apt install ffmpeg`
   - *Windows*: Download binaries and add to PATH.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt