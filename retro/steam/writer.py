"""Écriture de shortcuts.vdf.

Deux protections, et les deux sont là parce que leur absence produit un échec
MUET : Steam réécrit le fichier à sa fermeture, donc écrire pendant qu'il tourne
perd le travail sans rien dire ; et une écriture interrompue en place laisserait
une bibliothèque tronquée que Steam accepterait sans broncher.
"""
from __future__ import annotations

import datetime
import os
import pathlib
import subprocess

from retro.steam import vdf_io

# steamwebhelper.exe survit quelques secondes à la fermeture de Steam. Le
# compter pour Steam bloquerait la synchronisation sans raison, donc la
# correspondance est exacte, pas un préfixe.
STEAM_PROCESS_NAMES = {"steam.exe", "steam"}


class SteamRunningError(RuntimeError):
    """Steam tourne : écrire maintenant serait écrasé à sa fermeture."""


def _running_processes() -> list[str]:
    """Sous Windows uniquement. Ailleurs, la liste est vide : les tests et le
    développement sous Linux n'ont pas de Steam à surveiller."""
    if os.name != "nt":
        return []
    sortie = subprocess.run(
        ["tasklist", "/fo", "csv", "/nh"],
        capture_output=True, text=True, check=False,
    ).stdout
    return [ligne.split('","')[0].strip('"') for ligne in sortie.splitlines() if ligne]


def steam_is_running(processes: list[str] | None = None) -> bool:
    noms = _running_processes() if processes is None else processes
    return any(n.lower() in STEAM_PROCESS_NAMES for n in noms)


def assert_steam_not_running() -> None:
    if steam_is_running():
        raise SteamRunningError(
            "Steam est en cours d'exécution : il réécrirait shortcuts.vdf à sa "
            "fermeture et la synchronisation serait perdue. Fermer Steam d'abord."
        )


def write_shortcuts(path: pathlib.Path, entries: list[dict]) -> pathlib.Path | None:
    """Écriture atomique. Renvoie le chemin de la sauvegarde, ou None."""
    # Rendre AVANT de toucher au disque : un rendu qui échoue ne doit pas
    # laisser un fichier à moitié écrit ni une sauvegarde orpheline.
    blob = vdf_io.dumps_shortcuts(entries)

    sauvegarde = None
    if path.exists():
        horodatage = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        sauvegarde = path.with_suffix(f".vdf.bak-{horodatage}")
        sauvegarde.write_bytes(path.read_bytes())

    temporaire = path.with_suffix(".vdf.tmp")
    temporaire.write_bytes(blob)
    os.replace(temporaire, path)  # atomique sur Windows comme sur POSIX
    return sauvegarde
