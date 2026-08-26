"""Un raccourci Steam construit depuis une ROM, et le test de propriété.

Le test de propriété est la seule chose qui empêche la réconciliation de
supprimer les jeux non-Steam que le propriétaire a ajoutés lui-même. Il exige
DEUX conditions, jamais une seule : le tag nous marque, le chemin nous confirme.
Le tag seul serait ambigu — « Rétro » est un tag que quelqu'un peut légitimement
poser sur son propre jeu.
"""
from __future__ import annotations

import dataclasses
import pathlib

from retro.steam import appid as appid_mod

OWNER_TAG = "Rétro"


@dataclasses.dataclass(frozen=True)
class RomEntry:
    """Tous les chemins sont des chaînes Windows.

    Surtout pas des pathlib.Path : sur Linux, où tournent les tests,
    Path("D:\\Emulation") est un chemin RELATIF nommé « D:\\Emulation », et
    toute comparaison qu'on en tirerait serait fausse.
    """
    title: str
    rom_path: str
    system_name: str
    emulator_exe: str
    launch_template: str
    start_dir: str
    extra_tags: tuple[str, ...] = ()


def quote(path: str) -> str:
    """Steam stocke les chemins entre guillemets, et calcule l'identifiant sur
    la forme guillemetée. Ne jamais les retirer avant de dériver."""
    return path if path.startswith('"') else f'"{path}"'


def build_shortcut(entry: RomEntry) -> dict:
    exe = quote(entry.emulator_exe)
    tags = [OWNER_TAG, entry.system_name, *entry.extra_tags]
    legacy = appid_mod.legacy_appid(exe, entry.title)
    return {
        "appid": appid_mod.to_signed(legacy),
        "appname": entry.title,
        "exe": exe,
        "StartDir": quote(entry.start_dir),
        "icon": "",
        "ShortcutPath": "",
        "LaunchOptions": entry.launch_template.replace("{rom}", entry.rom_path),
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": "",
        "DevkitOverrideAppID": 0,
        # Steam récent écrit ces deux champs : mesurés présents sur les 10
        # raccourcis de la fixture. Les omettre laisse Steam les recréer, mais
        # produit une différence de fichier à chaque synchronisation.
        "FlatpakAppID": "",
        "sortas": "",
        "LastPlayTime": 0,
        "tags": {str(i): t for i, t in enumerate(tags)},
    }


def exe_path(exe_field: str) -> str:
    """Le chemin de l'exécutable, dépouillé des arguments qui le suivent.

    Nous écrivons les arguments dans LaunchOptions, mais les raccourcis
    existants du propriétaire — mesurés sur une installation réelle — les
    portent DANS le champ exe. Un test de propriété qui ne le prévoit pas
    juge ces entrées d'après une chaîne qui n'est pas un chemin.
    """
    exe_field = exe_field.strip()
    if exe_field.startswith('"'):
        fin = exe_field.find('"', 1)
        if fin != -1:
            return exe_field[1:fin]
    return exe_field.split(" ", 1)[0]


def is_under_root(exe_field: str, emulation_root: str) -> bool:
    """La moitié « chemin » du test de propriété, isolée pour être réutilisable.

    La ligne de commande s'en sert pour vérifier AVANT d'écrire que la racine
    d'émulation qu'on lui a donnée contient bien les émulateurs de l'inventaire.
    Sans cette vérification, une racine erronée rend is_owned faux pour nos
    propres entrées : chaque passage les recrée sans les reconnaître.

    PureWindowsPath compare segment par segment et sans casse : « D:\EmulationAutre »
    n'est donc pas sous « D:\Emulation », alors qu'une comparaison de préfixe
    de chaîne l'aurait accepté à tort.
    """
    chemin = pathlib.PureWindowsPath(exe_path(exe_field))
    racine = pathlib.PureWindowsPath(emulation_root.strip('"'))
    return racine in chemin.parents


def is_owned(shortcut: dict, emulation_root: str) -> bool:
    """Vrai seulement si les DEUX conditions tiennent."""
    tags = shortcut.get("tags")
    if not isinstance(tags, dict) or OWNER_TAG not in tags.values():
        return False
    exe = shortcut.get("exe")
    if not exe:
        return False
    return is_under_root(exe, emulation_root)
