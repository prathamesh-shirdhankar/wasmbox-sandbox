"""
Tests for plugin storage and retrieval endpoints.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
import app.api.storage as storage_module

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Ensure every test runs against a clean, isolated SQLite database file."""
    test_db = tmp_path / "test_plugins.db"
    monkeypatch.setattr(storage_module, "DEFAULT_DB_PATH", test_db)
    storage_module.init_db(test_db)
    yield test_db


def test_save_and_list_plugin():
    """Verify POST /plugins creates a plugin and GET /plugins returns it in list."""
    # 1. Save plugin
    res = client.post("/plugins", json={"name": "hello", "code": "print('hi')"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 1
    assert data["name"] == "hello"

    # 2. List plugins
    list_res = client.get("/plugins")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert isinstance(list_data, list)
    assert len(list_data) == 1
    assert list_data[0] == {"id": 1, "name": "hello"}


def test_get_single_plugin_by_id():
    """Verify GET /plugins/{id} returns the full plugin including code."""
    save_res = client.post("/plugins", json={"name": "my_calc", "code": "print(2 + 2)"})
    assert save_res.status_code == 200
    plugin_id = save_res.json()["id"]

    res = client.get(f"/plugins/{plugin_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == plugin_id
    assert data["name"] == "my_calc"
    assert data["code"] == "print(2 + 2)"


def test_get_unknown_plugin_returns_404():
    """Verify GET /plugins/{id} with non-existent id returns 404 with detail message."""
    res = client.get("/plugins/9999")
    assert res.status_code == 404
    data = res.json()
    assert data["detail"] == "Plugin not found"


def test_save_plugin_empty_name_rejected():
    """Verify POST /plugins rejects whitespace/empty name with 400."""
    res = client.post("/plugins", json={"name": "   ", "code": "print(1)"})
    assert res.status_code == 400
    assert "name" in res.json()["detail"].lower()


def test_save_plugin_name_exceeding_100_chars_rejected():
    """Verify POST /plugins rejects name longer than 100 characters."""
    long_name = "a" * 101
    res = client.post("/plugins", json={"name": long_name, "code": "print(1)"})
    assert res.status_code == 400
    assert "100" in res.json()["detail"]


def test_save_plugin_empty_code_rejected():
    """Verify POST /plugins rejects empty or whitespace code with 400."""
    res = client.post("/plugins", json={"name": "valid_name", "code": "   \n\t  "})
    assert res.status_code == 400
    assert "code" in res.json()["detail"].lower()


def test_save_plugin_oversized_code_rejected():
    """Verify POST /plugins rejects code exceeding 10,000 characters."""
    oversized = "x = 1\n" + ("# comment\n" * 1200)
    assert len(oversized) > 10_000
    res = client.post("/plugins", json={"name": "too_big", "code": oversized})
    assert res.status_code == 400
    assert "10000" in res.json()["detail"]


def test_save_plugin_missing_field_gives_422():
    """Verify missing field in request body returns 422 Unprocessable Entity."""
    res = client.post("/plugins", json={"name": "only_name"})
    assert res.status_code == 422


def test_trigger_webhook_executes_saved_plugin():
    """Verify POST /webhooks/{id} executes the stored plugin and returns standard 5-field contract."""
    save_res = client.post("/plugins", json={"name": "greeting", "code": "print('hi')"})
    assert save_res.status_code == 200
    plugin_id = save_res.json()["id"]

    res = client.post(f"/webhooks/{plugin_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["stdout"] == "hi\n"
    assert data["stderr"] == ""
    assert data["exec_ms"] == 0
    assert data["mem_bytes"] == 0


def test_trigger_webhook_unknown_id_returns_404():
    """Verify POST /webhooks/{id} returns 404 for non-existent plugin id."""
    res = client.post("/webhooks/9999")
    assert res.status_code == 404
    assert res.json()["detail"] == "Plugin not found"


def test_trigger_webhook_handles_runtime_error():
    """Verify webhook execution captures guest errors without crashing server."""
    save_res = client.post("/plugins", json={"name": "div_zero", "code": "1 / 0"})
    assert save_res.status_code == 200
    plugin_id = save_res.json()["id"]

    res = client.post(f"/webhooks/{plugin_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert "ZeroDivisionError" in data["stderr"]
    assert data["stdout"] == ""

