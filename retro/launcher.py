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

from retro import profiles as profiles_mod
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


def config_name(cle: str, mode: str) -> str:
    """Le nom du fichier de réglages d'un mode, s'il en a un."""
    return f"{cle}.{mode}.cfg"


BOOTSTRAP = "bootstrap"

# Les deux régimes d'écriture d'une configuration d'émulateur. Ils portent
# sur LE MÊME fichier et ne se déclarent pas : le profil les distingue par
# STRUCTURE — `content` pour l'un, `enforced` pour l'autre — de sorte qu'on ne
# puisse pas mettre le régime annoncé en contradiction avec ce qu'il contient.
#
# SI_ABSENT — le fichier est posé s'il n'existe pas, et plus jamais retouché.
#   Ce sont des préférences : le propriétaire les change dans l'interface de
#   son émulateur, et son choix tient.
#
# FUSION — les clés que la console IMPOSE, reposées à chaque lancement. Le
#   propriétaire l'a autorisé le 2026-08-29, et pour ces clés-là seulement :
#   sans elles, un jeu ne démarre pas sans clavier — assistant de première
#   configuration, fenêtre de mise à jour, plein écran manquant. Autorisé à
#   MODIFIER, jamais à ÉCRASER : la fusion ne touche qu'aux clés qu'elle
#   apporte, préserve tout le reste — clés inconnues, commentaires, ordre —
#   sauvegarde avant d'écrire, et ne réécrit rien si le fichier est déjà
#   conforme.
#
#   Un seul mécanisme pour deux dettes, délibérément : le remplissage de
#   DuckStation (D2) et sa manette (D3) se règlent tous deux dans un
#   settings.ini que « si-absent » ne rouvre jamais. Un mécanisme par dette
#   aurait divergé sur le MÊME fichier, ce que ce dépôt s'interdit déjà pour
#   les configurations d'entrée. D3 n'a qu'à ajouter sa section [Pad1] au
#   champ `enforced` du profil : rien d'autre à écrire.
SI_ABSENT = "si-absent"
FUSION = "fusion"
STRATEGIES = (SI_ABSENT, FUSION)


IMPOSE = "impose"


def _suffixe(target: str) -> str:
    """L'extension de la CIBLE, ou « .txt » si elle n'en a pas.

    Elle se prend sur la cible BRUTE, jetons compris : c'est son extension qui
    compte, et la substitution ne la change pas. Un `.yml` déposé sous un nom
    en `.ini` se lirait comme un fichier d'un autre format, et le premier
    lecteur du dossier n'aurait aucun moyen de savoir ce qu'il regarde.
    """
    return pathlib.PureWindowsPath(target).suffix or ".txt"


def enforced_name(profile_id: str, index: int, target: str) -> str:
    """Le nom du fragment des clés IMPOSÉES, déposé à côté des plans.

    Un fichier SÉPARÉ de celui de l'amorçage, et non un second bloc dans le
    même : les deux ont des durées de vie différentes — l'un n'est lu qu'une
    fois, l'autre à chaque lancement — et le lanceur doit pouvoir prendre le
    second sans rouvrir le premier.

    `index` est le rang de l'entrée dans le profil, 1-based. Sans lui, les deux
    cibles d'un même profil se disputeraient un nom de fichier, et le contenu
    de l'une serait posé dans l'autre — un YAML dans un INI, sans un mot.
    """
    return f"{profile_id}.{IMPOSE}.{index}{_suffixe(target)}"


def bootstrap_name(profile_id: str, index: int, target: str) -> str:
    """Le nom du fichier d'amorçage déposé à côté des plans.

    `profils_amorcables` retrouve l'identifiant du profil en coupant ce nom sur
    « .bootstrap » : l'indice se place APRÈS, jamais avant, sinon plus aucun
    profil ne serait ré-amorçable.
    """
    return f"{profile_id}.{BOOTSTRAP}.{index}{_suffixe(target)}"


def fragments_attendus(profile_id: str, index: int,
                       amorcage) -> list[tuple[str, str]]:
    """Ce qu'une entrée d'amorçage FAIT DÉPOSER : (nom de fichier, texte).

    UNE seule définition, employée par l'écriture ET par le contrôle. Deux
    divergeraient au premier changement de convention, et le contrôle finirait
    par accuser un fragment parfaitement à jour — ou, bien pire, par bénir un
    fragment périmé, ce qui est exactement la panne qu'il existe pour attraper.

    Le fichier des clés imposées n'est là que si l'entrée impose quelque
    chose : un fragment vide déposé se lirait comme « rien n'est imposé »,
    alors que le plan, lui, porterait déjà la ligne vide qui le dit.
    """
    fragments = [(bootstrap_name(profile_id, index, amorcage.target),
                  amorcage.content)]
    if amorcage.enforced:
        # Le saut de ligne final fait partie du fichier déposé : la comparaison
        # du contrôle est faite à l'octet près, et l'omettre ici ferait crier
        # au loup à chaque passage sur un fragment tout neuf.
        fragments.append((enforced_name(profile_id, index, amorcage.target),
                          amorcage.enforced + "\n"))
    return fragments


