import hmac
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Literal, Optional

import pandas as pd
import spotipy
import toml
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

from backend import database


logger = logging.getLogger("spotify_odyssey")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
LIVE_SPOTIFY_ENABLED = os.environ.get("ENABLE_LIVE_SPOTIFY", "false").lower() in {
    "1",
    "true",
    "yes",
}


def _load_spotify_credentials() -> tuple[Optional[str], Optional[str], str]:
    secrets_path = os.path.join(ROOT_DIR, ".streamlit", "secrets.toml")
    try:
        secrets = toml.load(secrets_path)
        spotify_secrets = secrets["spotify"]
        return (
            spotify_secrets["client_id"],
            spotify_secrets["client_secret"],
            spotify_secrets["redirect_uri"],
        )
    except (FileNotFoundError, KeyError, TypeError, toml.TomlDecodeError):
        return (
            os.environ.get("SPOTIFY_CLIENT_ID"),
            os.environ.get("SPOTIFY_CLIENT_SECRET"),
            os.environ.get(
                "SPOTIFY_REDIRECT_URI",
                "http://127.0.0.1:8080/",
            ),
        )


class NonBlockingSpotifyOAuth(SpotifyOAuth):
    def _get_auth_response_interactive(self, open_browser=False):
        raise RuntimeError(
            "Spotify authorization is missing. Run auth_spotify.py locally."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database_ready = False
    app.state.spotify_user = None
    app.state.spotify_public = None

    try:
        database.init_db()
        app.state.database_ready = True
    except Exception:
        logger.exception("Database initialization failed.")

    client_id, client_secret, redirect_uri = _load_spotify_credentials()
    if client_id and client_secret:
        try:
            public_auth = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
            )
            app.state.spotify_public = spotipy.Spotify(
                auth_manager=public_auth,
                retries=1,
                requests_timeout=10,
            )
        except Exception:
            logger.exception("Spotify public client initialization failed.")

        if LIVE_SPOTIFY_ENABLED and app.state.database_ready:
            try:
                auth_manager = NonBlockingSpotifyOAuth(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                    scope=(
                        "user-read-recently-played "
                        "user-read-currently-playing "
                        "user-read-playback-state"
                    ),
                    cache_handler=database.PostgresCacheHandler(),
                    open_browser=False,
                )
                app.state.spotify_user = spotipy.Spotify(
                    auth_manager=auth_manager,
                    retries=1,
                    requests_timeout=10,
                )
            except Exception:
                logger.exception("Spotify private client initialization failed.")
    else:
        logger.warning("Spotify credentials are not configured.")

    yield
    database.close_pool()


app = FastAPI(
    title="Spotify Odyssey API",
    description="Personal listening analytics with privacy-safe portfolio defaults.",
    version="2.0.0",
    lifespan=lifespan,
)

configured_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-API-Key"],
)


def parse_years(years: Optional[str]) -> Optional[list[int]]:
    if not years:
        return None
    if len(years) > 240:
        raise HTTPException(status_code=422, detail="Year filter is too long.")

    parts = [part.strip() for part in years.split(",") if part.strip()]
    if not parts or len(parts) > 40:
        raise HTTPException(status_code=422, detail="Select between 1 and 40 years.")
    if any(not re.fullmatch(r"\d{4}", part) for part in parts):
        raise HTTPException(status_code=422, detail="Years must use YYYY format.")

    parsed = sorted({int(part) for part in parts})
    if any(year < 1900 or year > 2100 for year in parsed):
        raise HTTPException(status_code=422, detail="Year is outside the supported range.")
    return parsed


def require_database(request: Request) -> None:
    if not request.app.state.database_ready:
        raise HTTPException(status_code=503, detail="Analytics database is unavailable.")


