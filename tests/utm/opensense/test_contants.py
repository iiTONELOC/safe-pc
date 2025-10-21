import re
from pathlib import Path
from importlib import reload
from collections.abc import Generator

from utm.opnsense.iso.constants import get_opns_iso_dir, OpnSenseConstants

import pytest
from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: MonkeyPatch) -> Generator[None, None, None]:
    """Ensure environment and dirs are clean before each test."""
    monkeypatch.delenv("SAFE_PC_OPNSENSE_VERSION", raising=False)
    yield


def test_get_opns_iso_dir_creates_dir(monkeypatch: MonkeyPatch) -> None:
    """Directory should be created if it does not exist."""
    monkeypatch.setattr("utm.opnsense.iso.constants.is_testing", lambda: False)
    monkeypatch.setattr("utm.opnsense.iso.constants.is_production", lambda: False)

    iso_dir: Path = get_opns_iso_dir()

    assert isinstance(iso_dir, Path)
    assert iso_dir.exists()
    assert "isos" in str(iso_dir)


def test_get_opns_iso_dir_testing(monkeypatch: MonkeyPatch) -> None:
    """Testing environment should point to tests/data/isos."""
    monkeypatch.setattr("utm.opnsense.iso.constants.is_testing", lambda: True)
    monkeypatch.setattr("utm.opnsense.iso.constants.is_production", lambda: False)

    path: Path = get_opns_iso_dir()
    assert "tests/data/isos" in str(path)


# def test_get_opns_iso_dir_production(monkeypatch: MonkeyPatch) -> None:
#     """Production environment uses correct path."""
#     monkeypatch.setattr("utm.opnsense.iso.constants.is_testing", lambda: False)
#     monkeypatch.setattr("utm.opnsense.iso.constants.is_production", lambda: True)

#     path: Path = get_opns_iso_dir()
#     assert "safe_pc" in str(path)
#     assert path.exists()
#     # remove it IF it's empty
#     if not any(path.iterdir()):
#         path.rmdir()


def test_constants_default_version(monkeypatch: MonkeyPatch) -> None:
    """Default version should be 25.7 if env var unset."""
    monkeypatch.delenv("SAFE_PC_OPNSENSE_VERSION", raising=False)
    assert OpnSenseConstants.CURRENT_VERSION == "25.7"


def test_constants_env_override(monkeypatch: MonkeyPatch) -> None:
    """Environment variable overrides default version."""
    monkeypatch.setenv("SAFE_PC_OPNSENSE_VERSION", "99.9")

    import utm.opnsense.iso.constants as consts

    reload(consts)

    assert consts.OpnSenseConstants.CURRENT_VERSION == "99.9"


def test_releases_structure() -> None:
    """RELEASES should contain proper keys and URLs."""
    releases: dict[str, list[list[str]]] = OpnSenseConstants.RELEASES
    assert "25.7" in releases

    entry: list[list[str]] = releases["25.7"]
    assert isinstance(entry, list)
    assert all(isinstance(url, str) for group in entry for url in group)


def test_version_hash_regex_matches_expected() -> None:
    """VERSION_HASH regex should capture a 64-hex digest."""
    regex: re.Pattern[str] = re.compile(OpnSenseConstants.VERSION_HASH)
    test_str: str = "SHA256 (OPNsense-25.7-dvd-amd64.iso.bz2) = " + "a" * 64

    m: re.Match[str] | None = regex.search(test_str)
    assert m is not None
    assert m.group(1) == "a" * 64
