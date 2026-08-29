"""Installer tous les émulateurs du manifeste.

Un émulateur dont l'URL est morte ne doit pas priver le propriétaire des neuf
autres : chaque échec est capturé, rapporté, et l'installation continue. Ce
qu'on ne fait jamais, c'est le taire.
"""
from __future__ import annotations

import pathlib
import re
import textwrap

from retro import acquire, profiles

# Un chemin du manifeste ou d'un profil est décrit POUR WINDOWS, séparateurs
# compris. Les deux séparateurs sont acceptés : Windows lit les deux, et un
# manifeste écrit à la main porte souvent des barres obliques.
_SEPARATEURS = re.compile(r"[\\/]+")

# L'état d'une installation, vu du disque. Vocabulaire PARTAGÉ : `scan`
# décide d'inventorier ou non, `status` en fait une phrase, et les deux
# doivent dire la même chose du même dossier — sans quoi une commande
# inventorie ce que l'autre déclare absent.
OK = "ok"
ABSENT = "absent"          # rien : ni témoin, ni exécutable
INCOMPLET = "incomplet"    # le témoin est là, l'exécutable non
SANS_TEMOIN = "sans-témoin"  # l'exécutable est là, rien n'atteste l'installation

MOTIFS = {
    ABSENT: "l'émulateur n'est pas installé",
    INCOMPLET: "l'installation est incomplète : l'exécutable est introuvable",
    SANS_TEMOIN: ("l'installation n'est pas attestée : le témoin "
                  f"{acquire.TEMOIN} manque"),
}

# `retro install` n'installe QUE ce que le manifeste décrit. Opposer cette
# seule commande à un profil qui ne figure dans aucun manifeste est un
# cul-de-sac : le propriétaire relance, rien ne change, rien ne l'explique.
# Les deux issues se disent donc ensemble.
REMEDE_SANS_TEMOIN = (
    "déclarer cet émulateur au manifeste utilisateur (--user-manifest) : "
    "« retro install » ne peut installer que ce qui y figure"
)


def local_path(emulation_root, *chemins: str) -> pathlib.Path:
    """Un chemin DÉCRIT POUR WINDOWS, ouvert sur le disque LOCAL.

    `install_dir` et `exe` sont des chaînes Windows jusque dans leurs
    séparateurs : les archives officielles ont toutes un dossier racine, et
    les profils livrés portent « RetroArch-Win64\\retroarch.exe ». Sous
    Linux, l'antislash n'est pas un séparateur : joint tel quel, il fabrique
    un segment UNIQUE « RetroArch/RetroArch-Win64\\retroarch.exe » qu'aucun
    is_file() ne confirme. Mesuré : tous les systèmes ignorés, inventaire
    vide, et chaque émulateur accusé d'être absent alors qu'il est intact.

    Windows masque le défaut, l'antislash y étant un séparateur — or ces
    chemins ne servent à vérifier quoi que ce soit que HORS Windows. Le seul
    cas d'usage qui les justifie est donc le seul où ils cassaient.
    """
    parties = [p for chemin in chemins
               for p in _SEPARATEURS.split(str(chemin)) if p]
    return pathlib.Path(emulation_root).joinpath(*parties)


def install_path(emulation_root, install_dir: str) -> pathlib.Path:
    """Le dossier où cet émulateur s'installe, sur CE disque."""
    return local_path(emulation_root, install_dir)


def emulator_exe(emulation_root, install_dir: str, exe: str) -> pathlib.Path:
    """L'exécutable de cet émulateur, sur CE disque."""
    return local_path(emulation_root, install_dir, exe)


def installed_version(emulation_root, install_dir: str) -> str | None:
    """La version déposée par `acquire`, ou None si rien ne l'atteste.

    Le témoin n'est écrit qu'APRÈS que toutes les archives ont été vérifiées
    et extraites — RetroArch sans ses cores ne lance rien tout en paraissant
    installé. Sa présence est donc un signal de complétude plus fort que
    celle de l'exécutable. Un dossier illisible n'est pas une exception ici :
    c'est un résultat à rapporter.
    """
    temoin = local_path(emulation_root, install_dir, acquire.TEMOIN)
    try:
        if not temoin.is_file():
            return None
        return temoin.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def emulator_state(emulation_root, install_dir: str, exe: str) -> str:
    """Ce que le disque dit de cet émulateur : OK, ABSENT, INCOMPLET ou
    SANS_TEMOIN.

    Les deux témoignages sont exigés parce qu'ils mentent séparément : un
    témoin sans exécutable est un dossier vidé à la main, un exécutable sans
    témoin est une installation dont personne n'a vérifié les archives.
    """
    version = installed_version(emulation_root, install_dir)
    present = emulator_exe(emulation_root, install_dir, exe).is_file()
    if version and present:
        return OK
    if version:
        return INCOMPLET
    if present:
        return SANS_TEMOIN
    return ABSENT


