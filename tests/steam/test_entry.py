"""Construction d'un raccourci et test de propriété."""
import pathlib

import pytest

from retro.steam import appid, entry, vdf_io

EMU_ROOT = "D:\\Emulation"
FIXTURE = pathlib.Path(__file__).parent.parent / "fixtures" / "shortcuts-reel.vdf"
REELS = vdf_io.load_shortcuts(FIXTURE)

ROM = entry.RomEntry(
    title="Chrono Trigger",
    rom_path="G:\\ROMs\\snes\\Chrono Trigger.sfc",
    system_name="Super Nintendo",
    emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
    launch_template='-L "cores\\snes9x_libretro.dll" -f "{rom}"',
    start_dir="D:\\Emulation\\RetroArch",
    extra_tags=("1995", "RPG"),
)


def test_les_champs_obligatoires_sont_presents():
    s = entry.build_shortcut(ROM)
    attendus = {
        "appid", "appname", "exe", "StartDir", "icon", "ShortcutPath",
        "LaunchOptions", "IsHidden", "AllowDesktopConfig", "AllowOverlay",
        "OpenVR", "Devkit", "DevkitGameID", "DevkitOverrideAppID",
        "LastPlayTime", "tags", "FlatpakAppID", "sortas",
    }
    assert attendus <= set(s)


def test_le_chemin_de_rom_est_substitue():
    s = entry.build_shortcut(ROM)
    assert "G:\\ROMs\\snes\\Chrono Trigger.sfc" in s["LaunchOptions"]
    assert "{rom}" not in s["LaunchOptions"]


def test_les_chemins_sont_entre_guillemets():
    """Sans guillemets, un chemin contenant une espace casse au lancement."""
    s = entry.build_shortcut(ROM)
    assert s["exe"].startswith('"') and s["exe"].endswith('"')
    assert s["StartDir"].startswith('"')


def test_le_tag_de_propriete_vient_en_premier():
    s = entry.build_shortcut(ROM)
    assert s["tags"]["0"] == entry.OWNER_TAG


def test_les_tags_contiennent_systeme_et_extras():
    s = entry.build_shortcut(ROM)
    valeurs = set(s["tags"].values())
    assert {"Rétro", "Super Nintendo", "1995", "RPG"} == valeurs


def test_les_tags_sont_indexes_consecutivement():
    s = entry.build_shortcut(ROM)
    assert sorted(s["tags"], key=int) == ["0", "1", "2", "3"]


def test_l_appid_correspond_a_la_derivation():
    s = entry.build_shortcut(ROM)
    attendu = appid.to_signed(appid.legacy_appid(s["exe"], s["appname"]))
    assert s["appid"] == attendu


def test_construction_deterministe():
    """Deux constructions de la même ROM doivent être identiques, sinon chaque
    synchronisation réécrirait le fichier pour rien."""
    assert entry.build_shortcut(ROM) == entry.build_shortcut(ROM)


# --- propriété ---

def test_notre_entree_est_reconnue():
    assert entry.is_owned(entry.build_shortcut(ROM), EMU_ROOT)


def test_jeu_du_proprietaire_sans_tag_est_etranger():
    """Un jeu ajouté à la main, même sous D:\\Emulation, ne nous appartient pas."""
    s = entry.build_shortcut(ROM)
    s["tags"] = {"0": "Favoris"}
    assert not entry.is_owned(s, EMU_ROOT)


def test_tag_present_mais_hors_arborescence_est_etranger():
    """Le propriétaire a le droit de taguer un de ses jeux « Rétro »."""
    s = entry.build_shortcut(ROM)
    s["exe"] = '"C:\\Program Files\\SonJeu\\jeu.exe"'
    assert not entry.is_owned(s, EMU_ROOT)


def test_propriete_insensible_a_la_casse_du_chemin():
    """Windows ne distingue pas d:\\emulation de D:\\Emulation."""
    s = entry.build_shortcut(ROM)
    s["exe"] = '"d:\\emulation\\RetroArch\\retroarch.exe"'
    assert entry.is_owned(s, EMU_ROOT)


def test_prefixe_trompeur_rejete():
    """D:\\EmulationAutre n'est pas sous D:\\Emulation, malgré le préfixe commun."""
    s = entry.build_shortcut(ROM)
    s["exe"] = '"D:\\EmulationAutre\\truc.exe"'
    assert not entry.is_owned(s, EMU_ROOT)


def test_entree_sans_champ_tags_est_etrangere():
    """Un shortcuts.vdf écrit par un outil tiers peut omettre le champ."""
    s = entry.build_shortcut(ROM)
    del s["tags"]
    assert not entry.is_owned(s, EMU_ROOT)


def test_entree_sans_champ_exe_est_etrangere():
    s = entry.build_shortcut(ROM)
    del s["exe"]
    assert not entry.is_owned(s, EMU_ROOT)


def test_exe_portant_ses_arguments_est_reconnu():
    """Les raccourcis existants du propriétaire mettent les arguments DANS exe."""
    s = entry.build_shortcut(ROM)
    s["exe"] = '"D:\\Emulation\\RetroArch\\retroarch.exe" -L core.dll "G:\\ROMs\\x.sfc"'
    assert entry.is_owned(s, EMU_ROOT)


def test_exe_sans_guillemets_avec_arguments():
    s = entry.build_shortcut(ROM)
    s["exe"] = "D:\\Emulation\\RetroArch\\retroarch.exe -f"
    assert entry.is_owned(s, EMU_ROOT)


def test_les_champs_recents_de_steam_sont_ecrits():
    s = entry.build_shortcut(ROM)
    assert s["FlatpakAppID"] == "" and s["sortas"] == ""


# --- propriété, éprouvée contre l'installation réelle ---

@pytest.mark.parametrize("raccourci", REELS, ids=lambda r: r["appname"])
def test_aucun_raccourci_reel_ne_nous_appartient(raccourci):
    """Le scénario que la double condition existe pour couvrir, sur du réel.

    Huit des dix raccourcis mesurés ont leur exe sous D:\\Emulation : seule la
    condition de tag les sauve. Jusqu'ici, ce cas n'était testé que sur des
    entrées synthétiques fabriquées par build_shortcut.
    """
    assert not entry.is_owned(raccourci, EMU_ROOT)


def test_la_fixture_met_bien_la_condition_de_tag_a_l_epreuve():
    """Sans cette garde, une fixture dont aucun exe ne vit sous la racine ferait
    passer le test ci-dessus sans jamais éprouver la condition de tag."""
    sous_racine = [r for r in REELS if entry.is_under_root(r["exe"], EMU_ROOT)]
    assert len(sous_racine) >= 8, [r["exe"] for r in REELS]
