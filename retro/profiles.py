"""Comment on parle à un émulateur.

Un profil décrit les systèmes qu'un émulateur couvre, les extensions de ROM
qu'il accepte, LES NOMS DE DOSSIER sous lesquels le propriétaire range ses
ROMs, la ligne de commande qui lance un jeu, les BIOS qu'il exige et la façon
d'en sortir à la manette.

Tout ce qui est propre à un émulateur vit ici, dans son TOML, jamais dans le
code : c'est ce qui permet d'en ajouter un sans rouvrir un module.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
import tomllib

from retro import render as render_mod
from retro.render import Render, RenderMode

SCHEMA = 1


class ProfileError(RuntimeError):
    """Un profil est illisible, incomplet ou incohérent."""


@dataclasses.dataclass(frozen=True)
class System:
    id: str
    name: str
    extensions: tuple[str, ...]
    launch: str
    bios: tuple[dict, ...]
    # Les noms de dossier USUELS de ce système, en plus de son identifiant et
    # de son nom. Le propriétaire range « Playstation\ », pas « psx\ », et
    # ce n'est pas à lui de renommer sa bibliothèque pour convenir à l'outil.
    # Déclaratif, dans le TOML : une liste d'exceptions dans le code
    # rouvrirait un module à chaque collection rencontrée.
    folders: tuple[str, ...] = ()
    # À quoi se reconnaît un jeu qui est un DOSSIER, et non un fichier.
    # `extensions` répond à la question « qu'est-ce qu'un jeu ? » tant qu'un
    # jeu est un fichier ; une bibliothèque PS Vita est faite d'applications
    # INSTALLÉES, qui sont des dossiers (« ux0:app\\PCSE00123\\ »), rangées à
    # côté des .vpk. Vide — le cas des neuf profils livrés — aucun dossier
    # n'est jamais inventorié : sous un système de ROMs, un dossier est un
    # dossier d'extras ou de disques, et en faire une entrée Steam donnerait
    # un raccourci qui ne lance rien.
    # Déclaré, il porte le nom du fichier qu'une application porte à sa
    # racine : c'est LUI qui distingue une application d'un dossier de
    # sauvegardes. Deviner « tout sous-dossier est un jeu » aurait fait de
    # « savedata » une entrée de la bibliothèque.
    app_dir_marker: str = ""
    # Ce que coûte l'émulation de ce système, pour le mode `auto`. Exigé dès
    # qu'un bloc `render` est déclaré : sans lui, `auto` n'aurait rien à
    # croiser avec la machine et déciderait sur une valeur inventée.
    cost: str = ""
    render: Render | None = None


# La phrase qu'un fichier d'amorçage porte en tête, dans la syntaxe de
# commentaire de son propre format. Elle est EXIGÉE : une configuration écrite
# par un outil et qui ne le dit pas est un piège pour le prochain lecteur, qui
# la prendrait pour la sienne et chercherait longtemps pourquoi ses réglages
# « reviennent ». C'est la même exigence que l'en-tête des plans de lancement.
MARQUE_BOOTSTRAP = "Écrit par « retro »"


# LES JETONS DE CHEMIN D'UNE CIBLE D'AMORÇAGE.
#
# Trois des quatre configurations mesurées le 2026-08-29 ne vivent NI dans le
# profil de l'utilisateur Windows, NI à un endroit absolu : elles vivent sous
# le dossier d'INSTALLATION de leur émulateur, dont le nom n'est connu qu'à
# l'écriture du plan.
#
# Le jeton est celui du dossier d'installation, PAS celui de la racine
# d'émulation, et ce choix se défend : `install_dir` est SURCHARGEABLE par le
# manifeste du propriétaire (`_install_dirs_pour` garde le jour où
# `install_dir = "DuckStation-v0.1"` a fait pointer tout l'inventaire sur un
# dossier inexistant). Écrire `{emulation_root}\Vita3K\…` réécrirait ce nom
# une seconde fois, dans le profil, et une surcharge ferait rater la cible EN
# SILENCE — l'émulateur repartirait sur ses défauts sans un mot.
#
# Publics parce que `launcher.py` les relit : la convention de nommage ne se
# décide qu'à un endroit.
JETON_INSTALL = "{install_dir}"
JETONS_CIBLE = (JETON_INSTALL,)

# Tout ce qui ressemble à un jeton, connu ou non. Sert au REFUS : sans lui,
# « {emulation_roo}\x.ini » tombait dans le message « chemin absolu », qui
# envoie corriger la mauvaise chose.
_JETON_CIBLE = re.compile(r"\{[^}]*\}")


# L'état du RELEVÉ d'une manette, et jamais l'identifiant lui-même.
#
# Un identifiant de périphérique n'est pas une propriété du périphérique :
# c'est une propriété de l'ÉMULATEUR qui le nomme. Le relevé du 2026-08-28
# (plan des manettes, tâche 1) a produit QUATRE identifiants pour une seule
# manette physique — le VID/PID de Windows, deux relevés SDL sous deux pilotes,
# et celui que l'émulateur avait écrit lui-même. Un seul était le bon, et
# c'était le dernier.
#
# D'où la règle, et d'où ce champ : toute valeur non relevée sur la machine est
# FAUSSE, et sa fausseté est indiscernable de l'absence de valeur — une liaison
# qui ne correspond à aucun périphérique est ignorée EN SILENCE, et la manette
# reste muette exactement comme si le fichier était vide. Un profil ne peut
# donc écrire honnêtement qu'une chose : où en est le relevé.
#
# QUATRE ÉTATS DEPUIS LE 2026-08-29, et le quatrième n'est pas un raffinement :
# aucun des trois premiers ne pouvait dire ce que la clôture de D3 a mesuré.
# Crash Team Racing a répondu à la manette, confirmé par le propriétaire.
# Écrire `auto` aurait été FAUX — DuckStation ne trouve pas sa manette seul,
# c'est précisément ce que D3 a réfuté, et il ne la trouve que parce que la
# console lui impose vingt-sept liaisons. Garder `a-relever` aurait été faux
# aussi — le relevé EST fait, et `retro status` aurait continué d'annoncer
# « manette muette » sur le seul émulateur dont on ait vu un bouton agir.
# `inconnu` aurait effacé la mesure. Plutôt que de tordre l'un des trois, le
# vocabulaire s'allonge d'un état qui dit exactement ce qui a été constaté.
MAPPING_AUTO = "auto"           # mesuré : cet émulateur trouve la manette seul
MAPPING_A_RELEVER = "a-relever"  # mesuré : il ne la trouve pas, rien n'est relevé
MAPPING_RELEVE = "releve"       # mesuré : relevé fait, imposé, et VU répondre
MAPPING_INCONNU = "inconnu"     # personne n'a mesuré
MAPPINGS = (MAPPING_AUTO, MAPPING_A_RELEVER, MAPPING_RELEVE, MAPPING_INCONNU)

# Les deux états qui NOMMENT un fichier : dans les deux cas le propriétaire a
# un endroit précis à ouvrir — celui où le relevé se fait, celui où les
# liaisons relevées sont reposées. `mapping_where` y est donc exigé.
MAPPINGS_AVEC_OU = (MAPPING_A_RELEVER, MAPPING_RELEVE)

# LE TYPE DE MANETTE SOUS LEQUEL UN RELEVÉ A ÉTÉ FAIT. Vocabulaire GELÉ, et
# c'est le point : un relevé n'est vrai QUE du pad sous lequel il a été fait.
#
# Apollo annonce aujourd'hui un Xbox 360 (`Gamepad 0 will be Xbox 360
# controller (default)`, relevé dans son journal). Le jour où il annoncera une
# DualShock, le VID/PID change, donc le GUID SDL, donc tout identifiant qu'une
# configuration d'entrée contiendrait — et une liaison qui ne correspond à
# aucun périphérique est ignorée EN SILENCE. La console redevient muette
# partout, sans un message. Ce champ est ce qui permet de le CONSTATER
# autrement qu'en jouant : `status` compare ce qui a été relevé au pad que le
# lanceur a vu au dernier lancement.
#
# Le vocabulaire est gelé, et un type inconnu est REFUSÉ plutôt que toléré :
# une valeur libre — « X360 », « ds-4 », « dualshock » — ne correspondrait
# jamais à la table vid:pid, la discordance ne serait jamais détectée, et le
# filet passerait pour vert alors qu'il ne compare plus rien. Ajouter un type
# de pad doit être un ACTE EXPLICITE, ici et dans la table de `status`.
PAD_X360 = "x360"
PAD_DS4 = "ds4"
PADS_CONNUS = (PAD_X360, PAD_DS4)

# DE QUOI ON RECONNAIT UN TYPE DE PAD : son VID/PID, en hexadecimal minuscule.
# Courte et GELEE, au meme endroit que le vocabulaire ci-dessus pour qu'aucun
# des deux ne puisse s'allonger sans l'autre.
#
# 045e:028e — MESURE le 2026-08-29 sur l'invite, qui portait
#   USB\VID_045E&PID_028E pendant qu'Apollo annoncait « Gamepad 0 will be
#   Xbox 360 controller (default) ». Deux sources concordantes.
# 054c:05c4 — SUPPOSE, et il faut le dire : c'est le VID/PID d'une DualShock 4
#   de premiere revision, celui que le plan de D4 attend de voir apparaitre
#   apres la bascule. AUCUNE console de ce projet ne l'a encore presente. La
#   valeur ne sera confirmee que par la tache 6, sur la machine.
#
# UN VID/PID ABSENT DE CETTE TABLE N'EST PAS UNE ERREUR. Il s'affiche brut et
# ne declenche aucun probleme : accuser sur une table incomplete serait pire
# que se taire — le rapport dirait « ce n'est pas le bon pad » d'une manette
# parfaitement saine, et le proprietaire apprendrait a ignorer la section.
PADS_PAR_VID_PID = {
    "045e:028e": PAD_X360,
    "054c:05c4": PAD_DS4,
}


def type_de_pad(vid_pid: str) -> str:
    """Le type d'un VID/PID, ou une chaine vide s'il n'est pas reconnu.

    Vide veut dire « on ne sait pas », JAMAIS « ce n'est aucun des deux » :
    l'appelant qui en tirerait une discordance accuserait sur une ignorance.
    """
    return PADS_PAR_VID_PID.get(vid_pid.strip().lower(), "")


@dataclasses.dataclass(frozen=True)
class Bootstrap:
    """La configuration qu'un émulateur neuf reçoit, et où elle va.

    `target` est un chemin WINDOWS, variables d'environnement comprises : la
    configuration d'un émulateur vit dans le profil de l'utilisateur Windows,
    que la machine qui pilote `retro` n'atteint pas. Le lanceur, lui, y est.

    DEUX RÉGIMES, et ils sont STRUCTURELS — deux champs, pas un mode déclaré
    qu'on pourrait mettre en contradiction avec ce que le bloc contient :

    `content`  est posé SI LE FICHIER EST ABSENT, et plus jamais retouché. Ce
      sont des préférences : le propriétaire les change dans l'interface de
      son émulateur, et son choix tient.
    `enforced` est REPOSÉ À CHAQUE LANCEMENT, par fusion. Ce sont les clés
      sans lesquelles un jeu ne démarre pas sans clavier — un assistant de
      première configuration qui s'ouvre par-dessus, une fenêtre de mise à
      jour, un plein écran manquant. La console doit pouvoir les imposer,
      sinon la bibliothèque entière devient inutilisable au premier réglage
      malheureux.

    Les deux visent LE MÊME fichier. Ce qui n'est dans ni l'un ni l'autre
    appartient entièrement au propriétaire et n'est jamais touché.
    """
    target: str
    content: str
    enforced: str = ""


def folder_key(nom: str) -> str:
    """La forme sous laquelle deux noms de dossier se comparent.

    La casse, et elle seule : « Gamecube », « GameCube » et « gamecube »
    désignent le même système, et aucune collection ne s'écrit deux fois de la
    même façon. Tout le reste — les espaces de « Game Boy », le « Sony »
    devant « Playstation » — se DÉCLARE dans le profil, où ça se lit et se
    corrige, plutôt que de se deviner ici par une heuristique que personne ne
    pourrait prévoir.
    """
    return nom.strip().casefold()


def folder_claims(systeme: System) -> tuple[str, ...]:
    """Tous les noms de dossier qui désignent ce système, normalisés.

    L'identifiant et le nom en font partie d'office : « gamecube » et
    « GameCube » sont déjà écrits dans le profil, les redéclarer serait du
    bruit. `folders` porte le reste — « Playstation » pour « psx ».
    """
    vus = {}
    for nom in (systeme.id, systeme.name, *systeme.folders):
        cle = folder_key(nom)
        if cle:
            vus.setdefault(cle, None)
    return tuple(vus)


@dataclasses.dataclass(frozen=True)
class Profile:
    id: str
    exe: str
    systems: tuple[System, ...]
    exit_native: str
    exit_fallback: str
    steam_input: str
    # Où en est le relevé de la manette de cet émulateur, et où il se fait.
    # `input_mapping_where` n'est PAS un identifiant : c'est le fichier, et la
    # section, que le propriétaire doit ouvrir sur la console. `retro status`
    # en fait le « où » du problème qu'il énonce — un constat sans chemin est
    # une accusation, pas un diagnostic.
    input_mapping: str = MAPPING_INCONNU
    input_mapping_where: str = ""
    # SOUS QUEL PAD ce relevé a été fait. Vide veut dire « rien n'a été
    # relevé », jamais « n'importe lequel » : c'est la condition de validité
    # de la mesure, pas une préférence. Exigé quand `input_mapping` vaut
    # « releve », interdit partout ailleurs.
    input_pad_releve: str = ""
    # Facultatif, et PLURIEL : un émulateur qui démarre nu n'a rien à recevoir,
    # et le profil doit alors DIRE pourquoi il n'a pas de bloc — sans quoi rien
    # ne distingue « cet émulateur se débrouille » d'un bloc oublié. Plusieurs,
    # parce que RPCS3 a deux fichiers à recevoir, dans deux formats : un profil
    # qui n'en portait qu'un rendait le second inexprimable.
    bootstraps: tuple[Bootstrap, ...] = ()


def _valider_groupes(path: pathlib.Path, pid: str, sid: str,
                     declares: tuple[dict, ...]) -> None:
    """Un groupe de BIOS dit « un parmi ceux-ci suffit ».

    Les trois BIOS PlayStation sont interchangeables : celui de la région des
    jeux suffit. Déclarés `required = true` un par un, quelqu'un qui déposait
    scph5501.bin — le bon — lisait « MANQUANT : scph5500.bin » et
    « MANQUANT : scph5502.bin » et partait chercher deux fichiers dont il
    n'avait pas besoin. Les basculer tous les trois en `required = false`
    aurait masqué le vrai cas, « aucun BIOS PlayStation ».

    Deux gardes, parce que l'une et l'autre erreur sont muettes :

    - un groupe d'UN SEUL membre n'a aucun sens, et c'est exactement ce que
      produit une faute de frappe sur le nom du groupe : le membre resté seul
      redevient exigé à lui tout seul, soit le défaut d'origine ;
    - des membres qui ne s'accordent pas sur `required` rendent « un parmi
      ceux-ci » indécidable — le groupe est-il exigé, ou non ?
    """
    groupes: dict[str, list[dict]] = {}
    for b in declares:
        if b.get("group"):
            groupes.setdefault(b["group"], []).append(b)
    for nom, membres in groupes.items():
        if len(membres) < 2:
            raise ProfileError(
                f"{path} : profil '{pid}', système '{sid}' — le groupe de BIOS "
                f"'{nom}' n'a qu'un seul membre ({membres[0]['file']}). Un "
                "groupe dit « un parmi ceux-ci suffit » : à un seul membre il "
                "ne dit rien, et c'est ce qu'une faute de frappe sur le nom du "
                "groupe produit — le fichier resté seul redevient exigé pour "
                "lui-même, en silence."
            )
        exigences = {bool(m.get("required", True)) for m in membres}
        if len(exigences) > 1:
            raise ProfileError(
                f"{path} : profil '{pid}', système '{sid}' — les membres du "
                f"groupe de BIOS '{nom}' ne s'accordent pas sur 'required'. "
                "« Un parmi ceux-ci suffit » ne veut alors plus rien dire : le "
                "groupe entier est exigé, ou il ne l'est pas."
            )


# Les seules variables qu'un gabarit de rendu peut employer. Une variable
# inconnue — « {res} », « {resolution} » — traverserait la substitution telle
# quelle et arriverait LITTÉRALEMENT sur la ligne de commande de l'émulateur,
# qui l'ignorerait ou refuserait de démarrer. La faute est muette : le mode
# aurait l'air appliqué.
# {width}, {height} et {scale} sont substituées AU LANCEMENT, par le lanceur,
# qui seul connaît la session. {render_config} l'est à l'écriture du plan : le
# chemin d'un fichier ne dépend pas de la résolution.
_VARIABLES = ("width", "height", "scale", "render_config")
_CLES_RENDER = ("native", "full", "native_height", "max_scale")
_CLES_MODE = ("args", "note", "crt", "crt_absent", "config",
              "fill", "fill_absent")


def _valider_variables(path, sid, quoi: str, gabarit: str) -> None:
    inconnues = sorted({m for m in re.findall(r"\{(\w+)\}", gabarit)
                        if m not in _VARIABLES})
    if inconnues:
        raise ProfileError(
            f"{path} [{sid}] : {quoi} emploie des variables inconnues : "
            f"{', '.join('{' + v + '}' for v in inconnues)}. Les variables "
            f"disponibles sont {', '.join('{' + v + '}' for v in _VARIABLES)}. "
            "Une variable inconnue arriverait telle quelle sur la ligne de "
            "commande de l'émulateur, qui l'ignorerait ou refuserait de "
            "démarrer — et le mode aurait pourtant l'air appliqué."
        )


def _lire_mode(path, sid, nom: str, brut) -> RenderMode:
    """Un bloc [system.render.native] ou [system.render.full]."""
    if not isinstance(brut, dict):
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}' doit être une table "
            f"([system.render.{nom}]), pas {type(brut).__name__}."
        )
    inconnues = sorted(k for k in brut if k not in _CLES_MODE)
    if inconnues:
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}' contient des clés inconnues : "
            f"{', '.join(inconnues)}. Les clés sont {', '.join(_CLES_MODE)}. "
            "Une clé mal orthographiée ne serait jamais lue, et le réglage "
            "qu'elle porte n'aurait aucun effet sans qu'un mot le dise."
        )
    if "args" not in brut:
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}' n'a pas de champ 'args'. Un mode "
            "sans arguments ne changerait rien au lancement : le propriétaire "
            f"choisirait « {nom} » et obtiendrait les réglages par défaut de "
            "l'émulateur. Si c'est bien le cas — l'émulateur n'expose rien en "
            "ligne de commande — le déclarer : args = \"\" avec une 'note' "
            "qui dit pourquoi."
        )
    for champ in _CLES_MODE:
        if champ in brut and not isinstance(brut[champ], str):
            raise ProfileError(
                f"{path} [{sid}] : 'render.{nom}.{champ}' doit être du texte."
            )
    config = brut.get("config", "")
    args, note = brut["args"].strip(), brut.get("note", "").strip()
    # Les deux vont ENSEMBLE, dans les deux sens. Un fichier déclaré que rien
    # ne référence ne serait jamais lu par l'émulateur ; un {render_config}
    # sans contenu ferait passer le chemin d'un fichier qui n'existe pas.
    # L'une et l'autre faute laissent le mode sans effet, sans un mot.
    marqueur = "{render_config}" in (args + " " + brut.get("crt", ""))
    if bool(config.strip()) != marqueur:
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}' déclare "
            + ("un 'config' que rien ne référence" if config.strip()
               else "{render_config} sans 'config'")
            + ". Les deux vont ensemble : 'config' est le CONTENU du fichier "
            "de réglages, {render_config} est l'endroit de la commande où son "
            "chemin s'insère. L'un sans l'autre laisse le mode sans effet."
        )
    if not args and not note:
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}.args' est vide sans 'note'. Un "
            "mode vide est peut-être la vérité — tous les émulateurs "
            "n'exposent pas leurs réglages en ligne de commande — mais rien ne "
            "le distinguerait d'un bloc oublié, et `retro status` ne pourrait "
            "pas expliquer au propriétaire pourquoi son choix ne change rien."
        )
    _valider_variables(path, sid, f"render.{nom}.args", args)

    crt, crt_absent = brut.get("crt", "").strip(), brut.get("crt_absent", "").strip()
    if nom == render_mod.NATIVE:
        # « Ce que la console d'origine fournissait » passait par un tube
        # cathodique. Le shader n'existe pas partout, et c'est une information
        # que le propriétaire doit pouvoir lire — pas une clé qu'on devine
        # absente, ce qu'une faute de frappe produirait tout aussi bien.
        if bool(crt) == bool(crt_absent):
            raise ProfileError(
                f"{path} [{sid}] : 'render.native' doit déclarer SOIT 'crt' — "
                "les arguments du shader — SOIT 'crt_absent', qui dit pourquoi "
                "cet émulateur n'en a pas. Ni l'un ni l'autre laisserait le "
                "mode natif rendre une image propre qu'aucun téléviseur de "
                "l'époque n'a produite, sans que le rapport puisse le dire ; "
                "les deux à la fois ne veulent rien dire."
            )
        _valider_variables(path, sid, f"render.{nom}.crt", crt)
    elif crt or crt_absent:
        raise ProfileError(
            f"{path} [{sid}] : 'render.full' ne prend ni 'crt' ni "
            "'crt_absent'. Le shader CRT n'a de sens qu'en mode natif — "
            "déclaré ici, il ne serait jamais appliqué."
        )
    fill, fill_absent = _lire_remplissage(path, sid, nom, brut, args, config)
    return RenderMode(args=args, note=note, crt=crt, crt_absent=crt_absent,
                      config=config, fill=fill, fill_absent=fill_absent)


def _lire_remplissage(path, sid, nom: str, brut, args: str,
                      config: str) -> tuple[str, str]:
    """Le TROISIÈME axe de ce mode : `fill`, `fill_absent`, ou ni l'un ni
    l'autre.

    Ni l'un ni l'autre est PERMIS — le troisième axe se remplit émulateur par
    émulateur, comme les deux autres, et un profil qui ne l'a pas encore
    mesuré doit continuer de lancer ses jeux. C'est `retro status` qui nomme
    ces systèmes, comme il nomme ceux qui n'ont aucun mode.

    Les trois refus ci-dessous portent chacun sur une faute qui ne se verrait
    que sur la télévision, sur une image dont rien ne dirait qu'elle est celle
    qu'on a demandée.
    """
    fill = brut.get("fill", "").strip()
    fill_absent = brut.get("fill_absent", "").strip()
    if fill and fill_absent:
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}' déclare SOIT 'fill' — le "
            "remplissage que ses arguments produisent — SOIT 'fill_absent', "
            "qui dit que cet émulateur n'expose aucun réglage de cet axe. Les "
            "deux à la fois ne veulent rien dire."
        )
    if not fill:
        return "", fill_absent
    if fill not in render_mod.REMPLISSAGES:
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}.fill' vaut {fill!r} — "
            f"remplissage inconnu. Les remplissages sont "
            f"{', '.join(render_mod.REMPLISSAGES)} : ce sont les deux seules "
            "façons d'agrandir une image SANS la déformer, et l'étirement "
            "n'est pas une troisième valeur qu'on aurait omise. Une valeur "
            "inconnue ne serait comparée à rien et le mode partirait sans son "
            "troisième axe, sans qu'un mot le dise."
        )
    if not args and not config.strip():
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}' déclare un remplissage alors "
            "qu'il ne passe RIEN à l'émulateur — ni argument, ni fichier de "
            "réglages. Rien ne l'appliquerait. Un mode vide n'a aucun axe à "
            "régler, celui-ci compris : sa 'note' le dit déjà, et `retro "
            "status` la répète."
        )
    attendu = render_mod.remplissage_attendu(nom)
    if fill != attendu:
        raise ProfileError(
            f"{path} [{sid}] : 'render.{nom}.fill' vaut {fill!r}, mais la "
            f"politique de remplissage retient {attendu!r} pour le mode "
            f"{nom} — {render_mod.motif_remplissage(nom)}. Un profil qui la "
            "contredit ne serait démenti par rien : la contradiction ne se "
            "verrait que sur l'écran. Corriger le profil, ou changer la "
            "politique dans retro/render.py — où elle est écrite en clair, et "
            "citée par le rapport."
        )
    return fill, ""


def _lire_render(path, sid, brut, launch: str) -> Render:
    if not isinstance(brut, dict):
        raise ProfileError(
            f"{path} [{sid}] : 'render' doit être une table "
            "([system.render.native] / [system.render.full])."
        )
    inconnues = sorted(k for k in brut if k not in _CLES_RENDER)
    if inconnues:
        raise ProfileError(
            f"{path} [{sid}] : 'render' contient des clés inconnues : "
            f"{', '.join(inconnues)}. Les clés sont {', '.join(_CLES_RENDER)}."
        )
    manquants = [m for m in render_mod.MODES_DECLARES if m not in brut]
    if manquants:
        raise ProfileError(
            f"{path} [{sid}] : 'render' ne déclare pas {', '.join(manquants)}. "
            "Les DEUX modes sont exigés : n'en déclarer qu'un ferait que "
            "l'autre se lance avec les réglages par défaut de l'émulateur, "
            "sans rien changer et sans rien dire — et `auto`, qui choisit "
            "entre les deux, en serait réduit à un seul."
        )
    modes = {m: _lire_mode(path, sid, m, brut[m])
             for m in render_mod.MODES_DECLARES}

    # {render} dit OÙ les arguments s'insèrent. Certains émulateurs exigent le
    # fichier en dernier, d'autres leurs options avant : personne, ici, ne peut
    # deviner la place juste. Sans le marqueur, les arguments n'iraient nulle
    # part — le mode serait déclaré, validé, et sans le moindre effet.
    if "{render}" not in launch:
        raise ProfileError(
            f"{path} [{sid}] : le gabarit launch ne contient pas {{render}} "
            "alors qu'un bloc 'render' est déclaré. C'est {{render}} qui dit "
            "OÙ les arguments de rendu s'insèrent dans la commande — sans lui "
            "ils n'iraient nulle part, et les trois modes se lanceraient tous "
            "de la même façon."
        )

    besoin_echelle = any("{scale}" in (m.args + " " + m.crt)
                         for m in modes.values())
    for champ in ("native_height", "max_scale"):
        valeur = brut.get(champ, 0)
        if not isinstance(valeur, int) or isinstance(valeur, bool):
            raise ProfileError(
                f"{path} [{sid}] : 'render.{champ}' doit être un entier."
            )
        if besoin_echelle and valeur <= 0:
            raise ProfileError(
                f"{path} [{sid}] : {{scale}} est employé mais "
                f"'render.{champ}' vaut {valeur}. L'échelle se calcule en "
                "divisant la hauteur de la session par la hauteur d'origine de "
                "la console, bornée par l'échelle maximale : sans ces deux "
                "nombres, elle n'est pas calculable."
            )
    return Render(native=modes[render_mod.NATIVE], full=modes[render_mod.FULL],
                  native_height=brut.get("native_height", 0),
                  max_scale=brut.get("max_scale", 0))


def _lire_bootstraps(path: pathlib.Path, brut) -> tuple[Bootstrap, ...]:
    """Les blocs [[bootstrap]] d'un profil, validés, dans l'ordre du fichier.

    PLUSIEURS, parce qu'un émulateur peut avoir plusieurs fichiers à recevoir :
    RPCS3 en a deux — ses modales dans un INI, son gestionnaire de manette dans
    un YAML — et un profil qui n'en portait qu'un rendait le second
    inexprimable. L'ordre est celui du fichier : c'est le seul que le lecteur
    du profil voie, et les fichiers déposés en portent l'indice.

    UNE SEULE FORME est acceptée, le tableau de tables. Garder aussi
    `[bootstrap]` ferait deux façons d'écrire la même chose, et le jour où
    quelqu'un mélangerait les deux, rien ne dirait laquelle gagne : le profil
    se chargerait, à moitié appliqué, sans un mot.
    """
    if brut is None:
        return ()
    if not isinstance(brut, list):
        raise ProfileError(
            f"{path} : l'amorçage s'écrit « [[bootstrap]] », un tableau de "
            "tables, et non « [bootstrap] ». Un profil peut porter PLUSIEURS "
            "cibles — RPCS3 en a deux — et une seule forme est acceptée : "
            "garder les deux ferait deux façons d'écrire la même chose, dont "
            "rien ne dirait laquelle gagne. Doubler les crochets suffit ; le "
            "contenu du bloc ne change pas."
        )
    entrees = []
    for rang, entree in enumerate(brut, 1):
        # Une entrée VIDE n'est pas « pas d'amorçage » : c'est un
        # « [[bootstrap]] » qu'on a écrit puis oublié de remplir. La laisser
        # passer ferait un trou dans la numérotation des fichiers déposés, et
        # le lanceur lirait une cible vide au milieu d'une boucle.
        lue = _lire_bootstrap(path, entree)
        if lue is None:
            raise ProfileError(
                f"{path} : le [[bootstrap]] n°{rang} est vide. Un bloc "
                "d'amorçage sans cible ni contenu n'amorce rien, et se lit "
                "pourtant comme un profil complet — le retirer, ou le remplir."
            )
        entrees.append(lue)
    return tuple(entrees)


def _lire_bootstrap(path: pathlib.Path, brut) -> Bootstrap | None:
    """UNE entrée [[bootstrap]], validée, ou None si elle est vide.

    Les trois refus ci-dessous portent chacun sur une faute MUETTE : un bloc
    à moitié écrit, un chemin qui vise un dossier au hasard, un fichier qui
    ne dit pas d'où il vient. Aucune ne fait échouer quoi que ce soit au
    moment où elle est commise — elles se découvrent devant une télévision,
    sur un jeu qui n'a pas démarré.
    """
    if not brut:
        return None
    target = brut.get("target", "")
    content = brut.get("content", "")
    for nom, valeur in (("target", target), ("content", content)):
        if not isinstance(valeur, str) or not valeur.strip():
            raise ProfileError(
                f"{path} [[bootstrap]] : champ '{nom}' manquant ou vide. La "
                "moitié d'un amorçage n'amorce rien, et se lit pourtant comme "
                "un profil complet."
            )
    # Le jeton se teste AVANT le chemin absolu, et il se refuse en se
    # NOMMANT. Un jeton mal orthographié n'est pas un chemin relatif : le dire
    # « relatif » enverrait corriger la mauvaise chose, et le profil repartirait
    # avec un chemin absolu inventé.
    jeton = _JETON_CIBLE.match(target)
    if jeton and jeton.group(0) not in JETONS_CIBLE:
        raise ProfileError(
            f"{path} [[bootstrap]] : 'target' commence par le jeton "
            f"{jeton.group(0)}, que ce projet ne connaît pas — reçu "
            f"{target!r}. Les jetons connus sont : "
            f"{', '.join(JETONS_CIBLE)}. Un jeton non substitué arriverait tel "
            "quel dans un chemin Windows, qui créerait un dossier portant "
            "littéralement ce nom : l'émulateur n'y lirait jamais rien, et "
            "rien ne le dirait."
        )
    if not (jeton
            or target.startswith("%")
            or pathlib.PureWindowsPath(target).is_absolute()):
        raise ProfileError(
            f"{path} [[bootstrap]] : 'target' doit être un chemin Windows "
            f"absolu, commencer par une variable d'environnement, ou par l'un "
            f"des jetons {', '.join(JETONS_CIBLE)} — reçu "
            f"{target!r}. Un chemin relatif s'écrirait dans le dossier de "
            "travail de l'émulateur, et le fichier posé ne serait lu par "
            "personne."
        )
    if MARQUE_BOOTSTRAP not in content:
        raise ProfileError(
            f"{path} [[bootstrap]] : 'content' ne porte pas « "
            f"{MARQUE_BOOTSTRAP} » en commentaire. Un fichier de "
            "configuration écrit par un outil doit dire qui l'a écrit : sans "
            "cela, le propriétaire le prend pour le sien."
        )
    enforced = brut.get("enforced", "")
    if not isinstance(enforced, str):
        raise ProfileError(
            f"{path} [[bootstrap]] : 'enforced' doit être du texte — le "
            "fragment de configuration que la console REPOSE à chaque "
            "lancement."
        )
    _valider_regimes(path, content, enforced)
    return Bootstrap(target=target, content=content,
                     enforced=enforced.strip())


def cles_ini(fragment: str) -> list[tuple[str, str]]:
    """Les couples (section, clé) d'un fragment INI, dans l'ordre.

    Rendue publique : `retro status` compte ce que la console impose, et
    recompter ailleurs ferait deux analyseurs qui divergeraient au premier
    format inhabituel.

    Les commentaires n'y sont PAS des clés. Une ligne « ; Scaling = ... » ne
    doit pas passer pour le réglage qu'elle explique — c'est la même règle que
    dans la fusion du lanceur, et l'y contredire ferait dire au rapport qu'une
    clé est imposée alors qu'elle ne l'est pas.
    """
    section, cles = "", []
    for ligne in fragment.splitlines():
        nu = ligne.strip()
        if not nu or nu[0] in ";#":
            continue
        if nu.startswith("[") and nu.endswith("]"):
            section = nu[1:-1].strip()
        elif "=" in nu:
            cles.append((section, nu.split("=", 1)[0].strip()))
    return cles


def _valider_regimes(path: pathlib.Path, content: str, enforced: str) -> None:
    """Les deux régimes ne se recouvrent pas, et l'en-tête dit lequel est quoi.

    Une clé déclarée DES DEUX CÔTÉS serait décidée à deux endroits. Le
    fusionné l'emporterait toujours — il passe après —, mais personne, en
    lisant le profil, ne pourrait dire lequel gagne, et la préférence
    apparemment posée ne tiendrait jamais. C'est la faute que ce dépôt refuse
    partout ailleurs, et elle serait ici parfaitement muette.

    La comparaison porte sur le couple SECTION/CLÉ : « Enabled » sous [Pad1]
    et sous [Display] ne sont pas le même réglage.

    Et l'en-tête. Il PROMET quelque chose au propriétaire, qui règle son
    comportement dessus. « Vos réglages ne sont jamais retouchés » était vrai
    tant que rien n'était imposé ; il devient faux pour les clés reposées.
    Mais « tout est reposé » serait faux aussi, pour les préférences. Dès
    qu'un profil impose quelque chose, son en-tête doit donc distinguer les
    TROIS catégories — imposé, posé une fois, à vous. La garde est
    volontairement grossière : elle n'attrape pas une formulation
    malheureuse, elle attrape l'oubli.
    """
    if not enforced.strip():
        return
    deux = sorted(set(cles_ini(content)) & set(cles_ini(enforced)))
    if deux:
        noms = ", ".join(f"[{s}] {c}" for s, c in deux)
        raise ProfileError(
            f"{path} [[bootstrap]] : {noms} — déclaré dans les DEUX régimes, "
            "'content' et 'enforced'. Le réglage serait décidé à deux "
            "endroits : l'imposé l'emporterait toujours, la préférence "
            "posée ne tiendrait jamais, et rien dans le profil ne dirait "
            "lequel gagne. Choisir : imposé par la console, ou posé une fois "
            "puis laissé au propriétaire."
        )
    minuscules = content.lower()
    if not ("impos" in minuscules and "une fois" in minuscules):
        raise ProfileError(
            f"{path} [[bootstrap]] : ce profil IMPOSE des clés, mais son "
            "'content' ne distingue pas les TROIS catégories que le fichier "
            "porte désormais : ce que la console impose et repose à chaque "
            "lancement, ce qu'elle a posé UNE FOIS et ne retouche plus, et "
            "tout le reste, qui appartient au propriétaire. L'en-tête d'un "
            "fichier de configuration est CRU : le propriétaire y lit une "
            "garantie et règle son comportement dessus. Une promesse qui "
            "survivrait au régime qui la rendait vraie serait pire qu'une "
            "absence d'en-tête."
        )


def _lire_mapping(path: pathlib.Path,
                  entree: dict) -> tuple[str, str, str]:
    """L'état du relevé de la manette, validé, et l'endroit où il se fait.

    Le défaut est `inconnu`, et ce choix se défend contre les trois autres :

    - `auto` par défaut ferait dire au rapport que neuf émulateurs trouvent
      leur manette seuls, ce que personne n'a mesuré. C'est très exactement le
      mensonge de `steam_input = "required"`, que ce module typographie et
      relit sans qu'aucun code ne l'applique jamais, et qui a fait croire
      pendant tout un diagnostic que la question des manettes était traitée ;
    - `a-relever` par défaut accuserait huit émulateurs d'une panne que
      personne n'a constatée, et noierait la seule qui l'a été ;
    - `releve` par défaut serait le pire des quatre : il affirmerait qu'un
      bouton a été VU répondre dans un jeu sur huit émulateurs où personne n'a
      tenu de manette. C'est la seule affirmation de ce vocabulaire qui exige
      un témoin humain, et elle ne peut jamais être un défaut.

    `inconnu` est le seul état vrai d'un profil qui se tait. Il n'est pas un
    problème — mais il est NOMMÉ, faute de quoi « personne n'a regardé » et
    « cet émulateur se débrouille » se lisent pareil.
    """
    etat = entree.get("mapping", MAPPING_INCONNU)
    if etat not in MAPPINGS:
        raise ProfileError(
            f"{path} [input] : 'mapping' vaut {etat!r}, attendu l'un de "
            f"{', '.join(MAPPINGS)}. Ce champ ne porte JAMAIS un identifiant "
            "de manette — il dit où en est le RELEVÉ, seule chose qu'on "
            "puisse écrire sans avoir mesuré. Une faute de frappe y "
            "retomberait sur le défaut « inconnu » et ferait taire "
            "« retro status » sur l'émulateur précisément concerné."
        )
    ou = entree.get("mapping_where", "")
    if not isinstance(ou, str):
        raise ProfileError(
            f"{path} [input] : 'mapping_where' doit être un texte — le "
            "fichier, et la section, que le propriétaire ouvrira sur la "
            f"console. Reçu {ou!r}."
        )
    ou = ou.strip()
    if etat in MAPPINGS_AVEC_OU and not ou:
        raise ProfileError(
            f"{path} [input] : 'mapping' vaut « {etat} » mais "
            "'mapping_where' est vide. « Un constat sans chemin ni action "
            "n'aide personne » : le rapport dirait « la manette restera "
            "muette » sans dire quel fichier ouvrir, et cette panne-là ne se "
            "constate que le pad en main, devant la télévision. Un relevé "
            "clos doit nommer le même fichier, pour la raison inverse : c'est "
            "là que le propriétaire ira voir si ses liaisons y sont encore."
        )
    return etat, ou, _lire_pad_releve(path, entree, etat)


def _lire_pad_releve(path: pathlib.Path, entree: dict, etat: str) -> str:
    """Le type de manette sous lequel le relevé a été fait, validé.

    EXIGÉ quand le relevé est clos, INTERDIT partout ailleurs, et les deux
    règles ont la même racine — une valeur qui n'a pas été mesurée ne doit pas
    pouvoir s'écrire :

    - sans lui, un relevé clos est une mesure privée de ses conditions.
      `status` ne peut alors ni confirmer ni infirmer que le pad vu au dernier
      lancement est celui-là : il se tait, et son silence se lit comme « tout
      va bien » par quelqu'un qui vient justement de ne pas pouvoir jouer ;
    - avec lui sur un `a-relever`, c'est l'inverse : `a-relever` veut dire que
      RIEN n'a été relevé, et y déclarer un pad serait un mensonge de la même
      famille que `steam_input = "required"` — une valeur d'apparence mesurée
      que personne n'a mesurée, et que le rapport relaierait comme un fait.
    """
    pad = entree.get("pad_releve", "")
    if not isinstance(pad, str):
        raise ProfileError(
            f"{path} [input] : 'pad_releve' doit être un texte, l'un de "
            f"{', '.join(PADS_CONNUS)}. Reçu {pad!r}."
        )
    pad = pad.strip()
    if pad and pad not in PADS_CONNUS:
        raise ProfileError(
            f"{path} [input] : 'pad_releve' vaut {pad!r}, attendu l'un de "
            f"{', '.join(PADS_CONNUS)}. Ce vocabulaire est GELÉ : un type "
            "hors liste ne correspondrait à aucun périphérique connu, la "
            "discordance avec le pad vu au dernier lancement ne serait JAMAIS "
            "détectée, et le rapport passerait pour vert en ne comparant plus "
            "rien. Ajouter un type de pad est un acte explicite."
        )
    if etat == MAPPING_RELEVE and not pad:
        raise ProfileError(
            f"{path} [input] : 'mapping' vaut « {MAPPING_RELEVE} » mais "
            "'pad_releve' est vide. Un relevé n'est vrai QUE du pad sous "
            "lequel il a été fait : changer de type de manette change le "
            "VID/PID, donc le GUID SDL, et une liaison qui ne correspond à "
            "aucun périphérique est ignorée en silence. Sans ce champ, rien "
            "ne pourra dire que la mesure a cessé d'être vraie."
        )
    if etat != MAPPING_RELEVE and pad:
        raise ProfileError(
            f"{path} [input] : 'pad_releve' vaut {pad!r} alors que 'mapping' "
            f"vaut « {etat} ». Ce champ dit sous quel pad un relevé a été "
            "fait ; hors d'un relevé clos, il n'y a pas de relevé, et "
            "l'écrire serait affirmer une mesure que personne n'a faite."
        )
    return pad


# L'identifiant d'un profil n'est pas une étiquette : il NOMME un fichier et
# il se DÉCOUPE, à trois endroits, dans trois langages différents.
#
# - `launcher.bootstrap_name` en fait « <id>.bootstrap.<ext> », déposé à côté
#   des plans ; `launcher.profils_amorcables` retrouve ensuite l'identifiant en
#   coupant sur « .bootstrap » — un identifiant qui porte cette chaîne se
#   couperait au mauvais endroit, et le profil deviendrait non ré-amorçable ;
# - `launcher.ordonner_reamorcage` écrit un identifiant par ligne dans
#   reamorcer.txt et relit le fichier avec `split()`, qui découpe sur les
#   BLANCS : un identifiant contenant un espace y devient deux ordres, dont
#   aucun ne désigne un profil ;
# - le lanceur retrouve le profil dans « <profil>.<système> » en coupant au
#   premier point : un identifiant qui en porte un désignerait un autre profil.
#
# Aucune de ces trois fautes ne fait échouer quoi que ce soit au moment où elle
# est commise : elles se découvrent devant une télévision, sur une
# configuration qui n'a pas été posée. La règle les ferme toutes les trois.
#
# Le point d'ancrage est \Z et non $ : « duckstation\n » satisferait $, et TOML
# accepte parfaitement un identifiant multiligne.
_ID_PROFIL = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


def _valider_id(path: pathlib.Path, pid) -> None:
    """L'identifiant du profil, tel que le reste du projet peut le manipuler."""
    if isinstance(pid, str) and _ID_PROFIL.match(pid):
        return
    raise ProfileError(
        f"{path} : 'id' vaut {pid!r}. Un identifiant de profil s'écrit en "
        "minuscules non accentuées, chiffres, tiret et souligné, et commence "
        "par une lettre ou un chiffre — ni espace, ni point, ni majuscule. Ce "
        "n'est pas une étiquette : il NOMME le fichier d'amorçage déposé pour "
        "le lanceur, il s'écrit seul sur une ligne de reamorcer.txt (relue en "
        "découpant sur les blancs), et le lanceur le retrouve en coupant "
        "« <profil>.<système> » au premier point. Un espace y ferait deux "
        "ordres qui ne désignent rien, un point désignerait un autre profil, "
        "et « .bootstrap » rendrait le profil non ré-amorçable — trois pannes "
        "qui ne se voient que devant la télévision.\n"
        "Renommer un profil DÉJÀ synchronisé n'est pas gratuit : l'identifiant "
        "entre dans la clé de système que porte le raccourci Steam, donc dans "
        "ses options de lancement, dont dérive l'identifiant de l'entrée. Les "
        "jeux de cet émulateur seront recréés sous une nouvelle identité et "
        "leur artwork retéléchargé — le faire Steam fermé, puis relancer "
        "« retro scan » et « retro sync »."
    )


