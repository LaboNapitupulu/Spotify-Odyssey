from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import toml
import os
import re
from fastapi.responses import JSONResponse

from backend import database

app = FastAPI(title="ProjectSpotify Backend")

# Setup CORS if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. SPOTIFY API CONFIG
def get_spotify_client():
    secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml")
    try:
        secrets = toml.load(secrets_path)
        client_id = secrets["spotify"]["client_id"]
        client_secret = secrets["spotify"]["client_secret"]
        redirect_uri = secrets["spotify"]["redirect_uri"]
        
        # If cache string is in secrets, save it (like the original app did)
        if "cache" in secrets["spotify"]:
            cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
            with open(cache_path, "w") as f:
                f.write(secrets["spotify"]["cache"])
                
    except Exception:
        # Fallback for testing if secrets.toml isn't there
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8080/")

    cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
    auth_manager = SpotifyOAuth(
        client_id=client_id, 
        client_secret=client_secret, 
        redirect_uri=redirect_uri, 
        scope='user-read-recently-played user-read-currently-playing user-read-playback-state',
        cache_path=cache_path
    )
    return spotipy.Spotify(auth_manager=auth_manager)

from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials

class NonBlockingSpotifyOAuth(SpotifyOAuth):
    def _get_auth_response_interactive(self, open_browser=False):
        raise Exception("Token expired or missing scopes. Please run 'python auth_spotify.py' in the terminal.")

# We will initialize this lazily or handle errors if tokens are missing
sp = None
sp_public = None
try:
    secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml")
    secrets = toml.load(secrets_path)
    client_id = secrets["spotify"]["client_id"]
    client_secret = secrets["spotify"]["client_secret"]
    redirect_uri = secrets["spotify"]["redirect_uri"]
    
    cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
    auth_manager = NonBlockingSpotifyOAuth(
        client_id=client_id, 
        client_secret=client_secret, 
        redirect_uri=redirect_uri, 
        scope='user-read-recently-played user-read-currently-playing user-read-playback-state',
        cache_path=cache_path,
        open_browser=False
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)
    
    # Public client for artwork fetching (no user auth required)
    public_auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp_public = spotipy.Spotify(auth_manager=public_auth)
except Exception as e:
    print(f"Warning: Could not initialize Spotify client: {e}")

def clean_query(text):
    text = str(text)
    text = re.sub(r'\(.*?\)', '', text) 
    text = text.split('feat')[0].split('ft.')[0].strip() 
    return " ".join(text.split())

# In-memory cache for artwork replaced with persistent SQLite cache
def get_artwork(name, search_type='artist', artist_name=None):
    cache_key = f"{search_type}_{name}_{artist_name}"
    cached_url = database.get_cached_artwork(cache_key)
    if cached_url is not None:
        return cached_url
        
    if not sp_public:
        return ""
        
    try:
        name_clean = clean_query(name)
        if search_type == 'artist':
            q_str = name_clean
        elif search_type == 'album' and artist_name:
            q_str = f'album:"{name_clean}" artist:"{clean_query(artist_name)}"'
        else:
            q_str = f'track:"{name_clean}" artist:"{clean_query(artist_name)}"'
            
        results = sp_public.search(q=q_str, type=search_type, limit=5)
        items = results[search_type + 's']['items']
        if items:
            # Try to find exact match first to avoid Spotify returning trending related artists
            best_item = items[0]
            for item in items:
                if item['name'].lower() == name_clean.lower():
                    best_item = item
                    break
                    
            images = best_item.get('images', [])
            url = images[0]['url'] if images else ""
            if not url and search_type == 'track' and 'album' in best_item:
                images = best_item['album'].get('images', [])
                url = images[0]['url'] if images else ""
                
            if url:
                database.set_cached_artwork(cache_key, url)
            return url
        else:
            database.set_cached_artwork(cache_key, "")
            return ""
    except Exception as e:
        print(f"Error fetching artwork for {name}: {e}")
        
    return ""

# 2. STATS ENDPOINTS
@app.get("/api/stats/years")
def api_get_years():
    return database.get_available_years()

@app.get("/api/stats/kpi")
def api_get_kpi(years: str = None, month: int = None):
    year_list = [int(y) for y in years.split(',')] if years else None
    return database.get_kpi_stats(year_list, month)

@app.get("/api/stats/clock")
def api_get_clock(years: str = None, month: int = None):
    year_list = [int(y) for y in years.split(',')] if years else None
    return database.get_hourly_clock(year_list, month)

@app.get("/api/stats/trends")
def api_get_trends(years: str = None, month: int = None):
    year_list = [int(y) for y in years.split(',')] if years else None
    return database.get_trends(year_list, month)

@app.get("/api/stats/fame")
def api_get_fame(years: str = None, top_n: int = 10, month: int = None):
    year_list = [int(y) for y in years.split(',')] if years else None
    data = database.get_hall_of_fame(top_n, year_list, month)
    
    # We will NOT fetch artwork here to avoid blocking the UI.
    # The frontend will lazy-load the artwork using the /api/spotify/artwork endpoint.
    for artist in data['artists']: artist['image_url'] = ''
    for album in data['albums']: album['image_url'] = ''
    for song in data['songs']: song['image_url'] = ''
        
    return data

@app.get("/api/spotify/artwork")
def api_get_artwork(name: str, type: str = 'artist', artist_name: str = None):
    # This allows the frontend to fetch images concurrently without blocking the main dashboard
    url = get_artwork(name, type, artist_name)
    return {"image_url": url}

# 3. LIVE SPOTIFY ENDPOINTS (Proxy)
@app.get("/api/spotify/now-playing")
def api_now_playing():
    if not sp: return JSONResponse({"error": "Spotify client not initialized"}, status_code=500)
    try:
        curr = sp.current_user_playing_track()
        if curr and curr.get('is_playing'):
            return {
                "is_playing": True,
                "track_id": curr['item']['id'],
                "track_name": curr['item']['name'],
                "artist_name": curr['item']['artists'][0]['name'],
                "image_url": curr['item']['album']['images'][0]['url'] if curr['item']['album']['images'] else ""
            }
        return {"is_playing": False}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/spotify/recently-played")
def api_recently_played(limit: int = 50):
    if not sp: return JSONResponse({"error": "Spotify client not initialized"}, status_code=500)
    try:
        res = sp.current_user_recently_played(limit=limit)
        items = []
        for item in res.get('items', []):
            track = item['track']
            items.append({
                "played_at": item['played_at'],
                "track_name": track['name'],
                "artist_name": track['artists'][0]['name'],
                "image_url": track['album']['images'][2]['url'] if len(track['album']['images']) > 2 else (track['album']['images'][0]['url'] if track['album']['images'] else "")
            })
        return {"items": items}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# 4. STATIC FILES (Frontend)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
# Only mount if directory exists (to prevent errors during setup)
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
