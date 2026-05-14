from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR

@pytest.fixture
def load_fixture(fixtures_dir):
    def _load(name: str) -> str:
        return (fixtures_dir / name).read_text()
    return _load
