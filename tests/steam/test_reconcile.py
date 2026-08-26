"""Réconciliation entre la bibliothèque Steam et les ROMs présentes."""
import dataclasses

from retro.steam import entry, reconcile

EMU_ROOT = "D:\\Emulation"


def rom(titre, systeme="Super Nintendo", fichier=None):
    return entry.RomEntry(
        title=titre,
        rom_path=fichier or f"G:\\ROMs\\snes\\{titre}.sfc",
        system_name=systeme,
        emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
        launch_template='-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        start_dir="D:\\Emulation\\RetroArch",
    )


def etranger(nom):
    """Un jeu non-Steam ajouté à la main par le propriétaire."""
    return {
        "appid": 42,
        "appname": nom,
        "exe": '"C:\\Program Files\\SonJeu\\jeu.exe"',
        "StartDir": '"C:\\Program Files\\SonJeu"',
        "icon": "", "ShortcutPath": "", "LaunchOptions": "",
        "IsHidden": 0, "AllowDesktopConfig": 1, "AllowOverlay": 1,
        "OpenVR": 0, "Devkit": 0, "DevkitGameID": "",
        "DevkitOverrideAppID": 0, "LastPlayTime": 0,
        "tags": {"0": "Favoris"},
    }


def noms(entrees):
    return sorted(e["appname"] for e in entrees)


def test_creation_depuis_une_bibliotheque_vide():
    r = reconcile.reconcile([], [rom("Chrono Trigger")], EMU_ROOT)
    assert r.created == ["Chrono Trigger"]
    assert noms(r.entries) == ["Chrono Trigger"]


def test_rom_disparue_supprime_l_entree():
    existant = [entry.build_shortcut(rom("Chrono Trigger"))]
    r = reconcile.reconcile(existant, [], EMU_ROOT)
    assert r.removed == ["Chrono Trigger"]
    assert r.entries == []


def test_entree_etrangere_jamais_touchee():
    """La garantie centrale : les jeux du propriétaire survivent à tout."""
    existant = [etranger("Mon jeu à moi")]
    r = reconcile.reconcile(existant, [], EMU_ROOT)
    assert r.removed == []
    assert noms(r.entries) == ["Mon jeu à moi"]


def test_etranger_conserve_pendant_qu_on_cree_et_supprime():
    existant = [etranger("Mon jeu à moi"), entry.build_shortcut(rom("Ancien"))]
    r = reconcile.reconcile(existant, [rom("Nouveau")], EMU_ROOT)
    assert noms(r.entries) == ["Mon jeu à moi", "Nouveau"]
    assert r.created == ["Nouveau"]
    assert r.removed == ["Ancien"]


def test_idempotence():
    """Deuxième passage : rien à créer, rien à supprimer, fichier inchangé."""
    r1 = reconcile.reconcile([], [rom("Chrono Trigger")], EMU_ROOT)
    r2 = reconcile.reconcile(r1.entries, [rom("Chrono Trigger")], EMU_ROOT)
    assert r2.created == [] and r2.removed == []
    assert r2.entries == r1.entries


def test_tags_mis_a_jour_sur_entree_conservee():
    """Les métadonnées s'enrichissent avec le temps ; l'entrée doit suivre."""
    r1 = reconcile.reconcile([], [rom("Chrono Trigger")], EMU_ROOT)
    enrichie = dataclasses.replace(rom("Chrono Trigger"), extra_tags=("1995", "RPG"))
    r2 = reconcile.reconcile(r1.entries, [enrichie], EMU_ROOT)
    assert "RPG" in r2.entries[0]["tags"].values()
    assert r2.created == [] and r2.removed == []
    assert r2.kept == ["Chrono Trigger"]


def test_les_etrangers_gardent_leur_place_en_tete():
    """Steam renumérote, mais on ne réordonne pas gratuitement la bibliothèque."""
    existant = [etranger("A"), entry.build_shortcut(rom("B")), etranger("C")]
    r = reconcile.reconcile(existant, [rom("B")], EMU_ROOT)
    assert [e["appname"] for e in r.entries] == ["A", "B", "C"]


def test_appid_orphelin_signale_en_non_signe():
    """L'artwork est nommé d'après l'identifiant NON signé. Rendre le signé
    ferait chercher des fichiers qui n'existent pas, et l'artwork resterait."""
    existant = [entry.build_shortcut(rom("Chrono Trigger"))]
    r = reconcile.reconcile(existant, [], EMU_ROOT)
    assert r.orphaned_appids == [2398962978]


def test_renommer_un_jeu_orpheline_l_ancien_appid():
    """Le titre entre dans l'identifiant : le renommer en crée un autre."""
    r1 = reconcile.reconcile([], [rom("Chrono Trigger")], EMU_ROOT)
    ancien = reconcile.reconcile(r1.entries, [], EMU_ROOT).orphaned_appids
    r2 = reconcile.reconcile(r1.entries, [rom("Chrono Trigger (FR)")], EMU_ROOT)
    assert r2.orphaned_appids == ancien
    assert r2.created == ["Chrono Trigger (FR)"]


def test_doublons_dans_le_voulu_ne_creent_qu_une_entree():
    """Deux ROMs de même titre — régions différentes — ne peuvent pas coexister :
    leur identifiant serait identique et Steam n'en garderait qu'une."""
    r = reconcile.reconcile([], [rom("Sonic"), rom("Sonic")], EMU_ROOT)
    assert len(r.entries) == 1


def test_bibliotheque_vide_des_deux_cotes():
    r = reconcile.reconcile([], [], EMU_ROOT)
    assert r.entries == [] and r.created == [] and r.removed == []
