"""Ligne de commande de retro."""
from __future__ import annotations

import argparse
import importlib.resources
import json
import pathlib
import sys

from retro import bios, install as install_mod
from retro import manifest, profiles, scan, status
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


def _grid_dir_windows(steam_root: str, account_id: str) -> str:
    """Le dossier de grille d'un compte, en chemin WINDOWS.

    C'est ce que sync_account écrit dans le champ `icon` des raccourcis, donc
    il doit être lisible par Steam, pas par nous : une chaîne, jamais un
    pathlib.Path, qui sur Linux prendrait « D:\\Steam » pour un chemin relatif.

    --steam-root EST ce chemin Windows en production, et Steam range toujours
    la grille au même endroit : <steam-root>\\userdata\\<compte>\\config\\grid.
    Rien d'autre n'est à demander à l'utilisateur.

    L'antislash final de --steam-root est retiré : « D:\\Steam\\ » et
    « D:\\Steam » doivent donner le même chemin. « D:\\ » se réduit à « D: »,
    qui reste juste ici puisqu'un antislash suit immédiatement.
    """
    racine = steam_root.rstrip("\\")
    return f"{racine}\\userdata\\{account_id}\\config\\grid"


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
    # sync_account écrit réellement sur le disque (shortcuts.vdf, sa
    # sauvegarde, l'artwork) : vdf_io.load_shortcuts lève ShortcutsError sur
    # un fichier illisible ou malformé, writer.write_shortcuts lève
    # BackupError si la sauvegarde échoue. `retro sync` est lancé par
    # l'hôte, sans personne devant l'écran, et c'est justement le fichier
    # dont la corruption casse la bibliothèque Steam du propriétaire : hors
    # filet, l'une ou l'autre remontait en trace Python brute.
    try:
        rapports = [
            sync.sync_account(
                c, voulu, args.emulation_root, client,
                grid_dir_windows=_grid_dir_windows(args.steam_root, c.account_id),
            )
            for c in comptes
        ]
    except Exception as exc:  # noqa: BLE001 - toute panne devient un message clair
        print(str(exc), file=sys.stderr)
        return 5
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
    émulateur s'installe, et `scan` lit les MÊMES manifestes qu'`install`,
    manifeste utilisateur compris. Sans ce dernier, le repli ci-dessous était
    le cas courant plutôt que l'exception : un emulators.toml déclarant
    install_dir = "DuckStation-v0.1" installait bien là, et l'inventaire
    pointait pourtant « ...\\duckstation\\ », un dossier qui n'existe pas.

    Le repli subsiste — un profil sans émulateur au manifeste ne doit pas faire
    échouer tout le scan — mais il DEVINE un chemin, et la garde de `retro
    sync` ne peut pas le rattraper : le chemin deviné reste sous la racine
    d'émulation. Steam créerait l'entrée, le rapport annoncerait « + <titre> »,
    et rien ne se lancerait. Donc il s'entend.
    """
    table = {emu.profile: emu.install_dir for emu in emulateurs.values()}
    devines = sorted(pid for pid in profils if pid not in table)
    if devines:
        print(
            "attention : aucun manifeste ne dit où sont installés les "
            f"émulateurs des profils suivants : {', '.join(devines)}. Leur "
            "dossier est DEVINÉ d'après l'identifiant du profil. S'il est "
            "faux, les raccourcis produits ne lanceront rien, et ni Steam ni "
            "ce paquet ne le signaleront. Déclarer ces émulateurs au "
            "manifeste — --user-manifest pour ceux qui vivent hors dépôt.",
            file=sys.stderr,
        )
    for pid in devines:
        table[pid] = pid
    return table


def _cmd_scan(args) -> int:
    try:
        profils = profiles.load_profiles(pathlib.Path(args.profiles))
        utilisateur = pathlib.Path(args.user_manifest) if args.user_manifest else None
        emulateurs = manifest.load_manifest(pathlib.Path(args.manifest), utilisateur)
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


def _cmd_status(args) -> int:
    """Le rapport lisible. Une consultation, jamais une validation : elle ne
    modifie rien et rend 0 même quand des problèmes sont signalés — les
    problèmes eux-mêmes sont le contenu utile du rapport, pas un motif
    d'échec de la commande. Seul un échec qui empêche de PRODUIRE le rapport
    (manifeste illisible, profils absents, racine des ROMs non montée) rend
    un code non nul."""
    try:
        profils = profiles.load_profiles(pathlib.Path(args.profiles))
        utilisateur = pathlib.Path(args.user_manifest) if args.user_manifest else None
        emulateurs = manifest.load_manifest(pathlib.Path(args.manifest), utilisateur)
        install_dirs = _install_dirs_pour(profils, emulateurs)
        inventaire = scan.scan(
            pathlib.Path(args.roms), profils, args.emulation_root, install_dirs,
            roms_root_windows=args.roms_windows,
        )

        comptes: dict[str, int] = {}
        for rom in inventaire:
            comptes[rom.system_name] = comptes.get(rom.system_name, 0) + 1
        systemes = sorted(comptes.items())

        # bios.check_bios, build_report et format_report font partie de la
        # PRODUCTION du rapport au même titre que le scan qui précède : la
        # docstring de cette fonction promet de couvrir tout ce qui l'en
        # empêche. Les en laisser hors du filet rendait une trace Python nue
        # sur la seule commande du paquet faite pour être lue par un humain,
        # depuis son canapé, sans clavier ni écran — par exemple sur un profil
        # dont le md5 d'un BIOS a été écrit sans guillemets (bios.py suppose
        # une chaîne et .lower() explose sur l'entier que TOML en tire).
        etat_bios = bios.check_bios(profils, pathlib.Path(args.bios))
        rapport = status.build_report(
            install_dirs=install_dirs,
            emulation_root=pathlib.Path(args.emulation_root),
            systems=systemes,
            bios_status=etat_bios,
            bios_root=pathlib.Path(args.bios),
        )
        texte = status.format_report(rapport)
    except Exception as exc:  # noqa: BLE001 - toute panne devient un message clair
        print(str(exc), file=sys.stderr)
        return 2

    print(texte)
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
    # Les mêmes manifestes qu'`install`, et pour la même raison : c'est le
    # manifeste qui décide où chaque émulateur s'installe, donc lui seul sait
    # où l'inventaire doit pointer. `scan` lisait le seul noyau, et les
    # émulateurs déclarés hors dépôt produisaient des raccourcis invalides.
    s.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    s.add_argument("--user-manifest", default=None)
    s.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    s.add_argument("--output", required=True)
    s.set_defaults(func=_cmd_scan)

    st = sous.add_parser(
        "status", help="rapport lisible : émulateurs, jeux, BIOS, problèmes"
    )
    st.add_argument("--roms", required=True)
    st.add_argument("--roms-windows", default="G:\\ROMs")
    st.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    st.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    st.add_argument("--user-manifest", default=None)
    st.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    st.add_argument("--bios", required=True,
                    help="dossier où le propriétaire dépose ses BIOS")
    st.set_defaults(func=_cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
