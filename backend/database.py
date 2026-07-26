import psycopg2
from psycopg2.extras import DictCursor
import os
import toml
from datetime import datetime
from typing import List, Optional

def get_db_url():
    secrets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml")
    try:
        secrets = toml.load(secrets_path)
        return secrets["database"]["url"]
    except Exception:
        # Fallback to environment variable if secrets.toml is missing (e.g. on Render)
        return os.environ.get("DATABASE_URL")

def get_db_connection():
    url = get_db_url()
    if not url:
        raise ValueError("Database URL not found in .streamlit/secrets.toml or DATABASE_URL env var")
    conn = psycopg2.connect(url, cursor_factory=DictCursor)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Artwork Cache Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS artwork_cache (
            cache_key TEXT PRIMARY KEY,
            image_url TEXT
        )
    ''')
    
    # 2. Listening History Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS listening_history (
            timestamp TIMESTAMP,
            duration_ms BIGINT,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            reason_start TEXT,
            reason_end TEXT,
            skipped BOOLEAN,
            year INT,
            month INT,
            day_name TEXT,
            hour INT,
            duration_min FLOAT
        )
    ''')
    
    # Create indexes if they don't exist
    c.execute("CREATE INDEX IF NOT EXISTS idx_year ON listening_history(year)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_artist ON listening_history(artist_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_track ON listening_history(track_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON listening_history(timestamp)")

    # 3. Spotify Token Cache Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS spotify_tokens (
            username TEXT PRIMARY KEY,
            token_info JSONB
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def get_cached_artwork(cache_key: str) -> Optional[str]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT image_url FROM artwork_cache WHERE cache_key = %s", (cache_key,))
        row = c.fetchone()
        return row['image_url'] if row else None
    finally:
        conn.close()