def lire_fragments(emulation_root_local) -> dict[str, str] | None:
    """Ce que le dossier des plans porte RÉELLEMENT : nom → texte.

    `None` et `{}` ne disent pas la même chose, et les confondre serait la
    faute : `None` veut dire que le dossier n'existe pas — « retro scan » n'a
    jamais tourné sur cette machine, ou l'hôte consulte le rapport sans voir le
    disque de la console —, et il n'y a alors rien à reprocher à personne. `{}`
    veut dire qu'il a tourné et n'a rien eu à déposer.

    Les erreurs de décodage ne sont pas rattrapées en silence vers un texte
    « probablement correct » : un fragment illisible N'EST PAS conforme, et le
    faire passer pour tel rendrait ce contrôle inutile précisément le jour où
    il servirait.
    """
    dossier = local_dir(emulation_root_local) / PLAN
    try:
        fichiers = [p for p in dossier.iterdir() if p.is_file()]
    except OSError:
        return None
    lus: dict[str, str] = {}
    for fichier in fichiers:
        try:
            lus[fichier.name] = fichier.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            lus[fichier.name] = ""
    return lus


def resoudre_cible(target: str, install_dir_windows: str) -> str:
    """La cible, jetons substitués — comme {render_config}.

    ICI et non dans le lanceur, pour la raison exacte qui a fait résoudre
    {render_config} ici : le chemin ne dépend pas de la session, et le laisser
    au lanceur lui ferait reconstruire une convention de nommage. Elle ne se
    décide qu'à un endroit — sinon deux, qui divergeraient au premier
    changement, et rien ne dirait laquelle s'applique.

    `install_dir_windows` est le `workdir` du plan : la racine d'émulation
    suivie du dossier d'installation TEL QUE LE MANIFESTE le nomme, surcharge
    du propriétaire comprise. Le profil n'a donc jamais à réécrire ce nom.
    """
    return target.replace(profiles_mod.JETON_INSTALL, install_dir_windows)


