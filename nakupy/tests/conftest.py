"""Spolecne fixtures - kazdy test bezi nad cistou docasnou databazi."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ADMIN_PASSWORD = "tajneheslo"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NAKUPY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NAKUPY_SECRET_KEY", "test-secret")
    monkeypatch.setenv("NAKUPY_ADMIN_USER", "admin")
    monkeypatch.setenv("NAKUPY_ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setenv("NAKUPY_SECURE_COOKIES", "false")

    for module in [name for name in list(sys.modules) if name.startswith("app")]:
        del sys.modules[module]

    from fastapi.testclient import TestClient

    main = importlib.import_module("app.main")
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def logged_in(client):
    response = client.post(
        "/prihlaseni",
        data={"username": "admin", "password": ADMIN_PASSWORD, "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


@pytest.fixture()
def shopping_list_id(logged_in):
    response = logged_in.post(
        "/seznamy/novy", data={"title": "Testovací nákup"}, follow_redirects=False
    )
    return int(response.headers["location"].rsplit("/", 1)[1])


@pytest.fixture()
def db(client):
    """Primy pristup k databazi bezici instance."""
    from app.db import session_scope

    with session_scope() as session:
        yield session