def load_profile(path: pathlib.Path) -> Profile:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{path} n'est pas du TOML valide : {exc}") from exc
    if data.get("schema") != SCHEMA:
        raise ProfileError(
            f"{path} déclare schema = {data.get('schema')}, attendu {SCHEMA}"
        )
    for champ in ("id", "exe"):
        if champ not in data:
            raise ProfileError(f"{path} : champ '{champ}' manquant")
    _valider_id(path, data["id"])

    systemes = []
    vus = set()
    for rang, brut in enumerate(data.get("system", [])):
        # 'id' est OBLIGATOIRE, et vérifié avant tout le reste : il nommait
        # les messages d'erreur suivants. Absent, il valait le littéral « ? »
        # et le profil se chargeait sans un mot — mais aucun dossier de ROMs
        # ne s'appelle « ? », donc le système entier n'apparaissait jamais
        # dans Steam et le scan rendait zéro. Même famille que la faute de
        # frappe sur une clé de BIOS : la faute est muette et le résultat
        # ressemble à une bibliothèque simplement vide.
        if "id" not in brut:
            raise ProfileError(
                f"{path} : le [[system]] n°{rang + 1} n'a pas de champ 'id'. "
                "L'identifiant est le nom du dossier de ROMs à chercher : "
                "sans lui, ce système n'apparaîtrait jamais dans Steam et le "
                "scan rendrait zéro, sans rien signaler."
            )
        sid = brut["id"]
        if sid in vus:
            raise ProfileError(f"{path} : le système '{sid}' est déclaré deux fois")
        vus.add(sid)
        for champ in ("name", "extensions", "launch"):
            if champ not in brut:
                raise ProfileError(f"{path} [{sid}] : champ '{champ}' manquant")
        exts = tuple(brut["extensions"])
        if not exts:
            raise ProfileError(
                f"{path} [{sid}] : aucune extension. Ce système ne pourrait "
                "matcher aucune ROM et serait absent sans rien signaler."
            )
        # Le scan compare à Path.suffix, qui porte toujours son point.
        mauvaises = [e for e in exts if not e.startswith(".")]
        if mauvaises:
            raise ProfileError(
                f"{path} [{sid}] : extension(s) sans point : {', '.join(mauvaises)}"
            )
        # `folders` dit sous quels AUTRES noms ce système peut être rangé.
        # Une bibliothèque réelle s'organise « Nintendo\\Gamecube\\ » ou
        # « Sony\\Playstation\\ », pas par identifiant technique, et ce n'est
        # pas au propriétaire de renommer sa collection pour convenir à
        # l'outil. Les fautes ci-dessous sont toutes muettes : un `folders`
        # mal typé ou vide ne fait pas échouer le scan, il fait rendre zéro.
        declares = brut.get("folders", [])
        if not isinstance(declares, list):
            raise ProfileError(
                f"{path} [{sid}] : 'folders' doit être une liste de noms de "
                "dossier (folders = [\"Playstation\", \"PS1\"]). Un autre "
                "type ne serait jamais comparé à quoi que ce soit, et le "
                "dossier du propriétaire resterait invisible."
            )
        mauvais = [repr(f) for f in declares
                   if not isinstance(f, str) or not f.strip()]
        if mauvais:
            raise ProfileError(
                f"{path} [{sid}] : 'folders' contient des entrées vides ou non "
                f"textuelles : {', '.join(mauvais)}. Chacune est un nom de "
                "dossier, comparé tel quel à la casse près — une entrée vide "
                "ne désigne rien et le dossier visé resterait ignoré, sans "
                "qu'aucun message ne le dise."
            )
        # Un nom de dossier ne PEUT pas contenir de séparateur : le scan
        # compare le nom d'UN dossier, jamais un chemin. Déclarer
        # « Nintendo/Gamecube » ne matcherait rien, et la faute serait muette.
        chemins = [f for f in declares if "/" in f or "\\" in f]
        if chemins:
            raise ProfileError(
                f"{path} [{sid}] : 'folders' contient des chemins : "
                f"{', '.join(chemins)}. Chaque entrée est le nom d'UN dossier, "
                "jamais un chemin — le scan descend tout seul dans les "
                "dossiers de constructeur, et un nom composé ne serait comparé "
                "à rien."
            )
        # Le marqueur de dossier d'application. Les trois refus ci-dessous
        # portent sur des fautes MUETTES : chacune laisse le profil se
        # charger, le système apparaître dans `retro status`, et le scan
        # rendre ZÉRO jeu — ce qui ressemble exactement à une bibliothèque
        # vide. C'est la même famille que `folders` mal typé.
        marqueur = brut.get("app_dir_marker", "")
        if not isinstance(marqueur, str):
            raise ProfileError(
                f"{path} [{sid}] : 'app_dir_marker' doit être le nom du "
                "fichier qu'une application installée porte à sa racine "
                "(app_dir_marker = \"eboot.bin\"). Un autre type ne serait "
                "comparé à aucun nom de fichier, et aucun dossier ne serait "
                "reconnu comme un jeu."
            )
        if "app_dir_marker" in brut and not marqueur.strip():
            raise ProfileError(
                f"{path} [{sid}] : 'app_dir_marker' est vide. Déclaré, il dit "
                "qu'un jeu de ce système peut être un DOSSIER ; vide, il n'en "
                "reconnaît aucun — le système aurait l'air de couvrir une "
                "bibliothèque en dossiers et rendrait zéro jeu. Le retirer "
                "dit « ici un jeu est un fichier », ce qui est une réponse."
            )
        if "/" in marqueur or "\\" in marqueur:
            raise ProfileError(
                f"{path} [{sid}] : 'app_dir_marker' contient un séparateur : "
                f"{marqueur!r}. Le marqueur est cherché à la RACINE du dossier "
                "d'application, jamais plus bas : un chemin n'y serait comparé "
                "à rien, et le système rendrait zéro jeu sans un mot."
            )
        if "{rom}" not in brut["launch"]:
            raise ProfileError(
                f"{path} [{sid}] : le gabarit launch ne contient pas {{rom}}. "
                "L'émulateur s'ouvrirait sur son propre menu, sans jeu, et la "
                "console aurait l'air de fonctionner."
            )
        # Un BIOS déclaré sans empreinte n'est pas vérifiable. Rien ne le
        # signalerait : une faute de frappe sur la clé (« md5s » pour « md5 »)
        # désactiverait la vérification sans un mot, et le propriétaire
        # croirait ses BIOS validés. L'empreinte est un MD5 parce que ce sont
        # les seules publiquement citables pour ces fichiers ; en calculer
        # d'autres exigerait de faire entrer un BIOS dans le dépôt, ce que ce
        # projet s'interdit.
        for i, b in enumerate(brut.get("bios", ())):
            manquants = [c for c in ("file", "md5") if c not in b]
            if manquants:
                raise ProfileError(
                    f"{path} : profil '{data['id']}', système '{sid}', "
                    f"bios[{i}] — champ(s) manquant(s) : {', '.join(manquants)}. "
                    "Un BIOS sans 'file' et 'md5' ne serait jamais vérifié, "
                    "en silence."
                )
            # Ces fichiers sont écrits à la main (docstring du module) : une
            # valeur numérique sans guillemets (md5 = 5501 au lieu de
            # md5 = "5501") est une faute de frappe naturelle que TOML rend
            # licite en la parsant comme entier. Sans cette vérification de
            # TYPE — la présence seule ne suffit pas — l'entier traverse le
            # chargement du profil et bios.check_bios explose sur l'appel
            # .lower() qu'il fait sur 'md5' : une trace Python sur la
            # commande faite pour expliquer les pannes, plutôt qu'un message
            # qui nomme le profil, le système et le champ à corriger.
            non_textuels = [c for c in ("file", "md5") if not isinstance(b[c], str)]
            # 'group' et 'region' sont facultatifs, mais s'ils sont là ils
            # sont lus : un entier y traverserait le chargement et casserait
            # le rapport, comme le md5 sans guillemets ci-dessus.
            non_textuels += [c for c in ("group", "region")
                             if c in b and not isinstance(b[c], str)]
            if non_textuels:
                raise ProfileError(
                    f"{path} : profil '{data['id']}', système '{sid}', "
                    f"bios[{i}] — champ(s) non textuel(s) : "
                    f"{', '.join(non_textuels)}. Entourer la valeur de "
                    "guillemets (ex. md5 = \"5501\" plutôt que md5 = 5501) : "
                    "ces fichiers sont écrits à la main, et une valeur "
                    "numérique sans guillemets désactiverait la vérification "
                    "sans un mot."
                )

        _valider_groupes(path, data["id"], sid, brut.get("bios", ()))

        # Le bloc `render` est FACULTATIF : les modes se remplissent
        # émulateur par émulateur, chaque option lue dans l'exécutable livré,
        # et un profil qui n'en a pas encore doit continuer de lancer ses
        # jeux. Ce qui est interdit, c'est qu'un système sans modes ait l'air
        # d'en avoir : `retro status` nomme ceux qui n'en déclarent pas.
        brut_render = brut.get("render")
        cout = brut.get("cost", "")
        if not isinstance(cout, str):
            raise ProfileError(f"{path} [{sid}] : 'cost' doit être du texte.")
        if brut_render is not None:
            if cout not in render_mod.COUTS:
                raise ProfileError(
                    f"{path} [{sid}] : 'cost' vaut {cout!r}, attendu l'un de "
                    f"{', '.join(render_mod.COUTS)}. C'est ce que le mode "
                    "`auto` croise avec la machine pour choisir entre natif et "
                    "full — sans lui il déciderait sur une valeur inventée, et "
                    "un jeu qui rame ressemblerait à du matériel insuffisant."
                )
        elif "{render}" in brut["launch"]:
            raise ProfileError(
                f"{path} [{sid}] : le gabarit launch contient {{render}} mais "
                "aucun bloc 'render' n'est déclaré. Le marqueur resterait tel "
                "quel sur la ligne de commande de l'émulateur."
            )

        systemes.append(System(
            id=sid, name=brut["name"], extensions=exts, launch=brut["launch"],
            bios=tuple(brut.get("bios", ())),
            folders=tuple(declares),
            app_dir_marker=marqueur.strip(),
            cost=cout,
            render=(_lire_render(path, sid, brut_render, brut["launch"])
                    if brut_render is not None else None),
        ))

    if not systemes:
        raise ProfileError(f"{path} : aucun système déclaré")

    sortie = data.get("exit", {})
    entree = data.get("input", {})
    mapping, mapping_ou, pad_releve = _lire_mapping(path, entree)
    return Profile(
        id=data["id"], exe=data["exe"], systems=tuple(systemes),
        exit_native=sortie.get("native", ""),
        exit_fallback=sortie.get("fallback", "alt+f4"),
        steam_input=entree.get("steam_input", "required"),
        input_mapping=mapping,
        input_mapping_where=mapping_ou,
        input_pad_releve=pad_releve,
        bootstraps=_lire_bootstraps(path, data.get("bootstrap")),
    )


