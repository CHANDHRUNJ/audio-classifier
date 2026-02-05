import os
import uuid
import base64
import requests
from flask import Flask, request, jsonify
from pydub import AudioSegment, silence

app = Flask(__name__)

# Configuration
API_KEY = "your-super-secret-key"
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)

def validate_api_key(headers):
    return headers.get("X-API-KEY") == API_KEY

def analyze_audio(file_path):
    """
    Performs basic analysis to 'classify' the audio.
    Uses duration and silence detection as proxies for classification.
    """
    audio = AudioSegment.from_file(file_path)
    duration_sec = len(audio) / 1000.0
    
    # Check for silence (if audio is mostly silent)
    # detecting silence usually returns a list of ranges, if list is empty, no silence found
    # This is a basic check: if avg dB is very low, we might call it 'Silence'
    if audio.dBFS < -50.0:
        return {
            "label": "Silence",
            "confidence": 0.99,
            "duration_seconds": duration_sec,
            "explanation": "Average volume is below -50dBFS."
        }

    # Duration-based classification logic
    if duration_sec < 5.0:
        label = "Short Command"
        confidence = 0.95
        explanation = "Audio is under 5 seconds, typical for voice commands."
    elif duration_sec < 60.0:
        label = "Voice Message"
        confidence = 0.88
        explanation = "Audio is between 5s and 60s, typical for conversation."
    else:
        label = "Long Form Content"
        confidence = 0.90
        explanation = "Audio exceeds 1 minute."
        
    return {
        "label": label,
        "confidence": confidence,
        "duration_seconds": duration_sec,
        "explanation": explanation
    }

@app.route('/classify', methods=['POST'])
def classify_audio():
    # 1. Security Check
    if not validate_api_key(request.headers):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Create a unique temp file
    temp_filename = f"{uuid.uuid4()}.wav" # pydub handles format conversion usually, but keeping extension helps
    temp_path = os.path.join(TEMP_DIR, temp_filename)

    try:
        # 2.