import os
import toml
import spotipy
from spotipy.oauth2 import SpotifyOAuth

secrets_path = os.path.join(".streamlit", "secrets.toml")
secrets = toml.load(secrets_path)
client_id = secrets["spotify"]["client_id"]
client_secret = secrets["spotify"]["client_secret"]
redirect_uri = secrets["spotify"]["redirect_uri"]

print("=========================================================")
print("Meminta otorisasi Spotify untuk fitur Live Pulse...")
print("Silakan ikuti instruksi di bawah ini:")
print("1. Halaman web browser akan otomatis terbuka (jika tidak, klik link yang muncul).")
print("2. Login ke Spotify dan izinkan akses aplikasi.")
print("3. Anda akan diarahkan ke URL error 'http://127.0.0.1:8080/?code=...'.")
print("4. COPY seluruh URL tersebut dan PASTE ke terminal ini, lalu tekan Enter.")
print("=========================================================")

auth_manager = SpotifyOAuth(
    client_id=client_id, 
    client_secret=client_secret, 
    redirect_uri=redirect_uri, 
    scope='user-read-recently-played user-read-currently-playing user-read-playback-state',
    cache_path=".cache",
    open_browser=True
)

sp = spotipy.Spotify(auth_manager=auth_manager)
sp.current_user_playing_track()
print("\n[+] Berhasil! Token baru dengan scope lengkap telah tersimpan.")
print("[+] Anda bisa menjalankan kembali server backend.")
