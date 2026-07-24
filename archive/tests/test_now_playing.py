import os
import toml
import spotipy
from spotipy.oauth2 import SpotifyOAuth

secrets_path = os.path.join(".streamlit", "secrets.toml")
secrets = toml.load(secrets_path)
client_id = secrets["spotify"]["client_id"]
client_secret = secrets["spotify"]["client_secret"]
redirect_uri = secrets["spotify"]["redirect_uri"]

auth_manager = SpotifyOAuth(
    client_id=client_id, 
    client_secret=client_secret, 
    redirect_uri=redirect_uri, 
    scope='user-read-recently-played user-read-currently-playing user-read-playback-state',
    cache_path=".cache",
    open_browser=False
)
sp = spotipy.Spotify(auth_manager=auth_manager)

print("Fetching now playing...")
try:
    res = sp.current_user_playing_track()
    print("Result:", res)
except Exception as e:
    print("Error:", e)
