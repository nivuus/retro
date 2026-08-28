"""Synchronisation d'un compte, de bout en bout, sans Steam ni réseau."""
import pathlib

from retro.steam import accounts, appid, artwork, entry, steam_input, sync, vdf_io


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


# --- champ icon ---

def test_icone_renseignee_quand_le_fichier_existe_et_la_racine_est_fournie(tmp_path):
    """Mesuré sur une installation réelle : le champ icon des raccourcis
    d'émulateurs porte un chemin absolu vers <grid_dir_windows>\\<appid>_icon.png."""
    compte = faire_compte(tmp_path)
    grid_windows = "D:\\Steam\\userdata\\123\\config\\grid"
    sync.sync_account(
        compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkComplet(),
        grid_dir_windows=grid_windows,
    )
    relu = vdf_io.load_shortcuts(compte.shortcuts_path)
    assert len(relu) == 1
    legacy = appid.to_unsigned(relu[0]["appid"])
    nom_attendu = f"{legacy}_icon.png"
    assert relu[0]["icon"] == f"{grid_windows}\\{nom_attendu}"


def test_icone_vide_sans_racine_windows(tmp_path):
    """Par défaut, grid_dir_windows est None : le champ icon reste vide, même
    quand l'artwork a été récupéré."""
    compte = faire_compte(tmp_path)
    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkComplet())
    relu = vdf_io.load_shortcuts(compte.shortcuts_path)
    assert relu[0]["icon"] == ""


def test_icone_vide_quand_le_fichier_manque(tmp_path):
    """La racine Windows est fournie, mais l'artwork n'a pas pu être récupéré :
    rien à référencer, le champ reste vide."""
    compte = faire_compte(tmp_path)
    sync.sync_account(
        compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkEnPanne(),
        grid_dir_windows="D:\\Steam\\userdata\\123\\config\\grid",
    )
    relu = vdf_io.load_shortcuts(compte.shortcuts_path)
    assert relu[0]["icon"] == ""


def test_la_racine_de_grille_terminee_par_un_antislash_est_normalisee(tmp_path):
    """« ...\\grid\\ » et « ...\\grid » doivent donner le même champ icon.

    Windows tolère l'antislash doublé hors préfixe UNC, donc ce n'est pas un
    défaut fonctionnel — mais le champ icon est comparé tel quel d'une
    synchronisation à l'autre, et deux écritures d'un même chemin sous deux
    formes sont une différence de fichier gratuite.
    """
    compte = faire_compte(tmp_path)
    sync.sync_account(
        compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkComplet(),
        grid_dir_windows="D:\\Steam\\userdata\\123\\config\\grid\\",
    )
    relu = vdf_io.load_shortcuts(compte.shortcuts_path)
    legacy = appid.to_unsigned(relu[0]["appid"])
    assert relu[0]["icon"] == (
        f"D:\\Steam\\userdata\\123\\config\\grid\\{legacy}_icon.png")


def test_un_seul_jeu_deja_a_jour_s_accorde_au_singulier(tmp_path):
    """« 1 jeux déjà à jour » : même famille que le « 1 jeux » du rapport de
    `retro status`."""
    compte = faire_compte(tmp_path)
    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    r = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    texte = sync.format_report([r])
    assert "1 jeu déjà à jour" in texte
    assert "1 jeux" not in texte


# --- Steam Input -------------------------------------------------------------
#
# Steam Input masque la manette a l'emulateur : mesure sur la console le
# 2026-08-28, et la seule prise est un reglage par jeu dans localconfig.vdf.
# Une bibliotheque ne se regle pas jeu par jeu a la main.

LOCALCONFIG_VIDE = '"UserLocalConfigStore"\n{\n\t"apps"\n\t{\n\t}\n}\n'


def _poser_localconfig(compte, contenu=LOCALCONFIG_VIDE):
    compte.localconfig_path.write_text(contenu, encoding="utf-8")


def test_desactive_steam_input_sur_les_jeux_ecrits(tmp_path):
    compte = faire_compte(tmp_path)
    _poser_localconfig(compte)

    rapport = sync.sync_account(
        compte, [rom("Jeu")], "D:\\Emulation", ArtworkMuet())

    ecrits = vdf_io.load_shortcuts(compte.shortcuts_path)
    assert steam_input.actifs(compte.localconfig_path,
                              [e["appid"] for e in ecrits]) == []
    assert rapport.steam_input_disabled == 1


def test_ne_touche_pas_a_steam_input_des_jeux_etrangers(tmp_path):
    """Le fichier appartient au proprietaire : on n'y regle que NOS entrees."""
    compte = faire_compte(tmp_path)
    _poser_localconfig(compte)
    compte.shortcuts_path.write_bytes(vdf_io.dumps_shortcuts([etranger("Perso")]))

    sync.sync_account(compte, [rom("Jeu")], "D:\\Emulation", ArtworkMuet())

    assert steam_input.etats(compte.localconfig_path).get(42) is None


def test_une_seconde_synchronisation_ne_reecrit_pas_localconfig(tmp_path):
    """Sans cela, chaque passage deposerait une sauvegarde de plus."""
    compte = faire_compte(tmp_path)
    _poser_localconfig(compte)
    sync.sync_account(compte, [rom("Jeu")], "D:\\Emulation", ArtworkMuet())
    avant = compte.localconfig_path.read_text(encoding="utf-8")

    rapport = sync.sync_account(compte, [rom("Jeu")], "D:\\Emulation", ArtworkMuet())

    assert compte.localconfig_path.read_text(encoding="utf-8") == avant
    assert rapport.steam_input_disabled == 0


def test_un_localconfig_absent_est_signale_sans_bloquer_la_synchro(tmp_path):
    """Les raccourcis sont le coeur du travail : ils s'ecrivent quand meme.

    Mais le dire, car une manette muette ne se diagnostique pas depuis un
    canape — c'est exactement la panne qui a coute une matinee le 2026-08-28."""
    compte = faire_compte(tmp_path)  # pas de localconfig.vdf

    rapport = sync.sync_account(
        compte, [rom("Jeu")], "D:\\Emulation", ArtworkMuet())

    assert len(vdf_io.load_shortcuts(compte.shortcuts_path)) == 1
    assert rapport.steam_input_disabled == 0
    assert "localconfig.vdf" in rapport.steam_input_error


def test_le_rapport_nomme_steam_input(tmp_path):
    compte = faire_compte(tmp_path)
    _poser_localconfig(compte)
    rapport = sync.sync_account(compte, [rom("Jeu")], "D:\\Emulation", ArtworkMuet())
    assert "Steam Input" in sync.format_report([rapport])