def _charger_source(directory: pathlib.Path,
                    obligatoire: bool) -> dict[str, tuple[Profile, pathlib.Path]]:
    """Les profils d'un dossier, avec le fichier d'où chacun vient.

    `obligatoire` distingue les deux sources, comme `manifest._lire` distingue
    le manifeste noyau du manifeste utilisateur : le dossier livré avec le
    paquet doit exister et contenir des profils — son absence est un paquet
    cassé, ou un --profiles mal orthographié — tandis que celui du
    propriétaire vit sur un partage qui n'est pas monté au moment du
    provisionnement, et son absence est NORMALE.

    Deux profils de même 'id' sont REFUSÉS. L'affectation seule laissait le
    dernier chargé écraser l'autre, qui disparaissait entièrement : un profil
    copié sans changer son 'id' a remplacé les neuf systèmes de RetroArch par
    deux, `retro scan` a rendu 0 en annonçant un inventaire plus court, puis la
    synchronisation a supprimé les entrées devenues orphelines. Ajouter des
    profils par copie est le chemin nominal, donc l'oubli l'est aussi.

    `load_profile` refuse déjà deux systèmes de même 'id' à l'intérieur d'un
    profil ; c'est la même garde, entre profils.
    """
    # Un chemin qui existe SANS être un dossier n'est pas « pas encore
    # monté » : c'est une erreur de frappe — le profil lui-même donné à la
    # place de son dossier, en général. Le traiter comme une absence rendrait
    # silencieusement les seuls profils du paquet, et les émulateurs du
    # propriétaire manqueraient sans qu'aucun message ne le dise.
    if directory.exists() and not directory.is_dir():
        raise ProfileError(
            f"{directory} n'est pas un dossier. Un dossier de profils est "
            "attendu — celui qui CONTIENT les fichiers .toml, pas l'un "
            "d'eux."
        )
    if not directory.is_dir():
        if obligatoire:
            raise ProfileError(
                f"dossier de profils introuvable : {directory}. Les profils "
                "livrés avec le paquet ne sont pas facultatifs : sans eux, "
                "aucun jeu ne pourrait être lancé. Le dossier des profils du "
                "propriétaire, lui, peut manquer."
            )
        return {}

    source: dict[str, tuple[Profile, pathlib.Path]] = {}
    for f in sorted(directory.glob("*.toml")):
        p = load_profile(f)
        if p.id in source:
            raise ProfileError(
                f"le profil '{p.id}' est déclaré deux fois : "
                f"{source[p.id][1].name} et {f.name}. Le second effacerait le "
                "premier en silence, avec tous ses systèmes — les ROMs "
                "correspondantes disparaîtraient de Steam sans qu'aucun "
                "message ne le dise. Donner un 'id' distinct à chaque profil."
            )
        source[p.id] = (p, f)

    _refuser_systemes_partages(source)
    if obligatoire and not source:
        raise ProfileError(
            f"aucun profil dans {directory} : aucun jeu ne pourrait être lancé"
        )
    return source


