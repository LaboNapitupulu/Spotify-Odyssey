import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re
import time


# 1. KONFIGURASI TEMA & CSS
st.set_page_config(page_title="Spotify Odyssey", page_icon="🎧", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #0b0f19; }
    ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #1DB954; }

    .column-wrapper { max-height: 520px; overflow-y: auto; overflow-x: hidden; padding-right: 8px; margin-top: 10px; }
    .column-wrapper::-webkit-scrollbar { width: 5px; }
    .column-wrapper::-webkit-scrollbar-track { background: #0f172a; }
    .column-wrapper::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
    .column-wrapper::-webkit-scrollbar-thumb:hover { background: #1DB954; }

    @keyframes fadeInUp { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
    .list-card { display: flex; align-items: center; background-color: #0f172a; padding: 10px 15px; margin-bottom: 8px; border-radius: 10px; border: 1px solid #1e293b; height: 85px; box-sizing: border-box; transition: all 0.2s ease; animation: fadeInUp 0.4s both; }
    .list-card:hover { transform: translateX(5px); background-color: #1e293b; border-color: #1DB954; }
    .list-rank { font-size: 16px; font-weight: 900; color: #475569; width: 35px; min-width: 35px; text-align: center; margin-right: 10px; }
    .list-card:hover .list-rank { color: #1DB954; }
    .list-details { flex-grow: 1; display: flex; flex-direction: column; justify-content: center; overflow: hidden; white-space: nowrap; margin-right: 10px;}
    .list-title { font-size: 14px; font-weight: 800; color: #f8fafc; margin: 0 0 2px 0; text-overflow: ellipsis; overflow: hidden;}
    .list-subtitle { font-size: 12px; color: #94a3b8; margin: 0; text-overflow: ellipsis; overflow: hidden;}
    .list-stats { color: #1DB954; font-weight: 900; text-align: right; min-width: 70px; font-size: 13px; }

    .section-header { font-size: 24px; font-weight: 900; color: #fff; margin-top: 40px; margin-bottom: 20px; border-left: 5px solid #1DB954; padding-left: 15px;}
    
    div[data-testid="stMetricValue"] { color: #fff; font-weight: 900; }
    div[data-testid="stMetricLabel"] { color: #94a3b8; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# 2. INISIALISASI API & PENYELUNDUPAN CLOUD
if "cache" in st.secrets["spotify"]:
    with open(".cache", "w") as f:
        f.write(st.secrets["spotify"]["cache"])

@st.cache_resource
def get_spotify_client():
    client_id = st.secrets["spotify"]["client_id"]
    client_secret = st.secrets["spotify"]["client_secret"]
    redirect_uri = st.secrets["spotify"]["redirect_uri"]
    
    auth_manager = SpotifyOAuth(
        client_id=client_id, client_secret=client_secret, 
        redirect_uri=redirect_uri, 
        scope='user-read-recently-played user-read-currently-playing user-read-playback-state'
    )
    return spotipy.Spotify(auth_manager=auth_manager), auth_manager

sp, sp_auth = get_spotify_client()

token_info = sp_auth.get_cached_token()
if token_info:
    ACCESS_TOKEN = token_info['access_token']
else:
    ACCESS_TOKEN = ""
    st.error("Failed to retrieve Spotify access token. Please check your credentials and re-run the app. ")

# 3. FUNGSI DATA & HELPER GRAFIK
def clean_query(text):
    text = str(text)
    text = re.sub(r'\(.*?\)', '', text) 
    text = text.split('feat')[0].split('ft.')[0].strip() 
    return " ".join(text.split())

@st.cache_data(ttl=86400, show_spinner=False, max_entries=5000)
def fetch_spotify_artwork(name, search_type='artist', artist_name=None):
    try:
        name_clean = clean_query(name)
        if search_type == 'artist':
            q_str = f'artist:"{name_clean}"'
        elif search_type == 'album' and artist_name:
            q_str = f'album:"{name_clean}" artist:"{clean_query(artist_name)}"'
        elif search_type == 'track' and artist_name:
            q_str = f'track:"{name_clean}" artist:"{clean_query(artist_name)}"'
        else:
            q_str = name_clean
            
        res = sp.search(q=q_str, type=search_type, limit=1)
        items = res[search_type + 's']['items']
        if items:
            imgs = items[0].get('album', {}).get('images', []) if search_type == 'track' else items[0].get('images', [])
            if imgs: return imgs[0]['url']
    except: pass
    return ""

def style_plotly_fig(fig):
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#94a3b8',
        margin=dict(l=10, r=10, t=40, b=20), hovermode="x unified",
        title_font=dict(size=18, color='#f8fafc', family='Inter')
    )
    fig.update_xaxes(showgrid=False, zeroline=False, title="")
    fig.update_yaxes(showgrid=True, gridcolor='#1e293b', zeroline=False, title="")
    return fig

def create_listening_clock(data, value_col, title):
    fig = px.bar_polar(data, r=value_col, theta='angle', template="plotly_dark", color_discrete_sequence=['#1DB954'])
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color='#f8fafc', family='Inter'), x=0.5),
        polar=dict(
            radialaxis=dict(visible=False), # Menyembunyikan garis jaring agar bersih
            angularaxis=dict(
                tickmode='array',
                tickvals=[0, 90, 180, 270],
                ticktext=['0', '6', '12', '18'], # Indikator Jam
                direction="clockwise",
                rotation=90, # Angka 0 diletakkan tepat di arah jam 12 atas
                gridcolor='#1e293b', linecolor='#1e293b'
            ),
            bgcolor='rgba(0,0,0,0)'
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=50, b=20, l=20, r=20),
        hoverlabel=dict(bgcolor="#1e293b", font_size=14, font_family="Inter")
    )
    # Mempercantik hover text
    fig.update_traces(hovertemplate="<b>Hour %{customdata[0]}:00</b><br>" + title + ": %{r:,.0f}<extra></extra>", customdata=data[['hour']])
    return fig

# 4. KONTROL SIDEBAR & FEATURE ENGINEERING
path_csv = os.path.join("data_processed", "spotify_clean_ready.csv")
try:
    df_history = pd.read_csv(path_csv)
    df_history['timestamp'] = pd.to_datetime(df_history['timestamp'], format='mixed')
    df_history['date'] = df_history['timestamp'].dt.date
    df_history['day_of_week'] = df_history['timestamp'].dt.dayofweek
    df_history['month_num'] = df_history['timestamp'].dt.month
    df_history['hour'] = df_history['timestamp'].dt.hour # Ekstrak JAM untuk Listening Clocks
    years = sorted(df_history['year'].unique())
except:
    df_history = pd.DataFrame()
    years = []

st.sidebar.image("https://storage.googleapis.com/pr-newsroom-wp/1/2018/11/Spotify_Logo_RGB_Green.png", width=150)
st.sidebar.markdown("<br>", unsafe_allow_html=True)
st.sidebar.success("⚡ JS Live Engine: Active")
st.sidebar.markdown("---")

if not df_history.empty:
    st.sidebar.markdown("<p style='font-size: 14px; margin-bottom: 5px; color: #94a3b8; font-weight: bold;'>Select Historical Year:</p>", unsafe_allow_html=True)
    if "select_all" not in st.session_state: st.session_state.select_all = True
    for y in years:
        if f"year_{y}" not in st.session_state: st.session_state[f"year_{y}"] = True
    def handle_select_all():
        for y in years: st.session_state[f"year_{y}"] = st.session_state.select_all
    def handle_single_change():
        st.session_state.select_all = all([st.session_state[f"year_{y}"] for y in years])
    st.sidebar.checkbox("All Years", key='select_all', on_change=handle_select_all)
    selected_years = []
    cols_sidebar = st.sidebar.columns(2)
    for i, y in enumerate(years):
        with cols_sidebar[i%2]:
            if st.sidebar.checkbox(str(y), key=f"year_{y}", on_change=handle_single_change): selected_years.append(y)
    top_n = st.sidebar.select_slider("Show Top List:", [10, 20, 50, 100], value=10)
    if selected_years: df_filtered = df_history[df_history['year'].isin(selected_years)]
    else: df_filtered = pd.DataFrame(columns=df_history.columns)
else:
    df_filtered = pd.DataFrame()

# 5. RENDER ANTARMUKA UTAMA

# A. JAVASCRIPT REAL-TIME NOW PLAYING 
html_now_playing = f"""
<!DOCTYPE html>
<html>
<head>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        body {{ margin: 0; padding: 0; font-family: 'Inter', sans-serif; background-color: #0b0f19; overflow: hidden; }}
        .now-playing-bar {{ background: rgba(15, 23, 42, 0.9); border-bottom: 2px solid #1DB954; padding: 15px 30px; border-radius: 0 0 15px 15px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 10px 30px rgba(0,0,0,0.5); height: 90px; box-sizing: border-box; }}
        .np-details {{ display: flex; align-items: center; gap: 20px; }}
        .np-text h4 {{ margin: 0; color: #fff; font-size: 18px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 450px;}}
        .np-text p {{ margin: 0; color: #1DB954; font-weight: bold; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 450px;}}
        .live-dot {{ height: 10px; width: 10px; background-color: #1DB954; border-radius: 50%; display: inline-block; animation: blink 1s infinite; margin-right: 10px;}}
        @keyframes blink {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} 100% {{ opacity: 1; }} }}
        .fade-in {{ animation: fadeIn 0.4s ease-in-out; }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    </style>
</head>
<body>
    <div id="np-container"></div>
    <script>
        const token = "{ACCESS_TOKEN}"; const container = document.getElementById('np-container'); let currentSongId = "";
        async function fetchNowPlaying() {{
            try {{
                const res = await fetch('https://api.spotify.com/v1/me/player/currently-playing', {{ headers: {{ 'Authorization': 'Bearer ' + token }} }});
                if (res.status === 200) {{
                    const data = await res.json();
                    if (data.is_playing && data.item) {{
                        if (currentSongId !== data.item.id) {{
                            currentSongId = data.item.id;
                            container.innerHTML = `<div class="now-playing-bar fade-in"><div class="np-details"><img src="${{data.item.album.images[0].url}}" style="width: 60px; height: 60px; min-width: 60px; border-radius: 8px; box-shadow: 0 0 15px #1DB954; object-fit: cover;"><div class="np-text"><p><span class="live-dot"></span>CURRENTLY PLAYING</p><h4>${{data.item.name}}</h4><p style="color:#94a3b8">${{data.item.artists[0].name}}</p></div></div><div style="color:#1DB954; font-weight:bold; font-size:24px;">🎵</div></div>`;
                        }} return;
                    }}
                }}
                if (currentSongId !== "sleep") {{
                    currentSongId = "sleep";
                    container.innerHTML = `<div class="now-playing-bar fade-in" style="border-bottom: 2px solid #334155;"><div class="np-details"><div style="width: 60px; height: 60px; border-radius: 8px; background-color: #1e293b; display: flex; align-items: center; justify-content: center; font-size: 20px;">💤</div><div class="np-text"><p style="color:#475569">STATUS LIVE</p><h4 style="color:#64748b">Tidur...</h4><p style="color:#475569">Tidak ada lagu yang sedang diputar.</p></div></div></div>`;
                }}
            }} catch(e) {{}}
        }}
        fetchNowPlaying(); setInterval(fetchNowPlaying, 10000); 
    </script>
</body>
</html>
"""
components.html(html_now_playing, height=110)

if not df_filtered.empty:
    
    # B. BARIS KPI METRICS 
    total_days = (df_filtered['date'].max() - df_filtered['date'].min()).days + 1
    if total_days <= 0: total_days = 1
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Airtime", f"{df_filtered['duration_min'].sum()/60:,.0f} hours")
    c2.metric("Total Tracks", f"{df_filtered['track_name'].nunique():,}")
    c3.metric("Total Artists", f"{df_filtered['artist_name'].nunique():,}")
    c4.metric("Avg Streams/Day", f"{len(df_filtered) / total_days:,.0f}")
    c5.metric("Avg Minutes/Day", f"{df_filtered['duration_min'].sum() / total_days:,.0f}")

    # C. LISTENING CLOCKS
    st.markdown("<div class='section-header'>⏱️ Listening Clocks</div>", unsafe_allow_html=True)
    
    # Menyiapkan data 24 jam utuh agar lingkaran jam tidak bolong
    hours_df = pd.DataFrame({'hour': range(24)})
    hourly_stats = df_filtered.groupby('hour').agg(streams=('track_name', 'count'), minutes=('duration_min', 'sum')).reset_index()
    hourly_stats = pd.merge(hours_df, hourly_stats, on='hour', how='left').fillna(0)
    
    # Mengkonversi jam (0-23) menjadi sudut derajat (0-345) untuk Plotly Polar (1 jam = 15 derajat)
    hourly_stats['angle'] = hourly_stats['hour'] * 15

    col_clock1, col_clock2 = st.columns(2)
    with col_clock1:
        fig_clock1 = create_listening_clock(hourly_stats, 'streams', 'streams')
        st.plotly_chart(fig_clock1, use_container_width=True, config={'displayModeBar': False})
    with col_clock2:
        fig_clock2 = create_listening_clock(hourly_stats, 'minutes', 'minutes streamed')
        st.plotly_chart(fig_clock2, use_container_width=True, config={'displayModeBar': False})

    # D. TREN MENDENGARKAN (AREA & BAR)
    st.markdown("<div class='section-header'>📈 Time Analytics</div>", unsafe_allow_html=True)
    
    daily_streams = df_filtered.groupby('date').size().reset_index(name='Streams')
    fig_daily = px.area(daily_streams, x='date', y='Streams', title="Daily Intensity (Streams per Day)")
    fig_daily.update_traces(line_color='#1DB954', fillcolor='rgba(29, 185, 84, 0.2)')
    st.plotly_chart(style_plotly_fig(fig_daily), use_container_width=True, config={'displayModeBar': False})

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        dow_streams = df_filtered.groupby('day_of_week').size().reset_index(name='Streams').sort_values('day_of_week')
        day_map = {0:'Monday', 1:'Tuesday', 2:'Wednesday', 3:'Thursday', 4:'Friday', 5:'Saturday', 6:'Sunday'}
        dow_streams['Day'] = dow_streams['day_of_week'].map(day_map)
        fig_dow = px.bar(dow_streams, x='Day', y='Streams', title="Distribution by Day")
        fig_dow.update_traces(marker_color='#1DB954')
        st.plotly_chart(style_plotly_fig(fig_dow), use_container_width=True, config={'displayModeBar': False})
    with col_chart2:
        month_streams = df_filtered.groupby('month_num').size().reset_index(name='Streams').sort_values('month_num')
        month_map = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}
        month_streams['Month'] = month_streams['month_num'].map(month_map)
        fig_month = px.bar(month_streams, x='Month', y='Streams', title="Distribution by Month")
        fig_month.update_traces(marker_color='#1DB954')
        st.plotly_chart(style_plotly_fig(fig_month), use_container_width=True, config={'displayModeBar': False})

    # E. HALL OF FAME 
    st.markdown("<div class='section-header'>🏆 Hall of Fame (Historical Data)</div>", unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns(3)

    def get_card_html(idx, title, subtitle, jam, img, is_artist=False):
        anim_delay = min(idx * 0.02, 1.0)
        radius = "50%" if is_artist else "6px"
        img_style = f"width: 55px; height: 55px; min-width: 55px; border-radius: {radius}; object-fit: cover; margin-right: 15px; background-color: #1e293b;"
        subtitle_html = f'<p class="list-subtitle" title="{subtitle}">{subtitle}</p>' if subtitle else ""
        return f'<div class="list-card" style="animation-delay: {anim_delay}s;"><div class="list-rank">#{idx+1}</div><img src="{img}" style="{img_style}"><div class="list-details"><p class="list-title" title="{title}">{title}</p>{subtitle_html}</div><div class="list-stats">{jam:,.1f}h</div></div>'

    with col_a:
        st.markdown("#### Top Artists")
        with st.spinner(f"⏳ Preparing Top {top_n} Artists..."):
            top_artists = df_filtered.groupby('artist_name')['duration_min'].sum().nlargest(top_n).reset_index()
            html_artists = "<div class='column-wrapper'>"
            for idx, row in top_artists.iterrows():
                img = fetch_spotify_artwork(row['artist_name'], 'artist')
                if not img: img = "https://cdn-icons-png.flaticon.com/512/149/149071.png"
                html_artists += get_card_html(idx, row['artist_name'], None, row['duration_min']/60, img, True)
            html_artists += "</div>"
        st.markdown(html_artists, unsafe_allow_html=True)

    with col_b:
        st.markdown("#### Top Albums")
        with st.spinner(f"⏳ Preparing Top {top_n} Albums..."):
            top_albums = df_filtered.groupby(['album_name', 'artist_name'])['duration_min'].sum().nlargest(top_n).reset_index()
            html_albums = "<div class='column-wrapper'>"
            for idx, row in top_albums.iterrows():
                img = fetch_spotify_artwork(row['album_name'], 'album', row['artist_name'])
                if not img: img = "https://cdn-icons-png.flaticon.com/512/33/33714.png"
                html_albums += get_card_html(idx, row['album_name'], "Album", row['duration_min']/60, img)
            html_albums += "</div>"
        st.markdown(html_albums, unsafe_allow_html=True)

    with col_c:
        st.markdown("#### Top Songs")
        with st.spinner(f"⏳ Preparing Top {top_n} Songs..."):
            top_songs = df_filtered.groupby(['track_name', 'artist_name'])['duration_min'].sum().nlargest(top_n).reset_index()
            html_songs = "<div class='column-wrapper'>"
            for idx, row in top_songs.iterrows():
                img = fetch_spotify_artwork(row['track_name'], 'track', row['artist_name'])
                if not img: img = "https://cdn-icons-png.flaticon.com/512/33/33714.png"
                html_songs += get_card_html(idx, row['track_name'], row['artist_name'], row['duration_min']/60, img)
            html_songs += "</div>"
        st.markdown(html_songs, unsafe_allow_html=True)
else:
    st.info("⚠️ Please check at least one year in the sidebar to see the Hall of Fame & Charts.")

# F. LIVE RECENTLY PLAYED
st.markdown("<div class='section-header'>📡 Live Pulse: Recently Played</div>", unsafe_allow_html=True)

html_recent_played = f"""
<!DOCTYPE html>
<html>
<head>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body {{ background-color: #0b0f19; margin: 0; padding: 0; font-family: 'Inter', sans-serif; color: #fff; }}
        .table-container {{ max-height: 550px; overflow-y: auto; border-radius: 8px; background-color: #0f172a; border: 1px solid #1e293b; }}
        .table-container::-webkit-scrollbar {{ width: 8px; }}
        .table-container::-webkit-scrollbar-track {{ background: #0b0f19; }}
        .table-container::-webkit-scrollbar-thumb {{ background: #1e293b; border-radius: 4px; }}
        .table-container::-webkit-scrollbar-thumb:hover {{ background: #1DB954; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 15px; text-align: left; font-size: 14px; border-bottom: 1px solid #1e293b;}}
        th {{ background-color: #1e293b; color: #1DB954; font-weight: 800; text-transform: uppercase; font-size: 12px; letter-spacing: 1px; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 5px rgba(0,0,0,0.2);}}
        tr:hover {{ background-color: #162032; }}
        .cover-img {{ width: 45px; height: 45px; border-radius: 4px; object-fit: cover; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }}
        .time-col {{ color: #94a3b8; font-weight: bold; font-size: 13px; }}
        .track-title {{ font-weight: 800; color: #f8fafc; font-size: 15px; }}
        .artist-name {{ color: #94a3b8; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="table-container">
        <table id="recent-table">
            <thead>
                <tr>
                    <th style="width: 65px;">Cover</th>
                    <th style="width: 140px;">Time Played</th>
                    <th>Track Title</th>
                    <th>Artist</th>
                </tr>
            </thead>
            <tbody id="recent-tbody">
                <tr><td colspan="4" style="text-align:center; color:#475569; padding: 30px;">📡 Loading last 50 played tracks...</td></tr>
            </tbody>
        </table>
    </div>
    <script>
        const token = "{ACCESS_TOKEN}"; const tbody = document.getElementById('recent-tbody'); let lastFirstTimestamp = "";
        async function fetchRecentPlayed() {{
            try {{
                const res = await fetch('https://api.spotify.com/v1/me/player/recently-played?limit=50', {{ headers: {{ 'Authorization': 'Bearer ' + token }} }});
                if (res.status === 200) {{
                    const data = await res.json();
                    if (data.items && data.items.length > 0) {{
                        const latestTimestamp = data.items[0].played_at;
                        if (lastFirstTimestamp !== latestTimestamp) {{
                            lastFirstTimestamp = latestTimestamp;
                            let htmlRows = "";
                            data.items.forEach(item => {{
                                const track = item.track;
                                const cover = track.album.images[2] ? track.album.images[2].url : "https://cdn-icons-png.flaticon.com/512/33/33714.png";
                                const playedDate = new Date(item.played_at);
                                const options = {{ day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }};
                                let timeStr = playedDate.toLocaleString('id-ID', options).replace(/\\./g, ':').replace(',', ' |');
                                htmlRows += `<tr><td><img src="${{cover}}" class="cover-img"></td><td class="time-col">${{timeStr}}</td><td class="track-title">${{track.name}}</td><td class="artist-name">${{track.artists[0].name}}</td></tr>`;
                            }});
                            tbody.innerHTML = htmlRows;
                        }}
                    }}
                }}
            }} catch(e) {{}}
        }}
        fetchRecentPlayed(); setInterval(fetchRecentPlayed, 30000);
    </script>
</body>
</html>
"""
components.html(html_recent_played, height=570)
