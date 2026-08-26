"""Installer tous les émulateurs du manifeste.

Un émulateur dont l'URL est morte ne doit pas priver le propriétaire des neuf
autres : chaque échec est capturé, rapporté, et l'installation continue. Ce
qu'on ne fait jamais, c'est le taire.
"""
from __future__ import annotations

import pathlib

from retro import acquire


def install_all(manifeste: dict, emulation_root: pathlib.Path,
                fetch=acquire._fetch) -> list[tuple[str, str]]:
    resultats = []
    for cle in sorted(manifeste):
        try:
            etat = acquire.acquire(manifeste[cle], emulation_root, fetch=fetch)
        except acquire.AcquireError as exc:
            etat = f"ÉCHEC : {exc}"
        resultats.append((cle, etat))
    return resultats


def format_install_report(resultats: list[tuple[str, str]]) -> str:
    lignes = []
    for cle, etat in resultats:
        marque = "!" if etat.startswith("ÉCHEC") else "·"
        lignes.append(f"  {marque} {cle} : {etat}")
    echecs = [c for c, e in resultats if e.startswith("ÉCHEC")]
    if echecs:
        lignes.append(f"  {len(echecs)} émulateur(s) non installé(s) : "
                      f"{', '.join(echecs)}")
    return "\n".join(lignes)
