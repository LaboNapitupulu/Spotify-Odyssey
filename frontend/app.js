// Global State & Config
const API_BASE = "/api";
let selectedYears = [];
let allAvailableYears = [];
let topN = 10;
let selectedMonth = null;
let charts = {};
let isMobileMenuOpen = false;

// Theme config for Chart.js
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Inter', sans-serif";

const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
        x: { grid: { display: false }, border: { display: false } },
        y: { grid: { color: '#1e293b' }, border: { display: false } }
    }
};

// Formatting utilities
const fmt = {
    number: (num) => new Intl.NumberFormat('en-US').format(Math.round(num) || 0),
    time: (dateStr) => {
        const d = new Date(dateStr);
        return d.toLocaleString('id-ID', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
               .replace(/\./g, ':').replace(',', ' |');
    }
};

// Initialize Dashboard
async function init() {
    await fetchYears();
    setupEventListeners();
    await updateDashboard();
    
    // Start live pulse
    fetchNowPlaying();
    fetchRecentlyPlayed();
    setInterval(fetchNowPlaying, 30000);    // 30s — now playing check
    setInterval(fetchRecentlyPlayed, 60000); // 60s — recent played (safe from rate limit)
}

// Data Fetchers
async function fetchYears() {
    try {
        const res = await fetch(`${API_BASE}/stats/years`);
        const years = await res.json();
        const container = document.getElementById('year-filters');
        
        allAvailableYears = years;
        selectedYears = [...years];
        
        let html = `<div class="filter-chip-container">
            <div class="filter-chip active" data-value="all">All Years</div>`;
        years.forEach(y => { html += `<div class="filter-chip" data-value="${y}">${y}</div>`; });
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
    setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 3500);
}

async function updateDashboard() {
    const yearsParam = selectedYears.join(',');
    const monthQuery = selectedMonth ? `&month=${selectedMonth}` : '';
    
    const skeletonHTML = Array(Number(topN)).fill('<div class="skeleton skeleton-list-card"></div>').join('');
    document.getElementById('hof-artists').innerHTML = skeletonHTML;
    document.getElementById('hof-albums').innerHTML = skeletonHTML;
    document.getElementById('hof-songs').innerHTML = skeletonHTML;

    // Mark KPI as loading
    const kpiIds = ['kpi-airtime','kpi-tracks','kpi-artists','kpi-avg-streams','kpi-avg-min'];
    kpiIds.forEach(id => { const el = document.getElementById(id); el.innerText = '\u00a0'; el.classList.add('kpi-loading'); });

    fetch(`${API_BASE}/stats/kpi?years=${yearsParam}${monthQuery}`)
        .then(res => res.json())
        .then(data => {
            const setKpi = (id, val) => { const el = document.getElementById(id); el.classList.remove('kpi-loading'); el.innerText = val; };
            setKpi('kpi-airtime', fmt.number(data.airtime_hours) + ' hours');
            setKpi('kpi-tracks', fmt.number(data.total_tracks));
            setKpi('kpi-artists', fmt.number(data.total_artists));
            setKpi('kpi-avg-streams', fmt.number(data.avg_streams_per_day));
            setKpi('kpi-avg-min', fmt.number(data.avg_min_per_day));
        })
        .catch(e => { kpiIds.forEach(id => document.getElementById(id).classList.remove('kpi-loading')); console.error(e); });

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
    const doneOverlay = (id) => { const o = document.getElementById(id); if (o) o.classList.add('done'); };

    if (charts.daily) {
        charts.daily.data.labels = data.daily.map(d => d.date);
        charts.daily.data.datasets[0].data = data.daily.map(d => d.streams);
        charts.daily.update();
        doneOverlay('overlay-daily');
    } else {
        const ctxDaily = document.getElementById('trend-daily').getContext('2d');
        charts.daily = new Chart(ctxDaily, {
            type: 'line',
            data: {
                labels: data.daily.map(d => d.date),
                datasets: [{
                    label: 'Streams', data: data.daily.map(d => d.streams),
                    borderColor: '#1DB954', backgroundColor: 'rgba(29, 185, 84, 0.15)',
                    fill: true, tension: 0.4, pointRadius: 0
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
        doneOverlay('overlay-daily');
    }

    // DOW Bar Chart
    if (charts.dow) {
        charts.dow.data.labels = data.dow.map(d => d.day);
        charts.dow.data.datasets[0].data = data.dow.map(d => d.streams);
        charts.dow.update();
        doneOverlay('overlay-dow');
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
        doneOverlay('overlay-dow');
    }

    // Monthly Bar Chart
    const getMonthlyColors = (monthlyData) => monthlyData.map(d => {
        if (!selectedMonth) return '#1DB954';
        return d.month_id === selectedMonth ? '#1DB954' : '#334155';
    });

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
        charts.monthly.update();
        doneOverlay('overlay-monthly');
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
                onHover: (e, elements) => { e.native.target.style.cursor = elements.length ? 'pointer' : 'default'; }
            }
        });
        doneOverlay('overlay-monthly');
    }
}

function renderClocks(data) {
    const clockOptions = {
        responsive: true, maintainAspectRatio: false,
        scales: { r: { grid: { color: '#1e293b' }, angleLines: { color: '#1e293b' }, ticks: { display: false } } },
        plugins: { legend: { display: false } }
    };

    const doneClockOverlay = (id) => { const o = document.getElementById(id); if (o) o.classList.add('done'); };

    if (charts.clockStreams) {
        charts.clockStreams.data.labels = data.map(d => `Hour ${d.hour}:00`);
        charts.clockStreams.data.datasets[0].data = data.map(d => d.streams);
        charts.clockStreams.update();
        doneClockOverlay('overlay-clock-streams');
    } else {
        const ctxStreams = document.getElementById('clock-streams').getContext('2d');
        charts.clockStreams = new Chart(ctxStreams, {
            type: 'polarArea',
            data: {
                labels: data.map(d => `Hour ${d.hour}:00`),
                datasets: [{ data: data.map(d => d.streams), backgroundColor: 'rgba(29, 185, 84, 0.7)', borderColor: '#1DB954', borderWidth: 1 }]
            },
            options: { ...clockOptions, plugins: { legend: { display: false }, title: { display: true, text: 'Streams by Hour', color: '#fff', font: { size: 16 } } } }
        });
        doneClockOverlay('overlay-clock-streams');
    }

    if (charts.clockMins) {
        charts.clockMins.data.labels = data.map(d => `Hour ${d.hour}:00`);
        charts.clockMins.data.datasets[0].data = data.map(d => d.minutes);
        charts.clockMins.update();
        doneClockOverlay('overlay-clock-minutes');
    } else {
        const ctxMins = document.getElementById('clock-minutes').getContext('2d');
        charts.clockMins = new Chart(ctxMins, {
            type: 'polarArea',
            data: {
                labels: data.map(d => `Hour ${d.hour}:00`),
                datasets: [{ data: data.map(d => d.minutes), backgroundColor: 'rgba(29, 185, 84, 0.7)', borderColor: '#1DB954', borderWidth: 1 }]
            },
            options: { ...clockOptions, plugins: { legend: { display: false }, title: { display: true, text: 'Minutes Streamed by Hour', color: '#fff', font: { size: 16 } } } }
        });
        doneClockOverlay('overlay-clock-minutes');
    }
}

function getCardHTML(idx, type, title, subtitle, value, img, artistName=null) {
    const delay = Math.min(idx * 0.02, 1.0);
    const isArtist = type === 'artist';
    const subHTML = subtitle ? `<p class="list-subtitle">${subtitle}</p>` : "";
    const safeTitle = title.replace(/"/g, '&quot;');
    const safeArtist = artistName ? artistName.replace(/"/g, '&quot;') : '';

    // KEY FIX: If no image URL yet, omit src entirely.
    // src="" causes browsers to fire onerror IMMEDIATELY (shows ugly fallback icon).
    // With no src, the img-loader shimmer stays visible until we set src via JS.
    const srcAttr = img ? `src="${img}"` : '';
    const loadedClass = img ? 'loaded' : '';

    return `
        <div class="list-card" style="animation-delay: ${delay}s;">
            <div class="list-rank">#${idx+1}</div>
            <div class="img-loader ${isArtist ? 'artist' : ''}">
                <img ${srcAttr}
                     class="${loadedClass}"
                     data-name="${safeTitle}" data-type="${type}" data-artist="${safeArtist}"
                     onload="this.classList.add('loaded')"
                     onerror="this.src='https://cdn-icons-png.flaticon.com/512/33/33714.png';this.classList.add('loaded')">
            </div>
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
    // IMPROVEMENT: Render immediately with placeholders (no more waiting for artwork)
    renderHallOfFame(data);
    
    // Then fetch artwork in parallel batches of 5 for speed
    const items = [
        ...data.artists.map(a => ({ obj: a, type: 'artist', name: a.artist_name, artist: '' })),
        ...data.albums.map(a => ({ obj: a, type: 'album', name: a.album_name, artist: a.artist_name })),
        ...data.songs.map(a => ({ obj: a, type: 'track', name: a.track_name, artist: a.artist_name }))
    ];

    const BATCH_SIZE = 5;
    for (let i = 0; i < items.length; i += BATCH_SIZE) {
        const batch = items.slice(i, i + BATCH_SIZE);
        await Promise.all(batch.map(async (item) => {
            if (!item.obj.image_url) {
                const url = `${API_BASE}/spotify/artwork?name=${encodeURIComponent(item.name)}&type=${encodeURIComponent(item.type)}&artist_name=${encodeURIComponent(item.artist)}`;
                try {
                    const res = await fetch(url);
                    const json = await res.json();
                    if (json.image_url) {
                        item.obj.image_url = json.image_url;
                        // Update DOM directly — no full re-render needed
                        const imgEl = document.querySelector(`img[data-name="${item.name.replace(/"/g, '&quot;')}"][data-type="${item.type}"]`);
                        if (imgEl) imgEl.src = json.image_url;
                    }
                } catch(e) {}
            }
        }));
        await new Promise(r => setTimeout(r, 150)); // brief pause between batches
    }
}