def plan_systeme(profile_id: str, systeme, emulator_exe: str,
                 workdir: str, plan_dir: str = "", bootstraps=()) -> str:
    """Tout ce que le lanceur doit savoir de CE système, table d'arbitrage
    comprise.

    Les trois lignes `auto_*` sont l'arbitrage de `render.resoudre`, déjà
    résolu pour chacune des classes de machine possibles. Le lanceur n'a plus
    qu'à classer la machine qu'il mesure et à lire la ligne : il ne rejoue
    aucune décision, donc il ne peut pas en prendre une autre.
    """
    rendu = systeme.render
    cle = system_key(profile_id, systeme.id)

    def gabarit(mode_nom: str, mode, avec_crt: bool) -> str:
        """Le gabarit d'un mode, chemin du fichier de réglages substitué.

        {render_config} est résolu ICI et non par le lanceur : le chemin d'un
        fichier ne dépend pas de la session, et le laisser au lanceur lui
        aurait fait reconstruire une convention de nommage — un second endroit
        où le nom du fichier serait décidé.
        """
        texte = _gabarit(mode, avec_crt)
        if mode.config.strip():
            texte = texte.replace(
                "{render_config}",
                f"{plan_dir}\\{config_name(cle, mode_nom)}")
        return texte

    lignes = [
        "# Écrit par « retro scan ». Toute modification sera écrasée.",
        f"emulator={emulator_exe}",
        f"workdir={workdir}",
        f"launch={systeme.launch}",
        f"native={gabarit(render_mod.NATIVE, rendu.native, True) if rendu else ''}",
        f"full={gabarit(render_mod.FULL, rendu.full, False) if rendu else ''}",
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

    # L'AMORÇAGE : un COMPTE, toujours écrit, puis une ligne indicée par
    # entrée. Le compte est ce que `Valeur()` protège — une clé absente est une
    # faute du plan, et c'est cette propriété qui a déjà attrapé des plans
    # écrits par une version antérieure. `bootstrap_count=0` dit « cet
    # émulateur n'a rien à recevoir », et AUCUNE ligne indicée ne suit : le
    # compte suffit désormais à porter cette propriété, et écrire des lignes
    # vides ferait boucler le lanceur sur du rien.
    lignes.append(f"bootstrap_count={len(bootstraps)}")
    for rang, amorcage in enumerate(bootstraps, 1):
        # La cible est SUBSTITUÉE ; le nom du fichier déposé, lui, suit la
        # cible BRUTE — c'est son extension qui compte, et elle ne change pas.
        source = f"{plan_dir}\\{bootstrap_name(profile_id, rang, amorcage.target)}"
        # Le fragment des clés imposées, s'il y en a. Vide sinon : c'est ce qui
        # distingue une entrée qui n'impose rien de celle qui impose, sans que
        # le lanceur ait à ouvrir quoi que ce soit pour le savoir.
        impose = (f"{plan_dir}\\{enforced_name(profile_id, rang, amorcage.target)}"
                  if amorcage.enforced else "")
        lignes += [
            f"bootstrap_target.{rang}="
            f"{resoudre_cible(amorcage.target, workdir)}",
            f"bootstrap_source.{rang}={source}",
            f"bootstrap_when.{rang}={SI_ABSENT}",
            # Les DEUX régimes visent la même cible, et le lanceur les applique
            # dans cet ordre : poser le fichier s'il est absent, puis y
            # refondre les clés imposées. L'ordre compte — sur une console
            # neuve, la seconde étape doit trouver le fichier que la première
            # vient de poser.
            f"bootstrap_enforced.{rang}={impose}",
        ]
    return "\n".join(lignes) + "\n"


REAMORCER = "reamorcer.txt"


class AmorcageError(RuntimeError):
    """L'ordre n'a pas été écrit, et le propriétaire sait pourquoi."""


def profils_amorcables(emulation_root_local) -> list[str]:
    """Les profils dont un amorçage est DÉPOSÉ, lus sur le disque.

    Lire le dossier plutôt que recharger les profils : c'est l'état réel de
    la console qui décide, et un profil dont l'amorçage n'a pas encore été
    déposé par « retro scan » ne peut pas être ré-amorcé — l'ordre serait
    donné pour un fichier que le lanceur ne trouverait pas.
    """
    dossier = local_dir(emulation_root_local) / PLAN
    try:
        noms = [p.name for p in dossier.iterdir() if p.is_file()]
    except OSError:
        return []
    marque = f".{BOOTSTRAP}"
    return sorted({n[:n.index(marque)] for n in noms if marque in n})


def ordonner_reamorcage(emulation_root_local, profile_id: str) -> pathlib.Path:
    """Demande au lanceur de reposer l'amorçage de ce profil, une fois.

    L'ordre, et pas l'écriture : la configuration d'un émulateur vit dans le
    profil de l'utilisateur Windows, que la machine qui pilote n'atteint pas.
    Le lanceur sauvegardera l'existant avant de le remplacer, puis consommera
    la ligne — un ordre ne vaut qu'un passage.
    """
    connus = profils_amorcables(emulation_root_local)
    if profile_id not in connus:
        raise AmorcageError(
            f"« {profile_id} » n'a pas d'amorçage déposé. "
            + (f"Profils amorçables : {', '.join(connus)}." if connus else
               "Aucun profil n'en a : lancer « retro scan » d'abord.")
        )
    dossier = local_dir(emulation_root_local)
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / REAMORCER
    try:
        deja = fichier.read_text(encoding="utf-8").split()
    except OSError:
        deja = []
    if profile_id not in deja:
        deja.append(profile_id)
    fichier.write_text("\n".join(deja) + "\n", encoding="utf-8")
    return fichier


TEMOIN_BOOTSTRAP = "bootstrap.txt"


def lire_amorcages(emulation_root_local) -> dict[str, list[tuple[str, str]]]:
    """Ce que le lanceur a posé : profil → [(date, cible), …].

    UNE LISTE par profil, parce que le témoin porte désormais une ligne par
    CIBLE : un profil à deux cibles en écrit deux, et n'en garder qu'une ferait
    disparaître la seconde du rapport sans que rien ne le dise. Le format de
    ligne — profil \t date \t cible — n'a pas changé.

    Une TRACE, pas une source de vérité : c'est la cible sur le disque de la
    console qui décide, et le lanceur ne consulte jamais ce fichier pour
    savoir s'il doit écrire. Un témoin effacé fait donc dire au rapport « pas
    encore amorcé » d'un émulateur qui l'est — sans que rien ne soit réécrit.
    """
    fichier = local_dir(emulation_root_local) / TEMOIN_BOOTSTRAP
    try:
        texte = fichier.read_text(encoding="utf-8")
    except OSError:
        return {}
    amorces: dict[str, list[tuple[str, str]]] = {}
    for ligne in texte.splitlines():
        parts = ligne.split("\t")
        if len(parts) == 3 and parts[0].strip():
            amorces.setdefault(parts[0].strip(), []).append(
                (parts[1].strip(), parts[2].strip()))
    return amorces


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


def lanceur_perime(emulation_root_local) -> bool:
    """Le binaire en place est-il plus ancien que la source déposée à côté ?

    Un `retro-launch.exe` compilé avant une évolution du plan ne DIT RIEN : il
    lit les clés qu'il connaît et ignore les autres. Les trois lignes
    `bootstrap_*` d'un plan tout neuf ne produisent alors aucun amorçage,
    aucune erreur, et `retro status` annonce « pas encore amorcé » après
    cinquante lancements — la fonctionnalité entière est inerte, sans un mot.
    C'est l'état du jour même de la livraison : `deposer_source` pose une
    source plus récente que le binaire, que personne n'a encore recompilé.

    La comparaison porte sur les dates de modification parce que c'est la
    seule preuve dont l'hôte dispose : il ne peut ni exécuter le binaire ni
    l'inspecter. `deposer_source` copie donc la source AVEC sa date (copy2) —
    autrement chaque dépôt rendrait périmé un lanceur qu'on vient de
    recompiler.

    L'absence de l'un ou de l'autre n'est pas une péremption : `est_installe`
    dit déjà l'absence du binaire, et une source manquante se corrige par
    `retro launcher`.
    """
    dossier = local_dir(emulation_root_local)
    try:
        return (dossier / SOURCE).stat().st_mtime > (dossier / EXE).stat().st_mtime
    except OSError:
        return False


# Le geste, écrit une seule fois : `retro launcher` et `retro status` le
# nomment tous les deux, et deux formulations du même geste feraient douter
# qu'il s'agisse du même.
RECOMPILER = "compiler.cmd"


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

    plan_dir = f"{launcher_dir(emulation_root)}\\{PLAN}"
    ecrits, fichiers = [], set()
    for pid in sorted(profils):
        profil = profils[pid]
        exe = f"{emulation_root}\\{install_dirs[pid]}\\{profil.exe}"
        workdir = f"{emulation_root}\\{install_dirs[pid]}"
        for systeme in profil.systems:
            cle = system_key(pid, systeme.id)
            (dossier / f"{cle}.ini").write_text(
                plan_systeme(pid, systeme, exe, workdir, plan_dir,
                             bootstraps=profil.bootstraps),
                encoding="utf-8")
            fichiers.add(f"{cle}.ini")
            ecrits.append(cle)
            # Les fichiers de réglages des modes qui en ont un. RetroArch est
            # dans ce cas : il n'a aucune option pour surcharger un réglage,
            # et son shader CRT resterait éteint sans ce fichier.
            for nom, mode in (("native", systeme.render.native),
                              ("full", systeme.render.full)
                              ) if systeme.render else ():
                if mode.config.strip():
                    (dossier / config_name(cle, nom)).write_text(
                        mode.config, encoding="utf-8")
                    fichiers.add(config_name(cle, nom))

        # Par PROFIL et non par système : la configuration d'un émulateur ne
        # change pas selon la console qu'il émule. Mais PLUSIEURS par profil,
        # numérotés dans l'ordre du profil — RPCS3 a deux fichiers à recevoir,
        # et un nom partagé ferait poser le contenu de l'un dans l'autre.
        for rang, amorcage in enumerate(profil.bootstraps, 1):
            # `fragments_attendus` dit ce qui doit être là ; c'est la MÊME
            # fonction que `retro status` interroge pour constater qu'un
            # fragment déposé n'est plus celui du profil.
            for nom, texte in fragments_attendus(pid, rang, amorcage):
                (dossier / nom).write_text(texte, encoding="utf-8")
                fichiers.add(nom)

    # Tout fichier que ce passage n'a pas écrit s'en va : ce dossier
    # appartient entièrement à « retro scan », et un amorçage d'un format
    # qu'on n'aurait pas pensé à énumérer réécrirait la configuration d'un
    # émulateur à chaque lancement, avec le contenu d'un autre âge.
    for perime in sorted(p for p in dossier.iterdir() if p.is_file()):
        if perime.name not in fichiers:
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
        # copy2 et non copyfile : la date de modification est COPIÉE, parce
        # que c'est elle que `lanceur_perime` compare au binaire. Avec
        # copyfile, chaque dépôt réestampillait la source à l'instant présent
        # et un lanceur fraîchement recompilé se serait annoncé périmé au
        # premier `retro launcher` suivant — un avertissement qui crie à tort
        # est un avertissement qu'on cesse de lire.
        shutil.copy2(origine, cible)
        deposes.append(cible)
    return deposes
