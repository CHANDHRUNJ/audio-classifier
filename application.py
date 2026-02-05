import os
import uuid
import base64
import wave
import json
import contextlib
import requests
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

# --- Configuration ---
API_KEY = "voice_detect_2026"
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)

# --- Frontend (HTML/JS/CSS) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio Classifier 2026</title>
    <style>
        :root { --primary: #2563eb; --bg: #f8fafc; --text: #1e293b; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
               background: var(--bg); color: var(--text); display: flex; 
               justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: white; padding: 2rem; border-radius: 12px; 
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); width: 100%; max-width: 400px; }
        h1 { font-size: 1.5rem; margin-bottom: 1.5rem; text-align: center; color: var(--primary); }
        .input-group { margin-bottom: 1.5rem; }
        input[type="file"] { width: 100%; padding: 0.5rem; border: 1px dashed #cbd5e1; border-radius: 6px; }
        button { width: 100%; background: var(--primary); color: white; border: none; 
                 padding: 0.75rem; border-radius: 6px; font-weight: 600; cursor: pointer; 
                 transition: opacity 0.2s; }
        button:hover { opacity: 0.9; }
        button:disabled { background: #94a3b8; cursor: not-allowed; }
        #results { margin-top: 1.5rem; padding: 1rem; background: #f1f5f9; 
                   border-radius: 6px; display: none; font-size: 0.9rem; }
        .label { font-weight: bold; font-size: 1.1rem; display: block; margin-bottom: 0.5rem; }
        .meta { color: #64748b; font-size: 0.85rem; margin-bottom: 0.5rem; }
        .loader { display: none; border: 3px solid #f3f3f3; border-top: 3px solid var(--primary); 
                  border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; 
                  margin: 10px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        pre { white-space: pre-wrap; word-break: break-all; font-size: 0.75rem; color: #334155; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Audio Analyzer</h1>
        
        <div class="input-group">
            <input type="file" id="audioInput" accept="audio/*">
        </div>

        <button id="analyzeBtn" onclick="processAudio()">Analyze Audio</button>
        <div id="loader" class="loader"></div>

        <div id="results">
            <span class="label" id="resLabel"></span>
            <div class="meta">
                Confidence: <span id="resConf"></span> | Duration: <span id="resDur"></span>s
            </div>
            <p id="resExpl"></p>
        </div>
    </div>

    <script>
        async function processAudio() {
            const input = document.getElementById('audioInput');
            const btn = document.getElementById('analyzeBtn');
            const loader = document.getElementById('loader');
            const resBox = document.getElementById('results');

            if (!input.files[0]) {
                alert("Please select a file first.");
                return;
            }

            // UI State: Loading
            btn.disabled = true;
            loader.style.display = 'block';
            resBox.style.display = 'none';

            try {
                // 1. Convert to Base64
                const file = input.files[0];
                const base64String = await toBase64(file);
                
                // Remove data URL prefix (e.g., "data:audio/wav;base64,") if present
                const cleanBase64 = base64String.split(',')[1] || base64String;

                // 2. Send API Request
                const response = await fetch('/classify', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-KEY': 'voice_detect_2026'
                    },
                    body: JSON.stringify({ "base64": cleanBase64 })
                });

                const data = await response.json();

                // 3. Render Results
                if (response.ok) {
                    document.getElementById('resLabel').innerText = data.classification.label;
                    document.getElementById('resConf').innerText = data.classification.confidence;
                    document.getElementById('resDur').innerText = data.classification.duration_seconds.toFixed(2);
                    document.getElementById('resExpl').innerText = data.classification.explanation;
                    resBox.style.display = 'block';
                } else {
                    alert("Error: " + (data.error || "Unknown error"));
                }

            } catch (err) {
                console.error(err);
                alert("An error occurred during processing.");
            } finally {
                btn.disabled = false;
                loader.style.display = 'none';
            }
        }

        const toBase64 = file => new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result);
            reader.onerror = error => reject(error);
        });
    </script>
</body>
</html>
"""

# --- Helpers ---

def get_duration_wave(file_path):
    """
    Get duration of a WAV file using only the standard 'wave' library.
    Returns duration in seconds (float).
    Raises wave.Error if file is not a valid WAV.
    """
    try:
        with contextlib.closing(wave.open(file_path, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    except wave.Error:
        raise ValueError("File is not a valid WAV format supported by native wave module.")
    except Exception as e:
        raise ValueError(f"Could not process audio: {str(e)}")

def classify_duration(duration):
    """Business logic for classification based on duration."""
    if duration < 5.0:
        return "Short Audio", 0.92, "Duration is less than 5 seconds."
    elif duration <= 60.0:
        return "Medium Audio", 0.88, "Duration is between 5 and 60 seconds."
    else:
        return "Long Audio", 0.90, "Duration exceeds 60 seconds."

# --- Routes ---

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/classify', methods=['POST'])
def classify():
    # 1. Security Check
    if request.headers.get('X-API-KEY') != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    temp_path = None
    try:
        # 2. Input Handling (Robust Parsing)
        # Try retrieving JSON body safely
        json_data = request.get_json(silent=True) or {}
        
        # Check Form Data
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No selected file"}), 400
            
            ext = os.path.splitext(file.filename)[1] or ".wav"
            temp_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}{ext}")
            file.save(temp_path)

        # Check JSON Base64
        elif any(k in json_data for k in ["base64", "audio_base64", "audio", "file_base64"]):
            # Find the key that exists
            key = next(k for k in ["base64", "audio_base64", "audio", "file_base64"] if k in json_data)
            b64_str = json_data[key]
            
            # Handle Data URL header if present (e.g., "data:audio/wav;base64,...")
            if "," in b64_str:
                b64_str = b64_str.split(",")[1]
                
            file_bytes = base64.b64decode(b64_str)
            temp_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}.wav")
            with open(temp_path, "wb") as f:
                f.write(file_bytes)

        # Check JSON URL
        elif "url" in json_data:
            url = json_data['url']
            resp = requests.get(url)
            if resp.status_code != 200:
                return jsonify({"error": "Failed to download from URL"}), 400
            
            temp_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}.wav")
            with open(temp_path, "wb") as f:
                f.write(resp.content)

        else:
            return jsonify({"error": "Invalid input: Provide 'file' (form-data), 'base64' (json), or 'url' (json)"}), 400

        # 3. Audio Analysis (Native Wave)
        try:
            duration = get_duration_wave(temp_path)
            label, confidence, explanation = classify_duration(duration)
            
            result = {
                "status": "success",
                "classification": {
                    "label": label,
                    "confidence": confidence,
                    "duration_seconds": round(duration, 4),
                    "explanation": explanation
                }
            }
            return jsonify(result)

        except ValueError as ve:
            # Handle non-wav files gracefully
            return jsonify({"error": str(ve), "hint": "Since ffmpeg is disabled, only .wav files are supported."}), 422

    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
        
    finally:
        # 4. Cleanup
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

if __name__ == '__main__':
    # Render deployment requirement
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
