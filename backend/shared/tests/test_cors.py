from backend.shared.cors import DEFAULT_DEV_ORIGINS, resolve_cors_origins


def test_default_dev_cors_origins_include_playwright_port(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    origins = resolve_cors_origins()

    assert "http://127.0.0.1:3100" in DEFAULT_DEV_ORIGINS
    assert "http://localhost:3100" in origins
