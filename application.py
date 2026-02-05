import os
import uuid
import base64
import requests
import wave

from flask import Flask, request, jsonify

# ---------------- CONFIG ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

API_KEY = "voice_detect_2026"
TEMP_DIR = os.path.join(BASE_DIR, "temp_audio")
os.makedirs(TEMP_DIR, exist_ok=True)
# ---------------------------------------

def validate_api_key(headers):
    return headers.get("X-API-KEY") == API_KEY

# --------- SIMPLE AUDIO ANALYSIS ----------
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

# ------------- HOMEPAGE (PRETTY UI, INLINE HTML) ----------------
@app.route('/', methods=['GET'])
def home():
    return """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <title>AI Voice Detector</title>
  <style>
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: linear-gradient(135deg, #1f2933, #111827);
      color: white;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
    }

    .app-card {
      background: #0f172a;
      padding: 30px;
      border-radius: 16px;
      width: 420px;
      box-shadow: 0px 10px 30px rgba(0,0,0,0.4);
      text-align: center;
      border: 1px solid #1e293b;
    }

    h2 {
      color: #38bdf8;
    }

    .file-box {
      border: 2px dashed #334155;
      padding: 20px;
      border-radius: 10px;
      background: #020617;
      margin-bottom: 15px;
    }

    button {
      width: 100%;
      padding: 12px;
      border: none;
      border-radius: 8px;
      background: linear-gradient(90deg, #0ea5e9, #38bdf8);
      color: #0f172a;
      font-size: 15px;
      font-weight: bold;
      cursor: pointer;
    }

    #result {
      margin-top: 18px;
      padding: 12px;
      border-radius: 10px;
      background: #020617;
      border: 1px solid #1e293b;
      display: none;
    }

    .loading {
      display: none;
      margin-top: 12px;
      color: #38bdf8;
    }
  </style>
</head>

<body>
  <div class="app-card">
    <h2>🎙️ AI Voice Detection</h2>

    <div class="file-box">
      <input type="file" id="audioFile" accept="audio/*" />
    </div>

    <button onclick="uploadAudio()">Analyze Audio</button>

    <div class="loading" id="loadingText">⏳ Analyzing your audio...</div>

    <div id="result">
      <div id="resLabel"></div>
      <div id="resConf"></div>
      <div id="resExplain"></div>
    </div>
  </div>

<script>
async function uploadAudio() {
  const fileInput = document.getElementById("audioFile");
  const loadingText = document.getElementById("loadingText");
  const resultBox = document.getElementById("result");

  if (!fileInput.files.length) {
    alert("Please select an audio file first!");
    return;
  }

  loadingText.style.display = "block";
  resultBox.style.display = "none";

  const file = fileInput.files[0];
  const reader = new FileReader();

  reader.readAsDataURL(file);

  reader.onload = async function () {
    const base64Audio = reader.result.split(",")[1];

    const response = await fetch("/classify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-KEY": "voice_detect_2026"
      },
      body: JSON.stringify({
        "base64": base64Audio
      })
    });

    const data = await response.json();

    loadingText.style.display = "none";
    resultBox.style.display = "block";

    if (data.status === "success") {
      document.getElementById("resLabel").innerText =
        "Result: " + data.classification.label;

      document.getElementById("resConf").innerText =
        "Confidence: " + data.classification.confidence;

      document.getElementById("resExplain").innerText =
        "Explanation: " + data.classification.explanation;
    } else {
      document.getElementById("resLabel").innerText = "Error ❌";
      document.getElementById("resExplain").innerText = data.error;
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

    if not validate_api_key(request.headers):
        return jsonify({"error": "Unauthorized - Invalid API Key"}), 401

    temp_filename = f"{uuid.uuid4()}.wav"
    temp_path = os.path.join(TEMP_DIR, temp_filename)

    try:
        # ---- CASE 1: FORM-DATA FILE UPLOAD ----
        if request.files and "file" in request.files:
            file = request.files["file"]
            file.save(temp_path)

        else:
            data = request.get_json(silent=True)

            # ---- CASE 2: FLEXIBLE BASE64 INPUT ----
            if data:
                possible_keys = ["base64", "audio_base64", "audio", "file_base64"]

                b64 = None
                for key in possible_keys:
                    if key in data:
                        b64 = data[key]
                        break

                if b64:
                    audio_data = base64.b64decode(b64)
                    with open(temp_path, "wb") as f:
                        f.write(audio_data)

                # ---- CASE 3: URL INPUT ----
                elif "url" in data:
                    response = requests.get(data["url"], stream=True, timeout=10)
                    if response.status_code != 200:
                        return jsonify({"error": "Failed to retrieve URL"}), 400

                    with open(temp_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                else:
                    return jsonify({
                        "error": "Send audio as file, base64/audio_base64/audio/file_base64, or url"
                    }), 400

            else:
                return jsonify({"error": "No valid body received"}), 400

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
