"""Réconciliation entre ce que Steam affiche et ce que le disque contient.

Fonction pure, sans effet de bord : elle prend l'existant et le voulu, elle
renvoie le résultat. Toute la logique délicate se teste ainsi sans Steam, sans
disque et sans réseau — et c'est précisément la logique qu'on n'a pas le droit
de rater, puisqu'elle SUPPRIME des entrées.

L'ordre des entrées conservées est préservé. Steam les renumérote de toute
façon, mais réordonner gratuitement la bibliothèque du propriétaire fabriquerait
une différence visible là où rien n'a changé.
"""
from __future__ import annotations

import dataclasses

from retro.steam import appid as appid_mod
from retro.steam import entry as entry_mod


@dataclasses.dataclass(frozen=True)
class ReconcileResult:
    entries: list[dict]
    created: list[str]
    removed: list[str]
    kept: list[str]
    orphaned_appids: list[int]  # NON signés : ce sont eux qui nomment l'artwork


def reconcile(
    existing: list[dict],
    wanted: list[entry_mod.RomEntry],
    emulation_root: str,
) -> ReconcileResult:
    # Les entrées voulues, indexées par identifiant. Un doublon de titre écrase :
    # deux ROMs de même titre produiraient le même identifiant et Steam n'en
    # garderait qu'une de toute façon.
    voulu: dict[int, dict] = {}
    for rom in wanted:
        raccourci = entry_mod.build_shortcut(rom)
        voulu[raccourci["appid"]] = raccourci

    sortie: list[dict] = []
    created: list[str] = []
    removed: list[str] = []
    kept: list[str] = []
    orphelins: list[int] = []
    vus: set[int] = set()

    for existante in existing:
        if not entry_mod.is_owned(existante, emulation_root):
            sortie.append(existante)          # jamais touchée
            continue
        cle = existante.get("appid")
        if cle in voulu:
            sortie.append(voulu[cle])         # remplacée : tags rafraîchis
            kept.append(voulu[cle]["appname"])
            vus.add(cle)
        else:
            removed.append(existante.get("appname", "?"))
            orphelins.append(appid_mod.to_unsigned(cle))

    for cle, raccourci in voulu.items():
        if cle not in vus:
            sortie.append(raccourci)
            created.append(raccourci["appname"])

    return ReconcileResult(
        entries=sortie,
        created=created,
        removed=removed,
        kept=kept,
        orphaned_appids=orphelins,
    )
