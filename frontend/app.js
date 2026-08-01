const CONFIG = window.SPOTIFY_ODYSSEY_CONFIG || {
    apiBase: "/api",
    demoFallback: false,
    allowDemoPreview: true,
    liveEnabled: true,
};
const API_BASE = CONFIG.apiBase;
const PLACEHOLDER_ART = "assets/music-placeholder.svg?v=20260729-1";
const SPOTIFY_GREEN = "#1ed760";
const SPOTIFY_GREEN_SOFT = "rgba(30, 215, 96, 0.14)";

let selectedYears = [];
let allAvailableYears = [];
let topN = 10;
let selectedMonth = null;
let charts = {};
let isMobileMenuOpen = false;
let isDemoMode = false;
let demoData = null;
let dashboardController = null;
let dashboardRequestId = 0;
let currentTrackId = null;
let lastPlayedAt = null;

Chart.defaults.color = "#98a2b3";
Chart.defaults.font.family = "'Inter', sans-serif";

const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 350 },
    plugins: { legend: { display: false } },
    scales: {
        x: {
            grid: { display: false },
            border: { display: false },
            ticks: { maxRotation: 0 },
        },
        y: {
            beginAtZero: true,
            grid: { color: "rgba(148, 163, 184, 0.1)" },
            border: { display: false },
        },
    },
};

const fmt = {
    number: (value) =>
        new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(
            Number(value) || 0,
        ),
    time: (dateString) => {
        const date = new Date(dateString);
        if (Number.isNaN(date.getTime())) return "Unknown time";
        return date.toLocaleString("en-GB", {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
        });
    },
};

function escapeHTML(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function safeImageURL(value) {
    if (!value) return PLACEHOLDER_ART;
    try {
        const url = new URL(value, window.location.href);
        if (url.protocol === "https:" || url.origin === window.location.origin) {
            return url.href;
        }
    } catch {
        return PLACEHOLDER_ART;
    }
    return PLACEHOLDER_ART;
}

async function requestJSON(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: { Accept: "application/json", ...(options.headers || {}) },
    });
    const contentType = response.headers.get("content-type") || "";
    if (!response.ok) {
        let detail = "";
        if (contentType.includes("application/json")) {
            const payload = await response.json().catch(() => ({}));
            detail = typeof payload.detail === "string" ? payload.detail : "";
        }
        const error = new Error(
            detail || `Request failed with status ${response.status}.`,
        );
        error.status = response.status;
        error.isApiRouteMissing =
            response.status === 404 && !contentType.includes("application/json");
        throw error;
    }
    if (!contentType.includes("application/json")) {
        throw new Error("The server returned a non-JSON response.");
    }
    return response.json();
}

async function loadDemoData() {
    if (demoData) return demoData;
    demoData = await requestJSON("demo-data.json", { cache: "no-store" });
    return demoData;
}

function setConnectionState(mode) {
    const status = document.getElementById("connection-status");
    status.className = `status-badge ${mode}`;
    const labels = {
        live: "Live analytics connected",
        demo: "Portfolio demo data",
        checking: "Checking data source",
        error: "Data source unavailable",
    };
    status.textContent = labels[mode] || labels.error;
}

function setDemoMode(enabled) {
    isDemoMode = enabled;
    document.getElementById("mode-banner").classList.toggle("hidden", !enabled);
    setConnectionState(enabled ? "demo" : "live");
}

function showError(message) {
    document.getElementById("app-error-message").textContent = message;
    document.getElementById("app-error").classList.remove("hidden");
    document
        .getElementById("demo-button")
        .classList.toggle("hidden", !CONFIG.allowDemoPreview);
    setConnectionState("error");
}

function clearError() {
    document.getElementById("app-error").classList.add("hidden");
}

