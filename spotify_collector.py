import os
import sqlite3
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import toml
from datetime import datetime
import pandas as pd

print("Starting Spotify Data Collector (SQLite Version)...")

# 1. READ CREDENTIALS
try:
    secrets = toml.load(".streamlit/secrets.toml")
    CLIENT_ID = secrets["spotify"]["client_id"]
    CLIENT_SECRET = secrets["spotify"]["client_secret"]
    REDIRECT_URI = secrets["spotify"]["redirect_uri"]
except Exception as e:
    print(f"Failed to read credentials: {e}")
    exit()

# 2. INIT SPOTIFY API
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope='user-read-recently-played'
))

# 3. CONNECT TO SQLITE
db_path = os.path.join("data_processed", "spotify_data.db")
if not os.path.exists(db_path):
    print("Database not found. Please run migration script first.")
    exit()

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Get the latest timestamp in the DB to avoid duplicates
c.execute("SELECT MAX(timestamp) FROM listening_history")
last_timestamp_str = c.fetchone()[0]
if last_timestamp_str:
    # Remove milliseconds if any, for simple comparison
    last_timestamp = pd.to_datetime(last_timestamp_str).tz_localize(None)
else:
    # If DB is empty, set a very old date
    last_timestamp = datetime(1970, 1, 1)

print(f"Latest record in DB: {last_timestamp}")

# 4. FETCH NEW DATA (Max 50)
try:
    results = sp.current_user_recently_played(limit=50)
except Exception as e:
    print(f"Failed to fetch data from Spotify: {e}")
    exit()

new_data_list = []
for item in results['items']:
    # Convert UTC to WIB (Asia/Jakarta) and remove timezone info
    played_at = pd.to_datetime(item['played_at']).tz_convert('Asia/Jakarta').tz_localize(None)
    
    if played_at > last_timestamp:
        track = item['track']
        new_row = (
            played_at.strftime('%Y-%m-%d %H:%M:%S'), # timestamp
            track['duration_ms'],
            track['name'],
            track['artists'][0]['name'],
            track['album']['name'],
            'API_Auto_Update', # reason_start
            'API_Auto_Update', # reason_end
            0, # skipped (False)
            played_at.year,
            played_at.month,
            played_at.day_name(),
            played_at.hour,
            track['duration_ms'] / 60000.0 # duration_min
        )
        new_data_list.append(new_row)

# 5. INSERT TO DATABASE
if new_data_list:
    # Reverse to insert oldest first
    new_data_list.reverse()
    
    c.executemany('''
        INSERT INTO listening_history 
        (timestamp, duration_ms, track_name, artist_name, album_name, reason_start, reason_end, skipped, year, month, day_name, hour, duration_min)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', new_data_list)
    
    conn.commit()
    print(f"{len(new_data_list)} new songs added to database.")
else:
    print("No new songs to add. Database is up to date.")

conn.close()