import os
import uuid
import base64
import requests
from flask import Flask, request, jsonify
from pydub import AudioSegment

app = Flask(__name__)

# Configuration
API_KEY = "voice_detect_2026"
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)

def validate_api_key(headers):
    return headers.get("X-API-KEY") == API_KEY

def analyze_audio(file_path):
    audio = AudioSegment.from_file(file_path)
    duration_sec = len(audio) / 1000.0

    if audio.dBFS < -50.0:
        return {
            "label": "Silence",
            "confidence": 0.99,
            "duration_seconds": duration_sec,
            "explanation": "Average volume is below -50dBFS."
        }

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
    if not validate_api_key(request.headers):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    temp_filename = f"{uuid.uuid4()}.wav"
    temp_path = os.path.join(TEMP_DIR, temp_filename)

    try:
        if 'base64' in data:
            audio_data = base64.b64decode(data['base64'])
            with open(temp_path, "wb") as f:
                f.write(audio_data)

        elif 'url' in data:
            response = requests.get(data['url'], stream=True)
            if response.status_code != 200:
                return jsonify({"error": "Failed to retrieve URL"}), 400

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        else:
            return jsonify({"error": "Missing 'base64' or 'url' field"}), 400

        result = analyze_audio(temp_path)

        return jsonify({
            "status": "success",
            "classification": result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
