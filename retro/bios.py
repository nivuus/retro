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

from retro import lecture


@dataclasses.dataclass(frozen=True)
class BiosFile:
    name: str
    expected_md5: str
    required: bool
    state: str  # "ok" | "absent" | "corrompu"
    group: str | None = None
    region: str = ""
    # LE SOUS-DOSSIER QUE L EMULATEUR DECLARE, sous son propre dossier de
    # BIOS. Vide pour presque tous : le fichier va a la racine. FBNeo, lui,
    # declare « fbneo/neogeo.zip » dans son propre .info — le sous-dossier
    # fait partie de ce que l emulateur dit, ce n est pas une supposition.
    #
    # Il ne concerne QUE le portage. La verification, elle, cherche par NOM
    # dans le dossier du proprietaire (bios._trouver), qui range comme il veut.
    subdir: str = ""


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
                        obtenu = lecture.md5(chemin)
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
                    subdir=declare.get("dir", ""),
                ))
            resultat.append(SystemBios(
                system_id=systeme.id, system_name=systeme.name,
                files=tuple(fichiers),
            ))
    return resultat


# --- Obtenir ce qui manque -------------------------------------------------
#
# CE PAQUET NE DISTRIBUE TOUJOURS AUCUN BIOS. Ce qui suit télécharge depuis une
# source QUE LE PROPRIÉTAIRE A DÉCLARÉE dans son manifeste, exactement comme
# `retro install` télécharge chaque émulateur depuis l'URL que le manifeste
# porte. Le manifeste noyau, livré dans un dépôt public, n'en déclare aucune.
#
# ET LA SOURCE N'EST PAS CRUE. Le fichier reçu est comparé au md5 QUE LE PROFIL
# DÉCLARE — jamais à un md5 rendu par la source, qui n'attesterait que d'elle.
# C'est la même règle que l'empreinte SHA256 des émulateurs, et elle vaut ici
# davantage : un émulateur faux plante, un BIOS faux démarre.

OBTENU = "obtenu"
DEJA_LA = "deja-la"
# Reçu, mais ce n'est pas ce fichier-là. RIEN N'EST ÉCRIT. Distinct d'une
# panne de réseau : celle-ci se réessaie, celle-là veut qu'on regarde la
# source.
REFUSE = "refuse"
INJOIGNABLE = "injoignable"


@dataclasses.dataclass(frozen=True)
class Obtention:
    """Ce qu'il est advenu d'UN fichier. Le rapport les énonce un par un :
    « 3 obtenus » sur quatre demandés laisse chercher lequel a échoué."""
    name: str
    system_name: str
    state: str
    detail: str = ""


def _a_obtenir(etats: list[SystemBios]) -> list[tuple[str, BiosFile]]:
    """Les fichiers qu'il vaut la peine de demander, sans doublon.

    UN BESOIN NON SATISFAIT FAIT DEMANDER TOUS SES CANDIDATS, pas seulement le
    premier. Les trois BIOS PlayStation sont interchangeables, mais lequel
    convient dépend de la RÉGION des jeux — que ce module ne connaît pas. En
    prendre un au hasard ferait rapporter « obtenu » sur un fichier qui ne sert
    pas à cette bibliothèque-là, et le jeu resterait sur son écran noir.

    Un besoin DÉJÀ satisfait ne fait rien demander : le propriétaire a déposé
    le sien, et le rapport n'a pas à le doubler des deux autres régions.

    Un fichier CORROMPU est redemandé. Ce n'est pas un réglage du
    propriétaire — c'est un fichier qui ne sert à rien, et le remplacer est la
    seule réparation. Le rapport le dit plutôt que de le faire en silence.
    """
    vus = set()
    sortie = []
    for systeme in etats:
        for besoin in systeme.needs:
            if besoin.satisfied:
                continue
            for f in besoin.files:
                if f.name.lower() in vus:
                    continue
                vus.add(f.name.lower())
                sortie.append((systeme.system_name, f))
    return sortie


