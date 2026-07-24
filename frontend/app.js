// Global State & Config
const API_BASE = "http://localhost:8000/api";
let selectedYears = [];
let allAvailableYears = [];
let topN = 10;
let selectedMonth = null;
let charts = {};

// Theme config for Chart.js
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Inter', sans-serif";

const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false }
    },
    scales: {
        x: { grid: { display: false }, border: { display: false } },
        y: { grid: { color: '#1e293b' }, border: { display: false } }
    }
};

// Formatting utilities
const fmt = {
    number: (num) => new Intl.NumberFormat('en-US').format(num || 0),
    time: (dateStr) => {
        const d = new Date(dateStr);
        return d.toLocaleString('id-ID', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).replace(/\./g, ':').replace(',', ' |');
    }
};

// Initialize Dashboard
async function init() {
    await fetchYears();
    setupEventListeners();
    await updateDashboard();
    
    // Live Pulse
    fetchNowPlaying();
    fetchRecentlyPlayed();
    setInterval(fetchNowPlaying, 10000);
    setInterval(fetchRecentlyPlayed, 30000);
}

// Data Fetchers
async function fetchYears() {
    try {
        const res = await fetch(`${API_BASE}/stats/years`);
        const years = await res.json();
        const container = document.getElementById('year-filters');
        
        allAvailableYears = years;
        // Default to "All Years" selected
        selectedYears = [...years];
        
        let html = `<div class="filter-chip-container">
            <div class="filter-chip active" data-value="all">All Years</div>`;
        
        years.forEach(y => {
            html += `<div class="filter-chip" data-value="${y}">${y}</div>`;
        });
        
        html += `</div>`;
        container.innerHTML = html;
        
    } catch(e) { console.error("Failed to fetch years", e); }
}

// Toast Notification System
function showToast(message) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = 'custom-toast';
    toast.innerText = message;
    
    container.appendChild(toast);
    
    // Remove toast after animation finishes (3s delay + 0.3s slide out)
    setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 3500);
}

