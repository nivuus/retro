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


def _dossier(valeur: str | None) -> pathlib.Path | None:
    """Un chemin facultatif de la ligne de commande, en Path ou en None.

    Les surcharges du propriétaire — manifeste et profils — vivent hors dépôt,
    sur un partage. None dit « aucune surcharge demandée » ; les modules qui
    les lisent traitent ensuite l'absence du fichier ou du dossier DEMANDÉ
    comme normale, puisqu'il vit sur un partage qui n'est pas toujours monté.
    """
    return pathlib.Path(valeur) if valeur else None


def _grid_dir_windows(steam_root_windows: str, account_id: str) -> str:
    """Le dossier de grille d'un compte, en chemin WINDOWS.

    C'est ce que sync_account écrit dans le champ `icon` des raccourcis, donc
    il doit être lisible par Steam, pas par nous : une chaîne, jamais un
    pathlib.Path, qui sur Linux prendrait « D:\\Steam » pour un chemin relatif.

    La racine passée ici est --steam-root-windows, PAS --steam-root. Les deux
    se confondaient, et une racine POSIX produisait
    « /mnt/steam\\userdata\\123\\config\\grid\\..._icon.png » : mi-POSIX
    mi-Windows, un chemin que Steam n'ouvre jamais — et rc = 0, « + Chrono
    Trigger », pas un mot. `scan` distingue déjà --roms de --roms-windows pour
    exactement cette raison ; c'est la même distinction.

    Steam range toujours la grille au même endroit :
    <racine>\\userdata\\<compte>\\config\\grid.

    L'antislash final est retiré : « D:\\Steam\\ » et « D:\\Steam » doivent
    donner le même chemin. « D:\\ » se réduit à « D: », qui reste juste ici
    puisqu'un antislash suit immédiatement.
    """
    racine = steam_root_windows.rstrip("\\")
    return f"{racine}\\userdata\\{account_id}\\config\\grid"


def _cmd_sync(args) -> int:
    inventaire_path = pathlib.Path(args.inventory)
    if not inventaire_path.exists():
        print(f"inventaire introuvable : {inventaire_path}", file=sys.stderr)
        return 2

    # Le champ `icon` des raccourcis est lu par Steam, sur la console : c'est
    # un chemin Windows, toujours. Un chemin POSIX y produirait un raccourci
    # sans icône, sans le moindre message — la panne exacte que la séparation
    # --steam-root / --steam-root-windows corrige. On refuse avant d'écrire.
    if "/" in args.steam_root_windows:
        print(
            f"--steam-root-windows {args.steam_root_windows} n'est pas un "
            "chemin Windows. C'est le chemin que STEAM lira dans "
            "shortcuts.vdf, sur la console — un chemin POSIX y donnerait des "
            "raccourcis sans icône, sans qu'aucun message ne le dise. "
            "--steam-root est le chemin par lequel CETTE machine atteint la "
            "même installation ; les deux ne se confondent que sur la console "
            "elle-même.",
            file=sys.stderr,
        )
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
                grid_dir_windows=_grid_dir_windows(args.steam_root_windows, c.account_id),
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
        emulateurs = manifest.load_manifest(pathlib.Path(args.manifest),
                                            _dossier(args.user_manifest))
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


def _signaler_ignores(ignores: list[scan.IgnoredSystem],
                      racine_locale: str) -> None:
    """Dit ce que le scan a laissé de côté, et comment le récupérer.

    Ignorer un système sans émulateur évite une bibliothèque d'entrées mortes ;
    l'ignorer EN SILENCE la remplace par une bibliothèque incomplète, tout
    aussi inexplicable pour le propriétaire. Le message porte donc les trois
    mêmes choses que les problèmes de `retro status` : ce qui manque, où on a
    cherché, et quoi faire.
    """
    if not ignores:
        return
    lignes = [
        "attention : ces systèmes sont ignorés, leur émulateur n'est pas "
        "utilisable — leurs jeux n'apparaîtront pas dans Steam :"
    ]
    # PAR ÉMULATEUR, pas par système : le RetroArch du profil livré en sert
    # neuf. Répéter neuf fois le même motif et le même chemin de cent
    # caractères pour UNE panne est ce que le rapport de `status` s'interdit
    # à lui-même — « un problème n'est énoncé qu'une fois ». Seul le coût se
    # compte système par système.
    par_emulateur: dict[str, list] = {}
    for i in ignores:
        par_emulateur.setdefault(i.profile, []).append(i)

    for pid in sorted(par_emulateur):
        groupe = sorted(par_emulateur[pid], key=lambda i: i.system_name)
        motif = groupe[0].reason
        lignes.append(f"  émulateur « {pid} » : {install_mod.MOTIFS[motif]}")
        # Le chemin qui manque VRAIMENT. Annoncer « cherché : ...\\retroarch.exe »
        # pour un émulateur posé à la main enverrait chercher un fichier qui
        # est là : ce qui manque, dans ce cas, est le témoin, donc le dossier.
        if motif == install_mod.SANS_TEMOIN:
            lignes.append(f"    dossier : {groupe[0].install_dir}")
            lignes.append(f"    à défaut : {install_mod.REMEDE_SANS_TEMOIN}")
        else:
            lignes.append(f"    cherché : {groupe[0].emulator}")
        for i in groupe:
            jeu = "jeu" if i.roms == 1 else "jeux"
            lignes.append(f"    {i.system_name} : {i.roms} {jeu} ignoré"
                          f"{'' if i.roms == 1 else 's'}")
    lignes.append(
        "Installer ce qui manque — retro install --emulation-root "
        f"'{racine_locale}' — puis relancer ce scan."
    )
    print("\n".join(lignes), file=sys.stderr)


