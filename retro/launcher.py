"""Le lanceur commun, et le plan qu'on lui écrit.

Steam fige les options de lancement dans `shortcuts.vdf` au moment de la
synchronisation. Or ce qu'il faut savoir pour rendre un jeu — la résolution de
la session, ce que la machine offre — n'est connu qu'au LANCEMENT : un flux
Apollo change de résolution selon le client qui se connecte, et une résolution
figée à la synchro donnerait une image étirée sur la télévision sans que rien
ne le signale.

Steam appelle donc un lanceur commun, qui mesure, compose et lance. Le
raccourci ne porte plus que le système et la ROM :

    "D:\\Emulation\\_launcher\\retro-launch.exe"   ← exe
    duckstation.psx "G:\\ROMs\\psx\\Jeu.chd"        ← LaunchOptions

**Le lanceur ne décide rien.** Toute la politique — quel mode pour quel
système sur quelle machine, quels seuils classent une machine — est calculée
ici, en Python, où elle est testée, et ÉCRITE dans un plan qu'il se contente
de lire. Un arbitrage réimplémenté en C# aurait divergé de celui-ci au premier
changement, et rien n'aurait dit lequel des deux s'appliquait.

Il rend aussi service à un problème qui n'a rien à voir : lancé en mode
fenêtré, il supprime la console noire qu'un émulateur au sous-système CONSOLE
fait apparaître au démarrage.
"""
from __future__ import annotations

import importlib.resources
import pathlib
import shutil

from retro import render as render_mod

# Sous la racine d'émulation, et pas ailleurs : la propriété d'une entrée
# Steam se prouve par son tag ET par un exe SOUS cette racine. Un lanceur posé
# hors d'elle ferait de chaque jeu une entrée que la réconciliation ne
# reconnaîtrait plus comme sienne — elle les recréerait à chaque passage sans
# jamais supprimer les précédentes.
DIR = "_launcher"
EXE = "retro-launch.exe"
SOURCE = "retro-launch.cs"
PLAN = "systems"
MODE = "mode.txt"


def launcher_dir(emulation_root: str) -> str:
    return f"{emulation_root}\\{DIR}"


def launcher_exe(emulation_root: str) -> str:
    return f"{emulation_root}\\{DIR}\\{EXE}"


def system_key(profile_id: str, system_id: str) -> str:
    """Ce que le raccourci Steam porte pour désigner un système.

    Le couple, jamais l'identifiant de système seul : c'est ce qui reste
    non ambigu si un jour deux profils servent un système de même nom.
    """
    return f"{profile_id}.{system_id}"


def _gabarit(mode: render_mod.RenderMode, avec_crt: bool) -> str:
    """Les arguments d'un mode, NON substitués — le lanceur substituera.

    Le shader CRT accompagne le mode natif : « ce que la console d'origine
    fournissait » passait par un tube cathodique.
    """
    return " ".join(x for x in (mode.args, mode.crt if avec_crt else "") if x)


def plan_systeme(profile_id: str, systeme, emulator_exe: str,
                 workdir: str) -> str:
    """Tout ce que le lanceur doit savoir de CE système, table d'arbitrage
    comprise.

    Les trois lignes `auto_*` sont l'arbitrage de `render.resoudre`, déjà
    résolu pour chacune des classes de machine possibles. Le lanceur n'a plus
    qu'à classer la machine qu'il mesure et à lire la ligne : il ne rejoue
    aucune décision, donc il ne peut pas en prendre une autre.
    """
    rendu = systeme.render
    lignes = [
        "# Écrit par « retro sync ». Toute modification sera écrasée.",
        f"emulator={emulator_exe}",
        f"workdir={workdir}",
        f"launch={systeme.launch}",
        f"native={_gabarit(rendu.native, avec_crt=True) if rendu else ''}",
        f"full={_gabarit(rendu.full, avec_crt=False) if rendu else ''}",
        f"native_height={rendu.native_height if rendu else 0}",
        f"max_scale={rendu.max_scale if rendu else 0}",
    ]
    for classe in render_mod.CLASSES:
        # Sans bloc de rendu, les trois modes lancent la même commande. Le
        # dire ici plutôt que de laisser le lanceur le déduire d'une ligne
        # vide : `retro status` nomme ces systèmes, et le plan doit dire la
        # même chose que le rapport.
        choix = (render_mod.NATIVE if rendu is None
                 else render_mod.arbitrer(classe, systeme.cost))
        lignes.append(f"auto_{classe}={choix}")
    for nom, vram, coeurs in render_mod.SEUILS:
        lignes.append(f"threshold_{nom}={vram},{coeurs}")
    return "\n".join(lignes) + "\n"