async function updateDashboard() {
    const yearsParam = selectedYears.join(',');
    const monthQuery = selectedMonth ? `&month=${selectedMonth}` : '';
    
    // Render Skeletons for Hall of Fame ONLY to show buffer
    const skeletonHTML = Array(Number(topN)).fill('<div class="skeleton skeleton-list-card"></div>').join('');
    document.getElementById('hof-artists').innerHTML = skeletonHTML;
    document.getElementById('hof-albums').innerHTML = skeletonHTML;
    document.getElementById('hof-songs').innerHTML = skeletonHTML;

    // Independent Async Fetches (No Promise.all)
    fetch(`${API_BASE}/stats/kpi?years=${yearsParam}${monthQuery}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('kpi-airtime').innerText = fmt.number(data.airtime_hours) + " hours";
            document.getElementById('kpi-tracks').innerText = fmt.number(data.total_tracks);
            document.getElementById('kpi-artists').innerText = fmt.number(data.total_artists);
            document.getElementById('kpi-avg-streams').innerText = fmt.number(data.avg_streams_per_day);
            document.getElementById('kpi-avg-min').innerText = fmt.number(data.avg_min_per_day);
        })
        .catch(e => console.error(e));

    fetch(`${API_BASE}/stats/trends?years=${yearsParam}${monthQuery}`)
        .then(res => res.json())
        .then(data => renderTrends(data))
        .catch(e => console.error(e));

    fetch(`${API_BASE}/stats/clock?years=${yearsParam}${monthQuery}`)
        .then(res => res.json())
        .then(data => renderClocks(data))
        .catch(e => console.error(e));

    fetch(`${API_BASE}/stats/fame?years=${yearsParam}&top_n=${topN}${monthQuery}`)
        .then(res => res.json())
        .then(data => fetchFameWithArtwork(data))
        .catch(e => console.error(e));
}

// Renderers
function renderTrends(data) {
    // Daily Area Chart
    if (charts.daily) {
        charts.daily.data.labels = data.daily.map(d => d.date);
        charts.daily.data.datasets[0].data = data.daily.map(d => d.streams);
        charts.daily.update();
    } else {
        const ctxDaily = document.getElementById('trend-daily').getContext('2d');
        charts.daily = new Chart(ctxDaily, {
            type: 'line',
            data: {
                labels: data.daily.map(d => d.date),
                datasets: [{
                    label: 'Streams',
                    data: data.daily.map(d => d.streams),
                    borderColor: '#1DB954',
                    backgroundColor: 'rgba(29, 185, 84, 0.2)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: { 
                ...commonOptions, 
                plugins: { 
                    legend: { display: false },
                    title: { display: true, text: 'Daily Intensity (Streams per Day)', color: '#fff', font: { size: 16 } },
                    zoom: {
                        pan: { enabled: true, mode: 'x' },
                        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
                    }
                } 
            }
        });
    }

    // DOW Bar Chart
    if (charts.dow) {
        charts.dow.data.labels = data.dow.map(d => d.day);
        charts.dow.data.datasets[0].data = data.dow.map(d => d.streams);
        charts.dow.update();
    } else {
        const ctxDow = document.getElementById('trend-dow').getContext('2d');
        charts.dow = new Chart(ctxDow, {
            type: 'bar',
            data: {
                labels: data.dow.map(d => d.day),
                datasets: [{ label: 'Streams', data: data.dow.map(d => d.streams), backgroundColor: '#1DB954' }]
            },
            options: { ...commonOptions, plugins: { legend: { display: false }, title: { display: true, text: 'Distribution by Day', color: '#fff', font: { size: 16 } } } }
        });
    }
    
    // Monthly Bar Chart
    const getMonthlyColors = (monthlyData) => {
        return monthlyData.map(d => {
            if (!selectedMonth) return '#1DB954';
            return d.month_id === selectedMonth ? '#1DB954' : '#334155';
        });
    };
    
    if (charts.monthly) {
        charts.monthly.data.labels = data.monthly.map(d => d.month);
        charts.monthly.data.datasets[0].data = data.monthly.map(d => d.streams);
        charts.monthly.data.datasets[0].backgroundColor = getMonthlyColors(data.monthly);
        charts.monthly.options.onClick = (e, elements) => {
            if (elements.length > 0) {
                const clickedMonthId = data.monthly[elements[0].index].month_id;
                selectedMonth = (selectedMonth === clickedMonthId) ? null : clickedMonthId;
                updateDashboard();
            }
        };
        charts.monthly.options.onHover = (e, elements) => {
            e.native.target.style.cursor = elements.length ? 'pointer' : 'default';
        };
        charts.monthly.update();
    } else {
        const ctxMonthly = document.getElementById('trend-monthly').getContext('2d');
        charts.monthly = new Chart(ctxMonthly, {
            type: 'bar',
            data: {
                labels: data.monthly.map(d => d.month),
                datasets: [{ label: 'Streams', data: data.monthly.map(d => d.streams), backgroundColor: getMonthlyColors(data.monthly) }]
            },
            options: { 
                ...commonOptions, 
                plugins: { legend: { display: false }, title: { display: true, text: 'Distribution by Month', color: '#fff', font: { size: 16 } } },
                onClick: (e, elements) => {
                    if (elements.length > 0) {
                        const clickedMonthId = data.monthly[elements[0].index].month_id;
                        selectedMonth = (selectedMonth === clickedMonthId) ? null : clickedMonthId;
                        updateDashboard();
                    }
                },
                onHover: (e, elements) => {
                    e.native.target.style.cursor = elements.length ? 'pointer' : 'default';
                }
            }
        });
    }
}

function renderClocks(data) {
    // Polar Area charts for listening clock
    const clockOptions = {
        responsive: true, maintainAspectRatio: false,
        scales: {
            r: { 
                grid: { color: '#1e293b' }, angleLines: { color: '#1e293b' },
                ticks: { display: false }
            }
        },
        plugins: { legend: { display: false } }
    };

    if (charts.clockStreams) {
        charts.clockStreams.data.labels = data.map(d => `Hour ${d.hour}:00`);
        charts.clockStreams.data.datasets[0].data = data.map(d => d.streams);
        charts.clockStreams.update();
    } else {
        const ctxStreams = document.getElementById('clock-streams').getContext('2d');
        charts.clockStreams = new Chart(ctxStreams, {
            type: 'polarArea',
            data: {
                labels: data.map(d => `Hour ${d.hour}:00`),
                datasets: [{
                    data: data.map(d => d.streams),
                    backgroundColor: 'rgba(29, 185, 84, 0.7)',
                    borderColor: '#1DB954',
                    borderWidth: 1
                }]
            },
            options: { ...clockOptions, plugins: { legend: { display: false }, title: { display: true, text: 'Streams by Hour', color: '#fff', font: { size: 16 } } } }
        });
    }

    if (charts.clockMins) {
        charts.clockMins.data.labels = data.map(d => `Hour ${d.hour}:00`);
        charts.clockMins.data.datasets[0].data = data.map(d => d.minutes);
        charts.clockMins.update();
    } else {
        const ctxMins = document.getElementById('clock-minutes').getContext('2d');
        charts.clockMins = new Chart(ctxMins, {
            type: 'polarArea',
            data: {
                labels: data.map(d => `Hour ${d.hour}:00`),
                datasets: [{
                    data: data.map(d => d.minutes),
                    backgroundColor: 'rgba(29, 185, 84, 0.7)',
                    borderColor: '#1DB954',
                    borderWidth: 1
                }]
            },
            options: { ...clockOptions, plugins: { legend: { display: false }, title: { display: true, text: 'Minutes Streamed by Hour', color: '#fff', font: { size: 16 } } } }
        });
    }
}

function getCardHTML(idx, type, title, subtitle, value, img, artistName=null) {
    const delay = Math.min(idx * 0.02, 1.0);
    const isArtist = type === 'artist';
    const imgClass = isArtist ? "hof-img artist-img" : "hof-img";
    const subHTML = subtitle ? `<p class="list-subtitle">${subtitle}</p>` : "";
    return `
        <div class="list-card" style="animation-delay: ${delay}s;">
            <div class="list-rank">#${idx+1}</div>
            <img src="${img || 'https://cdn-icons-png.flaticon.com/512/33/33714.png'}" class="${imgClass}" data-name="${title.replace(/"/g, '&quot;')}" data-type="${type}" data-artist="${artistName ? artistName.replace(/"/g, '&quot;') : ''}">
            <div class="list-details">
                <p class="list-title">${title}</p>
                ${subHTML}
            </div>
            <div class="list-stats">${fmt.number(value/60)}h</div>
        </div>
    `;
}

function renderHallOfFame(data) {
    let artHTML = "";
    data.artists.forEach((r, i) => artHTML += getCardHTML(i, 'artist', r.artist_name, null, r.minutes, r.image_url));
    document.getElementById('hof-artists').innerHTML = artHTML;

    let albHTML = "";
    data.albums.forEach((r, i) => albHTML += getCardHTML(i, 'album', r.album_name, "Album", r.minutes, r.image_url, r.artist_name));
    document.getElementById('hof-albums').innerHTML = albHTML;

    let sngHTML = "";
    data.songs.forEach((r, i) => sngHTML += getCardHTML(i, 'track', r.track_name, r.artist_name, r.minutes, r.image_url, r.artist_name));
    document.getElementById('hof-songs').innerHTML = sngHTML;
}

async function fetchFameWithArtwork(data) {
    // Sequentially fetch artworks so we don't kill the backend, 
    // while keeping the skeleton loader visible until everything is ready.
    const items = [
        ...data.artists.map(a => ({ obj: a, type: 'artist', name: a.artist_name, artist: '' })),
        ...data.albums.map(a => ({ obj: a, type: 'album', name: a.album_name, artist: a.artist_name })),
        ...data.songs.map(a => ({ obj: a, type: 'track', name: a.track_name, artist: a.artist_name }))
    ];

    for (const item of items) {
        if (!item.obj.image_url) {
            const url = `${API_BASE}/spotify/artwork?name=${encodeURIComponent(item.name)}&type=${encodeURIComponent(item.type)}&artist_name=${encodeURIComponent(item.artist)}`;
            try {
                const res = await fetch(url);
                const json = await res.json();
                if (json.image_url) item.obj.image_url = json.image_url;
                await new Promise(r => setTimeout(r, 50));
            } catch(e) { }
        }
    }
    
    // Now render the HTML all at once
    renderHallOfFame(data);
}

// Live Pulse fetchers
let currentSongId = "";
async function fetchNowPlaying() {
    try {
        const res = await fetch(`${API_BASE}/spotify/now-playing`);
        if(res.ok) {
            const data = await res.json();
            const container = document.getElementById('np-container');
            if (data.is_playing) {
                if (currentSongId !== data.track_id) {
                    currentSongId = data.track_id;
                    container.innerHTML = `
                        <div class="now-playing-bar fade-in">
                            <div class="np-details">
                                <img src="${data.image_url}" style="width: 60px; height: 60px; border-radius: 8px; box-shadow: 0 0 15px #1DB954; object-fit: cover;">
                                <div class="np-text">
                                    <p><span class="live-dot"></span>CURRENTLY PLAYING</p>
                                    <h4>${data.track_name}</h4>
                                    <p style="color:#94a3b8; font-weight:normal;">${data.artist_name}</p>
                                </div>
                            </div>
                            <div style="color:#1DB954; font-size:24px;">🎵</div>
                        </div>`;
                }
            } else {
                if (currentSongId !== "sleep") {
                    currentSongId = "sleep";
                    container.innerHTML = `
                        <div class="now-playing-bar fade-in" style="border-top: 2px solid #334155; background: rgba(15,23,42,0.95);">
                            <div class="np-details">
                                <div style="width: 60px; height: 60px; border-radius: 8px; background-color: #1e293b; display: flex; align-items: center; justify-content: center; font-size: 20px;">💤</div>
                                <div class="np-text">
                                    <p style="color:#475569">STATUS LIVE</p>
                                    <h4 style="color:#64748b">Tidur...</h4>
                                    <p style="color:#475569; font-weight:normal;">Tidak ada lagu yang sedang diputar.</p>
                                </div>
                            </div>
                        </div>`;
                }
            }
        }
    } catch(e) {}
}

let lastTimestamp = "";
async function fetchRecentlyPlayed() {
    try {
        const res = await fetch(`${API_BASE}/spotify/recently-played`);
        if(res.ok) {
            const data = await res.json();
            if(data.items && data.items.length > 0) {
                if(lastTimestamp !== data.items[0].played_at) {
                    lastTimestamp = data.items[0].played_at;
                    let html = "";
                    data.items.forEach(t => {
                        html += `<tr>
                            <td><img src="${t.image_url || 'https://cdn-icons-png.flaticon.com/512/33/33714.png'}" class="cover-img"></td>
                            <td class="time-col">${fmt.time(t.played_at)}</td>
                            <td class="track-title">${t.track_name}</td>
                            <td class="artist-name">${t.artist_name}</td>
                        </tr>`;
                    });
                    document.getElementById('recent-tbody').innerHTML = html;
                }
            }
        }
    } catch(e) {}
}

// Event Listeners
function setupEventListeners() {
    // Top N Slider
    const slider = document.getElementById('top-n-slider');
    slider.addEventListener('change', (e) => {
        topN = e.target.value;
        document.getElementById('top-n-value').innerText = topN;
        updateDashboard(); // Re-fetch all or just fame
    });
    
    // Filter Chips (Multi-Select & Single-Select Mode)
    document.addEventListener('click', (e) => {
        if(e.target.classList.contains('filter-chip')) {
            const clickedVal = e.target.getAttribute('data-value');
            const isMultiMode = document.getElementById('multi-select-toggle').checked;
            
            if (clickedVal === 'all') {
                // If "All Years" clicked, deselect others
                document.querySelectorAll('.filter-chip').forEach(chip => chip.classList.remove('active'));
                e.target.classList.add('active');
                selectedYears = [...allAvailableYears];
            } else {
                const allChip = document.querySelector('.filter-chip[data-value="all"]');
                
                if (!isMultiMode) {
                    // SINGLE-SELECT MODE
                    document.querySelectorAll('.filter-chip').forEach(chip => chip.classList.remove('active'));
                    e.target.classList.add('active');
                    selectedYears = [clickedVal];
                } else {
                    // MULTI-SELECT MODE
                    if (allChip && allChip.classList.contains('active')) {
                        allChip.classList.remove('active');
                        e.target.classList.add('active');
                        selectedYears = [clickedVal];
                    } else {
                        // Toggle this specific year
                        e.target.classList.toggle('active');
                        
                        // Rebuild selectedYears array
                        selectedYears = [];
                        document.querySelectorAll('.filter-chip.active').forEach(chip => {
                            const val = chip.getAttribute('data-value');
                            if (val !== 'all') selectedYears.push(val);
                        });
                        
                        // Prevent empty selection
                        if (selectedYears.length === 0) {
                            showToast("Peringatan: Anda wajib memilih minimal satu tahun!");
                            e.target.classList.add('active'); // Revert toggle
                            selectedYears = [clickedVal];
                        }
                    }
                }
            }
            
            updateDashboard();
        }
    });
}

// Start
init();

// --- LIVE PULSE & RECENTLY PLAYED ---
let currentTrackId = null;
async function fetchLivePulse() {
    try {
        const res = await fetch(`${API_BASE}/spotify/now-playing`);
        if (!res.ok) return;
        const data = await res.json();
        
        const npContainer = document.getElementById('np-container');
        if (data.is_playing) {
            if (currentTrackId !== data.track_id) {
                currentTrackId = data.track_id;
                npContainer.innerHTML = `
                    <div style="position: fixed; bottom: 0; left: 250px; width: calc(100% - 250px); background: #181818; border-top: 1px solid #282828; padding: 15px 30px; display: flex; align-items: center; z-index: 500; box-shadow: 0 -5px 20px rgba(0,0,0,0.5); box-sizing: border-box;">
                        <div class="live-dot"></div>
                        <img src="${data.image_url || 'https://cdn-icons-png.flaticon.com/512/33/33714.png'}" style="width: 60px; height: 60px; border-radius: 5px; margin-right: 20px; object-fit: cover;">
                        <div class="np-text">
                            <h4 style="margin:0; font-size: 16px; color: #fff;">${data.track_name}</h4>
                            <p style="margin:0; color: #b3b3b3; font-size: 14px;">${data.artist_name}</p>
                        </div>
                    </div>
                `;
            }
        } else {
            if (currentTrackId !== null) {
                currentTrackId = null;
                npContainer.innerHTML = '';
            }
        }
    } catch (e) {
        console.error("Live Pulse Error:", e);
    }
}

let lastPlayedAt = null;
async function fetchRecentlyPlayed() {
    try {
        const res = await fetch(`${API_BASE}/spotify/recently-played?limit=10`);
        if (!res.ok) return;
        const data = await res.json();
        
        if (data.items && data.items.length > 0) {
            if (lastPlayedAt !== data.items[0].played_at) {
                lastPlayedAt = data.items[0].played_at;
                const tbody = document.getElementById('recent-tbody');
                let html = '';
                data.items.forEach(t => {
                    const timeStr = new Date(t.played_at).toLocaleString('id-ID', {
                        day: '2-digit', month: 'short', hour: '2-digit', minute:'2-digit'
                    });
                    html += `
                        <tr>
                            <td><img src="${t.image_url || 'https://cdn-icons-png.flaticon.com/512/33/33714.png'}" style="width:40px; height:40px; border-radius:4px; object-fit:cover;"></td>
                            <td style="color:#94a3b8; font-size: 0.9em;">${timeStr}</td>
                            <td style="color:#fff; font-weight:bold;">${t.track_name}</td>
                            <td style="color:#94a3b8">${t.artist_name}</td>
                        </tr>
                    `;
                });
                tbody.innerHTML = html;
            }
        }
    } catch (e) {
        console.error("Recently Played Error:", e);
    }
}

// Initial fetch and set interval for real-time updates (every 10 seconds)
fetchLivePulse();
fetchRecentlyPlayed();
setInterval(() => {
    fetchLivePulse();
    fetchRecentlyPlayed();
}, 10000);
