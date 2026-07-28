import json
import logging
import os
import threading
from typing import List, Optional

import psycopg2
import spotipy
import toml
from psycopg2 import extensions
from psycopg2.extras import DictCursor, Json
from psycopg2.pool import ThreadedConnectionPool


logger = logging.getLogger(__name__)

_pool: Optional[ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def get_db_url() -> str:
    """Return a PostgreSQL connection string without exposing it in logs."""
    secrets_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        ".streamlit",
        "secrets.toml",
    )
    try:
        secrets = toml.load(secrets_path)
        url = secrets["database"]["url"]
    except (FileNotFoundError, KeyError, TypeError, toml.TomlDecodeError):
        url = os.environ.get("DATABASE_URL")

    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                min_connections = max(1, int(os.environ.get("DB_POOL_MIN", "1")))
                max_connections = max(
                    min_connections,
                    int(os.environ.get("DB_POOL_MAX", "5")),
                )
                _pool = ThreadedConnectionPool(
                    min_connections,
                    max_connections,
                    dsn=get_db_url(),
                    cursor_factory=DictCursor,
                )
    return _pool


class PooledConnection:
    """Proxy a psycopg2 connection and return it safely to the pool on close."""

    def __init__(self, pool: ThreadedConnectionPool, connection) -> None:
        self._pool = pool
        self._connection = connection
        self._released = False

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self) -> None:
        if self._released:
            return
        self._released = True

        if self._connection.closed:
            self._pool.putconn(self._connection, close=True)
            return

        try:
            if self._connection.status != extensions.STATUS_READY:
                self._connection.rollback()
            self._pool.putconn(self._connection)
        except Exception:
            self._pool.putconn(self._connection, close=True)
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is None:
            self._connection.commit()
        else:
            self._connection.rollback()
        self.close()


def get_db_connection() -> PooledConnection:
    pool = _get_pool()
    return PooledConnection(pool, pool.getconn())


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


def init_db() -> None:
    """Create the schema and enforce an idempotent listening-history key."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS artwork_cache (
                cache_key TEXT PRIMARY KEY,
                image_url TEXT NOT NULL DEFAULT ''
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS listening_history (
                timestamp TIMESTAMP NOT NULL,
                duration_ms BIGINT NOT NULL,
                track_name TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                album_name TEXT,
                reason_start TEXT,
                reason_end TEXT,
                skipped BOOLEAN NOT NULL DEFAULT FALSE,
                year INT NOT NULL,
                month INT NOT NULL,
                day_name TEXT NOT NULL,
                hour INT NOT NULL,
                duration_min DOUBLE PRECISION NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS spotify_tokens (
                username TEXT PRIMARY KEY,
                token_info JSONB NOT NULL
            )
            """
        )

        cursor.execute("SELECT to_regclass('public.uq_listening_event')")
        if cursor.fetchone()[0] is None:
            # Clean historical duplicates once so the unique index can be added safely.
            cursor.execute(
                """
                DELETE FROM listening_history older
                USING listening_history newer
                WHERE older.ctid < newer.ctid
                  AND older.timestamp = newer.timestamp
                  AND older.track_name = newer.track_name
                  AND older.artist_name = newer.artist_name
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX uq_listening_event
                ON listening_history(timestamp, track_name, artist_name)
                """
            )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_listening_year ON listening_history(year)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_listening_artist ON listening_history(artist_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_listening_track ON listening_history(track_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_listening_timestamp ON listening_history(timestamp)"
        )


def get_cached_artwork(cache_key: str) -> Optional[str]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT image_url FROM artwork_cache WHERE cache_key = %s",
            (cache_key,),
        )
        row = cursor.fetchone()
        return row["image_url"] if row else None


def set_cached_artwork(cache_key: str, image_url: str) -> None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO artwork_cache (cache_key, image_url)
            VALUES (%s, %s)
            ON CONFLICT (cache_key)
            DO UPDATE SET image_url = EXCLUDED.image_url
            """,
            (cache_key, image_url),
        )


def _build_where(years: Optional[List[int]], month: Optional[int]):
    clauses = []
    params = []
    if years:
        placeholders = ",".join("%s" for _ in years)
        clauses.append(f"year IN ({placeholders})")
        params.extend(years)
    if month is not None:
        clauses.append("month = %s")
        params.append(month)
    return (
        (" WHERE " + " AND ".join(clauses)) if clauses else "",
        tuple(params),
    )


def get_kpi_stats(
    years: Optional[List[int]] = None,
    month: Optional[int] = None,
) -> dict:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clause, params = _build_where(years, month)
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(duration_min), 0) AS total_min,
                COUNT(DISTINCT (track_name, artist_name)) AS total_tracks,
                COUNT(DISTINCT artist_name) AS total_artists,
                COUNT(DISTINCT CAST(timestamp AS DATE)) AS active_days,
                COUNT(*) AS total_streams
            FROM listening_history
            """
            + where_clause,
            params,
        )
        row = cursor.fetchone()
        active_days = max(1, int(row["active_days"] or 0))
        total_minutes = float(row["total_min"] or 0)
        total_streams = int(row["total_streams"] or 0)
        return {
            "airtime_hours": total_minutes / 60,
            "total_tracks": int(row["total_tracks"] or 0),
            "total_artists": int(row["total_artists"] or 0),
            "active_days": int(row["active_days"] or 0),
            "avg_streams_per_day": total_streams / active_days,
            "avg_min_per_day": total_minutes / active_days,
        }


