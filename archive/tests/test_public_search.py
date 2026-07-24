import os
import toml
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import time

secrets_path = os.path.join(".streamlit", "secrets.toml")
secrets = toml.load(secrets_path)
client_id = secrets["spotify"]["client_id"]
client_secret = secrets["spotify"]["client_secret"]

public_auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp_public = spotipy.Spotify(auth_manager=public_auth)

start_time = time.time()
print("Starting search...")
try:
    res = sp_public.search(q="Kanye West", type="artist", limit=1)
    print("Found:", res['artists']['items'][0]['name'])
except Exception as e:
    print("Error:", e)
print(f"Time taken: {time.time() - start_time} seconds")
