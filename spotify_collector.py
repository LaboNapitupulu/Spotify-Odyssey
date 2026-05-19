import os
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import toml
from datetime import datetime

print("Starting Spotify Data Collector...")

# 1. MEMBACA KREDENSIAL DARI SECRETS.TOML
try:
    secrets = toml.load(".streamlit/secrets.toml")
    CLIENT_ID = secrets["spotify"]["client_id"]
    CLIENT_SECRET = secrets["spotify"]["client_secret"]
    REDIRECT_URI = secrets["spotify"]["redirect_uri"]
except Exception as e:
    print(f"Failed to read credentials: {e}")
    exit()

# 2. INISIALISASI SPOTIFY API
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope='user-read-recently-played'
))

# 3. MEMBACA DATABASE LAMA (CSV)
csv_path = os.path.join("data_processed", "spotify_clean_ready.csv")
try:
    df_history = pd.read_csv(csv_path)
    df_history['timestamp'] = pd.to_datetime(df_history['timestamp'], format ="mixed")
    # Mengambil daftar timestamp yang sudah ada agar tidak terjadi duplikat
    existing_timestamps = set(df_history['timestamp'])
    print(f"Old data loaded: {len(df_history)} rows.")
except FileNotFoundError:
    print("No existing database found.")
    exit()

# 4. MENARIK DATA TERBARU DARI API (Maksimal 50 lagu)
try:
    results = sp.current_user_recently_played(limit=50)
except Exception as e:
    print(f"Failed to fetch data: {e}")
    exit()

new_tracks_count = 0
new_data_list = []

# 5. PROSES TRANSFORMASI DATA (ETL)
for item in results['items']:
    # Mengubah waktu UTC ke WIB, lalu menghapus info zona waktunya agar cocok dengan CSV statis Anda
    played_at = pd.to_datetime(item['played_at']).tz_convert('Asia/Jakarta').tz_localize(None)
    
    # Cek apakah lagu pada detik ini sudah pernah dicatat di CSV
    if played_at not in existing_timestamps:
        track = item['track']
        
        # Merakit data baru agar kolomnya sama persis dengan CSV
        new_row = {
            'timestamp': played_at,
            'duration_ms': track['duration_ms'],
            'track_name': track['name'],
            'artist_name': track['artists'][0]['name'],
            'album_name': track['album']['name'],
            'reason_start': 'API_Auto_Update', # Menandai bahwa ini data dari API
            'reason_end': 'API_Auto_Update',
            'skipped': False,
            'year': played_at.year,
            'month': played_at.month,
            'day_name': played_at.day_name(),
            'hour': played_at.hour,
            'duration_min': track['duration_ms'] / 60000
        }
        new_data_list.append(new_row)
        existing_timestamps.add(played_at)
        new_tracks_count += 1

# 6. MENYIMPAN KE DATABASE (APPEND)
if new_tracks_count > 0:
    # Membalik urutan (karena API memberikan lagu paling baru di atas)
    new_data_list.reverse() 
    
    # Menggabungkan data baru ke Dataframe
    df_new = pd.DataFrame(new_data_list)
    df_combined = pd.concat([df_history, df_new], ignore_index=True)
    
    # Menimpa file CSV dengan data yang sudah ditambahkan
    df_combined.to_csv(csv_path, index=False)
    print(f"{new_tracks_count} song added to database.")
    print(f"Total data after update: {len(df_combined)}")
else:
    print("No new songs to add. Database is up to date.")