def require_private_spotify(
    request: Request,
    x_api_key: Annotated[Optional[str], Header()] = None,
) -> None:
    if not LIVE_SPOTIFY_ENABLED:
        raise HTTPException(status_code=404, detail="Live Spotify features are disabled.")

    expected_key = os.environ.get("PRIVATE_API_KEY")
    client_host = request.client.host if request.client else ""
    is_loopback = client_host in {"127.0.0.1", "::1", "localhost"}

    if expected_key:
        if not x_api_key or not hmac.compare_digest(x_api_key, expected_key):
            raise HTTPException(status_code=401, detail="Invalid private API key.")
    elif not is_loopback:
        raise HTTPException(
            status_code=503,
            detail="PRIVATE_API_KEY is required outside localhost.",
        )


@app.get("/api/health")
def health(request: Request):
    return {
        "status": "ready" if request.app.state.database_ready else "degraded",
        "database_ready": request.app.state.database_ready,
        "live_spotify_enabled": LIVE_SPOTIFY_ENABLED,
        "spotify_public_ready": request.app.state.spotify_public is not None,
    }


@app.get("/api/stats/years", dependencies=[Depends(require_database)])
def api_get_years():
    return database.get_available_years()


@app.get("/api/stats/kpi", dependencies=[Depends(require_database)])
def api_get_kpi(
    years: Annotated[Optional[str], Query(max_length=240)] = None,
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
):
    return database.get_kpi_stats(parse_years(years), month)


@app.get("/api/stats/clock", dependencies=[Depends(require_database)])
def api_get_clock(
    years: Annotated[Optional[str], Query(max_length=240)] = None,
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
):
    return database.get_hourly_clock(parse_years(years), month)


@app.get("/api/stats/trends", dependencies=[Depends(require_database)])
def api_get_trends(
    years: Annotated[Optional[str], Query(max_length=240)] = None,
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
):
    return database.get_trends(parse_years(years), month)


@app.get("/api/stats/fame", dependencies=[Depends(require_database)])
def api_get_fame(
    years: Annotated[Optional[str], Query(max_length=240)] = None,
    top_n: Annotated[int, Query(ge=1, le=50)] = 10,
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
):
    data = database.get_hall_of_fame(top_n, parse_years(years), month)
    for category in ("artists", "albums", "songs"):
        for item in data[category]:
            item["image_url"] = ""
    return data


def clean_query(text: str) -> str:
    cleaned = re.sub(r"\(.*?\)", "", str(text))
    cleaned = cleaned.split("feat")[0].split("ft.")[0].strip()
    return " ".join(cleaned.split())


def get_artwork(
    request: Request,
    name: str,
    search_type: Literal["artist", "album", "track"],
    artist_name: Optional[str] = None,
) -> str:
    cache_key = f"{search_type}_{name}_{artist_name or ''}"
    cached_url = database.get_cached_artwork(cache_key)
    if cached_url is not None:
        return cached_url

    spotify_public = request.app.state.spotify_public
    if spotify_public is None:
        return ""

    name_clean = clean_query(name)
    if search_type == "artist":
        query = name_clean
    elif search_type == "album" and artist_name:
        query = f'album:"{name_clean}" artist:"{clean_query(artist_name)}"'
    else:
        query = f'track:"{name_clean}" artist:"{clean_query(artist_name or "")}"'

    try:
        results = spotify_public.search(q=query, type=search_type, limit=5)
        items = results.get(f"{search_type}s", {}).get("items", [])
        if not items:
            database.set_cached_artwork(cache_key, "")
            return ""

        best_item = next(
            (
                item
                for item in items
                if item.get("name", "").casefold() == name_clean.casefold()
            ),
            items[0],
        )
        images = best_item.get("images", [])
        if not images and search_type == "track":
            images = best_item.get("album", {}).get("images", [])
        image_url = images[0].get("url", "") if images else ""
        database.set_cached_artwork(cache_key, image_url)
        return image_url
    except Exception:
        logger.exception("Artwork lookup failed for type=%s.", search_type)
        return ""


@app.get("/api/spotify/artwork", dependencies=[Depends(require_database)])
def api_get_artwork(
    request: Request,
    name: Annotated[str, Query(min_length=1, max_length=200)],
    type: Annotated[Literal["artist", "album", "track"], Query()] = "artist",
    artist_name: Annotated[Optional[str], Query(max_length=200)] = None,
):
    return {"image_url": get_artwork(request, name, type, artist_name)}


