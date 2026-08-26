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

# Borne du suffixe de désambiguïsation des sauvegardes. Au-delà, c'est que
# quelque chose ne va pas : mieux vaut le dire que boucler.
_MAX_SAUVEGARDES = 1000


class SteamRunningError(RuntimeError):
    """Steam tourne : écrire maintenant serait écrasé à sa fermeture."""


class BackupError(RuntimeError):
    """Aucun chemin de sauvegarde libre : on n'écrit pas sans filet."""


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


def _horodatage() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _sauvegarder(path: pathlib.Path) -> pathlib.Path:
    """Copie ``path`` vers un `.bak` horodaté, sans jamais en écraser un.

    L'horodatage a une résolution d'une seconde : deux écritures rapprochées
    visent le même nom. Sans le suffixe de désambiguïsation, la seconde
    détruisait la première tout en rendant un chemin qui avait l'air d'une
    sauvegarde fraîche — le seul filet du paquet détruisant ce qu'il protège.

    La création est EXCLUSIVE ("xb") plutôt qu'un simple test d'existence :
    entre le test et l'écriture, un autre processus peut prendre le nom.
    """
    contenu = path.read_bytes()
    base = path.with_suffix(f".vdf.bak-{_horodatage()}")
    for n in range(_MAX_SAUVEGARDES):
        candidat = base if n == 0 else base.with_name(f"{base.name}-{n}")
        try:
            with open(candidat, "xb") as f:
                f.write(contenu)
        except FileExistsError:
            continue
        return candidat
    raise BackupError(
        f"impossible de sauvegarder {path.name} : {_MAX_SAUVEGARDES} chemins "
        f"déjà pris autour de {base.name}. Faire du ménage avant de réessayer."
    )


def write_shortcuts(path: pathlib.Path, entries: list[dict]) -> pathlib.Path | None:
    """Écriture atomique. Renvoie le chemin de la sauvegarde, ou None.

    Une écriture dont le contenu est déjà celui du fichier ne fait rien : ni
    sauvegarde, ni réécriture. C'est ce qui évite qu'une synchronisation sans
    changement accumule un `.bak` de plus à chaque passage, indéfiniment.
    """
    # Rendre AVANT de toucher au disque : un rendu qui échoue ne doit pas
    # laisser un fichier à moitié écrit ni une sauvegarde orpheline.
    blob = vdf_io.dumps_shortcuts(entries)

    existe = path.exists()
    if existe and path.read_bytes() == blob:
        return None

    sauvegarde = _sauvegarder(path) if existe else None

    temporaire = path.with_suffix(".vdf.tmp")
    temporaire.write_bytes(blob)
    os.replace(temporaire, path)  # atomique sur Windows comme sur POSIX
    return sauvegarde
