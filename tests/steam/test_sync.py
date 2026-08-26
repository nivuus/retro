"""Synchronisation d'un compte, de bout en bout, sans Steam ni réseau."""
import pathlib

from retro.steam import accounts, appid, artwork, entry, sync, vdf_io


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


def test_l_entree_etrangere_est_relue_dans_le_fichier_ecrit(tmp_path):
    """La garantie centrale, vérifiée AU NIVEAU DE L'ÉCRITURE.

    reconcile est couvert, mais rien ne relisait shortcuts.vdf après
    sync_account. Mesuré — filtrer les entrées étrangères juste avant
    write_shortcuts, c'est-à-dire effacer les jeux réels du propriétaire,
    laissait toute la suite verte.
    """
    compte = faire_compte(tmp_path)
    mien = etranger("Mon jeu à moi")
    compte.shortcuts_path.write_bytes(vdf_io.dumps_shortcuts([mien]))

    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())

    relu = vdf_io.load_shortcuts(compte.shortcuts_path)
    assert [e["appname"] for e in relu] == ["Mon jeu à moi", "Chrono Trigger"]
    assert relu[0] == mien, "l'entrée étrangère a été modifiée, pas seulement conservée"


class ArtworkEnPanne(artwork.ArtworkClient):
    """Clé d'API expirée : fetch_for avale l'exception et rend [].

    Indiscernable, du point de vue du rapport, d'une bibliothèque déjà
    complète — sauf si le rapport dit combien d'assets manquent encore.
    """

    def __init__(self):
        super().__init__(api_key="cle-expiree")

    def fetch_for(self, title, legacy_appid, grid_dir):
        return []


class ArtworkComplet(artwork.ArtworkClient):
    """Récupère les cinq assets, comme une clé valide un jour de beau temps."""

    def __init__(self):
        super().__init__(api_key="cle-valide")

    def fetch_for(self, title, legacy_appid, grid_dir):
        grid_dir.mkdir(parents=True, exist_ok=True)
        noms = [f"{p}.png" for p in appid.grid_prefixes(legacy_appid).values()]
        for nom in noms:
            (grid_dir / nom).write_bytes(b"\xff\xd8\xff")
        return noms


def test_une_panne_d_artwork_se_voit_dans_le_rapport(tmp_path):
    """« 0 récupéré(s) » disait la même chose pour une bibliothèque complète et
    pour une clé d'API expirée. Le second cas ne se répare jamais tout seul."""
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkEnPanne())
    assert r.artwork_missing == 5
    assert "5 manquant(s)" in sync.format_report([r])


def test_une_panne_d_artwork_ne_bloque_pas_la_synchronisation(tmp_path):
    """On signale, on ne bloque pas : les raccourcis sont écrits quand même."""
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkEnPanne())
    assert r.created == ["Chrono Trigger"]
    assert vdf_io.load_shortcuts(compte.shortcuts_path)


def test_artwork_complet_ne_signale_rien_de_manquant(tmp_path):
    """Sans ce test, un compteur bloqué sur une constante passerait le test
    de la panne."""
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkComplet())
    assert r.artwork_written == 5 and r.artwork_missing == 0
    assert "0 manquant(s)" in sync.format_report([r])
