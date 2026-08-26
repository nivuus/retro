"""Ligne de commande de retro."""
from __future__ import annotations

import argparse
import importlib.resources
import json
import pathlib
import sys

from retro import install as install_mod
from retro import manifest, profiles, scan
from retro.steam import accounts, artwork, entry, sync, writer

DEFAULT_STEAM_ROOT = "D:\\Steam"
DEFAULT_EMULATION_ROOT = "D:\\Emulation"

# Le manifeste et les profils vivent DANS le paquet (retro/data/), et on les
# atteint par importlib.resources plutôt que par __file__ : c'est la seule voie
# qui résout dans les deux modes. Un calcul relatif à __file__ visait
# site-packages/manifests/, un dossier que rien n'installe — le mode éditable,
# où __file__ reste dans le dépôt, masquait la panne jusqu'au premier wheel.
#
# files() rend un Traversable ; le paquet est toujours installé décompressé
# (setuptools, pas de zipimport), donc c'est un chemin du système de fichiers
# et la conversion est exacte. Le reste du code manipule des pathlib.Path.
_DONNEES = pathlib.Path(str(importlib.resources.files("retro"))) / "data"
DEFAULT_MANIFEST = _DONNEES / "manifests" / "core.toml"
DEFAULT_PROFILES = _DONNEES / "profiles"


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
        voulu = _load_inventory(inventaire_path)
    except Exception as exc:  # noqa: BLE001 - toute panne devient un message clair
        print(str(exc), file=sys.stderr)
        return 3

    # Une racine d'émulation erronée ne lève rien : is_owned devient faux pour
    # NOS PROPRES entrées, donc chaque passage les recrée sans les reconnaître,
    # en rapportant « + <titre> » comme si tout allait bien. Mesuré : trois
    # passages, trois entrées identiques. On refuse avant d'écrire.
    hors_racine = [rom.emulator_exe for rom in voulu
                   if not entry.is_under_root(entry.quote(rom.emulator_exe), args.emulation_root)]
    if hors_racine:
        print(
            f"--emulation-root {args.emulation_root} ne contient pas les "
            f"émulateurs de l'inventaire : {', '.join(sorted(set(hors_racine)))}. "
            "Synchroniser ainsi recréerait les mêmes raccourcis à chaque "
            "passage sans jamais les reconnaître. Corriger --emulation-root ou "
            "l'inventaire.",
            file=sys.stderr,
        )
        return 4

    client = artwork.ArtworkClient(api_key=args.steamgriddb_key)
    rapports = [
        sync.sync_account(c, voulu, args.emulation_root, client) for c in comptes
    ]
    print(sync.format_report(rapports))
    return 0


def _cmd_install(args) -> int:
    try:
        utilisateur = pathlib.Path(args.user_manifest) if args.user_manifest else None
        emulateurs = manifest.load_manifest(pathlib.Path(args.manifest), utilisateur)
        resultats = install_mod.install_all(emulateurs, pathlib.Path(args.emulation_root))
    except Exception as exc:  # noqa: BLE001 - toute panne devient un message clair
        print(str(exc), file=sys.stderr)
        return 2

    print(install_mod.format_install_report(resultats))
    echecs = [cle for cle, etat in resultats if etat.startswith("ÉCHEC")]
    return 1 if echecs else 0


def _install_dirs_pour(profils: dict, emulateurs: dict) -> dict[str, str]:
    """Dossier d'installation par identifiant de profil.

    La source de vérité est le manifeste : c'est lui qui décide où chaque
    émulateur s'installe. Un profil que le manifeste ne référence pas (un
    profil ajouté par le propriétaire sans émulateur correspondant dans le
    manifeste, par exemple) retombe sur son propre identifiant plutôt que de
    faire échouer tout le scan.
    """
    table = {emu.profile: emu.install_dir for emu in emulateurs.values()}
    for pid in profils:
        table.setdefault(pid, pid)
    return table


def _cmd_scan(args) -> int:
    try:
        profils = profiles.load_profiles(pathlib.Path(args.profiles))
        emulateurs = manifest.load_manifest(DEFAULT_MANIFEST)
        install_dirs = _install_dirs_pour(profils, emulateurs)
        inventaire = scan.scan(
            pathlib.Path(args.roms), profils, args.emulation_root, install_dirs,
            roms_root_windows=args.roms_windows,
        )
    except Exception as exc:  # noqa: BLE001 - toute panne devient un message clair
        print(str(exc), file=sys.stderr)
        return 2

    donnees = [
        {
            "title": rom.title,
            "rom_path": rom.rom_path,
            "system_name": rom.system_name,
            "emulator_exe": rom.emulator_exe,
            "launch_template": rom.launch_template,
            "start_dir": rom.start_dir,
            "extra_tags": list(rom.extra_tags),
        }
        for rom in inventaire
    ]
    # L'écriture est aussi faillible que le scan : un --output dont le dossier
    # parent n'existe pas, un volume plein, un fichier en lecture seule. Hors
    # de ce try, la trace Python remontait telle quelle — sur une console sans
    # clavier ni écran, elle n'est lisible par personne.
    try:
        pathlib.Path(args.output).write_text(
            json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        print(f"écriture de l'inventaire impossible : {exc}", file=sys.stderr)
        return 2
    print(f"{len(donnees)} ROM(s) répertoriée(s) dans {args.output}")
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

    i = sous.add_parser("install", help="installe les émulateurs du manifeste")
    i.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    i.add_argument("--user-manifest", default=None)
    i.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    i.set_defaults(func=_cmd_install)

    s = sous.add_parser("scan", help="produit l'inventaire des ROMs")
    s.add_argument("--roms", required=True)
    s.add_argument("--roms-windows", default="G:\\ROMs")
    s.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    s.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    s.add_argument("--output", required=True)
    s.set_defaults(func=_cmd_scan)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