function dataErrorMessage(error) {
    if (error?.status === 503) {
        return (
            "Your listening database is not connected to this deployment. " +
            "Add DATABASE_URL (or POSTGRES_URL) in the hosting environment, " +
            "redeploy, then select Retry."
        );
    }
    if (error?.isApiRouteMissing || error?.message?.includes("non-JSON")) {
        return (
            "The analytics API is not being served by this deployment. " +
            "Check the backend route configuration, then select Retry."
        );
    }
    return error?.message || "Personal analytics data could not be loaded.";
}

function showToast(message) {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = "custom-toast";
    toast.textContent = message;
    container.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3500);
}

// Cache frequent DOM elements
const els = {
    yearFilters: document.getElementById("year-filters"),
    multiSelectToggle: document.getElementById("multi-select-toggle"),
    kpi: {
        airtime: document.getElementById("kpi-airtime"),
        tracks: document.getElementById("kpi-tracks"),
        artists: document.getElementById("kpi-artists"),
        activeDays: document.getElementById("kpi-activedays"),
        avgStreams: document.getElementById("kpi-avgstreams"),
    },
    fameGrid: document.getElementById("fame-grid"),
    recentList: document.getElementById("recent-list"),
    topNSlider: document.getElementById("top-n-slider"),
    topNValue: document.getElementById("top-n-value"),
    connStatus: document.getElementById("connection-status"),
    errorBanner: document.getElementById("app-error"),
    errorMessage: document.getElementById("app-error-message"),
    hamburgerBtn: document.getElementById("hamburger-btn"),
    sidebar: document.getElementById("filter-sidebar"),
    sidebarOverlay: document.getElementById("sidebar-overlay"),
};

// Hamburger menu toggle logic
function toggleSidebar(forceState = null) {
    if (!els.sidebar || !els.hamburgerBtn || !els.sidebarOverlay) return;
    
    const isOpen = els.sidebar.classList.contains("open");
    const willOpen = forceState !== null ? forceState : !isOpen;
    
    if (willOpen) {
        els.sidebar.classList.add("open");
        els.hamburgerBtn.classList.add("open");
        els.hamburgerBtn.setAttribute("aria-expanded", "true");
        els.sidebarOverlay.classList.add("active");
        document.body.style.overflow = "hidden";
    } else {
        els.sidebar.classList.remove("open");
        els.hamburgerBtn.classList.remove("open");
        els.hamburgerBtn.setAttribute("aria-expanded", "false");
        els.sidebarOverlay.classList.remove("active");
        document.body.style.overflow = "";
    }
}

if (els.hamburgerBtn) {
    els.hamburgerBtn.addEventListener("click", () => toggleSidebar());
}
if (els.sidebarOverlay) {
    els.sidebarOverlay.addEventListener("click", () => toggleSidebar(false));
}

async function init() {
    setupEventListeners();
    setConnectionState("checking");

    try {
        await fetchYears();
        await updateDashboard();
    } catch (error) {
        finishLoadingOverlays();
        showError(dataErrorMessage(error));
    }

    if (!isDemoMode) {
        await fetchRecentlyPlayed();
        window.setInterval(fetchRecentlyPlayed, 60000);
        if (CONFIG.liveEnabled) {
            await fetchNowPlaying();
            window.setInterval(fetchNowPlaying, 30000);
        }
    } else {
        renderLiveUnavailable();
    }
}

async function fetchYears() {
    try {
        const years = await requestJSON(`${API_BASE}/stats/years`);
        if (!Array.isArray(years) || !years.length) {
            throw new Error("No listening years were returned.");
        }
        allAvailableYears = years;
        setDemoMode(false);
    } catch (error) {
        if (!CONFIG.demoFallback) throw error;
        const sample = await loadDemoData();
        allAvailableYears = sample.years;
        setDemoMode(true);
    }

    selectedYears = [...allAvailableYears];
    renderYearFilters();
}

function renderYearFilters() {
    const container = document.getElementById("year-filters");
    container.replaceChildren();

    const group = document.createElement("div");
    group.className = "filter-chip-container";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", "Listening years");

    const allButton = document.createElement("button");
    allButton.type = "button";
    allButton.className = "filter-chip active";
    allButton.dataset.value = "all";
    allButton.textContent = "All years";
    allButton.setAttribute("aria-pressed", "true");
    group.appendChild(allButton);

    allAvailableYears.forEach((year) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "filter-chip";
        button.dataset.value = String(year);
        button.textContent = String(year);
        button.setAttribute("aria-pressed", "false");
        group.appendChild(button);
    });
    container.appendChild(group);
}

