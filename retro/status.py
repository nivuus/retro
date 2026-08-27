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
from collections.abc import Sequence

from retro import acquire
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
class Report:
    emulators: list[tuple[str, str]]
    systems: list[tuple[str, int]]
    bios: list[SystemBios]
    problems: list[Problem]
    bios_root: pathlib.Path


def _joindre(racine: str, *parties: str) -> str:
    """Concatène des chemins POUR L'AFFICHAGE, au séparateur de la racine.

    `pathlib.Path("D:\\\\Emulation") / "Dolphin"` rend « D:\\Emulation/Dolphin »
    sur Linux : mi-Windows mi-POSIX, un chemin que personne ne peut ouvrir et
    que le propriétaire recopierait tel quel. La racine d'émulation est un
    chemin Windows en production et peut être un chemin POSIX en test : c'est
    elle qui décide du séparateur.
    """
    sep = "\\" if "\\" in racine and "/" not in racine else "/"
    return sep.join([racine.rstrip("\\/"), *parties])


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
) -> tuple[list[tuple[str, str]], list[Problem]]:
    """La version installée de chaque émulateur du manifeste, ou son absence.

    Un émulateur est considéré installé quand son dossier porte le témoin de
    version déposé par `acquire` ; son contenu EST la version. Son absence
    n'est jamais une exception ici : un dossier non monté, un émulateur pas
    encore installé, sont des résultats à rapporter, pas des pannes à lever.

    `ignores` vient du scan : ce sont les systèmes dont il n'a rien inscrit,
    faute d'exécutable. Le témoin et l'exécutable ne disent pas la même chose,
    et leur désaccord est un cas réel — un dossier vidé à la main, une
    extraction interrompue. Dire « pas installé » à qui vient d'installer
    l'enverrait recommencer ce qu'il a déjà fait.
    """
    racine = str(emulation_root)
    par_profil: dict[str, list[IgnoredSystem]] = {}
    for i in ignores:
        par_profil.setdefault(i.profile, []).append(i)

    emulateurs = []
    problemes = []
    for pid in sorted(install_dirs):
        temoin = pathlib.Path(emulation_root) / install_dirs[pid] / acquire.TEMOIN
        try:
            version = temoin.read_text(encoding="utf-8").strip() if temoin.is_file() else None
        except OSError:
            version = None
        sans_jeux = par_profil.get(pid, [])
        if version and not sans_jeux:
            emulateurs.append((pid, version))
        elif version:
            emulateurs.append((pid, f"{version}, exécutable introuvable"))
            problemes.append(Problem(
                what=(f"l'émulateur « {pid} » porte sa version {version}, mais "
                      "son exécutable est introuvable — l'installation est "
                      "incomplète"),
                where=str(sans_jeux[0].emulator),
                action=f"réinstaller : retro install --emulation-root '{racine}'",
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


def build_report(
    install_dirs: dict[str, str],
    emulation_root: pathlib.Path,
    systems: list[tuple[str, int]],
    bios_status: list[SystemBios],
    bios_root: pathlib.Path,
    ignored_systems: Sequence[IgnoredSystem] = (),
) -> Report:
    """Assemble le rapport. Ne lit que ce qui existe déjà sur le disque, et
    n'écrit jamais : `retro status` est une consultation, pas une validation.

    `ignored_systems` est ce que le scan a laissé de côté faute d'émulateur.
    Facultatif — un appelant qui ne peut pas le savoir rend le rapport d'avant
    — mais sans lui, « l'émulateur X n'est pas installé » ne dit pas ce que ça
    coûte, et le propriétaire ne relie pas ce constat aux jeux qu'il cherche.

    `bios_root` n'est pas décoratif : c'est le dossier que le propriétaire a
    donné à `--bios`, et le seul endroit où il puisse déposer ce qui manque.
    Sans lui, le rapport nommait un fichier sans jamais dire où le mettre.
    """
    emulateurs, problemes_emulateurs = _etat_emulateurs(
        install_dirs, emulation_root, ignored_systems)
    return Report(
        emulators=emulateurs,
        systems=list(systems),
        bios=list(bios_status),
        problems=[*problemes_emulateurs, *_problemes_bios(bios_status, bios_root)],
        bios_root=bios_root,
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

    nb = len(report.problems)
    # 0 et 1 prennent le singulier en français : « Problème (1) », pas
    # « Problèmes (1) ». Même famille que le « 1 jeux » déjà corrigé.
    sections += _section(
        f"Problème{'s' if nb > 1 else ''} ({nb})",
        _lignes_problemes(report.problems),
        "aucun problème détecté — tout est en ordre",
    )

    return "\n".join(sections).rstrip("\n")