def _cmd_scan(args) -> int:
    # Deux chemins pour la racine d'émulation, comme --roms et --roms-windows :
    # --emulation-root est ce que la CONSOLE lira dans shortcuts.vdf,
    # --emulation-root-local est le chemin par lequel CETTE machine atteint les
    # mêmes fichiers, donc le seul par lequel on puisse vérifier qu'un
    # émulateur existe. Sur Linux, pathlib.Path("D:\\Emulation") est un chemin
    # RELATIF : confondre les deux ne vérifierait jamais rien.
    racine_locale = (pathlib.Path(args.emulation_root_local)
                     if args.emulation_root_local else None)
    try:
        profils = profiles.load_profiles(pathlib.Path(args.profiles),
                                         _dossier(args.user_profiles))
        emulateurs = manifest.load_manifest(pathlib.Path(args.manifest),
                                            _dossier(args.user_manifest))
        install_dirs = _install_dirs_pour(profils, emulateurs)
        ignores = scan.ignored_systems(
            pathlib.Path(args.roms), profils, install_dirs, racine_locale,
        ) if racine_locale else []
        # `ignored=ignores` : le scan ne recalcule pas ce qu'on vient de
        # calculer pour l'annoncer. Deux calculs, ce sont deux vérités
        # possibles sur un disque qui bouge — un message qui contredirait
        # l'inventaire qu'il accompagne. Sans racine locale, l'ensemble est
        # vide et rien n'est ignoré : le comportement d'avant.
        inventaire = scan.scan(
            pathlib.Path(args.roms), profils, args.emulation_root, install_dirs,
            roms_root_windows=args.roms_windows,
            emulation_root_local=racine_locale, ignored=ignores,
        )
    except Exception as exc:  # noqa: BLE001 - toute panne devient un message clair
        print(str(exc), file=sys.stderr)
        return 2

    _signaler_ignores(ignores, args.emulation_root_local)

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
    # Aussi sur la sortie standard : c'est elle que l'hôte relaie au
    # propriétaire, et un inventaire amputé qui s'annonce complet est
    # exactement le défaut qu'on vient de fermer.
    if ignores:
        perdus = sum(i.roms for i in ignores)
        noms = ", ".join(i.system_name for i in ignores)
        # « faute d'émulateur installé » mentait sur l'émulateur posé à la
        # main, dont l'exécutable EST là — et c'est la seule ligne que l'hôte
        # relaie. « pas utilisable » couvre les trois motifs sans en trahir
        # aucun.
        print(f"{len(ignores)} système(s) ignoré(s), leur émulateur n'étant "
              f"pas utilisable ({noms}) : {perdus} ROM(s) non "
              "répertoriée(s) — détail ci-dessus")
    return 0


def _cmd_status(args) -> int:
    """Le rapport lisible. Une consultation, jamais une validation : elle ne
    modifie rien et rend 0 même quand des problèmes sont signalés — les
    problèmes eux-mêmes sont le contenu utile du rapport, pas un motif
    d'échec de la commande. Seul un échec qui empêche de PRODUIRE le rapport
    (manifeste illisible, profils absents, racine des ROMs non montée) rend
    un code non nul."""
    try:
        profils = profiles.load_profiles(pathlib.Path(args.profiles),
                                         _dossier(args.user_profiles))
        emulateurs = manifest.load_manifest(pathlib.Path(args.manifest),
                                            _dossier(args.user_manifest))
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

        # `status` lit le disque de CETTE machine — c'est déjà ainsi qu'il
        # trouve les témoins de version. Le même chemin sert donc à vérifier
        # que les exécutables existent : « l'émulateur n'est pas installé »
        # devient « et voici les jeux que ça vous coûte ».
        #
        # Le compte des systèmes ci-dessus, lui, reste celui du DISQUE : une
        # section « Systèmes » vide alors que le propriétaire a des ROMs se
        # lirait comme une panne d'affichage, et « aucun système avec des
        # ROMs » serait faux.
        ignores = scan.ignored_systems(
            pathlib.Path(args.roms), profils, install_dirs,
            pathlib.Path(args.emulation_root),
        )
        etat_bios = bios.check_bios(profils, pathlib.Path(args.bios))
        rapport = status.build_report(
            install_dirs=install_dirs,
            emulation_root=pathlib.Path(args.emulation_root),
            systems=systemes,
            bios_status=etat_bios,
            bios_root=pathlib.Path(args.bios),
            ignored_systems=ignores,
            # L'exécutable de chaque profil chargé : sans lui, le rapport
            # déduirait l'état des émulateurs de la liste des systèmes
            # ignorés, qui ne retient que ceux ayant des ROMs — et le verdict
            # dépendrait des jeux du propriétaire.
            emulator_exes={pid: p.exe for pid, p in profils.items()},
        )
        texte = status.format_report(rapport)
    except Exception as exc:  # noqa: BLE001 - toute panne devient un message clair
        print(str(exc), file=sys.stderr)
        return 2

    print(texte)
    return 0


