import sqlite3
db_path = 'c:/Coding/Ular/ProjectSpotify/data_processed/spotify_data.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("DELETE FROM artwork_cache WHERE cache_key LIKE '%Drake%'")
conn.commit()
print(f'Deleted {c.rowcount} cache entries for Drake.')
conn.close()
