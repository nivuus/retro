"""Ligne de commande de retro."""
from __future__ import annotations

import argparse
import importlib.resources
import json
import pathlib
import sys

from retro import launcher as launcher_mod
from retro import render as render_mod
from retro import bios, identite, install as install_mod
from retro import manifest, profiles, scan, status
from retro.steam import accounts, artwork, entry, steam_input, sync, vdf_io, writer

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


def _signaler_inconnus(roms_root: pathlib.Path, profils: dict,
                       affiche: str, detaille: bool) -> None:
    """Pourquoi un scan n'a rien trouvé, quand il n'a rien trouvé.

    Trois faits, parce qu'aucun ne suffit seul : ce qui a été VU sur le
    disque, ce qui était ATTENDU, et quoi faire de l'écart. Le propriétaire
    range « Nintendo\\Gamecube » et l'outil cherchait « gamecube » — l'un des
    deux doit céder, et ce n'est pas à lui de renommer sa collection.
    """
    try:
        vus, attendus = scan.unmatched_folders(roms_root, profils)
    except scan.ScanError as exc:
        print(str(exc), file=sys.stderr)
        return
    if not vus:
        if detaille:
            print(f"aucun dossier sous {affiche} : la bibliothèque est vide, "
                  "ou ce n'est pas la bonne racine.")
        return
    if not detaille:
        # Le scan a trouvé des jeux : ces dossiers-ci ne sont pas une panne,
        # mais les taire ferait passer un inventaire amputé pour complet.
        apercu = ", ".join(vus[:6]) + (" ..." if len(vus) > 6 else "")
        print(f"{len(vus)} dossier(s) ne correspondent à aucun système connu "
              f"et n'ont pas été répertoriés : {apercu}")
        return
    print("")
    print(f"aucun dossier de {affiche} ne correspond à un système connu.")
    print(f"  vus     : {', '.join(vus)}")
    print(f"  attendus: {', '.join(attendus)}")
    print("  Le nom du dossier désigne le système, à la casse près, et les")
    print("  dossiers de constructeur sont traversés. Pour garder vos noms,")
    print("  ajoutez-les au champ 'folders' du système, dans son profil :")
    print("      folders = [\"Playstation\", \"PS1\"]")


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
    # En PREMIÈRE ligne, avant tout le reste et même avant un échec : deux
    # exécutions de `scan` ont rendu deux inventaires différents le
    # 2026-08-29, et rien ne disait qu'elles ne venaient pas du même paquet.
    print(f"paquet : {identite.VERSION}")
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

    # Le plan que lit le lanceur : la commande de chaque émulateur, les
    # gabarits des trois modes, et l'arbitrage de `auto` déjà résolu pour
    # chaque classe de machine. Écrit ICI, avec les profils qui viennent
    # d'être chargés — un plan qui daterait d'un autre jeu de profils ferait
    # lancer l'ancien émulateur sur une entrée Steam d'apparence normale.
    if racine_locale is not None:
        try:
            plans = launcher_mod.ecrire_plan(
                racine_locale, args.emulation_root, profils, install_dirs)
        except OSError as exc:
            print(f"écriture du plan de lancement impossible : {exc}. Les "
                  "jeux ne démarreraient pas.", file=sys.stderr)
            return 2
        print(f"{len(plans)} plan(s) de lancement écrit(s) dans "
              f"{launcher_mod.local_dir(racine_locale) / launcher_mod.PLAN}")

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
    # Des dossiers non reconnus sont signalés DÈS QU'IL Y EN A, pas seulement
    # quand l'inventaire est vide. La première version ne parlait que du cas
    # vide ; sur la bibliothèque réelle, trois systèmes sur six étaient passés
    # sous silence parce que les trois autres avaient réussi — un inventaire
    # amputé qui s'annonce complet, exactement le défaut que ce projet
    # combat. Le cas vide garde le message long, qui explique quoi faire ;
    # le cas partiel n'en reçoit qu'une ligne, pour ne pas noyer un scan
    # nominal sous ses dossiers de BIOS et de sauvegardes.
    _signaler_inconnus(pathlib.Path(args.roms), profils, args.roms,
                       detaille=not donnees and not ignores)
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


