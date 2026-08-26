"""Les BIOS que les émulateurs exigent, et ce qui manque.

Sans BIOS, un jeu PlayStation apparaît dans Steam, se lance, écran noir. Rien
n'explique pourquoi, et le propriétaire est sur son canapé sans clavier : ce
module existe pour que « rien ne se passe » devienne une phrase lisible.

Trois états, pas deux. « Corrompu » n'est pas « absent » : le propriétaire
croit avoir déposé le fichier, et lui dire qu'il manque l'enverrait chercher ce
qui est déjà là.

Et un BESOIN n'est pas un fichier. Les trois BIOS PlayStation sont
interchangeables — celui de la région des jeux suffit — donc ils forment un
seul besoin, pas trois. Comptés un par un, ils faisaient dire au rapport
« MANQUANT : scph5500.bin » et « MANQUANT : scph5502.bin » à quelqu'un qui
venait de déposer scph5501.bin, le bon : la règle centrale du paquet exactement
à l'envers, sur son propre cas d'exemple.
"""
from __future__ import annotations

import dataclasses
import hashlib
import pathlib


@dataclasses.dataclass(frozen=True)
class BiosFile:
    name: str
    expected_md5: str
    required: bool
    state: str  # "ok" | "absent" | "corrompu"
    group: str | None = None
    region: str = ""


@dataclasses.dataclass(frozen=True)
class BiosNeed:
    """Ce qu'il manque, ou pas : un fichier précis, ou « un parmi ceux-ci ».

    C'est l'unité que le rapport énonce. Un besoin groupé est satisfait dès
    qu'un seul de ses fichiers est valide.
    """
    files: tuple[BiosFile, ...]
    required: bool
    group: str | None = None

    @property
    def satisfied(self) -> bool:
        return any(f.state == "ok" for f in self.files)


@dataclasses.dataclass(frozen=True)
class SystemBios:
    system_id: str
    system_name: str
    files: tuple[BiosFile, ...]

    @property
    def needs(self) -> tuple[BiosNeed, ...]:
        """Les besoins du système, dans l'ordre de déclaration du profil.

        Les fichiers d'un même groupe se replient sur le besoin du PREMIER
        d'entre eux : l'ordre du profil est celui que le propriétaire lira.
        """
        besoins: list[BiosNeed] = []
        par_groupe: dict[str, int] = {}
        for f in self.files:
            if f.group and f.group in par_groupe:
                rang = par_groupe[f.group]
                besoins[rang] = dataclasses.replace(
                    besoins[rang], files=besoins[rang].files + (f,))
                continue
            if f.group:
                par_groupe[f.group] = len(besoins)
            besoins.append(BiosNeed(files=(f,), required=f.required,
                                    group=f.group))
        return tuple(besoins)

    @property
    def ok(self) -> bool:
        return not self.missing_required

    @property
    def missing_required(self) -> tuple[str, ...]:
        """Les fichiers qu'il reste à obtenir. Pour un besoin groupé, tous
        les candidats sont nommés — n'importe lequel le satisfait."""
        return tuple(f.name for n in self.needs if n.required and not n.satisfied
                     for f in n.files)


def _trouver(racine: pathlib.Path, nom: str) -> pathlib.Path | None:
    """Le fichier, quelle que soit la casse de son nom.

    Le propriétaire dépose ses BIOS depuis Windows, qui ne distingue pas la
    casse ; ce code tourne peut-être sur un système qui la distingue.
    """
    try:
        direct = racine / nom
        if direct.is_file():
            return direct
        if not racine.is_dir():
            return None
        cible = nom.lower()
        for f in racine.iterdir():
            if f.is_file() and f.name.lower() == cible:
                return f
    except OSError:
        # Un dossier illisible est indiscernable d'un dossier absent du point de
        # vue du propriétaire : dans les deux cas, ses BIOS ne servent à rien.
        return None
    return None


def check_bios(profils: dict, bios_root: pathlib.Path) -> list[SystemBios]:
    """L'état des BIOS, système par système. Ne lève jamais : une racine
    absente — un partage non monté — est un résultat, pas une erreur."""
    resultat = []
    for pid in sorted(profils):
        for systeme in profils[pid].systems:
            fichiers = []
            for declare in systeme.bios:
                nom = declare["file"]
                attendu = declare["md5"].lower()
                chemin = _trouver(bios_root, nom)
                if chemin is None:
                    etat = "absent"
                else:
                    try:
                        obtenu = hashlib.md5(chemin.read_bytes()).hexdigest()
                    except OSError:
                        # Présent mais illisible — permissions refusées, partage
                        # qui répond sans servir. « Corrompu » est exactement ce
                        # que c'est pour le propriétaire : le fichier est là et
                        # ne sert à rien. Lever ici ferait échouer le rapport
                        # entier pour un seul fichier.
                        etat = "corrompu"
                    else:
                        etat = "ok" if obtenu == attendu else "corrompu"
                fichiers.append(BiosFile(
                    name=nom, expected_md5=attendu,
                    required=bool(declare.get("required", True)), state=etat,
                    group=declare.get("group") or None,
                    region=declare.get("region", ""),
                ))
            resultat.append(SystemBios(
                system_id=systeme.id, system_name=systeme.name,
                files=tuple(fichiers),
            ))
    return resultat
