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
    assert out.exists() and "0 eligible postings" in out.read_text()
    assert '"rows": 0' in capsys.readouterr().out
