"""Ligne de commande de retro."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from retro.steam import accounts, artwork, entry, sync, writer

DEFAULT_STEAM_ROOT = "D:\\Steam"
DEFAULT_EMULATION_ROOT = "D:\\Emulation"


def _load_inventory(path: pathlib.Path) -> list[entry.RomEntry]:
    donnees = json.loads(path.read_text(encoding="utf-8"))
    return [
        entry.RomEntry(
            title=d["title"],
            rom_path=d["rom_path"],
            system_name=d["system_name"],
            emulator_exe=d["emulator_exe"],
            launch_template=d["launch_template"],
            start_dir=d["start_dir"],
            extra_tags=tuple(d.get("extra_tags", ())),
        )
        for d in donnees
    ]


def _cmd_sync(args) -> int:
    inventaire_path = pathlib.Path(args.inventory)
    if not inventaire_path.exists():
        print(f"inventaire introuvable : {inventaire_path}", file=sys.stderr)
        return 2

    # Steam ne tourne jamais quand on écrit : sinon il réécrirait
    # shortcuts.vdf à sa fermeture et la synchronisation serait perdue en
    # silence. On refuse ici ; arrêter/redémarrer Steam relève de l'hôte,
    # dans un sous-projet ultérieur.
    try:
        writer.assert_steam_not_running()
        comptes = accounts.discover_accounts(pathlib.Path(args.steam_root))
    except Exception as exc:  # noqa: BLE001 - toute panne devient un message clair
        print(str(exc), file=sys.stderr)
        return 3

    voulu = _load_inventory(inventaire_path)
    client = artwork.ArtworkClient(api_key=args.steamgriddb_key)
    rapports = [
        sync.sync_account(c, voulu, args.emulation_root, client) for c in comptes
    ]
    print(sync.format_report(rapports))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retro")
    sous = parser.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("sync", help="fait remonter les ROMs dans Steam")
    p.add_argument("--steam-root", default=DEFAULT_STEAM_ROOT)
    p.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    p.add_argument("--inventory", required=True,
                    help="inventaire JSON produit par le scanner (sous-projet A)")
    p.add_argument("--steamgriddb-key", default=None)
    p.set_defaults(func=_cmd_sync)

    args = parser.parse_args(argv)
    return args.func(args)
