"""Authorize the project owner's Spotify account from a trusted local machine."""

import os

import spotipy
import toml
from spotipy.oauth2 import SpotifyOAuth

from backend import database


def load_credentials() -> tuple[str, str, str]:
    try:
        secrets = toml.load(os.path.join(".streamlit", "secrets.toml"))["spotify"]
        client_id = secrets["client_id"]
        client_secret = secrets["client_secret"]
        redirect_uri = secrets["redirect_uri"]
    except (FileNotFoundError, KeyError, TypeError, toml.TomlDecodeError):
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
        redirect_uri = os.environ.get(
            "SPOTIFY_REDIRECT_URI",
            "http://127.0.0.1:8080/",
        )

    if not client_id or not client_secret:
        raise RuntimeError("Spotify credentials are not configured.")
    return client_id, client_secret, redirect_uri


def main() -> None:
    client_id, client_secret, redirect_uri = load_credentials()
    database.init_db()

    print("Authorize Spotify in the browser using your project-owner account.")
    print("The resulting refresh token is stored in PostgreSQL, not in the repository.")

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=(
            "user-read-recently-played "
            "user-read-currently-playing "
            "user-read-playback-state"
        ),
        cache_handler=database.PostgresCacheHandler(),
        open_browser=True,
    )
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    spotify.current_user_playing_track()
    print("Spotify authorization completed.")


if __name__ == "__main__":
    main()
