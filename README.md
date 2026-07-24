# Spotify Odyssey: Personal Audio Analytics

A full-stack, real-time analytics dashboard engineered to track, process, and visualize personal Spotify streaming history. 

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-009688?style=flat-square&logo=fastapi)
![SQLite](https://img.shields.io/badge/SQLite-Data%2B-lightgrey?style=flat-square&logo=sqlite)
![JavaScript](https://img.shields.io/badge/JavaScript-Vanilla-F7DF1E?style=flat-square&logo=javascript)

---

## Project Overview

Instead of relying on end-of-year summaries like Spotify Wrapped, this application provides an interactive, live look at listening habits. It integrates directly with the Spotify Web API to process raw streaming JSON data and fetch live playback states, presenting the insights through a custom-built, zero-framework dashboard.

---

## Core Features

- **Live Pulse (Real-Time Playback):** Connects to the Spotify API to display the currently playing track in real-time.
- **Interactive Data Cross-Filtering:** Features an interactive dashboard architecture where selecting a specific metric (e.g., a month in the bar chart) automatically recalculates and filters all other components (KPIs, top tracks, time-of-day clocks) without page reloads.
- **Automated Data Pipeline:** 
  - Ingests and parses massive "Extended Streaming History" JSON dumps into a highly indexed SQLite database.
  - Implements a background collector script (`spotify_collector.py`) that periodically fetches the 50 most recent streams and appends them to the database to ensure data currency.
- **Custom UI Architecture:** A zero-dependency vanilla frontend constructed from scratch, styled to match modern dark-mode design systems.

---

## Technical Stack

- **Backend:** Python, FastAPI, SQLite
- **Data Processing:** Pandas
- **API Integration:** Spotipy (Spotify Web API)
- **Frontend:** Vanilla JavaScript, HTML5, CSS3, Chart.js

---

## Getting Started

### Prerequisites
- Python 3.9+
- A Spotify Developer account (Client ID & Client Secret)

### Installation & Setup

**1. Clone the repository:**
```bash
git clone https://github.com/LaboNapitupulu/ProjectSpotify.git
cd ProjectSpotify
```

**2. Install backend dependencies:**
```bash
pip install fastapi uvicorn spotipy pandas
```

**3. Configure Spotify Credentials:**
Create a `.streamlit/secrets.toml` file in the project root and add your Spotify Developer credentials:
```toml
[spotify]
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"
redirect_uri = "http://localhost:8080"
```

**4. Authenticate Account:**
Run the authentication script to generate your user token:
```bash
python auth_spotify.py
```

**5. Ingest Raw Data:**
Place your downloaded Spotify JSON history files into the `data_raw/` directory, then execute the data processor to build the SQLite database:
```bash
python scripts/process_raw_data.py
```

**6. Start the API Server:**
```bash
python -m uvicorn backend.main:app --port 8000
```

**7. Launch the Application:**
Open `frontend/index.html` in any modern web browser to view the dashboard.

---

## Privacy Notice

The `.gitignore` configuration strictly blocks `data_processed/spotify_data.db` and any credential files. Personal streaming history and API tokens will never be pushed to version control.