def _cmd_identite(args) -> int:
    """Quelle construction du paquet tourne ICI.

    Une ligne, la version seule : c'est l'hôte qui la lit, à travers WinRM,
    pour la comparer à la roue qu'il a livrée. La prose est dans `status`.

    Aucune option, aucun argument : elle doit se lancer sur une machine où
    rien n'est monté, rien n'est configuré — c'est justement quand plus rien
    ne marche qu'on demande quel code tourne.
    """
    print(identite.VERSION)
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

        # Steam Input, et seulement si la racine Steam est donnée. Un rapport
        # qui l'exigerait ne se rendrait plus du tout sur une machine où l'on
        # veut juste voir ce qui manque comme BIOS — or c'est justement là
        # qu'on le consulte, loin de la console.
        #
        # La source est shortcuts.vdf, pas l'inventaire : ce qui compte est ce
        # que Steam a RÉELLEMENT dans sa bibliothèque, et le réglage porte sur
        # l'appid d'un raccourci existant. Un jeu scanné mais jamais
        # synchronisé n'a pas encore de manette à régler.
        muets, echec_steam_input = [], ""
        if getattr(args, "steam_root", None):
            try:
                for compte in accounts.discover_accounts(
                        pathlib.Path(args.steam_root)):
                    notres = [r for r in vdf_io.load_shortcuts(compte.shortcuts_path)
                              if entry.is_owned(r, args.emulation_root)]
                    muets += steam_input.jeux_actifs(compte.localconfig_path, notres)
            except (accounts.NoSteamAccountError, steam_input.LocalConfigError,
                    vdf_io.ShortcutsError) as exc:
                # Signalé, jamais fatal : `status` est une consultation, et
                # tout le reste du rapport garde sa valeur.
                echec_steam_input = str(exc)

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
            # Ce que les trois modes de rendu font réellement, et le mode
            # posé. Un système sans modes déclarés se lit ici, plutôt que de
            # se découvrir en choisissant « full » et en ne voyant rien
            # changer.
            profils=profils,
            render_mode=launcher_mod.lire_mode(
                pathlib.Path(args.emulation_root)),
            steam_input_muets=muets,
            steam_input_echec=echec_steam_input,
            # Le témoin que le lanceur écrit : `status` ne peut pas
            # constater l'état d'un fichier qui vit dans le profil de
            # l'utilisateur Windows. Même racine que `lire_mode` ci-dessus,
            # et même limite : sur la machine, les deux chemins se
            # confondent.
            amorcages=launcher_mod.lire_amorcages(
                pathlib.Path(args.emulation_root)),
            # Un lanceur compilé avant les plans qu'il lit n'échoue pas : il
            # ignore les lignes qu'il ne connaît pas. Sans ce constat, la
            # section Amorçage annoncerait « pas encore amorcé » aussi
            # longtemps qu'il resterait en place, et rien ne dirait que le
            # geste à faire est de le recompiler.
            lanceur_perime=launcher_mod.lanceur_perime(
                pathlib.Path(args.emulation_root)),
            # Ce que les fichiers d'amorçage POSÉS contiennent réellement,
            # confronté à ce que les profils chargés ici décrivent. Seul
            # « retro scan » les écrit : un `enforced` corrigé dans un profil
            # restait sans le moindre effet tant que personne ne re-scannait,
            # et le symptôme était le réglage d'origine — indiscernable, vu du
            # canapé, d'un correctif qui serait faux.
            fragments=launcher_mod.lire_fragments(
                pathlib.Path(args.emulation_root)),
            # Quelle construction du paquet produit ce rapport. Le rapport le
            # CONSTATE et ne le reproche pas : il n'a aucune référence à
            # opposer, et c'est l'hôte qui a livré la roue qui sait laquelle
            # devrait être là.
            paquet=identite.VERSION,
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


