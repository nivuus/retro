"""Aller-retour sur shortcuts.vdf.

Steam relit ce fichier au démarrage. Une écriture qui perd un champ, change un
type d'entier ou casse l'UTF-8 corrompt la bibliothèque du propriétaire sans
rien signaler : Steam affiche simplement moins de jeux qu'avant.
"""
import pytest

from retro.steam import vdf_io

ENTRY = {
    "appid": -1896004318,
    "appname": "Chrono Trigger",
    "exe": '"D:\\Emulation\\RetroArch\\retroarch.exe"',
    "StartDir": '"D:\\Emulation\\RetroArch\\"',
    "icon": "",
    "ShortcutPath": "",
    "LaunchOptions": '-L "cores\\snes9x_libretro.dll" -f "G:\\ROMs\\snes\\ct.sfc"',
    "IsHidden": 0,
    "AllowDesktopConfig": 1,
    "AllowOverlay": 1,
    "OpenVR": 0,
    "Devkit": 0,
    "DevkitGameID": "",
    "DevkitOverrideAppID": 0,
    "LastPlayTime": 0,
    "tags": {"0": "Rétro", "1": "Super Nintendo"},
}


def test_aller_retour_preserve_tout():
    blob = vdf_io.dumps_shortcuts([ENTRY])
    assert vdf_io.loads_shortcuts(blob) == [ENTRY]


def test_appid_negatif_reste_negatif():
    """Le champ appid est un int32 signé. Un aller-retour qui le rendrait non
    signé produirait un identifiant que Steam n'associe à aucun artwork."""
    blob = vdf_io.dumps_shortcuts([ENTRY])
    assert vdf_io.loads_shortcuts(blob)[0]["appid"] == -1896004318


def test_utf8_survit():
    """Les titres rétro sont pleins d'accents et de caractères japonais."""
    entry = dict(ENTRY, appname="Pokémon Édition Rouge 赤")
    blob = vdf_io.dumps_shortcuts([entry])
    assert vdf_io.loads_shortcuts(blob)[0]["appname"] == "Pokémon Édition Rouge 赤"


def test_ordre_preserve():
    a = dict(ENTRY, appname="A")
    b = dict(ENTRY, appname="B")
    c = dict(ENTRY, appname="C")
    noms = [e["appname"] for e in vdf_io.loads_shortcuts(vdf_io.dumps_shortcuts([a, b, c]))]
    assert noms == ["A", "B", "C"]


def test_fichier_vide_donne_liste_vide(tmp_path):
    """Steam écrit un shortcuts.vdf ne contenant que la racine quand le
    propriétaire n'a aucun jeu non-Steam. Ce n'est pas une erreur."""
    p = tmp_path / "shortcuts.vdf"
    p.write_bytes(vdf_io.dumps_shortcuts([]))
    assert vdf_io.load_shortcuts(p) == []


def test_fichier_absent_donne_liste_vide(tmp_path):
    """Steam ne crée shortcuts.vdf qu'au premier raccourci ajouté."""
    assert vdf_io.load_shortcuts(tmp_path / "jamais-ecrit.vdf") == []


def test_blob_corrompu_leve_une_erreur_claire(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    p.write_bytes(b"ceci n'est pas du VDF binaire")
    with pytest.raises(vdf_io.ShortcutsError):
        vdf_io.load_shortcuts(p)
