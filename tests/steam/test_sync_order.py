"""The artwork of removed shortcuts is pruned only once the removal is written."""
import pytest

from retro.steam import appid, entry, sync, vdf_io, writer
from tests.steam.test_sync import ArtworkMuet, faire_compte, rom

ROOT = "D:\\Emulation"


def _grid_files(account, rom_entry):
    legacy = appid.to_unsigned(entry.build_shortcut(rom_entry)["appid"])
    paths = []
    account.grid_dir.mkdir(parents=True, exist_ok=True)
    for prefix in appid.grid_prefixes(legacy).values():
        p = account.grid_dir / f"{prefix}.png"
        p.write_bytes(b"png")
        paths.append(p)
    return paths


def test_artwork_survives_a_failed_shortcuts_write(tmp_path, monkeypatch):
    account = faire_compte(tmp_path)
    game = rom("Chrono Trigger")
    sync.sync_account(account, [game], ROOT, ArtworkMuet())
    files = _grid_files(account, game)

    def disk_full(*args, **kwargs):
        raise writer.BackupError("disk full")
    monkeypatch.setattr(writer, "write_shortcuts", disk_full)

    # The game left the inventory: its shortcut stays in shortcuts.vdf
    # because the write fails, so its artwork must stay too.
    with pytest.raises(writer.BackupError):
        sync.sync_account(account, [], ROOT, ArtworkMuet())
    assert all(p.exists() for p in files)
    assert len(vdf_io.load_shortcuts(account.shortcuts_path)) == 1


def test_artwork_of_a_removed_shortcut_is_pruned_after_a_good_write(tmp_path):
    account = faire_compte(tmp_path)
    game = rom("Chrono Trigger")
    sync.sync_account(account, [game], ROOT, ArtworkMuet())
    files = _grid_files(account, game)
    report = sync.sync_account(account, [], ROOT, ArtworkMuet())
    assert report.artwork_pruned == len(files)
    assert not any(p.exists() for p in files)
