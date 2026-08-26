"""Synchronisation d'un compte, de bout en bout, sans Steam ni réseau."""
import pathlib

from retro.steam import accounts, artwork, entry, sync, vdf_io


class ArtworkMuet(artwork.ArtworkClient):
    def __init__(self):
        super().__init__(api_key=None)


class ArtworkTemoin(artwork.ArtworkClient):
    """Observe l'état du monde au moment où l'artwork est demandé.

    ArtworkMuet ne peut rien attester : il rend [] sans regarder ni le disque ni
    l'entrée. Mesuré — avec lui seul, inverser l'ordre artwork/écriture ou
    retirer le filtre de propriété laisse toute la suite verte.
    """

    def __init__(self, shortcuts_path):
        super().__init__(api_key=None)
        self.shortcuts_path = shortcuts_path
        self.appels = []

    def fetch_for(self, title, legacy_appid, grid_dir):
        self.appels.append((title, self.shortcuts_path.exists()))
        return []


def faire_compte(tmp_path):
    config = tmp_path / "userdata" / "123" / "config"
    config.mkdir(parents=True)
    return accounts.SteamAccount(account_id="123", config_dir=config)


def etranger(nom):
    """Un jeu non-Steam que le propriétaire a ajouté lui-même."""
    return {
        "appid": 42, "appname": nom, "exe": '"C:\\Jeux\\perso.exe"',
        "StartDir": '"C:\\Jeux"', "icon": "", "ShortcutPath": "",
        "LaunchOptions": "", "IsHidden": 0, "AllowDesktopConfig": 1,
        "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0, "DevkitGameID": "",
        "DevkitOverrideAppID": 0, "FlatpakAppID": "", "sortas": "",
        "LastPlayTime": 0, "tags": {"0": "Favoris"},
    }


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


def test_l_artwork_est_recupere_avant_l_ecriture(tmp_path):
    """Un jeu sans vignette vaut mieux qu'une vignette sans jeu : une panne
    d'artwork ne doit pas empêcher les raccourcis d'être écrits. Le témoin
    observe que shortcuts.vdf n'existe pas encore quand l'artwork est demandé."""
    compte = faire_compte(tmp_path)
    client = ArtworkTemoin(compte.shortcuts_path)
    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", client)
    assert client.appels, "l'artwork n'a jamais été demandé"
    assert all(not existait for _, existait in client.appels), (
        "shortcuts.vdf existait déjà : l'écriture a précédé l'artwork"
    )


def test_l_artwork_n_est_demande_que_pour_nos_entrees(tmp_path):
    """Chercher de l'artwork pour les jeux du propriétaire écraserait le sien."""
    compte = faire_compte(tmp_path)
    compte.shortcuts_path.write_bytes(vdf_io.dumps_shortcuts([etranger("Mon jeu à moi")]))
    client = ArtworkTemoin(compte.shortcuts_path)
    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", client)
    assert [t for t, _ in client.appels] == ["Chrono Trigger"]


def test_le_rapport_est_lisible(tmp_path):
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    texte = sync.format_report([r])
    assert "Chrono Trigger" in texte and "123" in texte


def test_rapport_vide_le_dit(tmp_path):
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [], "D:\\Emulation", ArtworkMuet())
    assert "aucun" in sync.format_report([r]).lower()