def _refuser_systemes_partages(
        source: dict[str, tuple[Profile, pathlib.Path]]) -> None:
    """Dans UNE source, un NOM DE DOSSIER n'est revendiqué que par un système.

    Deux profils du même dossier qui revendiquent 'psx' se disputent le même
    dossier de ROMs. Rien dans le résultat ne le dirait : `scan` retient le
    premier profil par ordre alphabétique, donc renommer un fichier suffirait
    à changer l'émulateur qui lance les jeux — et le TOML fautif, lui, reste
    là. C'est le défaut que `load_profile` refuse déjà À L'INTÉRIEUR d'un
    profil ; entre profils d'une même source, il n'était vérifié que sur les
    données livrées, par un test, et jamais sur celles du propriétaire.

    La règle porte sur TOUS les noms qui désignent un système — son
    identifiant, son nom, et les `folders` qu'il déclare (`folder_claims`) —
    parce que c'est de ces noms que le scan se sert. Deux systèmes qui
    déclarent tous deux « Playstation » rendraient un dossier AMBIGU : le
    départager en silence est exactement ce que ce refus empêche, et la faute
    de frappe dans un `folders` recopié d'un profil voisin est le chemin
    nominal pour y arriver.

    Entre les DEUX sources, la règle est autre : voir `load_profiles`.
    """
    servi: dict[str, tuple[str, pathlib.Path, str]] = {}
    for pid in sorted(source):
        profil, fichier = source[pid]
        for s in profil.systems:
            for nom in folder_claims(s):
                if nom in servi:
                    autre_pid, autre_fichier, autre_sid = servi[nom]
                    precision = (
                        f"'{s.id}'" if autre_sid == s.id else
                        f"'{autre_sid}' et '{s.id}'"
                    )
                    raise ProfileError(
                        f"le dossier de ROMs « {nom} » est revendiqué par deux "
                        f"profils du même dossier : '{autre_pid}' "
                        f"({autre_fichier.name}) et '{pid}' ({fichier.name}), "
                        f"pour le système {precision}. Un seul dossier de ROMs "
                        "porte ce nom : les deux profils se le disputeraient, "
                        "et le scan trancherait par ordre alphabétique — "
                        "renommer un fichier suffirait alors à changer "
                        "l'émulateur qui lance ces jeux, sans qu'aucun message "
                        "ne le dise. Retirer ce système — ou ce nom de "
                        "'folders' — de l'un des deux profils, ou, pour "
                        "remplacer un émulateur livré, déclarer le vôtre dans "
                        "le dossier de profils du propriétaire, qui l'emporte."
                    )
                servi[nom] = (pid, fichier, s.id)


