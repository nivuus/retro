"""Le rapport que lit un humain.

Tout le reste de ce paquet tourne sans témoin : `sync`, `install` et `scan`
s'adressent à Steam ou au disque, jamais à une personne. `status` est
l'exception — son seul but est d'être lu par le propriétaire, souvent depuis
son canapé, sans clavier, pour comprendre pourquoi un jeu ne se lance pas.

Quatre règles en découlent directement :

- « corrompu » et « absent » ne se disent pas de la même façon. Un BIOS
  corrompu est LÀ — souvent un fichier renommé, bon nom et mauvais contenu.
  Dire « manquant » enverrait le propriétaire chercher ce qu'il a déjà déposé.
- une section vide se lit comme une panne d'affichage. Quand il n'y a rien à
  signaler, le rapport le dit, plutôt que de laisser un blanc que personne ne
  peut distinguer d'un bug.
- un constat sans chemin ni action n'aide personne. « MANQUANT :
  scph5500.bin » ne dit pas OÙ déposer le fichier ; « dolphin n'est pas
  installé » ne dit pas `retro install`. Le programme connaît pourtant ces
  chemins — ils sont dans ses propres options. Chaque problème porte donc les
  trois : ce qui ne va pas, où, et quoi faire.
- ce qui VA BIEN se voit. Sans confirmation, le propriétaire qui dépose un
  fichier et relance ne peut pas vérifier que son geste a marché ; il ne lit
  qu'un écran de reproches.

Un problème n'est énoncé qu'UNE fois. Il l'était deux, dans deux formulations
différentes — section BIOS puis section Problèmes — et un lecteur y voyait deux
constats distincts. `_problemes_bios` est désormais la source unique, et la
section BIOS ne porte que les confirmations et un renvoi.

`build_report` ne modifie jamais rien : ni fichier, ni dossier, ni cache.
C'est une consultation, pas une validation.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
from collections.abc import Sequence

from retro import install as install_mod
from retro import render as render_mod
from retro.bios import BiosNeed, SystemBios
from retro.scan import IgnoredSystem


@dataclasses.dataclass(frozen=True)
class Problem:
    """Un problème, tel qu'il se lit : le constat, le chemin, le geste.

    Les trois champs sont obligatoires. Un problème sans chemin ni action est
    une accusation, pas un diagnostic.
    """
    what: str
    where: str
    action: str
    details: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class SystemRender:
    """Ce que les trois modes font RÉELLEMENT pour un système.

    Un système sans bloc de rendu n'est pas une anomalie — les modes se
    remplissent émulateur par émulateur, chaque option lue dans l'exécutable
    livré — mais c'en devient une s'il n'est pas dit : le propriétaire
    choisirait « full » et obtiendrait, pour ce système, exactement ce qu'il
    avait avant, sans qu'un mot l'explique.
    """
    system_name: str
    declared: bool
    # Déclaré ne veut pas dire pilotant : un émulateur peut n'exposer AUCUN
    # réglage de rendu en ligne de commande — DuckStation v0.1-11609 n'a que
    # dix-sept arguments, aucun de rendu. Le déclarer avec une note dit « la
    # question a été tranchée, la réponse est non », là où l'absence de bloc
    # dit « personne n'a encore regardé ». Les confondre ferait rouvrir
    # l'enquête à chaque passage, ou pire, attendre un effet qui ne viendra
    # pas.
    pilote: bool = False
    crt: bool = False
    crt_absent: str = ""
    auto: tuple[tuple[str, str], ...] = ()   # (classe de machine, mode retenu)
    notes: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Report:
    emulators: list[tuple[str, str]]
    systems: list[tuple[str, int]]
    bios: list[SystemBios]
    problems: list[Problem]
    bios_root: pathlib.Path
    # Facultatifs : un appelant qui n'a pas les profils sous la main rend le
    # rapport d'avant, à l'identique.
    render_mode: str = ""
    render: list[SystemRender] = dataclasses.field(default_factory=list)


def _joindre(racine: str, *parties: str) -> str:
    """Concatène des chemins POUR L'AFFICHAGE, au séparateur de la racine.

    `pathlib.Path("D:\\\\Emulation") / "Dolphin"` rend « D:\\Emulation/Dolphin »
    sur Linux : mi-Windows mi-POSIX, un chemin que personne ne peut ouvrir et
    que le propriétaire recopierait tel quel. La racine d'émulation est un
    chemin Windows en production et peut être un chemin POSIX en test : c'est
    elle qui décide du séparateur.

    Les PARTIES aussi sont normalisées : `install_dir` vient du manifeste, et
    un manifeste utilisateur peut y mettre un sous-chemin Windows. Recopié
    tel quel sous une racine POSIX, il rendait le même chemin bâtard.
    """
    sep = "\\" if "\\" in racine and "/" not in racine else "/"
    segments = [s for partie in parties
                for s in re.split(r"[\\/]+", str(partie)) if s]
    return sep.join([racine.rstrip("\\/"), *segments])


def _cout(ignores: Sequence[IgnoredSystem]) -> tuple[str, ...]:
    """Ce qu'un émulateur manquant coûte, système par système.

    Le propriétaire ne compte pas ses émulateurs, il compte ses jeux : « pas
    installé » est un constat, « 42 jeux qui n'apparaîtront pas » est la
    raison d'agir. Ces lignes complètent le problème de l'émulateur au lieu
    d'en former un second — le même manque énoncé deux fois se lit comme deux
    pannes distinctes.
    """
    lignes = []
    for i in sorted(ignores, key=lambda i: i.system_name):
        jeu, s = ("jeu", "") if i.roms == 1 else ("jeux", "s")
        lignes.append(f"{i.system_name} : {i.roms} {jeu} ignoré{s} — "
                      f"absent{s} de la bibliothèque Steam")
    return tuple(lignes)


def _etat_emulateurs(
    install_dirs: dict[str, str], emulation_root: pathlib.Path,
    ignores: Sequence[IgnoredSystem] = (),
    exes: dict[str, str] | None = None,
) -> tuple[list[tuple[str, str]], list[Problem]]:
    """L'état de chaque émulateur du manifeste, LU SUR LE DISQUE.

    Lu, et non déduit des systèmes ignorés : cette liste-là ne retient que les
    systèmes qui ont des ROMs, et le verdict sur un émulateur se mettait à
    dépendre des jeux du propriétaire. Sur une console fraîchement
    provisionnée — le moment le plus probable, avant qu'il ait rien déposé —
    un émulateur amputé s'annonçait installé, et un émulateur posé à la main
    « pas installé » alors que son dossier contient l'exécutable. `scan` et
    `status` disaient deux choses du même disque.

    `ignores` ne sert donc plus qu'à CHIFFRER : combien de jeux chaque panne
    coûte. Son absence retire le coût, jamais le constat.

    `exes` porte le chemin de l'exécutable de chaque profil chargé — le seul
    que le manifeste ne connaisse pas. Sans lui, on retombe sur le témoin
    seul, et sur ce que le scan a rapporté s'il a rapporté quelque chose.
    """
    racine = str(emulation_root)
    par_profil: dict[str, list[IgnoredSystem]] = {}
    for i in ignores:
        par_profil.setdefault(i.profile, []).append(i)

    emulateurs = []
    problemes = []
    for pid in sorted(install_dirs):
        # La MÊME lecture du disque que `scan` et `install`, au même endroit :
        # le témoin de version, posé seulement après vérification de toutes
        # les archives, ET l'exécutable, qui n'atteste que lui-même.
        version = install_mod.installed_version(emulation_root, install_dirs[pid])
        sans_jeux = par_profil.get(pid, [])
        exe = (exes or {}).get(pid)
        if exe is not None:
            etat = install_mod.emulator_state(emulation_root, install_dirs[pid], exe)
            chemin_exe = install_mod.emulator_exe(
                emulation_root, install_dirs[pid], exe)
        elif sans_jeux:
            # Profil non chargé : le scan, lui, a vu l'exécutable.
            etat = sans_jeux[0].reason
            chemin_exe = sans_jeux[0].emulator
        else:
            etat = install_mod.OK if version else install_mod.ABSENT
            chemin_exe = None

        if etat == install_mod.OK:
            emulateurs.append((pid, version or "installé"))
        elif etat == install_mod.INCOMPLET:
            emulateurs.append((pid, f"{version}, exécutable introuvable"))
            problemes.append(Problem(
                what=(f"l'émulateur « {pid} » porte sa version {version}, mais "
                      "son exécutable est introuvable — l'installation est "
                      "incomplète"),
                where=str(chemin_exe),
                action=f"réinstaller : retro install --emulation-root '{racine}'",
                details=_cout(sans_jeux),
            ))
        elif etat == install_mod.SANS_TEMOIN:
            # L'exécutable est là, le témoin non. Dire « pas installé » à qui
            # voit son dossier plein le ferait douter du rapport ; dire
            # « installé » tairait que rien n'atteste sa complétude.
            emulateurs.append((pid, "présent, sans témoin de version"))
            problemes.append(Problem(
                what=(f"l'émulateur « {pid} » n'a pas été installé par "
                      "« retro install » : son exécutable est là, mais aucun "
                      "témoin de version n'atteste que l'installation soit "
                      "complète — un émulateur amputé de ses composants "
                      "paraît installé et ne lance rien"),
                where=_joindre(racine, install_dirs[pid]),
                action=(f"retro install --emulation-root '{racine}' — ou "
                        f"{install_mod.REMEDE_SANS_TEMOIN}"),
                details=_cout(sans_jeux),
            ))
        else:
            emulateurs.append((pid, "absent"))
            problemes.append(Problem(
                what=f"l'émulateur « {pid} » n'est pas installé",
                where=_joindre(racine, install_dirs[pid]),
                action=f"retro install --emulation-root '{racine}'",
                details=_cout(sans_jeux),
            ))
    return emulateurs, problemes


def _etat_lisible(fichier) -> str:
    if fichier.state == "ok":
        return "présent, empreinte vérifiée"
    if fichier.state == "absent":
        return "absent"
    return "présent mais son contenu ne correspond pas"


def _nomme(fichier) -> str:
    """Le fichier, et la région qui dit à quoi il sert quand elle est là."""
    return f"{fichier.name} ({fichier.region})" if fichier.region else fichier.name


def _probleme_groupe(systeme: SystemBios, besoin: BiosNeed,
                     bios_root: pathlib.Path) -> Problem:
    """« Aucun des trois, un seul suffit » — pas trois lignes accusatrices."""
    corrompu = any(f.state == "corrompu" for f in besoin.files)
    geste = ("déposer l'un de ces fichiers dans ce dossier — ou remplacer "
             "celui qui est corrompu") if corrompu else \
            "déposer l'un de ces fichiers dans ce dossier"
    return Problem(
        what=(f"{systeme.system_name} : aucun des {len(besoin.files)} BIOS de "
              "ce système n'est utilisable — un seul suffit, celui de la "
              "région de vos jeux"),
        details=tuple(f"{_nomme(f)} : {_etat_lisible(f)}" for f in besoin.files),
        where=str(bios_root),
        action=f"{geste}, puis relancer « retro status »",
    )


def _probleme_fichier(systeme: SystemBios, fichier,
                      bios_root: pathlib.Path) -> Problem:
    if fichier.state == "absent":
        return Problem(
            what=f"{systeme.system_name} : le BIOS {fichier.name} est absent",
            where=str(bios_root),
            action=(f"déposer {fichier.name} dans ce dossier, puis relancer "
                    "« retro status »"),
        )
    return Problem(
        what=(f"{systeme.system_name} : le BIOS {fichier.name} est corrompu — "
              "le fichier est présent mais son contenu ne correspond pas à "
              "celui attendu (peut-être renommé depuis un autre BIOS)"),
        where=str(bios_root / fichier.name),
        action="remplacer ce fichier, puis relancer « retro status »",
    )


def _problemes_bios(bios_status: list[SystemBios],
                    bios_root: pathlib.Path) -> list[Problem]:
    """La source UNIQUE des constats de BIOS.

    Un besoin, un problème — et un besoin groupé n'en fait qu'un, quel que
    soit le nombre de fichiers qu'il propose.
    """
    problemes = []
    for systeme in bios_status:
        for besoin in systeme.needs:
            if not besoin.required or besoin.satisfied:
                continue
            if besoin.group:
                problemes.append(_probleme_groupe(systeme, besoin, bios_root))
            else:
                problemes.append(
                    _probleme_fichier(systeme, besoin.files[0], bios_root))
    return problemes


def etat_rendu(profils: dict) -> list[SystemRender]:
    """Ce que les trois modes font, système par système.

    L'arbitrage de `auto` est rendu POUR CHAQUE CLASSE de machine, et non pour
    celle-ci : `retro status` tourne sur la machine qui pilote, pas sur celle
    qui joue. Annoncer un mode d'après le matériel de l'hôte serait une
    réponse fausse et convaincante.
    """
    etats = []
    for pid in sorted(profils):
        for systeme in profils[pid].systems:
            rendu = systeme.render
            if rendu is None:
                etats.append(SystemRender(systeme.name, declared=False))
                continue
            notes = tuple(m.note for m in (rendu.native, rendu.full) if m.note)
            etats.append(SystemRender(
                systeme.name, declared=True,
                pilote=bool(rendu.native.args or rendu.full.args),
                crt=bool(rendu.native.crt),
                crt_absent=rendu.native.crt_absent,
                auto=tuple((classe, render_mod.arbitrer(classe, systeme.cost))
                           for classe in render_mod.CLASSES),
                notes=notes,
            ))
    return sorted(etats, key=lambda e: e.system_name)


def _probleme_sans_modes(etats: list[SystemRender]) -> list[Problem]:
    """Un seul problème groupé, jamais un par système.

    Dix-sept lignes identiques noieraient les manques qui, eux, coûtent des
    jeux. Mais le taire ferait choisir un mode sans effet, en silence.
    """
    muets = [e.system_name for e in etats if not e.declared]
    if not muets:
        return []
    return [Problem(
        what=f"{len(muets)} système(s) n'ont aucun mode de rendu déclaré : "
             "les trois modes y lancent la même commande",
        where="retro/data/profiles/*.toml",
        action="déclarer [system.render.native] et [system.render.full] pour "
               "ces systèmes, chaque option lue dans l'exécutable livré",
        details=tuple(muets),
    )]


def _probleme_steam_input(muets: Sequence[str], echec: str = "") -> list[Problem]:
    """Un seul problème groupé, comme pour les modes de rendu.

    Steam Input masque la manette au jeu qu'il lance — mesuré sur la console
    le 2026-08-28 — et il se désactive jeu par jeu. Un jeu oublié est un jeu
    dont la manette ne répond pas, sans qu'aucun journal, ni celui de Steam ni
    celui de l'émulateur, n'en dise un mot. C'est la panne la plus coûteuse de
    cette console : elle se constate le pad en main, devant la télévision.
    """
    if echec:
        # Ne pas pouvoir vérifier n'est pas « tout va bien ». Se taire ici
        # laisserait croire que les manettes sont réglées alors que rien n'a
        # été lu — le rapport mentirait par omission sur le seul point qui se
        # constate le pad en main.
        return [Problem(
            what="Steam Input n'a pas pu être vérifié : des manettes peuvent "
                 "rester muettes sans que rien ne le signale",
            where="userdata/<compte>/config/localconfig.vdf",
            action="vérifier le chemin donné à --steam-root, puis lancer "
                   "`retro sync` Steam fermé",
            details=(echec,),
        )]
    if not muets:
        return []
    return [Problem(
        what=f"{len(muets)} jeu(x) ont encore Steam Input actif : leur manette "
             "restera muette dans l'émulateur",
        where="userdata/<compte>/config/localconfig.vdf",
        action="lancer `retro sync` Steam fermé — il éteint Steam Input sur "
               "les jeux qu'il écrit",
        details=tuple(muets),
    )]


def build_report(
    install_dirs: dict[str, str],
    emulation_root: pathlib.Path,
    systems: list[tuple[str, int]],
    bios_status: list[SystemBios],
    bios_root: pathlib.Path,
    ignored_systems: Sequence[IgnoredSystem] = (),
    emulator_exes: dict[str, str] | None = None,
    profils: dict | None = None,
    render_mode: str = "",
    steam_input_muets: Sequence[str] = (),
    steam_input_echec: str = "",
) -> Report:
    """Assemble le rapport. Ne lit que ce qui existe déjà sur le disque, et
    n'écrit jamais : `retro status` est une consultation, pas une validation.

    `ignored_systems` est ce que le scan a laissé de côté faute d'émulateur.
    Facultatif — un appelant qui ne peut pas le savoir rend le rapport d'avant
    — mais sans lui, « l'émulateur X n'est pas installé » ne dit pas ce que ça
    coûte, et le propriétaire ne relie pas ce constat aux jeux qu'il cherche.
    Il CHIFFRE le coût ; il ne décide pas de l'état d'un émulateur.

    `emulator_exes` porte l'exécutable de chaque profil chargé, que le
    manifeste ignore. Il permet de lire l'état sur le disque exactement comme
    `scan` le lit, plutôt que de le déduire — les deux commandes se
    contredisaient sur les émulateurs dont le propriétaire n'a aucun jeu.

    `steam_input_muets` porte les titres dont Steam Input est resté actif.
    Facultatif : il faut la racine Steam pour le savoir, et `retro status` ne
    l'exige pas — un rapport qui deviendrait impossible sans Steam ne se
    rendrait plus du tout sur une machine où l'on veut juste voir les BIOS.

    `bios_root` n'est pas décoratif : c'est le dossier que le propriétaire a
    donné à `--bios`, et le seul endroit où il puisse déposer ce qui manque.
    Sans lui, le rapport nommait un fichier sans jamais dire où le mettre.
    """
    emulateurs, problemes_emulateurs = _etat_emulateurs(
        install_dirs, emulation_root, ignored_systems, emulator_exes)
    rendu = etat_rendu(profils) if profils else []
    return Report(
        emulators=emulateurs,
        systems=list(systems),
        bios=list(bios_status),
        problems=[*problemes_emulateurs,
                  *_problemes_bios(bios_status, bios_root),
                  *_probleme_sans_modes(rendu),
                  *_probleme_steam_input(steam_input_muets, steam_input_echec)],
        bios_root=bios_root,
        render_mode=render_mode,
        render=rendu,
    )


def _section(titre: str, lignes: list[str], vide: str) -> list[str]:
    corps = lignes if lignes else [f"  {vide}"]
    return [titre, *corps, ""]


def _lignes_bios(report: Report) -> list[str]:
    """Ce qui VA BIEN, et rien d'autre — les manques sont dans « Problèmes ».

    Une section qui ne montrerait que les défauts laisse sans réponse la seule
    question du propriétaire qui vient de déposer un fichier : est-ce que mon
    geste a marché ? Et une section vide alors qu'un BIOS requis manque se
    lirait « tout va bien » : d'où le renvoi explicite en fin de section.
    """
    lignes = []
    for systeme in report.bios:
        for besoin in systeme.needs:
            if besoin.satisfied:
                valide = next(f for f in besoin.files if f.state == "ok")
                lignes.append(
                    f"  {systeme.system_name} : {_nomme(valide)} — "
                    "présent, empreinte vérifiée"
                )
            elif not besoin.required:
                noms = ", ".join(_nomme(f) for f in besoin.files)
                lignes.append(
                    f"  {systeme.system_name} : {noms} — absent, facultatif "
                    "(le système se lance sans)"
                )
    # La MÊME source que la section « Problèmes » : compter autrement, c'est
    # rouvrir la porte aux deux constats qui divergent.
    manques = len(_problemes_bios(report.bios, report.bios_root))
    if manques:
        lignes.append(
            f"  {manques} BIOS requis n'est pas utilisable — détail dans "
            "« Problèmes » ci-dessous" if manques == 1 else
            f"  {manques} BIOS requis ne sont pas utilisables — détail dans "
            "« Problèmes » ci-dessous"
        )
    return lignes


def _lignes_problemes(problems: list[Problem]) -> list[str]:
    lignes = []
    for p in problems:
        lignes.append(f"  - {p.what}")
        lignes += [f"      {d}" for d in p.details]
        lignes.append(f"    chemin : {p.where}")
        lignes.append(f"    action : {p.action}")
    return lignes


def _resume_auto(auto: tuple[tuple[str, str], ...]) -> str:
    """Ce que `auto` retient, classe de machine par classe de machine.

    Groupé par mode plutôt que listé par classe : « full sur machine solide,
    moyenne ; natif sur machine modeste » se lit d'un coup, là où trois lignes
    se comparent.
    """
    groupes: dict[str, list[str]] = {}
    for classe, mode in auto:
        groupes.setdefault(mode, []).append(classe)
    if len(groupes) == 1:
        return f"{next(iter(groupes))} sur toute machine"
    return " ; ".join(f"{mode} sur machine {', '.join(classes)}"
                      for mode, classes in groupes.items())


def _lignes_rendu(report: Report) -> list[str]:
    if not report.render:
        return []
    largeur = max(len(e.system_name) for e in report.render)
    lignes = []
    for e in report.render:
        nom = e.system_name.ljust(largeur)
        if not e.declared:
            # LE cas à ne pas taire : le propriétaire choisirait « full » et
            # obtiendrait exactement ce qu'il avait avant.
            lignes.append(f"  {nom}  aucun mode déclaré — les trois modes "
                          "lancent la même commande")
            continue
        if not e.pilote:
            lignes.append(f"  {nom}  cet émulateur ne pilote pas son rendu en "
                          "ligne de commande")
            for note in e.notes:
                lignes.append(f"  {' ' * largeur}    {note}")
            continue
        crt = "natif avec CRT" if e.crt else "natif sans CRT"
        lignes.append(f"  {nom}  {crt}  |  auto : {_resume_auto(e.auto)}")
        if not e.crt:
            lignes.append(f"  {' ' * largeur}    ({e.crt_absent})")
        for note in e.notes:
            lignes.append(f"  {' ' * largeur}    {note}")
    return lignes


def format_report(report: Report) -> str:
    """Le texte que l'hôte relaie tel quel au propriétaire."""
    sections: list[str] = []

    largeur_emu = max((len(cle) for cle, _ in report.emulators), default=0)
    lignes_emu = [
        f"  {cle.ljust(largeur_emu)}  {version}"
        for cle, version in sorted(report.emulators)
    ]
    sections += _section("Émulateurs", lignes_emu, "aucun émulateur déclaré")

    largeur_sys = max((len(nom) for nom, _ in report.systems), default=0)
    lignes_sys = [
        f"  {nom.ljust(largeur_sys)}  {nb:>4} {'jeu' if nb == 1 else 'jeux'}"
        for nom, nb in report.systems
    ]
    sections += _section("Systèmes", lignes_sys, "aucun système avec des ROMs")

    sections += _section(
        "BIOS", _lignes_bios(report),
        f"aucun BIOS n'est exigé par les profils chargés (dossier : "
        f"{report.bios_root})",
    )

    sections += _section(
        f"Rendu — mode « {report.render_mode} »" if report.render_mode
        else "Rendu",
        _lignes_rendu(report), "aucun système chargé")

    nb = len(report.problems)
    # 0 et 1 prennent le singulier en français : « Problème (1) », pas
    # « Problèmes (1) ». Même famille que le « 1 jeux » déjà corrigé.
    sections += _section(
        f"Problème{'s' if nb > 1 else ''} ({nb})",
        _lignes_problemes(report.problems),
        "aucun problème détecté — tout est en ordre",
    )

    return "\n".join(sections).rstrip("\n")