def install_all(manifeste: dict, emulation_root: pathlib.Path,
                fetch=acquire._fetch) -> list[tuple[str, str]]:
    resultats = []
    for cle in sorted(manifeste):
        try:
            etat = acquire.acquire(manifeste[cle], emulation_root, fetch=fetch)
        except acquire.AcquireError as exc:
            etat = f"ÉCHEC : {exc}"
        resultats.append((cle, etat))
    return resultats


def format_install_report(resultats: list[tuple[str, str]]) -> str:
    lignes = []
    for cle, etat in resultats:
        marque = "!" if etat.startswith("ÉCHEC") else "·"
        lignes.append(f"  {marque} {cle} : {etat}")
    echecs = [c for c, e in resultats if e.startswith("ÉCHEC")]
    if echecs:
        lignes.append(f"  {len(echecs)} émulateur(s) non installé(s) : "
                      f"{', '.join(echecs)}")
    return "\n".join(lignes)


# CE QU'UNE MONTÉE DE VERSION VIENT D'EFFACER, ET QUE PERSONNE NE VOIT PARTIR.
#
# `acquire` supprime le dossier d'installation (shutil.rmtree) avant de
# réextraire. Les configurations d'amorçage qui vivent SOUS ce dossier partent
# avec lui — pour RPCS3, c'est le fichier sans lequel `cfg_player` vaut
# `pad_handler::null`, c'est-à-dire aucune manette du tout.
#
# Le mécanisme les repose au lancement suivant : le régime « si-absent » voit
# la cible disparue et la recrée. Ce n'est donc PAS une panne. Ce qui manquait
# est le MESSAGE : entre la mise à jour et la partie suivante, la manette ne
# répond pas, et une manette muette ne ressemble en rien à une mise à jour.
# Sans cette phrase, le propriétaire cherche du côté du pad, des pilotes, de
# Steam — partout sauf là où c'est.

# Les deux états d'`acquire` qui ont effacé quelque chose. « à jour » n'a rien
# touché : l'y ajouter ferait crier ce message à chaque `retro install`, y
# compris ceux qui ne téléchargent rien, et un message qui crie tous les jours
# ne se lit plus le jour où il est vrai.
#
# Le couplage est par CHAÎNE, et il est gardé par un test qui fait tourner une
# vraie installation : le changer d'un seul côté rendrait ce rapport vide, sans
# erreur ni symptôme.
ETATS_EFFACANTS = ("installé", "réinstallé")


def configurations_effacees(resultats, emulateurs, profils) -> list[tuple[str, str]]:
    """(profil, cible) des amorçages disparus avec le dossier d'installation.

    Seuls ceux dont la cible commence par le jeton du dossier d'installation :
    un %USERPROFILE% survit à toutes les montées de version, et l'annoncer
    effacé enverrait chercher une panne là où il n'y en a pas.

    Le lien manifeste → profil est `emu.profile`, celui qu'`_install_dirs_pour`
    emploie déjà. La clé du manifeste n'est PAS l'identifiant du profil, et les
    confondre rendrait une liste vide — donc un silence, qui est très
    exactement ce que cette fonction existe pour rompre.
    """
    effaces = []
    for cle, etat in resultats:
        if etat not in ETATS_EFFACANTS:
            continue
        emu = emulateurs.get(cle)
        profil = profils.get(emu.profile) if emu else None
        if profil is None:
            continue
        effaces += [(profil.id, b.target) for b in profil.bootstraps
                    if b.target.startswith(profiles.JETON_INSTALL)]
    return effaces


def format_configurations_effacees(effacees: list[tuple[str, str]]) -> str:
    """Le rapport de ce qui vient de partir, ou rien du tout s'il n'y a rien.

    Rendre une phrase là où il n'y a rien à dire (« aucune configuration
    effacée ») allongerait la sortie de chaque installation d'une ligne vraie
    et inutile, jusqu'à ce que plus personne ne lise les lignes voisines.
    """
    lignes = []
    for pid, cible in effacees:
        # La cible est écrite TELLE QU'ELLE VIT dans le profil, jeton compris.
        # Au moment de l'installation, le nom du dossier est connu, mais le
        # chemin que la console verra ne l'est pas : inventer ici un chemin
        # Windows en ferait un faux à copier-coller, et le propriétaire irait
        # regarder un fichier qui n'existe pas.
        lignes.append(textwrap.fill(
            f"{pid} : sa configuration a été effacée avec son dossier "
            f"({cible}). Elle sera reposée au prochain lancement d'un de ses "
            "jeux — d'ici là, cet émulateur repart sur ses défauts : une "
            "manette qui ne répond pas, une fenêtre que rien ne ferme.",
            width=78, initial_indent="  · ", subsequent_indent="    ",
            # La cible ne porte pas d'espace : elle ne peut pas être coupée en
            # deux par le remplissage, et reste copiable d'un seul geste.
            break_long_words=False, break_on_hyphens=False,
        ))
    return "\n".join(lignes)
