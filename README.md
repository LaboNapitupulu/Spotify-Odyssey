# Spotify Odyssey

Spotify Odyssey is a privacy-conscious personal listening analytics dashboard. It transforms Spotify Extended Streaming History into interactive time patterns, rankings, and listening summaries while keeping private live activity disabled in public deployments by default.

## Highlights

- Interactive year, month, and ranking-size filters
- Daily, weekday, monthly, and hourly listening analysis
- Top artist, album, and track rankings
- PostgreSQL-backed import and artwork cache
- Optional owner-only now-playing and recently-played features
- Optional synthetic preview that is only shown when the visitor explicitly selects it
- Responsive, accessible vanilla JavaScript interface

## Architecture

```text
Spotify history JSON
        |
        v
scripts/process_raw_data.py
        |
        v
PostgreSQL <---- Spotify Web API
        |               |
        v               v
FastAPI analytics + private live endpoints
        |
        v
Vanilla JavaScript + Chart.js dashboard
```

## Privacy model

The repository contains no personal listening export, database, OAuth token, or Spotify secret.

- `data_raw/`, `data_processed/`, `.streamlit/`, `.cache`, `.env*`, and exported CSV files are ignored.
- Docker excludes those files independently through `.dockerignore`.
- Personal deployments show a clear connection error when the analytics API is unavailable.
- Synthetic data is never substituted for personal data automatically.
- Live Spotify endpoints are disabled unless `ENABLE_LIVE_SPOTIFY=true`.
- A `PRIVATE_API_KEY` is required for live endpoints outside localhost.
- `/api/sync` is a protected `POST` endpoint.

The bundled demo dataset is synthetic and does not represent a real Spotify account.

## Requirements

- Python 3.11
- PostgreSQL
- A Spotify Developer application for artwork or optional live features

## Local setup

```bash
git clone https://github.com/LaboNapitupulu/Spotify-Odyssey.git
cd Spotify-Odyssey

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env` and load those values into your shell or deployment platform.

Required for analytics:

```env
DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require
```

The backend also recognizes `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, and
`SUPABASE_DB_URL`. This makes Vercel and Supabase integrations work without
renaming their generated connection variable.

Optional Spotify configuration:

```env
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8080/
```

Import Extended Streaming History:

```bash
python scripts/process_raw_data.py
```

Start the application:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Optional private live features

Authorize the project-owner account from a trusted local machine:

```bash
python auth_spotify.py
```

Enable live endpoints locally:

```env
ENABLE_LIVE_SPOTIFY=true
```

For any non-local deployment, also configure a long random value:

```env
PRIVATE_API_KEY=replace_with_a_long_random_value
```

Trigger a protected synchronization:

```bash
curl -X POST \
  -H "X-API-Key: replace_with_a_long_random_value" \
  https://your-domain.example/api/sync
```

Do not embed `PRIVATE_API_KEY` in public frontend code.

## Personal dashboard deployment

Deploy the complete project when you want to see your own listening statistics:

1. Deploy the repository, not only `frontend/`.
2. Add `DATABASE_URL` as a secret environment variable in the hosting platform.
3. Apply it to the Production environment and redeploy.
4. Open `/api/health` and confirm that `database_ready` is `true`.
5. Keep `liveEnabled: false` unless private Spotify OAuth is also configured.

Vercel serves both the static frontend and FastAPI adapter using `vercel.json`.
Without a database connection variable, the dashboard displays a configuration
message instead of silently replacing your statistics with sample numbers.
Visitors can still select **View sample data** manually.

Never commit the connection URL to GitHub or place it in `frontend/config.js`.

The Docker image runs as a non-root user on port `7860`:

```bash
docker build -t spotify-odyssey .
docker run --rm -p 7860:7860 --env-file .env spotify-odyssey
```

## API

| Method | Endpoint | Access |
|---|---|---|
| `GET` | `/api/health` | Public |
| `GET` | `/api/stats/years` | Public aggregate |
| `GET` | `/api/stats/kpi` | Public aggregate |
| `GET` | `/api/stats/clock` | Public aggregate |
| `GET` | `/api/stats/trends` | Public aggregate |
| `GET` | `/api/stats/fame` | Public aggregate |
| `GET` | `/api/spotify/artwork` | Public, validated |
| `GET` | `/api/spotify/now-playing` | Private |
| `GET` | `/api/spotify/recently-played` | Private |
| `POST` | `/api/sync` | Private |

Only deploy the aggregate endpoints with a database you are comfortable presenting publicly. Use the synthetic static mode when the original listening history must remain private.

## Quality checks

```bash
python -m pytest
python -m compileall -q backend api scripts
node --check frontend/app.js
```

## Data correctness

- Listening events are unique by timestamp, track, and artist.
- Imports and Spotify synchronization use conflict-safe inserts.
- Track counts distinguish identical titles by different artists.
- “Per day” metrics mean active listening days, avoiding misleading gaps between non-contiguous year filters.