def local_dir(emulation_root_local) -> pathlib.Path:
    """Le dossier du lanceur, sur CE disque."""
    return pathlib.Path(emulation_root_local) / DIR


def est_installe(emulation_root_local) -> bool:
    """Le lanceur est-il RÉELLEMENT là ?

    Chaque raccourci Steam pointe sur lui : absent, c'est toute la
    bibliothèque qui ne démarre plus, et l'erreur que Steam affiche ne nomme
    aucun jeu. La même exigence que pour un émulateur — `install.emulator_state`
    — parce que le coût d'une absence est ici plus grand encore.
    """
    return (local_dir(emulation_root_local) / EXE).is_file()


def lire_mode(emulation_root_local) -> str:
    """Le mode choisi par le propriétaire, ou `auto` à défaut.

    Le mode vit dans un fichier, PAS dans les options de lancement de Steam :
    l'identifiant d'un raccourci dérive de ses options, donc l'écrire là
    ferait changer d'identifiant à toute la bibliothèque à chaque changement
    de mode — et tout l'artwork serait à retélécharger pour un réglage.
    """
    fichier = local_dir(emulation_root_local) / MODE
    try:
        valeur = fichier.read_text(encoding="utf-8").strip()
    except OSError:
        return render_mod.AUTO
    return valeur if valeur in render_mod.MODES else render_mod.AUTO


def ecrire_mode(emulation_root_local, mode: str) -> pathlib.Path:
    """Pose le mode. Le lanceur le relit à chaque jeu : rien à resynchroniser."""
    if mode not in render_mod.MODES:
        raise render_mod.RenderError(
            f"mode de rendu inconnu : « {mode} ». Les modes sont "
            f"{', '.join(render_mod.MODES)}."
        )
    dossier = local_dir(emulation_root_local)
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / MODE
    fichier.write_text(mode + "\n", encoding="utf-8")
    return fichier


def ecrire_plan(emulation_root_local, emulation_root: str, profils: dict,
                install_dirs: dict[str, str]) -> list[str]:
    """Écrit un plan par système, et retire ceux qui n'ont plus de profil.

    Le retrait n'est pas une coquetterie : un plan resté là après qu'un
    système a changé d'émulateur ferait lancer l'ANCIEN, avec l'ancienne
    ligne de commande, sur une entrée Steam d'apparence normale.
    """
    dossier = local_dir(emulation_root_local) / PLAN
    dossier.mkdir(parents=True, exist_ok=True)

    ecrits = []
    for pid in sorted(profils):
        profil = profils[pid]
        exe = f"{emulation_root}\\{install_dirs[pid]}\\{profil.exe}"
        workdir = f"{emulation_root}\\{install_dirs[pid]}"
        for systeme in profil.systems:
            cle = system_key(pid, systeme.id)
            (dossier / f"{cle}.ini").write_text(
                plan_systeme(pid, systeme, exe, workdir), encoding="utf-8")
            ecrits.append(cle)

    connus = {f"{cle}.ini" for cle in ecrits}
    for perime in sorted(dossier.glob("*.ini")):
        if perime.name not in connus:
            perime.unlink()
    return ecrits


# La source du lanceur est LIVRÉE, jamais son binaire : un dépôt public n'a
# pas à faire confiance à un exécutable qu'on ne peut pas relire. Elle se
# compile sur la machine, avec le csc.exe que tout Windows porte depuis
# le .NET Framework 4.x — donc sans outil à télécharger ni empreinte à
# épingler, et le binaire se reconstruit à l'identique depuis la source
# versionnée.
SOURCES = (pathlib.Path(str(importlib.resources.files("retro")))
           / "data" / "launcher")


def deposer_source(emulation_root_local) -> list[pathlib.Path]:
    """Copie la source du lanceur et son script de compilation à leur place.

    Ne compile pas : csc.exe est un outil Windows, et cette commande tourne
    sur la machine qui pilote, laquelle n'est pas forcément celle-là. La
    compilation se déclenche sur Windows, par le script déposé ici.
    """
    dossier = local_dir(emulation_root_local)
    dossier.mkdir(parents=True, exist_ok=True)
    deposes = []
    for nom in (SOURCE, "compiler.cmd"):
        origine = SOURCES / nom
        if not origine.is_file():
            raise FileNotFoundError(
                f"{origine} manque : le paquet est incomplet. Le lanceur ne "
                "peut pas être compilé sans sa source."
            )
        cible = dossier / nom
        shutil.copyfile(origine, cible)
        deposes.append(cible)
    return deposes
