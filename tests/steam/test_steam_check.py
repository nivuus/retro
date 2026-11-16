"""A failed process listing must never read as "Steam is not running"."""
import os
import types

import pytest

from retro.steam import vdf_io, writer


def _tasklist(monkeypatch, *, stdout="", returncode=0, error=None):
    monkeypatch.setattr(os, "name", "nt")

    def run(*args, **kwargs):
        if error:
            raise error
        return types.SimpleNamespace(stdout=stdout, returncode=returncode)
    monkeypatch.setattr(writer.subprocess, "run", run)


def test_a_nonzero_exit_refuses_the_write(monkeypatch):
    _tasklist(monkeypatch, stdout='"explorer.exe","1"\n', returncode=1)
    with pytest.raises(writer.SteamRunningError):
        writer.assert_steam_not_running()


def test_an_empty_listing_refuses_the_write(monkeypatch):
    """Windows always runs System and explorer: nothing at all is a failure."""
    _tasklist(monkeypatch, stdout="")
    with pytest.raises(writer.SteamRunningError):
        writer.assert_steam_not_running()


def test_a_missing_tasklist_binary_refuses_the_write(monkeypatch):
    _tasklist(monkeypatch, error=FileNotFoundError("tasklist"))
    with pytest.raises(writer.SteamRunningError):
        writer.assert_steam_not_running()


def test_a_good_listing_without_steam_lets_the_write_through(monkeypatch):
    _tasklist(monkeypatch, stdout='"explorer.exe","912"\n')
    writer.assert_steam_not_running()


def test_the_check_is_repeated_right_before_the_write(tmp_path, monkeypatch):
    """The CLI checks once, minutes before the artwork is downloaded: Steam may
    have started since."""
    monkeypatch.setattr(writer, "_running_processes", lambda: ["steam.exe"])
    target = tmp_path / "shortcuts.vdf"
    with pytest.raises(writer.SteamRunningError):
        writer.write_shortcuts(target, [])
    assert not target.exists()
