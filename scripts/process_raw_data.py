import pandas as pd
import glob
import os
import sqlite3

def process_and_append_data():
    print("Starting Spotify Raw Data Processor...")
    
    # 1. READ RAW JSON
    raw_path = os.path.join("..", "data_raw")
    if not os.path.exists(raw_path):
        raw_path = "data_raw"
    
    all_files = glob.glob(os.path.join(raw_path, "Streaming_History_Audio_*.json"))
    if not all_files:
        print("No raw JSON files found in data_raw/")
        return
        
    print(f"Found {len(all_files)} JSON files. Loading data...")
    df_list = [pd.read_json(f) for f in all_files]
    df_raw = pd.concat(df_list, ignore_index=True)
    print(f"Total raw rows: {df_raw.shape[0]}")
    
    # 2. CLEAN AND TRANSFORM
    columns_to_keep = [
        'ts', 'ms_played', 'master_metadata_track_name', 
        'master_metadata_album_artist_name', 'master_metadata_album_album_name',
        'reason_start', 'reason_end', 'skipped'
    ]
    
    # Check if files are extended history format
    missing_cols = [col for col in columns_to_keep if col not in df_raw.columns]
    if missing_cols:
        print(f"Error: JSON format does not match Extended Streaming History. Missing columns: {missing_cols}")
        return
        
    df = df_raw[columns_to_keep].copy()
    df.rename(columns={
        'ts': 'timestamp',
        'ms_played': 'duration_ms',
        'master_metadata_track_name': 'track_name',
        'master_metadata_album_artist_name': 'artist_name',
        'master_metadata_album_album_name': 'album_name'
    }, inplace=True)
    
    df.dropna(subset=['track_name', 'artist_name'], inplace=True)
    
    # Timezone conversion (UTC -> Asia/Jakarta)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Jakarta')
    
    df['year'] = df['timestamp'].dt.year
    df['month'] = df['timestamp'].dt.month
    df['day_name'] = df['timestamp'].dt.day_name()
    df['hour'] = df['timestamp'].dt.hour
    
    df['duration_min'] = df['duration_ms'] / 60000
    
    # Filter 30s
    df_clean = df[df['duration_ms'] >= 30000].copy()
    
    # Strip timezone for DB storage
    df_clean['timestamp'] = df_clean['timestamp'].dt.tz_localize(None)
    
    # 3. CONNECT TO SQLITE & SMART APPEND
    db_path = os.path.join("..", "data_processed", "spotify_data.db")
    if not os.path.exists(os.path.dirname(db_path)):
        db_path = os.path.join("data_processed", "spotify_data.db")
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get max timestamp
    c.execute("SELECT MAX(timestamp) FROM listening_history")
    last_timestamp_str = c.fetchone()[0]
    
    if last_timestamp_str:
        # Convert DB string to datetime for comparison
        last_timestamp = pd.to_datetime(last_timestamp_str)
        print(f"Latest record in DB: {last_timestamp}")
        
        # Filter new rows
        new_rows = df_clean[df_clean['timestamp'] > last_timestamp].copy()
    else:
        print("Database is empty. Inserting all processed rows.")
        new_rows = df_clean.copy()
        
    if new_rows.empty:
        print("No new records to insert. Database is already up to date with these files.")
        conn.close()
        return
        
    print(f"Found {new_rows.shape[0]} new records to insert.")
    
    # Format timestamp explicitly as string to match collector
    new_rows['timestamp'] = new_rows['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Ensure boolean type is native python bool before inserting
    new_rows['skipped'] = new_rows['skipped'].astype(bool)
    
    # Append to DB
    new_rows.to_sql('listening_history', conn, if_exists='append', index=False)
    
    conn.commit()
    conn.close()
    
    print("Successfully appended new data to the database!")

if __name__ == "__main__":
    process_and_append_data()
