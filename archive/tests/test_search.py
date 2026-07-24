import os
import toml
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

secrets_path = os.path.join(".streamlit", "secrets.toml")
secrets = toml.load(secrets_path)
client_id = secrets["spotify"]["client_id"]
client_secret = secrets["spotify"]["client_secret"]

# Test with Client Credentials (no user auth needed for search)
auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(auth_manager=auth_manager)

try:
    results = sp.search(q="Kanye West", type="artist", limit=1)
    print("Search results:", results['artists']['items'][0]['name'])
except Exception as e:
    print("Error:", e)
