"""Le rapport que lit un humain.

Tout le reste de ce paquet tourne sans témoin : `sync`, `install` et `scan`
s'adressent à Steam ou au disque, jamais à une personne. `status` est
l'exception — son seul but est d'être lu par le propriétaire, souvent depuis
son canapé, sans clavier, pour comprendre pourquoi un jeu ne se lance pas.

Deux règles en découlent directement :

- « corrompu » et « absent » ne se disent pas de la même façon. Un BIOS
  corrompu est LÀ — souvent un fichier renommé, bon nom et mauvais contenu.
  Dire « manquant » enverrait le propriétaire chercher ce qu'il a déjà déposé.
- une section vide se lit comme une panne d'affichage. Quand il n'y a rien à
  signaler, le rapport le dit, plutôt que de laisser un blanc que personne ne
  peut distinguer d'un bug.

`build_report` ne modifie jamais rien : ni fichier, ni dossier, ni cache.
C'est une consultation, pas une validation.
"""
from __future__ import annotations

import dataclasses
import pathlib

from retro import acquire
from retro.bios import SystemBios


@dataclasses.dataclass(frozen=True)
class Report:
    emulators: list[tuple[str, str]]
    systems: list[tuple[str, int]]
    bios: list[SystemBios]
    problems: list[str]


def _etat_emulateurs(
    install_dirs: dict[str, str], emulation_root: pathlib.Path,
) -> tuple[list[tuple[str, str]], list[str]]:
    """La version installée de chaque émulateur du manifeste, ou son absence.

    Un émulateur est considéré installé quand son dossier porte le témoin de
    version déposé par `acquire` ; son contenu EST la version. Son absence
    n'est jamais une exception ici : un dossier non monté, un émulateur pas
    encore installé, sont des résultats à rapporter, pas des pannes à lever.
    """
    emulateurs = []
    problemes = []
    for pid in sorted(install_dirs):
        temoin = pathlib.Path(emulation_root) / install_dirs[pid] / acquire.TEMOIN
        try:
            version = temoin.read_text(encoding="utf-8").strip() if temoin.is_file() else None
        except OSError:
            version = None
        if version:
            emulateurs.append((pid, version))
        else:
            emulateurs.append((pid, "absent"))
            problemes.append(f"{pid} n'est pas installé")
    return emulateurs, problemes


def _problemes_bios(bios_status: list[SystemBios]) -> list[str]:
    """Un problème par fichier de BIOS requis dont l'état n'est pas « ok »,
    en distinguant explicitement l'absent du corrompu — c'est tout l'objet
    de ce module."""
    problemes = []
    for systeme in bios_status:
        for fichier in systeme.files:
            if not fichier.required or fichier.state == "ok":
                continue
            if fichier.state == "absent":
                problemes.append(f"{systeme.system_name} : BIOS {fichier.name} absent")
            else:  # "corrompu"
                problemes.append(
                    f"{systeme.system_name} : BIOS {fichier.name} corrompu — "
                    "le fichier est présent mais son contenu ne correspond "
                    "pas à celui attendu (peut-être renommé depuis un autre "
                    "BIOS)"
                )
    return problemes


def build_report(
    install_dirs: dict[str, str],
    emulation_root: pathlib.Path,
    systems: list[tuple[str, int]],
    bios_status: list[SystemBios],
) -> Report:
    """Assemble le rapport. Ne lit que ce qui existe déjà sur le disque, et
    n'écrit jamais : `retro status` est une consultation, pas une validation.
    """
    emulateurs, problemes_emulateurs = _etat_emulateurs(install_dirs, emulation_root)
    problemes_bios = _problemes_bios(bios_status)
    return Report(
        emulators=emulateurs,
        systems=list(systems),
        bios=list(bios_status),
        problems=[*problemes_emulateurs, *problemes_bios],
    )


def _section(titre: str, lignes: list[str], vide: str) -> list[str]:
    corps = lignes if lignes else [f"  {vide}"]
    return [titre, *corps, ""]


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

    lignes_bios = []
    for systeme in report.bios:
        for fichier in systeme.files:
            if not fichier.required or fichier.state == "ok":
                continue
            if fichier.state == "absent":
                lignes_bios.append(
                    f"  {systeme.system_name} : MANQUANT : {fichier.name}"
                )
            else:  # "corrompu"
                lignes_bios.append(
                    f"  {systeme.system_name} : CORROMPU : {fichier.name} "
                    "(le fichier est là mais ne correspond pas — il a "
                    "peut-être été renommé)"
                )
    sections += _section("BIOS", lignes_bios, "aucun problème de BIOS détecté")

    lignes_pb = [f"  - {p}" for p in report.problems]
    sections += _section(
        f"Problèmes ({len(report.problems)})", lignes_pb,
        "aucun problème détecté — tout est en ordre",
    )

    return "\n".join(sections).rstrip("\n")
