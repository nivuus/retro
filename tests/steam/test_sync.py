"""Synchronisation d'un compte, de bout en bout, sans Steam ni réseau."""
import pathlib

from retro.steam import accounts, artwork, entry, sync, vdf_io


class ArtworkMuet(artwork.ArtworkClient):
    def __init__(self):
        super().__init__(api_key=None)


def faire_compte(tmp_path):
    config = tmp_path / "userdata" / "123" / "config"
    config.mkdir(parents=True)
    return accounts.SteamAccount(account_id="123", config_dir=config)


def rom(titre):
    return entry.RomEntry(
        title=titre,
        rom_path=f"G:\\ROMs\\snes\\{titre}.sfc",
        system_name="Super Nintendo",
        emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
        launch_template='-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        start_dir="D:\\Emulation\\RetroArch",
    )


def test_synchronisation_depuis_zero(tmp_path):
    compte = faire_compte(tmp_path)
    rapport = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    assert rapport.created == ["Chrono Trigger"]
    assert [e["appname"] for e in vdf_io.load_shortcuts(compte.shortcuts_path)] == ["Chrono Trigger"]


def test_deuxieme_passage_ne_change_rien(tmp_path):
    compte = faire_compte(tmp_path)
    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    avant = compte.shortcuts_path.read_bytes()
    r2 = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    assert r2.created == [] and r2.removed == []
    assert compte.shortcuts_path.read_bytes() == avant


def test_le_rapport_est_lisible(tmp_path):
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    texte = sync.format_report([r])
    assert "Chrono Trigger" in texte and "123" in texte


def test_rapport_vide_le_dit(tmp_path):
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [], "D:\\Emulation", ArtworkMuet())
    assert "aucun" in sync.format_report([r]).lower()
