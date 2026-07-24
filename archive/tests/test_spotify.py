import os
import toml
import spotipy
from spotipy.oauth2 import SpotifyOAuth

secrets = toml.load('c:/Coding/Ular/ProjectSpotify/.streamlit/secrets.toml')
auth_manager = SpotifyOAuth(
    client_id=secrets["spotify"]["client_id"], 
    client_secret=secrets["spotify"]["client_secret"], 
    redirect_uri=secrets["spotify"]["redirect_uri"], 
    cache_path='c:/Coding/Ular/ProjectSpotify/.cache'
)
sp = spotipy.Spotify(auth_manager=auth_manager)
res1 = sp.search(q='Drake', type='artist', limit=1)
print('Drake:', res1['artists']['items'][0]['images'][0]['url'])
res2 = sp.search(q='Kendrick Lamar', type='artist', limit=1)
print('Kendrick:', res2['artists']['items'][0]['images'][0]['url'])