// --- LIVE PULSE ---
let currentTrackId = null;
async function fetchNowPlaying() {
    try {
        const res = await fetch(`${API_BASE}/spotify/now-playing`);
        if (!res.ok) return;
        const data = await res.json();
        const npContainer = document.getElementById('np-container');

        if (data.is_playing) {
            if (currentTrackId !== data.track_id) {
                currentTrackId = data.track_id;
                npContainer.innerHTML = `
                    <div class="now-playing-bar fade-in">
                        <div class="np-details">
                            <div class="live-dot"></div>
                            <img src="${data.image_url || 'https://cdn-icons-png.flaticon.com/512/33/33714.png'}"
                                 style="width:55px;height:55px;border-radius:6px;object-fit:cover;box-shadow:0 0 12px rgba(29,185,84,0.5);">
                            <div class="np-text">
                                <p style="color:#1DB954;font-size:11px;font-weight:800;letter-spacing:1px;text-transform:uppercase;margin:0;">▶ Now Playing</p>
                                <h4>${data.track_name}</h4>
                                <p style="color:#94a3b8;font-weight:normal;">${data.artist_name}</p>
                            </div>
                        </div>
                        <div style="color:#1DB954;font-size:22px;">🎵</div>
                    </div>`;
            }
        } else {
            if (currentTrackId !== null) {
                currentTrackId = null;
                npContainer.innerHTML = '';
            }
        }
    } catch (e) {}
}

