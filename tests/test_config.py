from app.config import Settings


def test_defaults(monkeypatch) -> None:
    monkeypatch.delenv("TIMEZONE", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    settings = Settings.from_env()
    assert str(settings.timezone) == "Asia/Kolkata"
    assert settings.database_path.as_posix() == "data/ipo_radar.db"
