"""Fetch the most recent Spotify plays and append them idempotently."""

from datetime import datetime

import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from auth_spotify import load_credentials
from backend import database


INSERT_SQL = """
    INSERT INTO listening_history
    (
        timestamp, duration_ms, track_name, artist_name, album_name,
        reason_start, reason_end, skipped, year, month, day_name,
        hour, duration_min
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (timestamp, track_name, artist_name) DO NOTHING
"""


def main() -> None:
    client_id, client_secret, redirect_uri = load_credentials()
    database.init_db()
    spotify = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
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
        ),
        retries=1,
        requests_timeout=10,
    )

    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(timestamp) FROM listening_history")
        latest = cursor.fetchone()[0]
        latest_timestamp = (
            pd.to_datetime(latest).tz_localize(None)
            if latest
            else datetime(1970, 1, 1)
        )

        response = spotify.current_user_recently_played(limit=50)
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

        if rows:
            cursor.executemany(INSERT_SQL, list(reversed(rows)))
            inserted = max(0, cursor.rowcount)
        else:
            inserted = 0

    print(f"Spotify collector completed: {inserted} new plays.")


if __name__ == "__main__":
    main()
