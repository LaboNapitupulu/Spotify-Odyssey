"""Transform Spotify Extended Streaming History JSON and insert it safely."""

import glob
import os
import sys

import pandas as pd
from psycopg2.extras import execute_values

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import database


INSERT_SQL = """
    INSERT INTO listening_history
    (
        timestamp, duration_ms, track_name, artist_name, album_name,
        reason_start, reason_end, skipped, year, month, day_name,
        hour, duration_min
    )
    VALUES %s
    ON CONFLICT (timestamp, track_name, artist_name) DO NOTHING
"""


def find_history_files() -> list[str]:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pattern = os.path.join(
        project_root,
        "data_raw",
        "Streaming_History_Audio_*.json",
    )
    return sorted(glob.glob(pattern))


def transform_history(files: list[str]) -> pd.DataFrame:
    if not files:
        raise FileNotFoundError(
            "No Streaming_History_Audio_*.json files found in data_raw/."
        )

    raw = pd.concat([pd.read_json(path) for path in files], ignore_index=True)
    source_columns = [
        "ts",
        "ms_played",
        "master_metadata_track_name",
        "master_metadata_album_artist_name",
        "master_metadata_album_album_name",
        "reason_start",
        "reason_end",
        "skipped",
    ]
    missing = [column for column in source_columns if column not in raw.columns]
    if missing:
        raise ValueError(
            "Input is not Spotify Extended Streaming History. "
            f"Missing columns: {', '.join(missing)}"
        )

    transformed = raw[source_columns].copy()
    transformed.rename(
        columns={
            "ts": "timestamp",
            "ms_played": "duration_ms",
            "master_metadata_track_name": "track_name",
            "master_metadata_album_artist_name": "artist_name",
            "master_metadata_album_album_name": "album_name",
        },
        inplace=True,
    )
    transformed.dropna(subset=["track_name", "artist_name"], inplace=True)
    transformed = transformed[transformed["duration_ms"] >= 30000].copy()

    timestamps = pd.to_datetime(transformed["timestamp"], utc=True).dt.tz_convert(
        "Asia/Jakarta"
    )
    transformed["timestamp"] = timestamps.dt.tz_localize(None)
    transformed["year"] = timestamps.dt.year
    transformed["month"] = timestamps.dt.month
    transformed["day_name"] = timestamps.dt.day_name()
    transformed["hour"] = timestamps.dt.hour
    transformed["duration_min"] = transformed["duration_ms"] / 60000
    transformed["skipped"] = transformed["skipped"].fillna(False).astype(bool)
    transformed["album_name"] = transformed["album_name"].where(
        transformed["album_name"].notna(),
        None,
    )
    return transformed.drop_duplicates(
        subset=["timestamp", "track_name", "artist_name"],
        keep="last",
    )


def process_and_append_data() -> int:
    files = find_history_files()
    transformed = transform_history(files)
    columns = [
        "timestamp",
        "duration_ms",
        "track_name",
        "artist_name",
        "album_name",
        "reason_start",
        "reason_end",
        "skipped",
        "year",
        "month",
        "day_name",
        "hour",
        "duration_min",
    ]
    rows = list(transformed[columns].itertuples(index=False, name=None))

    database.init_db()
    inserted = 0
    with database.get_db_connection() as conn:
        cursor = conn.cursor()
        for offset in range(0, len(rows), 1000):
            chunk = rows[offset : offset + 1000]
            execute_values(cursor, INSERT_SQL, chunk, page_size=len(chunk))
            inserted += max(0, cursor.rowcount)

    print(f"Data import completed: {inserted} new listening events.")
    return inserted


if __name__ == "__main__":
    process_and_append_data()
