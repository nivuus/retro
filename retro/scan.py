"""Du disque du propriétaire à l'inventaire.

Le scan tourne sur la machine qui possède les ROMs, mais décrit une machine
Windows : les chemins de l'inventaire sont ceux que verra Steam, pas ceux du
système de fichiers qui scanne.
"""
from __future__ import annotations

import pathlib
import re

from retro.steam import entry

# Les conventions No-Intro et Redump : « Titre (Région) (Langues) [flags] ».
# Tout ce qui suit le titre est entre parenthèses ou crochets.
_PARENTHESES = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
# ... à une exception près : le marqueur de disque. Deux disques du même jeu
# donneraient sinon le même titre, donc le même identifiant Steam, et une
# seule entrée survivrait aux deux.
_DISQUE = re.compile(r"\((Disc|Disk|CD)\s+[^\)]*\)", re.IGNORECASE)


class ScanError(RuntimeError):
    """La racine des ROMs est inaccessible."""


def base_title(filename: str) -> str:
    """Le titre SANS son marqueur de disque.

    C'est la clé de regroupement : les trois disques d'un même jeu et le .m3u
    qui les rassemble ont tous le même titre de base.
    """
    tige = pathlib.PurePosixPath(filename).stem
    return _PARENTHESES.sub("", tige).strip()


def clean_title(filename: str) -> str:
    """Le titre affiché dans Steam, marqueur de disque compris.

    Le marqueur est CONSERVÉ : deux disques du même jeu donneraient sinon le
    même titre, donc le même identifiant Steam, et une seule entrée survivrait
    aux deux.
    """
    tige = pathlib.PurePosixPath(filename).stem
    m = _DISQUE.search(tige)
    if not m:
        return base_title(filename)
    sans_disque = tige[: m.start()] + tige[m.end():]
    return f"{_PARENTHESES.sub('', sans_disque).strip()} {m.group(0)}".strip()


def _systeme_par_dossier(profils):
    """Le nom du dossier désigne le système. Un même identifiant ne peut être
    servi que par un profil : le premier dans l'ordre alphabétique gagne, ce
    qui rend le résultat indépendant de l'ordre de chargement."""
    table = {}
    for pid in sorted(profils):
        for s in profils[pid].systems:
            table.setdefault(s.id, (pid, s))
    return table


def scan(roms_root: pathlib.Path, profils: dict, emulation_root: str,
         install_dirs: dict[str, str],
         roms_root_windows: str = "G:\\ROMs") -> list[entry.RomEntry]:
    if not roms_root.is_dir():
        raise ScanError(
            f"racine des ROMs introuvable : {roms_root}. Le partage est-il monté ?"
        )
    table = _systeme_par_dossier(profils)
    inventaire = []

    for dossier in sorted(p for p in roms_root.iterdir() if p.is_dir()):
        trouve = table.get(dossier.name)
        if not trouve:
            continue  # dossier qu'aucun profil ne couvre
        pid, systeme = trouve
        profil = profils[pid]
        exe = f"{emulation_root}\\{install_dirs[pid]}\\{profil.exe}"
        start_dir = f"{emulation_root}\\{install_dirs[pid]}"

        fichiers = sorted(f for f in dossier.iterdir()
                          if f.is_file() and f.suffix.lower() in
                          tuple(e.lower() for e in systeme.extensions))

        # Un .m3u regroupe les disques d'un même jeu. Lancer un disque isolé
        # alors qu'un .m3u existe est une erreur : le jeu réclamerait le disque
        # suivant sans pouvoir l'obtenir. Le titre de BASE est la clé de
        # regroupement — il ignore le marqueur de disque, que le titre affiché
        # conserve.
        titres_m3u = {base_title(f.name) for f in fichiers
                      if f.suffix.lower() == ".m3u"}
        for f in fichiers:
            if f.suffix.lower() != ".m3u" and base_title(f.name) in titres_m3u:
                continue
            inventaire.append(entry.RomEntry(
                title=clean_title(f.name),
                rom_path=f"{roms_root_windows}\\{dossier.name}\\{f.name}",
                system_name=systeme.name,
                emulator_exe=exe,
                launch_template=systeme.launch,
                start_dir=start_dir,
                extra_tags=(),
            ))
    return inventaire