def load_profiles(directory: pathlib.Path,
                  user_directory: pathlib.Path | None = None,
                  ) -> dict[str, Profile]:
    """Les profils livrés, surchargés par ceux du propriétaire.

    Le manifeste accepte déjà une surcharge utilisateur : c'est l'échappatoire
    qui permet au dépôt public de ne référencer aucun émulateur au statut
    contesté sans brider personne. Déclarer un émulateur au manifeste ne
    suffit pourtant pas à s'en servir — il lui faut un profil, qui dit quels
    systèmes il couvre, quelles extensions il accepte et comment on le lance.
    Les deux surcharges vont donc ensemble, et suivent la MÊME règle : à
    identifiant égal, le profil du propriétaire remplace celui du paquet,
    entièrement, comme `dict.update` remplace une entrée de manifeste.

    L'absence du dossier du propriétaire est NORMALE : il vit sur le partage
    qui n'est pas monté au moment du provisionnement.

    **Un système revendiqué des deux côtés revient au propriétaire**, et
    QUITTE le profil livré. Pourquoi ce choix, plutôt que le refus qui vaut
    entre deux profils d'une même source :

    - c'est la raison même d'ajouter un profil standalone. Duckstation sert
      « psx » mieux que le core que RetroArch y met : le propriétaire écrit
      son profil pour prendre la place, pas pour être refusé ;
    - c'est déjà la règle du manifeste, à laquelle ce mécanisme est jumelé.
      Deux règles différentes pour la même idée — « le vôtre l'emporte » —
      seraient une source de bugs, et le propriétaire attendrait la même des
      deux côtés ;
    - refuser ferait d'une collision une panne TOTALE : `scan`, `status` et
      la console entière s'arrêteraient sur un fichier que le propriétaire a
      ajouté pour gagner un émulateur, pas pour en perdre neuf.

    Ce qui reste interdit dans les deux cas, c'est que deux profils se
    disputent SILENCIEUSEMENT le même dossier de ROMs : ici le perdant est
    connu d'avance et ne dépend d'aucun ordre alphabétique, et le système ne
    figure plus que dans un seul profil du résultat — `scan` n'a plus rien à
    arbitrer.

    Un profil livré dont TOUS les systèmes ont été repris disparaît du
    résultat : il ne pourrait plus rien lancer, `load_profile` refuse déjà de
    produire un profil sans système, et le garder ferait réclamer par `retro
    status` l'installation d'un émulateur dont plus aucun jeu ne dépend.
    """
    livres = _charger_source(directory, obligatoire=True)
    miens = (_charger_source(user_directory, obligatoire=False)
             if user_directory is not None else {})

    # La préséance porte sur les NOMS DE DOSSIER, pas sur le seul identifiant
    # de système. Un profil du propriétaire qui sert « Playstation » sous un
    # identifiant à lui — « psx-perso » — ne reprenait rien du tout : les deux
    # systèmes survivaient, tous deux revendiquant ce dossier, et `scan`
    # tranchait par ordre alphabétique des identifiants de PROFIL. Le
    # propriétaire gagnait ou perdait selon le nom qu'il avait donné à son
    # fichier, sans qu'aucun message ne le dise. C'est de ces noms-là que le
    # scan se sert, donc c'est sur eux que la règle doit porter.
    revendiques = {nom for profil, _ in miens.values() for s in profil.systems
                   for nom in folder_claims(s)}
    fusionnes: dict[str, Profile] = {}
    for pid, (profil, _) in livres.items():
        # Un seul nom repris suffit à retirer le système livré : lui en
        # laisser les autres le remettrait en concurrence sur ceux-là, et on
        # retomberait sur l'arbitrage silencieux qu'on vient de fermer.
        restants = tuple(s for s in profil.systems
                         if not any(n in revendiques for n in folder_claims(s)))
        if not restants:
            continue  # tous ses systèmes sont passés au propriétaire
        fusionnes[pid] = (profil if len(restants) == len(profil.systems)
                          else dataclasses.replace(profil, systems=restants))

    # La surcharge à identifiant égal tient dans ce seul `update`, comme celle
    # du manifeste : le profil du propriétaire remplace ENTIÈREMENT celui du
    # paquet, systèmes compris. Écarter l'homonyme plus haut n'y changerait
    # rien — c'est ici, et nulle part ailleurs, que la préséance se décide.
    fusionnes.update({pid: profil for pid, (profil, _) in miens.items()})
    return fusionnes
