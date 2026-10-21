# CITYMIND AI — Final Prototype

This folder contains a runnable hackathon prototype with a live weather feed, OpenStreetMap, and an optional TomTom Traffic Flow API integration.

## What works

- Live current weather from Open-Meteo (no API key needed; internet required).
- Interactive OpenStreetMap using Leaflet.
- City selector for Noida, New Delhi, Gurugram, and Faridabad.
- Transparent speed-loss risk score when observed and free-flow traffic speeds are available.
- Backend endpoint that keeps the TomTom API key off the browser.
- Clearly labelled illustrative traffic values when no real traffic API is configured.

## Important honesty note

The dashboard's traffic data starts in **demo mode**. Its five traffic rows and their markers are illustrative, not actual measured traffic or verified incidents. Real traffic-flow measurements appear only after you configure a valid TomTom Traffic API key and request a supported coordinate. Weather is fetched live from Open-Meteo. The risk score is an explainable indicator, not a trained AI prediction model.

## Run on Windows

1. Install Python 3.10 or newer.
2. Extract this folder.
3. Open Command Prompt or PowerShell in this folder.
4. Run:

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```

5. Open `.env` in Notepad and paste your TomTom API key after `TOMTOM_API_KEY=`. Leave it blank if you do not have one.
6. Run:

   ```powershell
   python app.py
   ```

7. Open http://127.0.0.1:5000 in your browser.

Without a TomTom key, the app still runs with live weather and an interactive map; traffic remains clearly marked as illustrative.

## Add real traffic flow

- Create/check a TomTom developer account and obtain a Traffic API key from the official TomTom developer portal.
- Ensure your account/key is entitled to Traffic Flow API access and check current terms, limits, and pricing.
- Enter a latitude,longitude in the dashboard and click **Check traffic at point**.
- The app calls the local `/api/traffic` endpoint, which calls TomTom and returns measured `currentSpeed` and `freeFlowSpeed`.
- Coverage and returned street names vary by location. If an API call fails, do not present demo values as live data.

## Data and method

For a returned segment:

`speed_loss_percent = (1 - currentSpeed / freeFlowSpeed) * 100`

The dashboard clamps the displayed indicator to 0–100 and labels levels as Low, Medium, or High. These thresholds are demonstration heuristics and must be validated before operational use. They are not an official traffic severity classification.

## External services

- Open-Meteo API: https://open-meteo.com/
- OpenStreetMap: https://www.openstreetmap.org/copyright
- TomTom Traffic API documentation: https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/traffic-flow-service

Internet access is required to load map tiles, weather, and live traffic API data. For a hackathon, disclose which data is live, which is illustrative, and which features remain future work.