@app.get(
    "/api/spotify/now-playing",
    dependencies=[Depends(require_private_spotify)],
)
def api_now_playing(request: Request):
    spotify_user = request.app.state.spotify_user
    if spotify_user is None:
        raise HTTPException(status_code=503, detail="Spotify user client is unavailable.")
    try:
        current = spotify_user.current_user_playing_track()
        if not current or not current.get("is_playing") or not current.get("item"):
            return {"is_playing": False}
        track = current["item"]
        images = track.get("album", {}).get("images", [])
        artists = track.get("artists", [])
        return {
            "is_playing": True,
            "track_id": track.get("id"),
            "track_name": track.get("name", "Unknown track"),
            "artist_name": artists[0].get("name", "Unknown artist") if artists else "",
            "image_url": images[0].get("url", "") if images else "",
        }
    except Exception:
        logger.exception("Now-playing request failed.")
        return JSONResponse(
            {"error": "Spotify is temporarily unavailable."},
            status_code=502,
        )


@app.get(
    "/api/spotify/recently-played",
    dependencies=[Depends(require_private_spotify)],
)
def api_recently_played(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    spotify_user = request.app.state.spotify_user
    if spotify_user is None:
        raise HTTPException(status_code=503, detail="Spotify user client is unavailable.")
    try:
        response = spotify_user.current_user_recently_played(limit=limit)
        items = []
        for entry in response.get("items", []):
            track = entry.get("track", {})
            artists = track.get("artists", [])
            images = track.get("album", {}).get("images", [])
            preferred_image = images[2] if len(images) > 2 else (images[0] if images else {})
            items.append(
                {
                    "played_at": entry.get("played_at"),
                    "track_name": track.get("name", "Unknown track"),
                    "artist_name": artists[0].get("name", "Unknown artist")
                    if artists
                    else "",
                    "image_url": preferred_image.get("url", ""),
                }
            )
        return {"items": items}
    except Exception:
        logger.exception("Recently-played request failed.")
        return JSONResponse(
            {"error": "Spotify is temporarily unavailable."},
            status_code=502,
        )


@app.post(
    "/api/sync",
    dependencies=[Depends(require_private_spotify), Depends(require_database)],
)
def api_sync_spotify(request: Request):
    spotify_user = request.app.state.spotify_user
    if spotify_user is None:
        raise HTTPException(status_code=503, detail="Spotify user client is unavailable.")

    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(timestamp) FROM listening_history")
            latest = cursor.fetchone()[0]
            latest_timestamp = (
                pd.to_datetime(latest).tz_localize(None)
                if latest
                else datetime(1970, 1, 1)
            )

            response = spotify_user.current_user_recently_played(limit=50)
            rows = []
            for entry in response.get("items", []):
                played_at = (
                    pd.to_datetime(entry["played_at"])
                    .tz_convert("Asia/Jakarta")
                    .tz_localize(None)
                )
                if played_at <= latest_timestamp:
                    continue
                track = entry["track"]
                rows.append(
                    (
                        played_at,
                        track["duration_ms"],
                        track["name"],
                        track["artists"][0]["name"],
                        track["album"]["name"],
                        "API_Auto_Update",
                        "API_Auto_Update",
                        False,
                        played_at.year,
                        played_at.month,
                        played_at.day_name(),
                        played_at.hour,
                        track["duration_ms"] / 60000.0,
                    )
                )

            inserted = 0
            if rows:
                cursor.executemany(
                    """
                    INSERT INTO listening_history
                    (
                        timestamp, duration_ms, track_name, artist_name,
                        album_name, reason_start, reason_end, skipped,
                        year, month, day_name, hour, duration_min
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (timestamp, track_name, artist_name) DO NOTHING
                    """,
                    list(reversed(rows)),
                )
                inserted = max(0, cursor.rowcount)
        return {"status": "success", "inserted": inserted}
    except Exception:
        logger.exception("Spotify synchronization failed.")
        return JSONResponse(
            {"error": "Spotify synchronization failed."},
            status_code=502,
        )


if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
