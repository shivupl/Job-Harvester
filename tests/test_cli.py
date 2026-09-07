import os

from jobwatch.__main__ import load_dotenv


def test_load_dotenv_accepts_api_key_alias(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("# comment\nAPI_KEY=sk-test-123")   # no trailing newline, like a hand-written file
    load_dotenv(env)
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-test-123"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")
    env = tmp_path / ".env"
    env.write_text('ANTHROPIC_API_KEY="from-file"\n')
    load_dotenv(env)
    assert os.environ["ANTHROPIC_API_KEY"] == "from-shell"


def test_board_command_writes_file(tmp_path, capsys):
    from jobwatch.__main__ import main
    db = tmp_path / "t.db"
    out = tmp_path / "board.html"
    main(["board", "--db", str(db), "--out", str(out)])
    assert out.exists() and "Nothing to look at right now" in out.read_text()
    assert '"rows": 0' in capsys.readouterr().out


def test_refresh_pulls_then_rebuilds_and_opens(tmp_path, monkeypatch, capsys):
    import subprocess
    from jobwatch import __main__ as cli
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "Already up to date.\n", ""))
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    db, out = tmp_path / "t.db", tmp_path / "board.html"
    cli.main(["refresh", "--db", str(db), "--out", str(out)])
    assert calls == [["git", "pull", "--rebase", "--quiet"]]
    assert out.exists() and opened == [out.resolve().as_uri()]
    assert '"rows": 0' in capsys.readouterr().out


def test_refresh_stops_when_pull_fails(tmp_path, monkeypatch):
    import subprocess, pytest
    from jobwatch import __main__ as cli
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "error: cannot pull with rebase"))
    with pytest.raises(SystemExit, match="cannot pull"):
        cli.main(["refresh", "--db", str(tmp_path / "t.db"), "--out", str(tmp_path / "b.html")])