function markDashboardLoading() {
    const skeleton = Array.from(
        { length: Number(topN) },
        () => '<div class="skeleton skeleton-list-card"></div>',
    ).join("");
    ["hof-artists", "hof-albums", "hof-songs"].forEach((id) => {
        document.getElementById(id).innerHTML = skeleton;
    });
    [
        "kpi-airtime",
        "kpi-tracks",
        "kpi-artists",
        "kpi-avg-streams",
        "kpi-avg-min",
    ].forEach((id) => {
        const element = document.getElementById(id);
        element.textContent = "—";
        element.classList.add("kpi-loading");
    });
}

async function updateDashboard() {
    const requestId = ++dashboardRequestId;
    dashboardController?.abort();
    dashboardController = new AbortController();
    markDashboardLoading();
    clearError();

    if (isDemoMode) {
        const sample = await loadDemoData();
        if (requestId !== dashboardRequestId) return;
        renderKpi(sample.kpi);
        renderTrends(sample.trends);
        renderClocks(sample.clock);
        renderHallOfFame({
            artists: sample.fame.artists.slice(0, topN),
            albums: sample.fame.albums.slice(0, topN),
            songs: sample.fame.songs.slice(0, topN),
        });
        renderRecentlyPlayed(sample.recently_played.items);
        return;
    }

    const yearsParam = encodeURIComponent(selectedYears.join(","));
    const monthQuery = selectedMonth ? `&month=${selectedMonth}` : "";
    const signal = dashboardController.signal;

    try {
        const [kpi, trends, clock, fame] = await Promise.all([
            requestJSON(
                `${API_BASE}/stats/kpi?years=${yearsParam}${monthQuery}`,
                { signal },
            ),
            requestJSON(
                `${API_BASE}/stats/trends?years=${yearsParam}${monthQuery}`,
                { signal },
            ),
            requestJSON(
                `${API_BASE}/stats/clock?years=${yearsParam}${monthQuery}`,
                { signal },
            ),
            requestJSON(
                `${API_BASE}/stats/fame?years=${yearsParam}&top_n=${topN}${monthQuery}`,
                { signal },
            ),
        ]);
        if (requestId !== dashboardRequestId) return;
        renderKpi(kpi);
        renderTrends(trends);
        renderClocks(clock);
        void fetchFameWithArtwork(fame, signal, requestId);
    } catch (error) {
        if (error.name === "AbortError") return;
        if (CONFIG.demoFallback) {
            setDemoMode(true);
            await updateDashboard();
            renderLiveUnavailable();
            return;
        }
        finishLoadingOverlays();
        showError(dataErrorMessage(error));
    }
}

function renderKpi(data) {
    const values = {
        "kpi-airtime": `${fmt.number(data.airtime_hours)} hours`,
        "kpi-tracks": fmt.number(data.total_tracks),
        "kpi-artists": fmt.number(data.total_artists),
        "kpi-avg-streams": fmt.number(data.avg_streams_per_day),
        "kpi-avg-min": fmt.number(data.avg_min_per_day),
    };
    Object.entries(values).forEach(([id, value]) => {
        const element = document.getElementById(id);
        element.classList.remove("kpi-loading");
        element.textContent = value;
    });
}

function finishOverlay(id) {
    document.getElementById(id)?.classList.add("done");
}

function finishLoadingOverlays() {
    [
        "overlay-clock-streams",
        "overlay-clock-minutes",
        "overlay-daily",
        "overlay-dow",
        "overlay-monthly",
    ].forEach(finishOverlay);
}

