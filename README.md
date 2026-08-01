# Spotify Odyssey

![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

Spotify Odyssey is a privacy-conscious personal listening analytics dashboard. It transforms your raw Spotify Extended Streaming History into interactive time patterns, rankings, and deep listening summaries—while strictly keeping your private live activity disabled in public deployments by default.

## Highlights & Features

- **Interactive Analytics**: Drill down through your music history using year, month, and ranking-size filters.
- **Time Patterns**: Visualize your habits with daily, weekday, monthly, and hourly listening charts.
- **Top Rankings**: Discover your all-time or monthly top artists, albums, and tracks effortlessly.
- **Robust Synchronization**: Latest imported tracks have a PostgreSQL database fallback, ensuring your dashboard remains resilient even when the Spotify API is unavailable.
- **Smart Caching**: PostgreSQL-backed import and artwork cache for lightning-fast load times.
- **Live Pulse (Optional)**: Owner-only "now-playing" and "recently-played" features for a dynamic, real-time dashboard experience.
- **Privacy-First Design**: Optional synthetic preview mode that is only shown when the visitor explicitly selects it.
- **Lightweight Frontend**: Highly responsive, accessible, and blazing fast Vanilla JavaScript interface powered by Chart.js.

## Architecture

Spotify Odyssey leverages a lightweight, decoupled stack to process and serve your music history securely.

```text
Spotify History JSON
        |
        v
scripts/process_raw_data.py
        |
        v
PostgreSQL <---- Spotify Web API
        |               |
        v               v
FastAPI Analytics + Private Live Endpoints
        |
        v
Vanilla JavaScript + Chart.js Dashboard
```

## Privacy Model

This project is built from the ground up for **absolute privacy**. The repository contains no personal listening exports, databases, OAuth tokens, or Spotify secrets.

- **Git Safety**: `data_raw/`, `data_processed/`, `.streamlit/`, `.cache`, `.env*`, and exported CSV files are strictly ignored by Git and Docker.
- **Fail-safe Display**: Personal deployments show a clear connection error when the analytics API is unavailable.
- **No Deceptive Fallbacks**: Synthetic data is never substituted for personal data automatically.
- **Strict Endpoint Control**: 
  - Live Spotify endpoints are disabled unless `ENABLE_LIVE_SPOTIFY=true`.
  - Read-only live activity can be made public with `PUBLIC_LIVE_SPOTIFY_READS=true`.
  - A `PRIVATE_API_KEY` remains required for synchronization outside `localhost`.
  - `/api/sync` is a protected `POST` endpoint.

*Note: The bundled demo dataset is synthetic and does not represent a real Spotify account.*

## Requirements

- **Python 3.11**
- **PostgreSQL**
- A **Spotify Developer application** (required for artwork fetching or optional live features)

## Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/LaboNapitupulu/Spotify-Odyssey.git
   cd Spotify-Odyssey
   ```

2. **Initialize Environment:**
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   
   pip install -r requirements-dev.txt
   ```

3. **Configure Settings:**
   Copy `.env.example` to `.env` and load those values into your shell or deployment platform.
   
   *Required for analytics:*
   ```env
   DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require
   ```
   *(The backend also recognizes `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, and `SUPABASE_DB_URL` for seamless Vercel/Supabase integrations).*

   *Optional Spotify configuration:*
   ```env
   SPOTIFY_CLIENT_ID=...
   SPOTIFY_CLIENT_SECRET=...
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8080/
   ```

4. **Import Extended Streaming History:**
   ```bash
   python scripts/process_raw_data.py
   ```

5. **Start the Application:**
   ```bash
   uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```
   Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Optional Private Live Features

Authorize the project-owner account from a trusted local machine:
```bash
python auth_spotify.py
```

Enable live endpoints locally:
```env
ENABLE_LIVE_SPOTIFY=true
```

To show "now-playing" and Spotify's "recently-played" list on a public dashboard:
```env
PUBLIC_LIVE_SPOTIFY_READS=true
```
*This intentionally makes those two read-only endpoints visible to dashboard visitors. If the Spotify API or OAuth token is unavailable, the recent-tracks table gracefully falls back to the latest rows already stored in PostgreSQL.*

For synchronization on any non-local deployment, configure a long random value:
```env
PRIVATE_API_KEY=replace_with_a_long_random_value
```

Trigger a protected synchronization:
```bash
curl -X POST \
  -H "X-API-Key: replace_with_a_long_random_value" \
  https://your-domain.example/api/sync
```

⚠️ **Security Note:** Do not embed `PRIVATE_API_KEY` in public frontend code. It protects write access to `/api/sync`; it is not needed by the public read-only Live Pulse.

## Personal Dashboard Deployment

Deploy the complete project when you want to see your own listening statistics publicly or privately:

1. Deploy the repository (backend and frontend together).
2. Add `DATABASE_URL` as a secret environment variable in your hosting platform.
3. Apply it to the Production environment and redeploy.
4. Open `/api/health` and confirm that `database_ready` is `true`.
5. Run `python auth_spotify.py` once locally so the refresh token is stored in PostgreSQL.
6. Set `ENABLE_LIVE_SPOTIFY=true` and `PUBLIC_LIVE_SPOTIFY_READS=true` when the public Live Pulse is intentional.

**Vercel Deployment:** Vercel serves both the static frontend and FastAPI adapter using `vercel.json`. Without a database connection variable, the dashboard displays a configuration message instead of silently replacing your statistics with sample numbers. Visitors can still select **View sample data** manually.

⚠️ **WARNING:** Never commit the connection URL to GitHub or place it in `frontend/config.js`.

**Docker Deployment:** The Docker image runs as a non-root user on port `7860`:
```bash
docker build -t spotify-odyssey .
docker run --rm -p 7860:7860 --env-file .env spotify-odyssey
```

## API Reference

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/api/health` | Public |
| `GET` | `/api/stats/years` | Public aggregate |
| `GET` | `/api/stats/kpi` | Public aggregate |
| `GET` | `/api/stats/clock` | Public aggregate |
| `GET` | `/api/stats/trends` | Public aggregate |
| `GET` | `/api/stats/fame` | Public aggregate |
| `GET` | `/api/stats/recent` | Public latest-history fallback |
| `GET` | `/api/spotify/artwork` | Public, validated |
| `GET` | `/api/spotify/now-playing` | Public only when explicitly enabled |
| `GET` | `/api/spotify/recently-played` | Public only when explicitly enabled |
| `POST` | `/api/sync` | Private |

*Only deploy the aggregate endpoints with a database you are comfortable presenting publicly. Use the synthetic static mode when the original listening history must remain private.*

## Quality Checks

Ensure the code remains stable before pushing:
```bash
python -m pytest
python -m compileall -q backend api scripts
node --check frontend/app.js
```

## Data Correctness

- Listening events are deduplicated and unique by timestamp, track, and artist.
- Imports and Spotify synchronization use conflict-safe atomic inserts.
- Track counts automatically distinguish identical titles by different artists.
- “Per day” metrics accurately reflect active listening days, avoiding misleading gaps between non-contiguous year filters.
