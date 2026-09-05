from app.__main__ import main


def test_daily_job_initializes_database(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "ipo_radar.db"
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setattr("sys.argv", ["ipo-radar", "--job", "daily"])
    main()
    assert database_path.exists()

