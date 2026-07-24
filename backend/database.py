import sqlite3
import os
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_processed", "spotify_data.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS artwork_cache (
            cache_key TEXT PRIMARY KEY,
            image_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_cached_artwork(cache_key: str) -> Optional[str]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT image_url FROM artwork_cache WHERE cache_key = ?", (cache_key,))
    row = c.fetchone()
    conn.close()
    return row['image_url'] if row else None

def set_cached_artwork(cache_key: str, image_url: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO artwork_cache (cache_key, image_url) VALUES (?, ?)", (cache_key, image_url))
    conn.commit()
    conn.close()

def _build_where(years, month):
    clauses = []
    params = []
    if years:
        placeholders = ','.join('?' for _ in years)
        clauses.append(f"year IN ({placeholders})")
        params.extend(years)
    if month is not None:
        clauses.append("month = ?")
        params.append(month)
    if clauses:
        return " WHERE " + " AND ".join(clauses), tuple(params)
    return "", ()

def get_kpi_stats(years: List[int] = None, month: int = None):
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT SUM(duration_min) as total_min, COUNT(DISTINCT track_name) as total_tracks, COUNT(DISTINCT artist_name) as total_artists, MIN(timestamp) as min_date, MAX(timestamp) as max_date, COUNT(*) as total_streams FROM listening_history"
    where_clause, params = _build_where(years, month)
    query += where_clause
        
    c.execute(query, params)
    row = c.fetchone()
    
    if not row or not row['min_date']:
        conn.close()
        return {}
        
    min_d = datetime.strptime(row['min_date'].split(' ')[0], '%Y-%m-%d')
    max_d = datetime.strptime(row['max_date'].split(' ')[0], '%Y-%m-%d')
    total_days = (max_d - min_d).days + 1
    if total_days <= 0: total_days = 1
    
    res = {
        "airtime_hours": (row['total_min'] or 0) / 60,
        "total_tracks": row['total_tracks'],
        "total_artists": row['total_artists'],
        "avg_streams_per_day": row['total_streams'] / total_days,
        "avg_min_per_day": (row['total_min'] or 0) / total_days
    }
    conn.close()
    return res

def get_hourly_clock(years: List[int] = None, month: int = None):
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT hour, COUNT(track_name) as streams, SUM(duration_min) as minutes FROM listening_history"
    where_clause, params = _build_where(years, month)
    query += where_clause
        
    query += " GROUP BY hour ORDER BY hour"
    
    c.execute(query, params)
    rows = c.fetchall()
    
    hours = list(range(24))
    streams_map = {row['hour']: row['streams'] for row in rows}
    minutes_map = {row['hour']: row['minutes'] for row in rows}
    
    data = []
    for h in hours:
        data.append({
            "hour": h,
            "streams": streams_map.get(h, 0),
            "minutes": minutes_map.get(h, 0.0)
        })
        
    conn.close()
    return data

def get_trends(years: List[int] = None, month: int = None):
    conn = get_db_connection()
    c = conn.cursor()
    
    where_clause, params = _build_where(years, month)
        
    # Daily streams
    c.execute(f"SELECT date(timestamp) as date, COUNT(*) as streams FROM listening_history {where_clause} GROUP BY date(timestamp) ORDER BY date(timestamp)", params)
    daily = [dict(r) for r in c.fetchall()]
    
    # Day of week streams (0 = Monday in pandas, sqlite strftime('%w') 0 = Sunday)
    # the CSV has 'day_name'. Let's group by day_name and sort
    c.execute(f"SELECT day_name, COUNT(*) as streams FROM listening_history {where_clause} GROUP BY day_name", params)
    dow_raw = c.fetchall()
    day_order = {'Monday':0, 'Tuesday':1, 'Wednesday':2, 'Thursday':3, 'Friday':4, 'Saturday':5, 'Sunday':6}
    dow = sorted([{"day": r['day_name'], "streams": r['streams']} for r in dow_raw], key=lambda x: day_order.get(x['day'], 0))
    
    # Monthly streams
    # Intentionally EXCLUDE the month filter so the user can still see all months to select from
    where_no_month, params_no_month = _build_where(years, None)
    c.execute(f"SELECT month, COUNT(*) as streams FROM listening_history {where_no_month} GROUP BY month ORDER BY month", params_no_month)
    month_map = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}
    monthly = [{"month_id": r['month'], "month": month_map.get(r['month'], str(r['month'])), "streams": r['streams']} for r in c.fetchall()]
    
    conn.close()
    return {"daily": daily, "dow": dow, "monthly": monthly}

def get_hall_of_fame(top_n: int = 10, years: List[int] = None, month: int = None):
    conn = get_db_connection()
    c = conn.cursor()
    
    where_clause, params = _build_where(years, month)
        
    # Artists
    c.execute(f"SELECT artist_name, SUM(duration_min) as minutes FROM listening_history {where_clause} GROUP BY artist_name ORDER BY minutes DESC LIMIT ?", params + (top_n,))
    artists = [dict(r) for r in c.fetchall()]
    
    # Albums
    c.execute(f"SELECT album_name, artist_name, SUM(duration_min) as minutes FROM listening_history {where_clause} GROUP BY album_name, artist_name ORDER BY minutes DESC LIMIT ?", params + (top_n,))
    albums = [dict(r) for r in c.fetchall()]
    
    # Songs
    c.execute(f"SELECT track_name, artist_name, SUM(duration_min) as minutes FROM listening_history {where_clause} GROUP BY track_name, artist_name ORDER BY minutes DESC LIMIT ?", params + (top_n,))
    songs = [dict(r) for r in c.fetchall()]
    
    conn.close()
    return {"artists": artists, "albums": albums, "songs": songs}

def get_available_years():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT year FROM listening_history ORDER BY year")
    years = [r['year'] for r in c.fetchall()]
    conn.close()
    return years