def get_hourly_clock(
    years: Optional[List[int]] = None,
    month: Optional[int] = None,
) -> list:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clause, params = _build_where(years, month)
        cursor.execute(
            """
            SELECT
                hour,
                COUNT(track_name) AS streams,
                COALESCE(SUM(duration_min), 0) AS minutes
            FROM listening_history
            """
            + where_clause
            + " GROUP BY hour ORDER BY hour",
            params,
        )
        rows = cursor.fetchall()
        streams_map = {row["hour"]: row["streams"] for row in rows}
        minutes_map = {row["hour"]: row["minutes"] for row in rows}
        return [
            {
                "hour": hour,
                "streams": int(streams_map.get(hour, 0)),
                "minutes": float(minutes_map.get(hour, 0)),
            }
            for hour in range(24)
        ]


def get_trends(
    years: Optional[List[int]] = None,
    month: Optional[int] = None,
) -> dict:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clause, params = _build_where(years, month)
        cursor.execute(
            f"""
            SELECT CAST(timestamp AS DATE) AS date, COUNT(*) AS streams
            FROM listening_history
            {where_clause}
            GROUP BY CAST(timestamp AS DATE)
            ORDER BY CAST(timestamp AS DATE)
            """,
            params,
        )
        daily = [
            {"date": row["date"].strftime("%Y-%m-%d"), "streams": row["streams"]}
            for row in cursor.fetchall()
        ]

        cursor.execute(
            f"""
            SELECT day_name, COUNT(*) AS streams
            FROM listening_history
            {where_clause}
            GROUP BY day_name
            """,
            params,
        )
        day_order = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6,
        }
        day_of_week = sorted(
            [
                {"day": row["day_name"], "streams": row["streams"]}
                for row in cursor.fetchall()
            ],
            key=lambda item: day_order.get(item["day"], 7),
        )

        # Keep the full monthly distribution visible while one month is selected.
        years_where, years_params = _build_where(years, None)
        cursor.execute(
            f"""
            SELECT month, COUNT(*) AS streams
            FROM listening_history
            {years_where}
            GROUP BY month
            ORDER BY month
            """,
            years_params,
        )
        month_names = {
            1: "Jan",
            2: "Feb",
            3: "Mar",
            4: "Apr",
            5: "May",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Oct",
            11: "Nov",
            12: "Dec",
        }
        monthly = [
            {
                "month_id": row["month"],
                "month": month_names.get(row["month"], str(row["month"])),
                "streams": row["streams"],
            }
            for row in cursor.fetchall()
        ]
        return {"daily": daily, "dow": day_of_week, "monthly": monthly}


def get_hall_of_fame(
    top_n: int = 10,
    years: Optional[List[int]] = None,
    month: Optional[int] = None,
) -> dict:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clause, params = _build_where(years, month)

        cursor.execute(
            f"""
            SELECT artist_name, SUM(duration_min) AS minutes
            FROM listening_history
            {where_clause}
            GROUP BY artist_name
            ORDER BY minutes DESC
            LIMIT %s
            """,
            params + (top_n,),
        )
        artists = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            f"""
            SELECT album_name, artist_name, SUM(duration_min) AS minutes
            FROM listening_history
            {where_clause}
            GROUP BY album_name, artist_name
            ORDER BY minutes DESC
            LIMIT %s
            """,
            params + (top_n,),
        )
        albums = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            f"""
            SELECT track_name, artist_name, SUM(duration_min) AS minutes
            FROM listening_history
            {where_clause}
            GROUP BY track_name, artist_name
            ORDER BY minutes DESC
            LIMIT %s
            """,
            params + (top_n,),
        )
        songs = [dict(row) for row in cursor.fetchall()]
        return {"artists": artists, "albums": albums, "songs": songs}


def get_available_years() -> list:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT year FROM listening_history WHERE year IS NOT NULL ORDER BY year"
        )
        return [row["year"] for row in cursor.fetchall()]


class PostgresCacheHandler(spotipy.CacheHandler):
    def __init__(self, username: str = "default") -> None:
        self.username = username

    def get_cached_token(self):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT token_info FROM spotify_tokens WHERE username = %s",
                (self.username,),
            )
            row = cursor.fetchone()
            if not row or not row["token_info"]:
                return None
            token = row["token_info"]
            return token if isinstance(token, dict) else json.loads(token)

    def save_token_to_cache(self, token_info) -> None:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO spotify_tokens (username, token_info)
                VALUES (%s, %s)
                ON CONFLICT (username)
                DO UPDATE SET token_info = EXCLUDED.token_info
                """,
                (self.username, Json(token_info)),
            )