function renderTrends(data) {
    const monthlyColors = data.monthly.map((item) =>
        !selectedMonth || item.month_id === selectedMonth
            ? SPOTIFY_GREEN
            : "#344054",
    );

    if (charts.daily) {
        charts.daily.data.labels = data.daily.map((item) => item.date);
        charts.daily.data.datasets[0].data = data.daily.map((item) => item.streams);
        charts.daily.update();
    } else {
        charts.daily = new Chart(document.getElementById("trend-daily"), {
            type: "line",
            data: {
                labels: data.daily.map((item) => item.date),
                datasets: [{
                    label: "Streams",
                    data: data.daily.map((item) => item.streams),
                    borderColor: SPOTIFY_GREEN,
                    backgroundColor: SPOTIFY_GREEN_SOFT,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                }],
            },
            options: {
                ...commonOptions,
                plugins: {
                    legend: { display: false },
                    title: chartTitle("Daily listening intensity"),
                    zoom: {
                        pan: { enabled: true, mode: "x" },
                        zoom: {
                            wheel: { enabled: true },
                            pinch: { enabled: true },
                            mode: "x",
                        },
                    },
                },
            },
        });
    }
    finishOverlay("overlay-daily");

    if (charts.dow) {
        charts.dow.data.labels = data.dow.map((item) => item.day);
        charts.dow.data.datasets[0].data = data.dow.map((item) => item.streams);
        charts.dow.update();
    } else {
        charts.dow = new Chart(document.getElementById("trend-dow"), {
            type: "bar",
            data: {
                labels: data.dow.map((item) => item.day.slice(0, 3)),
                datasets: [{
                    data: data.dow.map((item) => item.streams),
                    backgroundColor: SPOTIFY_GREEN,
                    borderRadius: 7,
                }],
            },
            options: {
                ...commonOptions,
                plugins: {
                    legend: { display: false },
                    title: chartTitle("Distribution by weekday"),
                },
            },
        });
    }
    finishOverlay("overlay-dow");

    const onMonthClick = (_event, elements) => {
        if (!elements.length) return;
        const monthId = data.monthly[elements[0].index].month_id;
        selectedMonth = selectedMonth === monthId ? null : monthId;
        updateDashboard();
    };
    if (charts.monthly) {
        charts.monthly.data.labels = data.monthly.map((item) => item.month);
        charts.monthly.data.datasets[0].data = data.monthly.map(
            (item) => item.streams,
        );
        charts.monthly.data.datasets[0].backgroundColor = monthlyColors;
        charts.monthly.options.onClick = onMonthClick;
        charts.monthly.update();
    } else {
        charts.monthly = new Chart(document.getElementById("trend-monthly"), {
            type: "bar",
            data: {
                labels: data.monthly.map((item) => item.month),
                datasets: [{
                    data: data.monthly.map((item) => item.streams),
                    backgroundColor: monthlyColors,
                    borderRadius: 7,
                }],
            },
            options: {
                ...commonOptions,
                plugins: {
                    legend: { display: false },
                    title: chartTitle("Distribution by month"),
                },
                onClick: onMonthClick,
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length
                        ? "pointer"
                        : "default";
                },
            },
        });
    }
    finishOverlay("overlay-monthly");
}

function chartTitle(text) {
    return {
        display: true,
        text,
        align: "start",
        color: "#f7f8f5",
        font: { size: 14, weight: "600" },
        padding: { bottom: 18 },
    };
}

