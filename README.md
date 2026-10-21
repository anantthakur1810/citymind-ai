# CITYMIND AI — Final Prototype

This is the existing dashboard project, packaged for website deployment and Android APK creation. Read `README_DEPLOY_APK.md` for the complete step-by-step guide.

## Existing prototype capabilities
- Live current weather from Open-Meteo (internet required; no API key needed).
- Interactive OpenStreetMap.
- City selector for Noida, New Delhi, Gurugram, and Faridabad.
- Optional TomTom Traffic Flow API integration through the Flask backend.
- Transparent speed-loss risk score when observed and free-flow speeds are available.

## Important data note
Traffic rows and markers are illustrative in demo mode, not measured traffic or verified incidents. Real traffic measurements require a valid TomTom Traffic Flow API key with appropriate access. The risk score is an explainable indicator, not a trained AI prediction model.

## Run locally on Windows
```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```
Open http://127.0.0.1:5000. Add your TomTom key only to `.env` if you have one. Never commit `.env` or expose your key in frontend code.


## Issue reporting and admin dashboard
- Users can submit issues in the Help & Issue Center and receive an Issue ID plus private lookup code. They need both to check status.
- Open `/admin` to sign in and update issue status or the public update note.
- For local testing, SQLite is used automatically if `DATABASE_URL` is blank. On Render, configure a PostgreSQL database and set its internal connection URL as `DATABASE_URL`; do not rely on the local SQLite file for hosted persistence.
- Set `ADMIN_PASSWORD` and a long random `FLASK_SECRET_KEY` as Render environment variables. Do not commit actual secrets.
- Status values: Received, In Progress, Resolved, Closed.
