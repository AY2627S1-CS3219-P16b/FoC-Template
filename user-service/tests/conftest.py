import pytest


@pytest.fixture(autouse=True)
def configure_test_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