function renderClocks(data) {
    const clockOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            r: {
                grid: { color: "rgba(148, 163, 184, 0.12)" },
                angleLines: { color: "rgba(148, 163, 184, 0.12)" },
                ticks: { display: false },
            },
        },
        plugins: { legend: { display: false } },
    };

    const labels = data.map((item) => `${item.hour}:00`);
    if (charts.clockStreams) {
        charts.clockStreams.data.labels = labels;
        charts.clockStreams.data.datasets[0].data = data.map(
            (item) => item.streams,
        );
        charts.clockStreams.update();
    } else {
        charts.clockStreams = new Chart(document.getElementById("clock-streams"), {
            type: "polarArea",
            data: {
                labels,
                datasets: [{
                    data: data.map((item) => item.streams),
                    backgroundColor: "rgba(30, 215, 96, 0.52)",
                    borderColor: SPOTIFY_GREEN,
                    borderWidth: 1,
                }],
            },
            options: {
                ...clockOptions,
                plugins: {
                    legend: { display: false },
                    title: chartTitle("Streams by hour"),
                },
            },
        });
    }
    finishOverlay("overlay-clock-streams");

    if (charts.clockMinutes) {
        charts.clockMinutes.data.labels = labels;
        charts.clockMinutes.data.datasets[0].data = data.map(
            (item) => item.minutes,
        );
        charts.clockMinutes.update();
    } else {
        charts.clockMinutes = new Chart(
            document.getElementById("clock-minutes"),
            {
                type: "polarArea",
                data: {
                    labels,
                    datasets: [{
                        data: data.map((item) => item.minutes),
                        backgroundColor: "rgba(116, 232, 204, 0.5)",
                        borderColor: "#74e8cc",
                        borderWidth: 1,
                    }],
                },
                options: {
                    ...clockOptions,
                    plugins: {
                        legend: { display: false },
                        title: chartTitle("Minutes by hour"),
                    },
                },
            },
        );
    }
    finishOverlay("overlay-clock-minutes");
}

function getCardHTML(index, type, title, subtitle, minutes, imageURL) {
    const delay = Math.min(index * 0.025, 0.5);
    const artwork = safeImageURL(imageURL);
    return `
        <article class="list-card" style="animation-delay:${delay}s">
            <div class="list-rank">#${index + 1}</div>
            <div class="img-loader ${type === "artist" ? "artist" : ""}">
                <img
                    src="${escapeHTML(artwork)}"
                    alt=""
                    class="loaded"
                    data-item-key="${type}-${index}"
                >
            </div>
            <div class="list-details">
                <p class="list-title">${escapeHTML(title)}</p>
                ${subtitle ? `<p class="list-subtitle">${escapeHTML(subtitle)}</p>` : ""}
            </div>
            <div class="list-stats">${fmt.number(minutes / 60)}h</div>
        </article>
    `;
}

function renderHallOfFame(data) {
    document.getElementById("hof-artists").innerHTML = data.artists
        .map((item, index) =>
            getCardHTML(
                index,
                "artist",
                item.artist_name,
                "Artist",
                item.minutes,
                item.image_url,
            ),
        )
        .join("");
    document.getElementById("hof-albums").innerHTML = data.albums
        .map((item, index) =>
            getCardHTML(
                index,
                "album",
                item.album_name,
                item.artist_name,
                item.minutes,
                item.image_url,
            ),
        )
        .join("");
    document.getElementById("hof-songs").innerHTML = data.songs
        .map((item, index) =>
            getCardHTML(
                index,
                "track",
                item.track_name,
                item.artist_name,
                item.minutes,
                item.image_url,
            ),
        )
        .join("");

    document.querySelectorAll(".img-loader img").forEach((image) => {
        image.addEventListener(
            "error",
            () => {
                image.src = PLACEHOLDER_ART;
            },
            { once: true },
        );
    });
}

async function fetchFameWithArtwork(data, signal, requestId) {
    renderHallOfFame(data);
    const items = [
        ...data.artists.map((item, index) => ({
            item,
            key: `artist-${index}`,
            type: "artist",
            name: item.artist_name,
            artist: "",
        })),
        ...data.albums.map((item, index) => ({
            item,
            key: `album-${index}`,
            type: "album",
            name: item.album_name,
            artist: item.artist_name,
        })),
        ...data.songs.map((item, index) => ({
            item,
            key: `track-${index}`,
            type: "track",
            name: item.track_name,
            artist: item.artist_name,
        })),
    ];

    const batchSize = 5;
    for (let offset = 0; offset < items.length; offset += batchSize) {
        if (signal.aborted || requestId !== dashboardRequestId) return;
        const batch = items.slice(offset, offset + batchSize);
        await Promise.all(
            batch.map(async ({ key, type, name, artist }) => {
                const query = new URLSearchParams({
                    name,
                    type,
                    artist_name: artist,
                });
                try {
                    const result = await requestJSON(
                        `${API_BASE}/spotify/artwork?${query}`,
                        { signal },
                    );
                    const image = document.querySelector(
                        `img[data-item-key="${key}"]`,
                    );
                    if (image && result.image_url) {
                        image.src = safeImageURL(result.image_url);
                    }
                } catch (error) {
                    if (error.name !== "AbortError") {
                        console.warn(`Artwork unavailable for ${type}.`);
                    }
                }
            }),
        );
    }
}

