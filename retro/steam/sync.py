"""Synchronisation d'un compte Steam."""
from __future__ import annotations

import dataclasses
import pathlib

from retro.steam import appid as appid_mod
from retro.steam import accounts, artwork, entry, reconcile, steam_input, vdf_io, writer


@dataclasses.dataclass(frozen=True)
class SyncReport:
    account_id: str
    created: list[str]
    removed: list[str]
    kept: list[str]
    artwork_written: int
    artwork_pruned: int
    artwork_missing: int
    backup: pathlib.Path | None
    # Le premier échec d'artwork rencontré, ou "". Un seul suffit : ils se
    # répètent d'une synchronisation à l'autre, et le nommer est ce qui
    # distingue « rien à faire » de « quelque chose ne marche pas ».
    artwork_error: str = ""
    # Combien de jeux ont eu Steam Input éteint lors de ce passage. Zéro est le
    # cas normal d'une synchronisation qui n'ajoute rien : le réglage tient.
    steam_input_disabled: int = 0
    # Ce qui a empêché d'y toucher, ou "". Signalé plutôt que levé : les
    # raccourcis sont le cœur du travail et ils sont déjà écrits — mais une
    # manette muette ne se diagnostique pas depuis un canapé, donc ça se dit.
    steam_input_error: str = ""


def sync_account(
    account: accounts.SteamAccount,
    wanted: list[entry.RomEntry],
    emulation_root: str,
    artwork_client,
    grid_dir_windows: str | None = None,
) -> SyncReport:
    # L'antislash final est retiré une fois pour toutes : « ...\\grid\\ » et
    # « ...\\grid » doivent produire le MÊME champ icon, sinon deux écritures
    # d'un même chemin sous deux formes font une différence de fichier
    # gratuite à chaque synchronisation.
    grille = grid_dir_windows.rstrip("\\") if grid_dir_windows is not None else None

    existant = vdf_io.load_shortcuts(account.shortcuts_path)
    resultat = reconcile.reconcile(existant, wanted, emulation_root)

    # L'artwork AVANT l'écriture : un jeu sans vignette vaut mieux qu'une
    # vignette sans jeu, et une panne réseau ne doit pas empêcher l'écriture.
    ecrits = 0
    manquants = 0
    for raccourci in resultat.entries:
        if not entry.is_owned(raccourci, emulation_root):
            continue
        legacy = appid_mod.to_unsigned(raccourci["appid"])
        ecrits += len(artwork_client.fetch_for(raccourci["appname"], legacy, account.grid_dir))
        # Compté APRÈS le passage : ce qui manque encore est ce qu'une panne a
        # laissé derrière elle. On le signale, on ne bloque pas.
        manquants += len(artwork.missing_assets(account.grid_dir, legacy))
        # Le champ icon est renseigné dans ce même passage, pas avant : il lui
        # faut le résultat du fetch qui précède. Il ne participe jamais au
        # calcul de l'identifiant (appid), qui reste dérivé de (exe, appname)
        # seul — sinon tout l'artwork déjà déposé deviendrait orphelin d'un
        # coup, sur toute la bibliothèque, dès qu'une icône serait renseignée.
        if grille is not None:
            prefixe = appid_mod.grid_prefixes(legacy)["icone"]
            fichier = appid_mod.existing_asset(account.grid_dir, prefixe)
            if fichier is not None:
                raccourci["icon"] = f"{grille}\\{fichier.name}"

    purges = len(artwork.prune_orphans(account.grid_dir, resultat.orphaned_appids))

    sauvegarde = writer.write_shortcuts(account.shortcuts_path, resultat.entries)

    # Steam Input APRÈS l'écriture des raccourcis, et sans pouvoir la faire
    # échouer : une bibliothèque écrite dont les manettes restent à régler vaut
    # mieux qu'une synchronisation qui abandonne tout parce qu'un fichier
    # voisin manque.
    #
    # Seules NOS entrées : localconfig.vdf porte les réglages du propriétaire,
    # et ses jeux à lui ne nous regardent pas.
    notres = [r["appid"] for r in resultat.entries
              if entry.is_owned(r, emulation_root)]
    eteints, echec = 0, ""
    try:
        a_regler = steam_input.actifs(account.localconfig_path, notres)
        if a_regler:
            steam_input.desactiver(account.localconfig_path, a_regler)
            eteints = len(a_regler)
    except steam_input.LocalConfigError as exc:
        echec = str(exc)

    return SyncReport(
        account_id=account.account_id,
        created=resultat.created,
        removed=resultat.removed,
        kept=resultat.kept,
        artwork_written=ecrits,
        artwork_missing=manquants,
        artwork_error=(artwork_client.erreurs[0]
                       if getattr(artwork_client, "erreurs", None) else ""),
        artwork_pruned=purges,
        backup=sauvegarde,
        steam_input_disabled=eteints,
        steam_input_error=echec,
    )


def format_report(reports: list[SyncReport]) -> str:
    lignes = []
    for r in reports:
        lignes.append(f"Compte {r.account_id}")
        if not r.created and not r.removed:
            n = len(r.kept)
            lignes.append(
                f"  aucun changement ({n} {'jeu' if n <= 1 else 'jeux'} "
                "déjà à jour)"
            )
        for titre in r.created:
            lignes.append(f"  + {titre}")
        for titre in r.removed:
            lignes.append(f"  - {titre}")
        lignes.append(
            f"  artwork : {r.artwork_written} récupéré(s), "
            f"{r.artwork_pruned} purgé(s), {r.artwork_missing} manquant(s)"
        )
        if r.artwork_error:
            lignes.append(f"    échec : {r.artwork_error}")
        # Toujours dite, même à zéro : « Steam Input : rien à faire » est une
        # information, « rien » n'en est pas une. Une manette muette est la
        # panne la plus coûteuse de cette console, et la plus silencieuse.
        if r.steam_input_error:
            lignes.append(f"  Steam Input : NON RÉGLÉ — {r.steam_input_error}")
        elif r.steam_input_disabled:
            lignes.append(
                f"  Steam Input : désactivé sur {r.steam_input_disabled} jeu(x)")
        else:
            lignes.append("  Steam Input : déjà désactivé partout")
        if r.backup:
            lignes.append(f"  sauvegarde : {r.backup.name}")
    return "\n".join(lignes)