let lastPlayedAt = null;
async function fetchRecentlyPlayed() {
    try {
        const res = await fetch(`${API_BASE}/spotify/recently-played?limit=10`);
        if (!res.ok) {
            const tbody = document.getElementById('recent-tbody');
            if (tbody.innerHTML.includes("Loading")) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:#94a3b8;padding:20px;">
                    ⏸️ Spotify API sedang beristirahat. Data akan kembali otomatis.<br>
                    <small style="color:#475569;">Cron job tetap berjalan di background.</small>
                </td></tr>`;
            }
            return;
        }
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
                            <td><img src="${t.image_url || 'https://cdn-icons-png.flaticon.com/512/33/33714.png'}" class="cover-img"></td>
                            <td class="time-col">${timeStr}</td>
                            <td class="track-title">${t.track_name}</td>
                            <td class="artist-name">${t.artist_name}</td>
                        </tr>`;
                });
                tbody.innerHTML = html;
            }
        }
    } catch (e) {
        console.error("Recently Played Error:", e);
    }
}

// Mobile sidebar toggle
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    isMobileMenuOpen = !isMobileMenuOpen;
    sidebar.classList.toggle('open', isMobileMenuOpen);
    overlay.classList.toggle('visible', isMobileMenuOpen);
    document.body.style.overflow = isMobileMenuOpen ? 'hidden' : '';
}

// Event Listeners
function setupEventListeners() {
    const slider = document.getElementById('top-n-slider');
    slider.addEventListener('change', (e) => {
        topN = e.target.value;
        document.getElementById('top-n-value').innerText = topN;
        updateDashboard();
    });

    document.getElementById('sidebar-overlay').addEventListener('click', toggleSidebar);
    document.getElementById('hamburger-btn').addEventListener('click', toggleSidebar);

    // Filter Chips (Multi-Select & Single-Select Mode)
    document.addEventListener('click', (e) => {
        if(e.target.classList.contains('filter-chip')) {
            const clickedVal = e.target.getAttribute('data-value');
            const isMultiMode = document.getElementById('multi-select-toggle').checked;

            if (clickedVal === 'all') {
                document.querySelectorAll('.filter-chip').forEach(chip => chip.classList.remove('active'));
                e.target.classList.add('active');
                selectedYears = [...allAvailableYears];
            } else {
                const allChip = document.querySelector('.filter-chip[data-value="all"]');
                if (!isMultiMode) {
                    document.querySelectorAll('.filter-chip').forEach(chip => chip.classList.remove('active'));
                    e.target.classList.add('active');
                    selectedYears = [clickedVal];
                } else {
                    if (allChip && allChip.classList.contains('active')) {
                        allChip.classList.remove('active');
                        e.target.classList.add('active');
                        selectedYears = [clickedVal];
                    } else {
                        e.target.classList.toggle('active');
                        selectedYears = [];
                        document.querySelectorAll('.filter-chip.active').forEach(chip => {
                            const val = chip.getAttribute('data-value');
                            if (val !== 'all') selectedYears.push(val);
                        });
                        if (selectedYears.length === 0) {
                            showToast("Peringatan: Anda wajib memilih minimal satu tahun!");
                            e.target.classList.add('active');
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