function renderNowPlaying(data) {
    const container = document.getElementById("np-container");
    if (!data?.is_playing) {
        container.replaceChildren();
        currentTrackId = null;
        return;
    }
    if (currentTrackId === data.track_id) return;
    currentTrackId = data.track_id;

    const bar = document.createElement("section");
    bar.className = "now-playing-bar fade-in";
    bar.setAttribute("aria-label", "Now playing");

    const details = document.createElement("div");
    details.className = "np-details";
    const liveDot = document.createElement("span");
    liveDot.className = "live-dot";
    liveDot.setAttribute("aria-hidden", "true");
    const image = document.createElement("img");
    image.src = safeImageURL(data.image_url);
    image.alt = "";
    image.className = "np-cover";
    image.addEventListener("error", () => {
        image.src = PLACEHOLDER_ART;
    }, { once: true });

    const text = document.createElement("div");
    text.className = "np-text";
    const label = document.createElement("p");
    label.className = "np-label";
    label.textContent = "Now playing";
    const title = document.createElement("h4");
    title.textContent = data.track_name || "Unknown track";
    const artist = document.createElement("p");
    artist.textContent = data.artist_name || "Unknown artist";
    text.append(label, title, artist);
    details.append(liveDot, image, text);
    bar.append(details);
    container.replaceChildren(bar);
}

async function fetchNowPlaying() {
    try {
        const data = await requestJSON(`${API_BASE}/spotify/now-playing`);
        renderNowPlaying(data);
    } catch {
        renderNowPlaying({ is_playing: false });
    }
}

function renderRecentlyPlayed(items) {
    const body = document.getElementById("recent-tbody");
    body.replaceChildren();

    if (!items?.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.className = "table-message";
        cell.textContent = "No recent listening activity is available.";
        row.appendChild(cell);
        body.appendChild(row);
        return;
    }

    items.forEach((item) => {
        const row = document.createElement("tr");
        const coverCell = document.createElement("td");
        const cover = document.createElement("img");
        cover.src = safeImageURL(item.image_url);
        cover.alt = "";
        cover.className = "cover-img";
        cover.addEventListener("error", () => {
            cover.src = PLACEHOLDER_ART;
        }, { once: true });
        coverCell.appendChild(cover);

        const timeCell = document.createElement("td");
        timeCell.className = "time-col";
        timeCell.textContent = fmt.time(item.played_at);
        const trackCell = document.createElement("td");
        trackCell.className = "track-title";
        trackCell.textContent = item.track_name || "Unknown track";
        const artistCell = document.createElement("td");
        artistCell.className = "artist-name";
        artistCell.textContent = item.artist_name || "Unknown artist";
        row.append(coverCell, timeCell, trackCell, artistCell);
        body.appendChild(row);
    });
}

async function fetchRecentlyPlayed() {
    let data = null;
    if (CONFIG.liveEnabled) {
        try {
            data = await requestJSON(
                `${API_BASE}/spotify/recently-played?limit=10`,
            );
        } catch {
            data = null;
        }
    }

    try {
        if (!data?.items?.length) {
            data = await requestJSON(`${API_BASE}/stats/recent?limit=10`);
        }
        if (data.items?.[0]?.played_at === lastPlayedAt) return;
        lastPlayedAt = data.items?.[0]?.played_at || null;
        renderRecentlyPlayed(data.items);
    } catch {
        renderLiveUnavailable();
    }
}

