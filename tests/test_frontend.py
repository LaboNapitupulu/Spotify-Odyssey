import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_demo_dataset_is_valid_and_complete():
    data = json.loads((ROOT / "frontend" / "demo-data.json").read_text("utf-8"))

    assert len(data["clock"]) == 24
    assert len(data["trends"]["monthly"]) == 12
    assert len(data["trends"]["dow"]) == 7
    assert data["years"]
    assert data["fame"]["artists"]


def test_frontend_avoids_inline_event_handlers_and_remote_fallback_images():
    app_js = (ROOT / "frontend" / "app.js").read_text("utf-8")
    index_html = (ROOT / "frontend" / "index.html").read_text("utf-8")

    assert "onerror=" not in app_js.lower()
    assert "onload=" not in app_js.lower()
    assert "flaticon.com" not in app_js
    assert "storage.googleapis.com" not in index_html


def test_personal_mode_is_default_and_uses_spotify_green():
    config_js = (
        (ROOT / "frontend" / "config.js").read_text("utf-8").lower()
    )
    styles_css = (ROOT / "frontend" / "styles.css").read_text("utf-8").lower()
    app_js = (ROOT / "frontend" / "app.js").read_text("utf-8").lower()

    assert "demofallback: false" in config_js
    assert "liveenabled: true" in config_js
    assert "#1ed760" in styles_css
    assert "#1ed760" in app_js
    assert "/stats/recent" in app_js
