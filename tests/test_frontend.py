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
