import sqlite3
import os

db_path = 'c:/Coding/Ular/ProjectSpotify/data_processed/spotify_data.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM artwork_cache WHERE image_url = '' OR image_url IS NULL")
    conn.commit()
    print(f'Deleted {c.rowcount} empty cache entries.')
    conn.close()
else:
    print('DB not found.')
