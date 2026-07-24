import sqlite3
import os

db_path = 'c:/Coding/Ular/ProjectSpotify/data_processed/spotify_data.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT * FROM artwork_cache WHERE cache_key LIKE '%Kendrick Lamar%' OR cache_key LIKE '%Drake%'")
print(c.fetchall())
conn.close()