def _cmd_launcher(args) -> int:
    """Dépose la source du lanceur commun et son script de compilation.

    Ne compile pas : csc.exe est un outil Windows, et cette commande tourne
    sur la machine qui PILOTE, laquelle n'est pas forcément celle-là. Le
    binaire n'est jamais livré tout fait — un dépôt public n'a pas à faire
    confiance à un exécutable qu'on ne peut pas relire.
    """
    racine = pathlib.Path(args.emulation_root_local)
    # Le ré-amorçage est un geste à part : il ne redépose pas la source du
    # lanceur, et il ne dépend pas de sa compilation.
    if args.reamorcer:
        try:
            fichier = launcher_mod.ordonner_reamorcage(racine, args.reamorcer)
        except (launcher_mod.AmorcageError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"ré-amorçage demandé pour « {args.reamorcer} » : {fichier}\n"
              "Il sera posé au prochain lancement d'un jeu de cet émulateur, "
              "après sauvegarde de sa configuration actuelle.")
        return 0
    try:
        deposes = launcher_mod.deposer_source(racine)
    except OSError as exc:
        print(f"dépôt du lanceur impossible : {exc}", file=sys.stderr)
        return 2
    for f in deposes:
        print(f"déposé : {f}")

    if launcher_mod.est_installe(racine):
        if launcher_mod.lanceur_perime(racine):
            # Un binaire plus vieux que sa source ignore EN SILENCE les
            # lignes de plan qu'il ne connaît pas : pas d'erreur, pas
            # d'amorçage, et `retro status` annoncerait « pas encore amorcé »
            # indéfiniment. Ne pas rendre 0 : c'est l'état du jour même de la
            # livraison, et « en place » l'a déjà fait croire une fois.
            print(
                "le lanceur en place est plus ancien que sa source : il "
                "ignorerait en silence ce que les plans portent de nouveau "
                "(l'amorçage des émulateurs, notamment). Le recompiler depuis "
                f"Windows :\n    {launcher_mod.launcher_dir(args.emulation_root)}"
                f"\\{launcher_mod.RECOMPILER}",
                file=sys.stderr,
            )
            return 1
        print("le lanceur est compilé et en place")
        return 0
    # Ne PAS rendre 0 : sans binaire, le lanceur n'est pas installé, et
    # `retro scan` refusera d'inventorier. Rendre 0 ici ferait croire à une
    # étape terminée, et la panne apparaîtrait deux commandes plus loin.
    print(
        "le lanceur n'est pas encore compilé. Depuis Windows, exécuter :\n"
        f"    {launcher_mod.launcher_dir(args.emulation_root)}\\"
        f"{launcher_mod.RECOMPILER}\n"
        "csc.exe du .NET Framework suffit : il est présent sur toute "
        "installation de Windows, rien à télécharger.",
        file=sys.stderr,
    )
    return 1


def _cmd_render(args) -> int:
    """Lit ou pose le mode de rendu.

    Le mode vit dans un fichier que le lanceur relit à CHAQUE jeu : le
    changer ne touche aucune option de raccourci, donc aucun identifiant
    Steam, donc aucune vignette. Rien à resynchroniser.
    """
    racine = pathlib.Path(args.emulation_root_local)
    if args.mode is None:
        print(launcher_mod.lire_mode(racine))
        return 0
    try:
        fichier = launcher_mod.ecrire_mode(racine, args.mode)
    except (render_mod.RenderError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"mode de rendu : {args.mode} ({fichier})")
    if not launcher_mod.est_installe(racine):
        # Le mode est bien posé, mais rien ne le lira. Le taire ferait
        # croire au propriétaire que son choix s'applique.
        print("le lanceur n'est pas installé : ce mode ne sera lu par "
              "personne tant qu'il ne l'est pas (« retro launcher »).",
              file=sys.stderr)
        return 1
    return 0


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

    lan = sous.add_parser(
        "launcher", help="déposer le lanceur commun (source + compilation)")
    lan.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT,
                     help="la racine telle que la CONSOLE la verra")
    lan.add_argument("--emulation-root-local", required=True,
                     help="le chemin par lequel CETTE machine y accède")
    lan.add_argument("--reamorcer", metavar="PROFIL", default=None,
                     help="reposer la configuration de cet émulateur au "
                          "prochain lancement, en sauvegardant l'actuelle. "
                          "Sans cette option, une configuration existante "
                          "n'est jamais touchée.")
    lan.set_defaults(func=_cmd_launcher)

    ren = sous.add_parser(
        "render", help="lire ou poser le mode de rendu (native, auto, full)")
    ren.add_argument("--emulation-root-local", required=True)
    ren.add_argument("--mode", choices=render_mod.MODES, default=None,
                     help="sans --mode, affiche le mode courant")
    ren.set_defaults(func=_cmd_render)

    # Sans aucune option, et c'est le contrat : sur une console d'où l'on ne
    # sait plus quel code tourne, exiger --roms ou --emulation-root ferait
    # échouer la seule commande capable de répondre. Sur un paquet ANTÉRIEUR à
    # celle-ci, argparse rend 2 — ce n'est pas une panne, c'est le premier
    # constat, et l'hôte le lit comme tel.
    idt = sous.add_parser(
        "identite",
        help="dit quelle construction du paquet tourne ici (une ligne)")
    idt.set_defaults(func=_cmd_identite)

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
    st.add_argument("--steam-root", default=None,
                   help="racine Steam, pour dire quels jeux ont encore Steam "
                        "Input actif — leur manette reste muette dans "
                        "l'émulateur. Facultatif : sans elle, le rapport se "
                        "rend comme avant, sans cette section.")
    st.add_argument("--bios", required=True,
                    help="dossier où le propriétaire dépose ses BIOS")
    st.set_defaults(func=_cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
