"""Synchronisation d'un compte Steam."""
from __future__ import annotations

import dataclasses
import pathlib

from retro.steam import appid as appid_mod
from retro.steam import accounts, artwork, entry, reconcile, vdf_io, writer


@dataclasses.dataclass(frozen=True)
class SyncReport:
    account_id: str
    created: list[str]
    removed: list[str]
    kept: list[str]
    artwork_written: int
    artwork_pruned: int
    backup: pathlib.Path | None


def sync_account(
    account: accounts.SteamAccount,
    wanted: list[entry.RomEntry],
    emulation_root: str,
    artwork_client,
) -> SyncReport:
    existant = vdf_io.load_shortcuts(account.shortcuts_path)
    resultat = reconcile.reconcile(existant, wanted, emulation_root)

    # L'artwork AVANT l'écriture : un jeu sans vignette vaut mieux qu'une
    # vignette sans jeu, et une panne réseau ne doit pas empêcher l'écriture.
    ecrits = 0
    for raccourci in resultat.entries:
        if not entry.is_owned(raccourci, emulation_root):
            continue
        legacy = appid_mod.to_unsigned(raccourci["appid"])
        ecrits += len(artwork_client.fetch_for(raccourci["appname"], legacy, account.grid_dir))

    purges = len(artwork.prune_orphans(account.grid_dir, resultat.orphaned_appids))

    sauvegarde = writer.write_shortcuts(account.shortcuts_path, resultat.entries)
    return SyncReport(
        account_id=account.account_id,
        created=resultat.created,
        removed=resultat.removed,
        kept=resultat.kept,
        artwork_written=ecrits,
        artwork_pruned=purges,
        backup=sauvegarde,
    )


def format_report(reports: list[SyncReport]) -> str:
    lignes = []
    for r in reports:
        lignes.append(f"Compte {r.account_id}")
        if not r.created and not r.removed:
            lignes.append(f"  aucun changement ({len(r.kept)} jeux déjà à jour)")
        for titre in r.created:
            lignes.append(f"  + {titre}")
        for titre in r.removed:
            lignes.append(f"  - {titre}")
        lignes.append(
            f"  artwork : {r.artwork_written} récupéré(s), {r.artwork_pruned} purgé(s)"
        )
        if r.backup:
            lignes.append(f"  sauvegarde : {r.backup.name}")
    return "\n".join(lignes)
