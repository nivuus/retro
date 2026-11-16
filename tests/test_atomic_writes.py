"""A write that dies half-way must leave the previous file, not a fragment.

The fault is real, not mocked: RLIMIT_FSIZE makes the kernel refuse a write
past a size after part of it is on disk, the same shape as a VM cut off in the
middle of a write. SIGXFSZ is ignored so the failure surfaces as OSError.
"""
import contextlib
import json
import pathlib
import resource
import signal

import pytest

from retro import atomic, launcher, profiles
from retro.steam import appid, artwork
from tests.test_launcher import PROFIL

pytestmark = pytest.mark.skipif(not hasattr(resource, "RLIMIT_FSIZE"),
                                reason="needs RLIMIT_FSIZE (POSIX)")

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@contextlib.contextmanager
def file_size_limit(nbytes):
    old_handler = signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    old_limit = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (nbytes, old_limit[1]))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, old_limit)
        signal.signal(signal.SIGXFSZ, old_handler)


def test_helper_keeps_the_old_content_when_the_write_fails(tmp_path):
    target = tmp_path / "file.bin"
    target.write_bytes(b"old")
    with file_size_limit(100), pytest.raises(OSError):
        atomic.write(target, b"x" * 10_000)
    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["file.bin"]


def test_helper_writes_text_and_replaces_in_one_step(tmp_path):
    target = tmp_path / "plan.ini"
    atomic.write(target, "emulator=\u00e9\n")
    atomic.write(target, "emulator=\u30d5\n")
    assert target.read_text(encoding="utf-8") == "emulator=\u30d5\n"
    assert [p.name for p in tmp_path.iterdir()] == ["plan.ini"]


def test_a_truncated_download_is_not_taken_for_an_artwork(tmp_path):
    search = json.loads((FIXTURES / "sgdb-search.json").read_text())
    grids = json.loads((FIXTURES / "sgdb-grids.json").read_text())
    client = artwork.ArtworkClient(
        api_key="k",
        fetch_json=lambda url, headers: search if "search" in url else grids,
        fetch_bytes=lambda url: b"\xff\xd8" * 50_000)
    grid = tmp_path / "grid"
    with file_size_limit(1000):
        assert client.fetch_for("Some Game", 1234, grid) == []
    assert client.erreurs, "the failure must still reach the report"
    # No partial image may be seen as present, or it is never fetched again.
    for prefix in appid.grid_prefixes(1234).values():
        assert appid.existing_asset(grid, prefix) is None


def test_a_plan_is_never_left_half_written(tmp_path):
    p = tmp_path / "duckstation.toml"
    p.write_text(PROFIL, encoding="utf-8")
    profs = {"duckstation": profiles.load_profile(p)}
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profs, {"duckstation": "DS"})
    plan = tmp_path / launcher.DIR / launcher.PLAN / "duckstation.psx.ini"
    before = plan.read_text(encoding="utf-8")
    assert before
    # The new emulation root makes the plan longer than the limit.
    with file_size_limit(20), pytest.raises(OSError):
        launcher.ecrire_plan(tmp_path, "D:\\Emulation\\" + "Deeper\\" * 20,
                             profs, {"duckstation": "DS"})
    assert plan.read_text(encoding="utf-8") == before