_AIDE_USER_PROFILES = (
    "dossier de profils du propriétaire, hors dépôt, FUSIONNÉ avec ceux du "
    "paquet ; à identifiant égal le sien l'emporte, et son absence est normale"
)


def _build_parser() -> argparse.ArgumentParser:
    """L'analyseur, à part de `main` : le README doit pouvoir se vérifier
    contre les commandes réellement offertes, plutôt que contre une liste
    tenue à la main qui vieillit en silence (`retro status` y a manqué)."""
    parser = argparse.ArgumentParser(prog="retro")
    sous = parser.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("sync", help="fait remonter les ROMs dans Steam")
    # Deux chemins, comme --roms et --roms-windows de `scan`, et pour la même
    # raison : celui par lequel CETTE machine lit shortcuts.vdf, et celui par
    # lequel la CONSOLE verra la même installation. Confondus, le champ `icon`
    # sortait mi-POSIX mi-Windows et Steam n'affichait jamais l'icône.
    p.add_argument("--steam-root", required=True,
                   help="chemin par lequel cette machine atteint "
                        "l'installation Steam (lecture de shortcuts.vdf)")
    p.add_argument("--steam-root-windows", default=DEFAULT_STEAM_ROOT,
                   help="chemin par lequel la console voit la même "
                        "installation ; c'est lui que Steam relira")
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
    # Le pendant de --user-manifest pour les profils, et il va avec lui :
    # déclarer un émulateur au manifeste ne suffit pas à s'en servir, il lui
    # faut un profil qui dise quels systèmes il couvre et comment on le lance.
    # Ce dossier est FUSIONNÉ avec celui du paquet, jamais substitué : y
    # pointer perdait les profils livrés, et avec eux tous leurs systèmes.
    s.add_argument("--user-profiles", default=None,
                   help=_AIDE_USER_PROFILES)
    # Les mêmes manifestes qu'`install`, et pour la même raison : c'est le
    # manifeste qui décide où chaque émulateur s'installe, donc lui seul sait
    # où l'inventaire doit pointer. `scan` lisait le seul noyau, et les
    # émulateurs déclarés hors dépôt produisaient des raccourcis invalides.
    s.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    s.add_argument("--user-manifest", default=None)
    s.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT,
                   help="chemin par lequel la console verra les émulateurs ; "
                        "c'est lui qui part dans l'inventaire")
    # Facultatif, et son absence conserve le comportement d'avant : un hôte
    # peut inventorier pour une machine dont il n'atteint pas le disque des
    # émulateurs. Donné, il fait vérifier que chaque exécutable existe
    # vraiment — sans quoi une installation ratée peuple Steam d'entrées qui
    # ne démarrent pas, et rien ne le dit.
    s.add_argument("--emulation-root-local", default=None,
                   help="chemin par lequel CETTE machine atteint les mêmes "
                        "émulateurs ; donné, les systèmes dont l'exécutable "
                        "manque sont ignorés et signalés")
    s.add_argument("--output", required=True)
    s.set_defaults(func=_cmd_scan)

    st = sous.add_parser(
        "status", help="rapport lisible : émulateurs, jeux, BIOS, problèmes"
    )
    st.add_argument("--roms", required=True)
    st.add_argument("--roms-windows", default="G:\\ROMs")
    st.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    # Les mêmes profils que `scan`, pour la même raison que les mêmes
    # manifestes : les deux commandes doivent parler du MÊME parc, sinon
    # l'une rapporte l'état d'émulateurs que l'autre n'inventorie pas.
    st.add_argument("--user-profiles", default=None,
                    help=_AIDE_USER_PROFILES)
    st.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    st.add_argument("--user-manifest", default=None)
    st.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    st.add_argument("--bios", required=True,
                    help="dossier où le propriétaire dépose ses BIOS")
    st.set_defaults(func=_cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