def fetch_bios(profils: dict, bios_root: pathlib.Path, source,
               fetch=None) -> list[Obtention]:
    """Télécharge les BIOS manquants, et n'écrit que ce qui est vérifié.

    `source` porte l'adresse ; None veut dire qu'aucune n'est déclarée, ce qui
    est le cas normal et n'est pas une erreur — l'appelant le dit.

    L'ORDRE COMPTE : vérifier PUIS écrire. Écrire d'abord, quitte à effacer
    ensuite, laisserait après une coupure un fichier de la bonne taille et du
    mauvais contenu dans le dossier des BIOS — que `check_bios` rapporterait
    « corrompu », donc rattrapable, mais qu'un émulateur aurait chargé entre
    temps.
    """
    if fetch is None:
        from retro.acquire import _fetch as fetch
    etats = check_bios(profils, bios_root)
    resultats = []
    for nom_systeme, f in _a_obtenir(etats):
        if source is None:
            continue
        url = source.url_for(f.name)
        try:
            blob = fetch(url)
        except Exception as exc:  # noqa: BLE001 — toute panne de transport
            resultats.append(Obtention(
                name=f.name, system_name=nom_systeme, state=INJOIGNABLE,
                detail=f"{url} : {exc}"))
            continue
        obtenu = hashlib.md5(blob).hexdigest()
        if obtenu != f.expected_md5:
            resultats.append(Obtention(
                name=f.name, system_name=nom_systeme, state=REFUSE,
                detail=(f"empreinte inattendue : {obtenu} reçu, "
                        f"{f.expected_md5} attendu ({url}). Rien n'a été "
                        "écrit — un BIOS faux ne se distingue d'un BIOS "
                        "absent qu'une fois en jeu.")))
            continue
        try:
            bios_root.mkdir(parents=True, exist_ok=True)
            provisoire = bios_root / (f.name + ".partiel")
            provisoire.write_bytes(blob)
            provisoire.replace(bios_root / f.name)
        except OSError as exc:
            resultats.append(Obtention(
                name=f.name, system_name=nom_systeme, state=INJOIGNABLE,
                detail=f"écriture impossible dans {bios_root} : {exc}"))
            continue
        resultats.append(Obtention(
            name=f.name, system_name=nom_systeme, state=OBTENU,
            detail="remplace un fichier corrompu" if f.state == "corrompu"
                   else ""))
    return resultats


# --- Porter les BIOS là où l'émulateur regarde -----------------------------
#
# LE DOSSIER DU PROPRIÉTAIRE N'EST PAS CELUI DE L'ÉMULATEUR. `check_bios`
# vérifie le premier ; c'est le second qu'un jeu interroge. Tant que rien ne
# les reliait, le rapport pouvait annoncer « présent, empreinte vérifiée » sur
# un émulateur qui ne voyait aucun BIOS — le pire des états, un rapport qui
# ment, et il ment d'autant mieux qu'il est VERT.

PORTE = "porte"
DEJA_PORTE = "deja-porte"
# Le profil ne déclare pas de `bios_dir`. Ce n'est PAS « cet émulateur n'en a
# pas besoin » : c'est « personne n'a mesuré où il regarde ». Deviner
# déposerait les fichiers à côté, sans autre symptôme qu'un écran noir.
SANS_DOSSIER = "sans-dossier"


@dataclasses.dataclass(frozen=True)
class Portage:
    name: str
    profile: str
    state: str
    detail: str = ""


def place_bios(profils: dict, bios_root: pathlib.Path,
               emulation_root_local: pathlib.Path,
               install_dirs: dict) -> list[Portage]:
    """Copie chaque BIOS VÉRIFIÉ dans le dossier où son émulateur regarde.

    Seuls les fichiers dont `check_bios` dit « ok » sont portés : copier un
    fichier corrompu le rendrait indiscernable d'un bon aux yeux de
    l'émulateur, et le rapport, lui, continuerait de le dire corrompu — deux
    vérités contradictoires sur la même machine.

    La copie se REFAIT à chaque appel plutôt que de se fier à une présence :
    « retro install » efface le dossier d'installation à chaque montée de
    version, donc le dossier de BIOS de l'émulateur disparaît avec lui. C'est
    la même raison qui fait rejouer l'amorçage.
    """
    resultats = []
    for pid in sorted(profils):
        profil = profils[pid]
        declares = {b["file"]: b for s in profil.systems for b in s.bios}
        if not declares:
            continue
        if not profil.bios_dir:
            resultats.append(Portage(
                name=", ".join(sorted(declares)), profile=pid,
                state=SANS_DOSSIER,
                detail="ce profil ne dit pas où cet émulateur cherche ses "
                       "BIOS : rien n'a été porté, et rien n'a été deviné"))
            continue
        dossier = emulation_root_local.joinpath(
            install_dirs.get(pid, pid),
            *pathlib.PureWindowsPath(profil.bios_dir).parts)
        for etat in check_bios({pid: profil}, bios_root):
            for f in etat.files:
                if f.state != "ok":
                    continue
                source = _trouver(bios_root, f.name)
                sous = (dossier.joinpath(*pathlib.PureWindowsPath(f.subdir).parts)
                        if f.subdir else dossier)
                cible = sous / f.name
                try:
                    if cible.is_file() and \
                            lecture.md5(cible) == f.expected_md5:
                        resultats.append(Portage(name=f.name, profile=pid,
                                                 state=DEJA_PORTE,
                                                 detail=str(sous)))
                        continue
                    sous.mkdir(parents=True, exist_ok=True)
                    provisoire = sous / (f.name + ".partiel")
                    provisoire.write_bytes(lecture.octets(source))
                    provisoire.replace(cible)
                except OSError as exc:
                    resultats.append(Portage(
                        name=f.name, profile=pid, state=INJOIGNABLE,
                        detail=f"{sous} : {exc}"))
                    continue
                resultats.append(Portage(name=f.name, profile=pid,
                                         state=PORTE, detail=str(sous)))
    return resultats
