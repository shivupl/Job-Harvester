from pathlib import Path
import json
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_json():
    def load(name):
        return json.loads((FIXTURES / name).read_text())
    return load


@pytest.fixture
def fixture_text():
    def load(name):
        return (FIXTURES / name).read_text()
    return load
