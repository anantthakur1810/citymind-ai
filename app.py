import os
from flask import Flask, jsonify, request
import requests
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, static_folder=".", static_url_path="")
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "").strip()

@app.get("/")
def index():
    return app.send_static_file("index.html")

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "tomtom_configured": bool(TOMTOM_API_KEY)})

@app.get("/api/traffic")
def traffic():
    if not TOMTOM_API_KEY:
        return jsonify({"error": "TOMTOM_API_KEY is not configured in the local .env file."}), 503
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError()
    except ValueError:
        return jsonify({"error": "Provide valid latitude and longitude."}), 400

    url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
    try:
        response = requests.get(
            url,
            params={"point": f"{lat},{lon}", "unit": "KMPH", "key": TOMTOM_API_KEY},
            timeout=15,
        )
        if response.status_code == 401 or response.status_code == 403:
            return jsonify({"error": "TomTom rejected the key. Check key permissions and account access."}), 502
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as exc:
        return jsonify({"error": f"TomTom request failed: {exc}"}), 502

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
