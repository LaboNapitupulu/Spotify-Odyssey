from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from backend import database, main


def test_parse_years_normalizes_and_deduplicates():
    assert main.parse_years("2024, 2022,2024") == [2022, 2024]
    assert main.parse_years(None) is None


@pytest.mark.parametrize(
    "value",
    ["not-a-year", "1899", "2020,,not-valid", ",".join(["2024"] * 41)],
)
def test_parse_years_rejects_invalid_values(value):
    with pytest.raises(HTTPException) as error:
        main.parse_years(value)
    assert error.value.status_code == 422


def test_health_reports_degraded_without_database(monkeypatch):
    monkeypatch.setattr(
        main.database,
        "init_db",
        lambda: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    monkeypatch.setattr(main.database, "close_pool", lambda: None)
    monkeypatch.setattr(main, "_load_spotify_credentials", lambda: (None, None, ""))

    with TestClient(main.app, raise_server_exceptions=False) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["database_ready"] is False


def test_private_spotify_routes_are_disabled_by_default(monkeypatch):
    monkeypatch.setattr(main, "LIVE_SPOTIFY_ENABLED", False)
    monkeypatch.setattr(main.database, "init_db", lambda: None)
    monkeypatch.setattr(main.database, "close_pool", lambda: None)
    monkeypatch.setattr(main, "_load_spotify_credentials", lambda: (None, None, ""))

    with TestClient(main.app) as client:
        now_playing = client.get("/api/spotify/now-playing")
        sync = client.post("/api/sync")

    assert now_playing.status_code == 404
    assert sync.status_code == 404


def test_query_bounds_are_enforced(monkeypatch):
    monkeypatch.setattr(main.database, "init_db", lambda: None)
    monkeypatch.setattr(main.database, "close_pool", lambda: None)
    monkeypatch.setattr(main, "_load_spotify_credentials", lambda: (None, None, ""))

    with TestClient(main.app) as client:
        invalid_month = client.get("/api/stats/kpi?month=13")
        excessive_ranking = client.get("/api/stats/fame?top_n=500")

    assert invalid_month.status_code == 422
    assert excessive_ranking.status_code == 422


def test_database_url_accepts_vercel_postgres_alias(monkeypatch):
    for key in database.DATABASE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(
        "POSTGRES_URL",
        "postgres://example:secret@database.example:5432/spotify",
    )
    monkeypatch.setattr(
        database.toml,
        "load",
        lambda _path: (_ for _ in ()).throw(FileNotFoundError()),
    )

    assert database.get_db_url().startswith("postgresql://")


def test_recent_history_endpoint_uses_database_fallback(monkeypatch):
    monkeypatch.setattr(main.database, "init_db", lambda: None)
    monkeypatch.setattr(main.database, "close_pool", lambda: None)
    monkeypatch.setattr(main, "_load_spotify_credentials", lambda: (None, None, ""))
    monkeypatch.setattr(
        main.database,
        "get_recent_history",
        lambda limit: [{"track_name": "Latest track", "limit": limit}],
    )

    with TestClient(main.app) as client:
        response = client.get("/api/stats/recent?limit=7")

    assert response.status_code == 200
    assert response.json()["items"] == [{"track_name": "Latest track", "limit": 7}]


def test_public_live_reads_do_not_expose_sync(monkeypatch):
    class SpotifyStub:
        def current_user_playing_track(self):
            return {"is_playing": False}

    monkeypatch.setattr(main, "LIVE_SPOTIFY_ENABLED", True)
    monkeypatch.setattr(main, "PUBLIC_LIVE_SPOTIFY_READS", True)
    monkeypatch.setattr(main.database, "init_db", lambda: None)
    monkeypatch.setattr(main.database, "close_pool", lambda: None)
    monkeypatch.setattr(main, "_load_spotify_credentials", lambda: (None, None, ""))

    with TestClient(main.app) as client:
        client.app.state.spotify_user = SpotifyStub()
        now_playing = client.get("/api/spotify/now-playing")
        sync = client.post("/api/sync")

    assert now_playing.status_code == 200
    assert now_playing.json() == {"is_playing": False}
    assert sync.status_code == 503
