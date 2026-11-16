from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_text():
    def _read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _read


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    """Los tests corren sin internet: si alguno intenta bajar algo, falla en vez de salir a la red."""
    def _bloqueado(*args, **kwargs):
        raise AssertionError(f"un test intentó salir a la red: {args[0] if args else kwargs}")

    monkeypatch.setattr("alertas.http._opener.open", _bloqueado)
