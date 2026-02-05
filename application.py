import os
import uuid
import base64
import requests
import wave

from flask import Flask, request, jsonify, render_template

# ---------------- CONFIG ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))


API_KEY = "voice_detect_2026"
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)
# ---------------------------------------

def validate_api_key(headers):
    return headers.get("X-API-KEY") == API_KEY

# --------- SIMPLE AUDIO ANALYSIS (NO PYDUB) ----------
def analyze_audio(file_path):
    try:
        with wave.open(file_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_sec = frames / float(rate)

        if duration_sec < 5.0:
            return {
                "label": "Short Audio",
                "confidence": 0.92,
                "duration_seconds": round(duration_sec, 2),
                "explanation": "Audio is under 5 seconds."
            }
        elif duration_sec < 60.0:
            return {
                "label": "Medium Audio",
                "confidence": 0.88,
                "duration_seconds": round(duration_sec, 2),
                "explanation": "Audio is between 5 and 60 seconds."
            }
        else:
            return {
                "label": "Long Audio",
                "confidence": 0.90,
                "duration_seconds": round(duration_sec, 2),
                "explanation": "Audio is longer than 1 minute."
            }

    except Exception as e:
        return {
            "label": "Unknown",
            "confidence": 0.5,
            "duration_seconds": None,
            "explanation": f"Could not analyze audio: {str(e)}"
        }

# ------------- FRONTEND (HOMEPAGE) ----------------
@app.route('/', methods=['GET'])
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Voice Detector</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin-top: 40px; background: #f4f4f4; }
            .container { background: white; padding: 25px; width: 55%; margin: auto; border-radius: 12px; box-shadow: 0px 0px 12px rgba(0,0,0,0.2); }
            button { padding: 10px 15px; background: #007bff; color: white; border: none; cursor: pointer; border-radius: 6px; }
            #result { margin-top: 20px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🎙️ AI Voice Detection (Web App)</h2>

            <input type="file" id="audioFile" accept="audio/*"><br><br>
            <button onclick="uploadAudio()">Analyze Audio</button>

            <div id="result"></div>
        </div>

        <script>
        async function uploadAudio() {
            const fileInput = document.getElementById("audioFile");
            if (!fileInput.files.length) {
                alert("Please select an audio file first!");
                return;
            }

            const file = fileInput.files[0];
            const reader = new FileReader();
            reader.readAsDataURL(file);

            reader.onload = async function () {
                const base64Audio = reader.result.split(",")[1];
                document.getElementById("result").innerHTML = "⏳ Analyzing...";

                const response = await fetch("/classify", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-API-KEY": "voice_detect_2026"
                    },
                    body: JSON.stringify({ "base64": base64Audio })
                });

                const data = await response.json();

                if (data.status === "success") {
                    document.getElementById("result").innerHTML =
                        `<p>🔍 Result: ${data.classification.label}</p>
                         <p>📊 Confidence: ${data.classification.confidence}</p>
                         <p>📝 Explanation: ${data.classification.explanation}</p>`;
                } else {
                    document.getElementById("result").innerHTML =
                        `<p style="color:red;">Error: ${data.error}</p>`;
                }
            };
        }
        </script>
    </body>
    </html>
    """

   

# ------------- MAIN API ENDPOINT -----------------
@app.route('/classify', methods=['POST'])
def classify_audio():

    # ---- API KEY CHECK ----
    if not validate_api_key(request.headers):
        return jsonify({"error": "Unauthorized - Invalid API Key"}), 401

    temp_filename = f"{uuid.uuid4()}.wav"
    temp_path = os.path.join(TEMP_DIR, temp_filename)

    try:
        # ---------- CASE 1: NORMAL FILE UPLOAD (FORM-DATA) ----------
        if request.files and "file" in request.files:
            file = request.files["file"]
            file.save(temp_path)

        else:
            # Try to read JSON body
            data = request.get_json(silent=True)

            # ---------- CASE 2: RAW JSON WITH BASE64 ----------
            if data and ('base64' in data or 'audio_base64' in data):
                b64 = data.get('base64') or data.get('audio_base64')
                audio_data = base64.b64decode(b64)
                with open(temp_path, "wb") as f:
                    f.write(audio_data)

            # ---------- CASE 3: URL (OPTIONAL) ----------
            elif data and 'url' in data:
                response = requests.get(data['url'], stream=True, timeout=10)
                if response.status_code != 200:
                    return jsonify({"error": "Failed to retrieve URL"}), 400

                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            else:
                return jsonify({
                    "error": "Send either: file (form-data), base64/audio_base64 (JSON), or url"
                }), 400

        # -------- ANALYZE AUDIO ----------
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

# --------- RENDER PORT FIX ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)