def set_cached_artwork(cache_key: str, image_url: str):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            INSERT INTO artwork_cache (cache_key, image_url) 
            VALUES (%s, %s)
            ON CONFLICT (cache_key) DO UPDATE SET image_url = EXCLUDED.image_url
        ''', (cache_key, image_url))
        conn.commit()
    finally:
        conn.close()

def _build_where(years, month):
    clauses = []
    params = []
    if years:
        placeholders = ','.join('%s' for _ in years)
        clauses.append(f"year IN ({placeholders})")
        params.extend(years)
    if month is not None:
        clauses.append("month = %s")
        params.append(month)
    if clauses:
        return " WHERE " + " AND ".join(clauses), tuple(params)
    return "", ()

def get_kpi_stats(years: List[int] = None, month: int = None):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        query = "SELECT SUM(duration_min) as total_min, COUNT(DISTINCT track_name) as total_tracks, COUNT(DISTINCT artist_name) as total_artists, MIN(timestamp) as min_date, MAX(timestamp) as max_date, COUNT(*) as total_streams FROM listening_history"
        where_clause, params = _build_where(years, month)
        query += where_clause
        c.execute(query, params)
        row = c.fetchone()
        
        if not row or not row['min_date']:
            return {}
            
        min_d = row['min_date']
        max_d = row['max_date']
        total_days = max(1, (max_d - min_d).days + 1)
        
        return {
            "airtime_hours": (row['total_min'] or 0) / 60,
            "total_tracks": row['total_tracks'],
            "total_artists": row['total_artists'],
            "avg_streams_per_day": row['total_streams'] / total_days,
            "avg_min_per_day": (row['total_min'] or 0) / total_days
        }
    finally:
        conn.close()

def get_hourly_clock(years: List[int] = None, month: int = None):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        query = "SELECT hour, COUNT(track_name) as streams, SUM(duration_min) as minutes FROM listening_history"
        where_clause, params = _build_where(years, month)
        query += where_clause + " GROUP BY hour ORDER BY hour"
        c.execute(query, params)
        rows = c.fetchall()
        
        streams_map = {row['hour']: row['streams'] for row in rows}
        minutes_map = {row['hour']: row['minutes'] for row in rows}
        return [{"hour": h, "streams": streams_map.get(h, 0), "minutes": minutes_map.get(h, 0.0)} for h in range(24)]
    finally:
        conn.close()

def get_trends(years: List[int] = None, month: int = None):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        where_clause, params = _build_where(years, month)
        
        c.execute(f"SELECT CAST(timestamp AS DATE) as date, COUNT(*) as streams FROM listening_history {where_clause} GROUP BY CAST(timestamp AS DATE) ORDER BY CAST(timestamp AS DATE)", params)
        daily = [{"date": r['date'].strftime('%Y-%m-%d'), "streams": r['streams']} for r in c.fetchall()]
        
        c.execute(f"SELECT day_name, COUNT(*) as streams FROM listening_history {where_clause} GROUP BY day_name", params)
        day_order = {'Monday':0,'Tuesday':1,'Wednesday':2,'Thursday':3,'Friday':4,'Saturday':5,'Sunday':6}
        dow = sorted([{"day": r['day_name'], "streams": r['streams']} for r in c.fetchall()], key=lambda x: day_order.get(x['day'], 0))
        
        where_no_month, params_no_month = _build_where(years, None)
        c.execute(f"SELECT month, COUNT(*) as streams FROM listening_history {where_no_month} GROUP BY month ORDER BY month", params_no_month)
        month_map = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
        monthly = [{"month_id": r['month'], "month": month_map.get(r['month'], str(r['month'])), "streams": r['streams']} for r in c.fetchall()]
        
        return {"daily": daily, "dow": dow, "monthly": monthly}
    finally:
        conn.close()

def get_hall_of_fame(top_n: int = 10, years: List[int] = None, month: int = None):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        where_clause, params = _build_where(years, month)
        
        c.execute(f"SELECT artist_name, SUM(duration_min) as minutes FROM listening_history {where_clause} GROUP BY artist_name ORDER BY minutes DESC LIMIT %s", params + (top_n,))
        artists = [dict(r) for r in c.fetchall()]
        
        c.execute(f"SELECT album_name, artist_name, SUM(duration_min) as minutes FROM listening_history {where_clause} GROUP BY album_name, artist_name ORDER BY minutes DESC LIMIT %s", params + (top_n,))
        albums = [dict(r) for r in c.fetchall()]
        
        c.execute(f"SELECT track_name, artist_name, SUM(duration_min) as minutes FROM listening_history {where_clause} GROUP BY track_name, artist_name ORDER BY minutes DESC LIMIT %s", params + (top_n,))
        songs = [dict(r) for r in c.fetchall()]
        
        return {"artists": artists, "albums": albums, "songs": songs}
    finally:
        conn.close()

def get_available_years():
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT DISTINCT year FROM listening_history ORDER BY year")
        return [r['year'] for r in c.fetchall() if r['year'] is not None]
    finally:
        conn.close()

import spotipy
import json

class PostgresCacheHandler(spotipy.CacheHandler):
    def __init__(self, username="default"):
        self.username = username

    def get_cached_token(self):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT token_info FROM spotify_tokens WHERE username = %s", (self.username,))
        row = c.fetchone()
        conn.close()
        if row and row['token_info']:
            # Ensure it is a dict if the driver returns string, though JSONB usually returns dict in psycopg2
            return row['token_info'] if isinstance(row['token_info'], dict) else json.loads(row['token_info'])
        return None

    def save_token_to_cache(self, token_info):
        conn = get_db_connection()
        c = conn.cursor()
        token_str = json.dumps(token_info)
        c.execute('''
            INSERT INTO spotify_tokens (username, token_info) 
            VALUES (%s, %s)
            ON CONFLICT (username) DO UPDATE SET token_info = EXCLUDED.token_info
        ''', (self.username, token_str))
        conn.commit()
        conn.close()