function renderLiveUnavailable() {
    if (isDemoMode && demoData?.recently_played?.items) {
        renderRecentlyPlayed(demoData.recently_played.items);
        return;
    }
    const body = document.getElementById("recent-tbody");
    body.replaceChildren();
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.className = "table-message";
    cell.textContent =
        "Recent listening is temporarily unavailable. Historical analytics above are still connected.";
    row.appendChild(cell);
    body.appendChild(row);
}

function toggleSidebar() {
    isMobileMenuOpen = !isMobileMenuOpen;
    document
        .getElementById("filter-sidebar")
        .classList.toggle("open", isMobileMenuOpen);
    document
        .getElementById("sidebar-overlay")
        .classList.toggle("visible", isMobileMenuOpen);
    document.body.style.overflow = isMobileMenuOpen ? "hidden" : "";

    const button = document.getElementById("hamburger-btn");
    button.setAttribute("aria-expanded", String(isMobileMenuOpen));
    button.setAttribute(
        "aria-label",
        isMobileMenuOpen ? "Close filters" : "Open filters",
    );
}

function setupEventListeners() {
    const slider = document.getElementById("top-n-slider");
    slider.addEventListener("input", (event) => {
        topN = Number(event.target.value);
        document.getElementById("top-n-value").value = String(topN);
    });
    slider.addEventListener("change", updateDashboard);

    document.getElementById("retry-button").addEventListener("click", async () => {
        isDemoMode = false;
        demoData = null;
        clearError();
        setConnectionState("checking");
        try {
            await fetchYears();
            await updateDashboard();
        } catch (error) {
            finishLoadingOverlays();
            showError(dataErrorMessage(error));
        }
    });
    document.getElementById("demo-button").addEventListener("click", async () => {
        clearError();
        const sample = await loadDemoData();
        allAvailableYears = sample.years;
        selectedYears = [...allAvailableYears];
        setDemoMode(true);
        renderYearFilters();
        await updateDashboard();
        renderLiveUnavailable();
    });
    document
        .getElementById("sidebar-overlay")
        .addEventListener("click", toggleSidebar);
    document
        .getElementById("hamburger-btn")
        .addEventListener("click", toggleSidebar);

    document
        .getElementById("year-filters")
        .addEventListener("click", (event) => {
            const button = event.target.closest("button.filter-chip");
            if (!button) return;

            const clickedValue = button.dataset.value;
            const multiMode = document.getElementById(
                "multi-select-toggle",
            ).checked;
            const buttons = document.querySelectorAll(".filter-chip");
            const allButton = document.querySelector(
                '.filter-chip[data-value="all"]',
            );

            if (clickedValue === "all") {
                buttons.forEach((chip) => {
                    chip.classList.remove("active");
                    chip.setAttribute("aria-pressed", "false");
                });
                button.classList.add("active");
                button.setAttribute("aria-pressed", "true");
                selectedYears = [...allAvailableYears];
            } else if (!multiMode) {
                buttons.forEach((chip) => {
                    chip.classList.remove("active");
                    chip.setAttribute("aria-pressed", "false");
                });
                button.classList.add("active");
                button.setAttribute("aria-pressed", "true");
                selectedYears = [Number(clickedValue)];
            } else {
                allButton?.classList.remove("active");
                allButton?.setAttribute("aria-pressed", "false");
                button.classList.toggle("active");
                button.setAttribute(
                    "aria-pressed",
                    String(button.classList.contains("active")),
                );
                selectedYears = Array.from(
                    document.querySelectorAll(
                        '.filter-chip.active:not([data-value="all"])',
                    ),
                    (chip) => Number(chip.dataset.value),
                );
                if (!selectedYears.length) {
                    button.classList.add("active");
                    button.setAttribute("aria-pressed", "true");
                    selectedYears = [Number(clickedValue)];
                    showToast("Select at least one year.");
                }
            }
            updateDashboard();
        });
}

init();
