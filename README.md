# Spotify Odyssey

A lightweight, real-time dashboard built to track and visualize my personal Spotify listening history. 

Instead of waiting for Spotify Wrapped at the end of the year, I built this full-stack app to give me a live, interactive look at my listening habits whenever I want.

## Features

- **Live Pulse:** Connects to the Spotify API to show the exact song I am listening to right now in real-time.
- **Interactive Cross-Filtering:** Click on any month in the bar chart, and the entire dashboard (KPIs, Hall of Fame, Clocks) automatically filters to show data for just that month.
- **Automated Data Pipeline:** 
  - Parses Spotify's massive "Extended Streaming History" JSON dumps into a fast SQLite database.
  - Includes a background collector script (`spotify_collector.py`) that automatically fetches my 50 most recent streams and appends them to the database, so the data never gets stale.
- **Custom UI:** A zero-framework vanilla frontend styled from scratch to match Spotify's sleek dark mode aesthetic.

## Tech Stack

- **Backend:** Python, FastAPI, SQLite
- **Frontend:** Vanilla JS, CSS3, HTML5, Chart.js
- **API:** Spotipy (Spotify Web API)

## Setup & Installation

If you want to run this with your own Spotify data:

1. Clone the repository.
2. Install the required Python packages:
   ```bash
   pip install fastapi uvicorn spotipy pandas
   ```
3. Create a `.streamlit/secrets.toml` file and add your Spotify Developer credentials (Client ID, Secret, and Redirect URI).
4. Run `python auth_spotify.py` to authenticate your account.
5. Place your downloaded Spotify JSON history files into the `data_raw/` directory.
6. Run the initial data processor to build your SQLite database:
   ```bash
   python scripts/process_raw_data.py
   ```
7. Start the API server:
   ```bash
   python -m uvicorn backend.main:app --port 8000
   ```
8. Just open `frontend/index.html` in any web browser.

## Privacy Note
The `.gitignore` is set up to block `data_processed/spotify_data.db` and any credential files. Your private listening history will not be pushed to GitHub.
