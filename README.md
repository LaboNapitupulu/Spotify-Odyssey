# 🎧 Spotify Odyssey: Interactive Data Science Dashboard

[![Streamlit App](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://share.streamlit.io/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

> 🎥 **[Pratinjau Dasbor](https://spotify-odyssey.streamlit.app/):**
> 
> ![Demo Spotify Odyssey](https://media.discordapp.net/attachments/756442876170207263/1506467444376604743/image.png?ex=6a0e5ea3&is=6a0d0d23&hm=85902b0f0dc5dcffa3a5fb8debb85d6ebfd20188654efcebe811998ae41a35b8&=&format=webp&quality=lossless&width=1866&height=834)

**Spotify Odyssey** merupakan platform dasbor analitik interaktif berbasis web yang memadukan arsitektur pemrosesan data historis berskala besar menggunakan **Python (Pandas & Plotly)** dengan integrasi **JavaScript Asinkron** di sisi klien (*client-side*) untuk pelacakan aktivitas pemutaran musik secara *real-time*.

Proyek ini dirancang secara khusus sebagai instrumen rekayasa data eksploratif (*Exploratory Data Analysis*) yang menyoroti siklus ETL (*Extract, Transform, Load*) seutuhnya—mulai dari ekstraksi data mentah (JSON) dari server privasi Spotify, pembersihan data (*Data Wrangling*), hingga penyajian visualisasi tingkat lanjut.

---

## ✨ Fitur Utama

* **🗄️ End-to-End Data Pipeline (ETL):** Alur kerja yang terstruktur untuk memproses ratusan ribu baris data JSON mentah (*Extended Streaming History*) dari Spotify menjadi format CSV yang teroptimasi untuk analisis analitik.
* **📡 Pemantauan Aktivitas *Real-Time* (Live Pulse Bar):** Implementasi modul JavaScript murni yang beroperasi secara asinkron di latar belakang. Modul ini melakukan *polling* ke Spotify API setiap 10 detik untuk mendeteksi lagu yang sedang diputar tanpa memicu siklus *re-render* pada *framework* Streamlit.
* **🕰️ Riwayat Putar Dinamis (Live History):** Menampilkan log 50 lagu terakhir yang telah selesai diputar secara dinamis, dilengkapi dengan informasi metadata (sampul album, nama artis) serta konversi zona waktu lokal (`Asia/Jakarta`).
* **⏱️ Visualisasi Waktu Mendengarkan (Polar Clocks):** Implementasi *Advanced Polar Bar Chart* untuk memetakan distribusi perilaku mendengarkan musik dalam siklus 24 jam secara melingkar (Frekuensi Putar vs Durasi Putar).
* **📈 Analitik Tren Komprehensif:** Modul visualisasi data interaktif yang mencakup *Time-Series Area Chart* untuk melacak intensitas pemutaran harian, serta histogram untuk distribusi aktivitas berdasarkan hari dan bulan.
* **🏆 Kontainer *Hall of Fame* Independen:** Sistem pemeringkatan (Top Artis, Top Album, dan Top Lagu) yang diimplementasikan dengan *CSS Custom Scrollbar*. Hal ini memungkinkan pemuatan hingga 100 peringkat teratas tanpa mendisrupsi tata letak antarmuka utama.
* **🔒 Sistem Temu Kembali Gambar Teroptimasi:** Terintegrasi dengan *Advanced Search Query Filters* (`artist:"NAME"`) dan sistem *Cache Per-Item Injection* untuk memastikan akurasi dan efisiensi pengunduhan aset visual (Cover Album) secara otomatis.

---

## 🛠️ Arsitektur Proyek dan Teknologi

Struktur direktori proyek dirancang berdasarkan standar industri Data Science:

```text
ProjectSpotify/
│
├── .streamlit/
│   └── secrets.toml                  # Kredensial API lokal (Diabaikan oleh git)
│
├── data_raw/                         # RAW DATA: Hasil unduhan dari Spotify Privacy
│   ├── ReadMeFirst_ExtendedStreamingHistory.pdf
│   ├── Streaming_History_Audio_2018.json
│   ├── Streaming_History_Audio_2020.json
│   └── ... (File riwayat JSON lainnya)
│
├── notebooks/
│   └── 01_data_cleaning.ipynb        # Skrip Python untuk pembersihan JSON ke CSV
│
├── data_processed/
│   └── spotify_clean_ready.csv       # Data historis bersih siap pakai (Hasil ETL)
│
├── requirements.txt                  # Dependensi pustaka lingkungan produksi
├── .gitignore                        # Konfigurasi isolasi keamanan repositori
├── spotify_app.py                    # Berkas utama aplikasi dasbor Streamlit
└── spotify_collector.py              # Skrip pendukung automasi koleksi data

```

* **Data Processing & ETL:** Python, Pandas, Jupyter Notebook.
* **Front-End Framework:** Streamlit, HTML5, CSS3 Custom Variables.
* **Reactive & Graphics Engine:** Vanilla JavaScript, Web Fetch API, Plotly Express, Plotly Graph Objects.
* **Authentication & Web API:** Spotipy (OAuth 2.0 Client Credentials), Spotify Web API.

---

## 🚀 Panduan Replikasi dan Instalasi

Ikuti langkah-langkah sistematis berikut untuk melakukan ekstraksi data pribadi Anda dan meluncurkan dasbor ini secara mandiri.

### Tahap 1: Meminta Data Historis Mentah (Spotify Privacy)

Aplikasi ini menggunakan data riwayat mendengarkan seumur hidup Anda.

1. Kunjungi halaman [Privasi Akun Spotify](https://www.spotify.com/id-id/account/privacy/) Anda di *browser*.
2. Gulir ke bagian **Download your data**.
3. Minta (*Request*) paket **Extended streaming history**. Catatan: Spotify membutuhkan waktu beberapa hari untuk mengumpulkan data ini sebelum mengirimkannya ke email Anda.
4. Setelah email diterima, unduh dan ekstrak file `.zip` tersebut.
5. Pindahkan seluruh file berformat `.json` (misal: `Streaming_History_Audio_2020.json`, dst.) ke dalam folder `data_raw/` di repositori proyek Anda.

### Tahap 2: Pemrosesan Data (Data Wrangling)

1. Buka folder `notebooks/` dan jalankan file `01_data_cleaning.ipynb` menggunakan Jupyter Notebook atau VS Code.
2. Jalankan seluruh sel kode (*Run All*) di dalam notebook tersebut. Skrip ini akan otomatis membaca seluruh file JSON di folder `data_raw/`, membersihkan kolom yang tidak perlu, memfilter podcast, mengkonversi durasi milidetik ke menit, dan mengekspor hasilnya menjadi satu file utuh.
3. Pastikan file keluaran `spotify_clean_ready.csv` telah berhasil terbuat di dalam folder `data_processed/`.

### Tahap 3: Persiapan Kredensial API (Spotify Developer)

Aplikasi memerlukan otorisasi akses API untuk melacak lagu secara *real-time* dan mengunduh gambar:

1. Akses **[Spotify Developer Dashboard](https://developer.spotify.com/dashboard)** dan masuk menggunakan kredensial akun Spotify Anda.
2. Klik tombol **Create App** dan isi informasi aplikasi.
3. Pada bagian **Redirect URIs**, daftarkan alamat lokal berikut secara presisi:
```text
[http://127.0.0.1:8080](http://127.0.0.1:8080)

```


4. Simpan konfigurasi. Akses menu **Settings** pada aplikasi tersebut, lalu salin **Client ID** dan **Client Secret**.

### Tahap 4: Pengaturan Lingkungan Lokal

1. Lakukan kloning repositori ini ke komputer Anda:
```bash
git clone [https://github.com/USERNAME_ANDA/spotify-odyssey.git](https://github.com/USERNAME_ANDA/spotify-odyssey.git)
cd spotify-odyssey

```


2. Buat direktori tersembunyi bernama `.streamlit` di dalam *root* proyek. Buat berkas konfigurasi baru bernama `secrets.toml` di dalamnya.
3. Definisikan variabel kredensial Anda:
```toml
[spotify]
client_id = "ISI_DENGAN_CLIENT_ID_ANDA"
client_secret = "ISI_DENGAN_CLIENT_SECRET_ANDA"
redirect_uri = "[http://127.0.0.1:8080](http://127.0.0.1:8080)"

```



### Tahap 5: Menjalankan Aplikasi

1. Lakukan instalasi seluruh dependensi pustaka:
```bash
pip install -r requirements.txt

```


2. Inisialisasi server lokal Streamlit:
```bash
streamlit run spotify_app.py

```


3. Pada eksekusi perdana, *browser* akan membuka halaman otorisasi Spotify secara otomatis. Berikan izin (*Agree*) untuk melanjutkan. Dasbor kini dapat diakses melalui alamat `http://localhost:8501`.

### Tahap 6: Penerapan (*Deployment*) ke Streamlit Community Cloud

1. Setelah Anda berhasil masuk di lingkungan lokal, buka berkas tersembunyi `.cache` di direktori proyek dan salin seluruh teks JSON di dalamnya.
2. Unggah (push) repositori lokal Anda ke GitHub. **Sangat Penting:** Pastikan direktori `.streamlit/`, `.venv`, folder `data_raw/`, dan berkas `.cache` TIDAK diikutsertakan demi privasi data dan keamanan kredensial.
3. Akses **[Streamlit Community Cloud](https://share.streamlit.io/)** dan buat aplikasi baru (Deploy) dengan menghubungkan repositori GitHub Anda.
4. Sebelum mengeksekusi *deployment*, akses menu **Advanced Settings > Secrets** di Streamlit Cloud.
5. Tambahkan konfigurasi kredensial Anda beserta injeksi kunci *cache* (gunakan tanda kutip tunggal `'`):
```toml
[spotify]
client_id = "CLIENT_ID_ANDA"
client_secret = "CLIENT_SECRET_ANDA"
redirect_uri = "[http://127.0.0.1:8080](http://127.0.0.1:8080)"
cache = 'TEMPEL_KESELURUHAN_TEKS_DARI_BERKAS_CACHE_LOKAL_ANDA_DISINI'

```


6. Simpan pengaturan dan jalankan **Deploy!**. Dasbor analitik seumur hidup Anda kini mengudara dan siap memukau dunia.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah **MIT License**. Anda diizinkan untuk menggunakan, menyalin, memodifikasi, dan/atau mendistribusikan perangkat lunak ini secara bebas.
