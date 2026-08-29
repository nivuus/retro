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

from retro import identite as identite_mod
from retro import install as install_mod
from retro import launcher as launcher_mod
from retro import licence as licence_mod
from retro import profiles as profiles_mod
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
    # Le TROISIÈME axe, un triplet par mode déclaré : (mode, remplissage,
    # motif). Le motif est là pour la même raison que celui de `auto` : des
    # bandes noires sur les côtés sont soit le ratio d'époque correctement
    # rendu, soit un remplissage entier, soit un cadrage que personne n'a
    # réglé — et vues du canapé, les trois se ressemblent exactement.
    remplissage: tuple[tuple[str, str, str], ...] = ()
    # Vrai quand ce remplissage vient du fragment que l'amorçage IMPOSE, et
    # non des arguments du mode. La légende de la section ne peut alors rien
    # en dire — elle cite la politique PAR MODE, et un fragment imposé est
    # posé avant que le mode ne soit résolu. Le motif reste donc sur la ligne
    # du système, là où la légende le remplace d'ordinaire.
    remplissage_impose: bool = False


@dataclasses.dataclass(frozen=True)
class Amorcage:
    """Ce qu'un émulateur a reçu comme configuration, ou n'a pas reçu.

    Trois états, et ils appellent trois lectures différentes : configuration
    posée (avec sa date), profil qui en déclare une mais dont aucun jeu n'a
    encore été lancé, et profil qui n'en déclare aucune. Le dernier n'est une
    anomalie que s'il n'est pas dit : « cet émulateur démarre nu » et « le
    bloc a été oublié » se ressemblent exactement, vus du canapé.
    """
    profile_id: str
    declare: bool
    date: str = ""
    target: str = ""
    # Combien de clés la console IMPOSE dans ce fichier — reposées à chaque
    # lancement, donc rendues à cette valeur chaque fois que le propriétaire
    # les changerait dans l'interface de son émulateur. Il doit le lire AVANT,
    # pas le découvrir après. Zéro pour les profils qui n'imposent rien.
    imposees: int = 0


def etat_amorcage(profils: dict,
                  amorcages: dict[str, list[tuple[str, str]]]
                  ) -> list[Amorcage]:
    """L'état d'amorçage de chaque CIBLE, croisé avec le témoin du lanceur.

    Une entrée par cible, et non par profil : un profil à deux cibles en a deux
    à dire, et les faire tenir sur une ligne ferait disparaître la seconde du
    rapport — elle passerait pour « pas encore amorcée » alors qu'elle est en
    place. C'est pourquoi le témoin porte lui aussi une ligne par cible.

    Le témoin ne peut renseigner que les profils qui DÉCLARENT un amorçage :
    un profil sans bloc `[[bootstrap]]` n'aura jamais de ligne dans le témoin,
    et ce n'est pas une panne — c'est cet émulateur qui se règle seul.
    """
    etats = []
    for pid in sorted(profils):
        poses = list(amorcages.get(pid, ()))
        if not profils[pid].bootstraps:
            etats.append(Amorcage(profile_id=pid, declare=False))
            continue
        for rang, amorcage in enumerate(profils[pid].bootstraps):
            date, cible = poses[rang] if rang < len(poses) else ("", "")
            etats.append(Amorcage(
                # Amorçée, la cible est celle que le lanceur a RÉSOLUE et
                # écrite au témoin ; pas encore amorcée, c'est celle que le
                # profil DÉCLARE, jeton compris. Sans ce repli, un profil à
                # deux cibles imprimait deux lignes identiques mot pour mot —
                # qui ne se lisent pas comme deux cibles, mais comme un
                # doublon d'affichage, alors que l'une impose huit clés et
                # l'autre aucune.
                profile_id=pid, declare=True, date=date,
                target=cible or amorcage.target,
                # `cles_de` et non `cles_ini` : le dialecte suit l'extension de
                # la cible. Compté à l'INI seul, un config.yml rendait ZÉRO, et
                # le rapport annonçait « aucun réglage imposé » là où la console
                # en reprend un.
                imposees=len(profiles_mod.cles_de(amorcage.target,
                                                  amorcage.enforced))))
    return etats


# Les trois états d'un fragment déposé à côté des plans. « conforme » n'est PAS
# dit dans le rapport : un fragment à jour est le cas normal, et le dire dix
# fois noierait celui qui, lui, est périmé.
FRAGMENT_CONFORME = "conforme"
FRAGMENT_ECART = "ne correspond plus au profil"
FRAGMENT_ABSENT = "jamais déposé"


@dataclasses.dataclass(frozen=True)
class Fragment:
    """Un fichier que `ecrire_plan` dépose, confronté à ce que le profil dit.

    C'est la dette D11 : ces fichiers ne sont écrits que par « retro scan ».
    Changer le champ `enforced` d'un profil, voir la suite verte et ne pas
    re-scanner laisse la console fusionner l'ANCIEN fragment. Rien ne le disait,
    et le symptôme est le réglage d'origine — c'est-à-dire, vu du canapé, un
    correctif qui « ne marche pas ».
    """
    profile_id: str
    nom: str
    etat: str


def etat_fragments(profils: dict,
                   fragments: dict[str, str] | None) -> list[Fragment]:
    """Ce que le dépôt impose, confronté à ce que la console porte.

    `fragments` à `None` veut dire que le dossier des plans n'existe pas —
    « retro scan » n'a jamais tourné sur cette machine, ou l'hôte consulte le
    rapport sans voir le disque de la console. Rien n'est alors reprochable, et
    accuser dix profils apprendrait au lecteur à ignorer la section Problèmes.

    La comparaison est faite À L'OCTET PRÈS, contre `fragments_attendus` — la
    fonction même dont `ecrire_plan` se sert pour écrire. Comparer les seules
    clés laisserait passer une VALEUR changée, qui est le cas le plus courant
    d'un `enforced` corrigé ; et une seconde définition de « ce qui devrait être
    là » divergerait de l'écriture au premier changement de convention.
    """
    if fragments is None:
        return []
    etats = []
    for pid in sorted(profils):
        for rang, amorcage in enumerate(profils[pid].bootstraps, 1):
            for nom, attendu in launcher_mod.fragments_attendus(
                    pid, rang, amorcage):
                depose = fragments.get(nom)
                etats.append(Fragment(
                    profile_id=pid, nom=nom,
                    etat=(FRAGMENT_ABSENT if depose is None
                          else FRAGMENT_CONFORME if depose == attendu
                          else FRAGMENT_ECART)))
    return etats


def _probleme_fragments(fragments: list[Fragment],
                        emulation_root: pathlib.Path) -> list[Problem]:
    """UN seul problème groupé — la cause est unique : un scan à rejouer.

    Une ligne par fragment noierait les autres problèmes du rapport, et dix
    lignes disant la même chose se lisent comme dix pannes. Même groupement que
    les modes de rendu et que Steam Input.
    """
    fautifs = [f for f in fragments if f.etat != FRAGMENT_CONFORME]
    if not fautifs:
        return []
    return [Problem(
        what=f"{len(fautifs)} fichier(s) d'amorçage posés sur cette machine ne "
             "sont plus ceux que les profils décrivent : la console applique "
             "un réglage d'un autre âge, et le symptôme sera le défaut qu'on "
             "croyait corrigé",
        where=_joindre(str(emulation_root), launcher_mod.DIR,
                       launcher_mod.PLAN),
        # Le geste, nommé : « retro scan » est le SEUL qui redépose ces
        # fichiers, et rien dans le rapport ne le disait. Le propriétaire
        # cherchait la panne dans le profil, qui était pourtant juste.
        action="lancer « retro scan » sur cette machine : c'est le seul geste "
               "qui redépose ces fichiers",
        details=tuple(f"{f.nom} — {f.etat}" for f in fautifs),
    )]


# La page que `retro status` fait ouvrir au propriétaire quand une manette
# reste à relever. Le chemin est relatif à la racine du dépôt : c'est la seule
# forme qui vaille depuis la console comme depuis l'hôte.
PROCEDURE_RELEVE = "docs/releve-manettes.md"


@dataclasses.dataclass(frozen=True)
class Manette:
    """Où en est le relevé de la manette d'un émulateur.

    Quatre états, et il faut les quatre : « il trouve sa manette seul », « il
    ne la trouve pas et rien n'a été relevé », « le relevé est fait, imposé, et
    un bouton a été vu répondre », « personne n'a mesuré ». Réduits, ils se
    confondraient — et c'est précisément cette confusion qui a laissé
    DuckStation muet sur Crash Team Racing, le plan des manettes le rangeant
    parmi ceux qui « détectent bien tout seuls » sans que ce soit vrai.

    Le quatrième est né le 2026-08-29, à la clôture de D3, parce qu'aucun des
    trois premiers ne pouvait porter ce qui venait d'être constaté : la manette
    répond dans Crash Team Racing, et elle ne répond QUE parce que la console
    impose vingt-sept liaisons. « il trouve sa manette seul » aurait été le
    mensonge exact que D3 a réfuté.

    `where` n'est jamais un identifiant : c'est le fichier, et la section, que
    le propriétaire ouvrira. Aucun identifiant relevé ailleurs que sur la
    machine n'a le droit d'entrer dans ce projet.
    """
    profile_id: str
    etat: str
    where: str = ""
    # SOUS QUEL PAD le relevé a été fait, quand il l'a été. Vide veut dire
    # « rien n'a été relevé », jamais « n'importe lequel » : c'est la
    # condition de validité de la mesure, et c'est elle que la section
    # compare au pad vu au dernier lancement.
    pad: str = ""


def etat_manettes(profils: dict) -> list[Manette]:
    """L'état de relevé de chaque profil, tel qu'il se déclare."""
    return [Manette(profile_id=pid,
                    etat=getattr(profils[pid], "input_mapping",
                                 profiles_mod.MAPPING_INCONNU),
                    where=getattr(profils[pid], "input_mapping_where", ""),
                    pad=getattr(profils[pid], "input_pad_releve", ""))
            for pid in sorted(profils)]


def _releves_clos(manettes: list[Manette]) -> list[Manette]:
    """Les seuls profils qui aient quelque chose à PERDRE au dernier
    lancement : ceux dont un relevé a été fait, et sous un pad nommé.

    Un profil jamais relevé n'a rien qui puisse cesser d'être vrai ;
    l'inscrire aux problèmes ci-dessous noierait ceux qui, eux, sont
    concernés.
    """
    return [m for m in manettes
            if m.etat == profiles_mod.MAPPING_RELEVE and m.pad]


def _problemes_pads(pads: list, manettes: list[Manette]) -> list[Problem]:
    """DEUX problèmes, et deux seulement, tirés du témoin du lanceur.

    Ni « le témoin est absent » — `lanceur_perime` porte déjà ce signal, et le
    redire ici apprendrait à ignorer la section — ni « zéro manette », qui est
    l'état normal d'une session ouverte sans pad branché.
    """
    concernes = _releves_clos(manettes)
    if not pads or not concernes:
        return []
    problemes = []
    ou = " ; ".join(f"{m.profile_id} : {m.where}" for m in concernes)

    # 1. UN PAD DE PLUS. C'est la FRAGILITÉ 1 de duckstation.toml rendue
    # visible : ses vingt-sept liaisons visent « SDL-0 », un INDEX. Le pad
    # d'Apollo qui devient SDL-1 les fait toutes viser un périphérique absent.
    if len(pads) > 1:
        problemes.append(Problem(
            what=f"plus d'une manette au dernier lancement ({len(pads)}) : "
                 "les liaisons relevées visent un INDEX d'énumération, et un "
                 "pad de plus le décale — "
                 + ", ".join(sorted(m.profile_id for m in concernes)),
            where=ou,
            action="ne garder qu'une seule manette branchée pendant la "
                   "session, puis relancer un jeu et relire ce rapport",
            details=("un index qui désigne la mauvaise manette est ignoré "
                     "en silence, exactement comme une valeur inventée : le "
                     "symptôme est une manette muette et rien au journal",
                     "vues : " + ", ".join(
                         f"{p.index} {p.vid_pid} {p.nom}" for p in pads)),
        ))

    # 2. LE PAD D'INDEX 0 N'EST PAS DU TYPE DÉCLARÉ. C'est la panne que D4
    # existe pour empêcher : changer de type de pad change le VID/PID, donc le
    # GUID SDL, donc tout identifiant qu'une configuration d'entrée porterait.
    premier = next((p for p in pads if p.index == 0), None)
    vu = profiles_mod.type_de_pad(premier.vid_pid) if premier else ""
    # Un type inconnu ne prouve RIEN : accuser sur une table incomplète serait
    # pire que se taire.
    if vu:
        discordants = [m for m in concernes if m.pad != vu]
        if discordants:
            problemes.append(Problem(
                what="le pad d'index 0 est un « " + vu + " » alors que ces "
                     "relevés ont été faits sous un autre : "
                     + ", ".join(f"{m.profile_id} ({m.pad})"
                                 for m in sorted(discordants,
                                                 key=lambda m: m.profile_id)),
                where=" ; ".join(f"{m.profile_id} : {m.where}"
                                 for m in discordants),
                action="rejouer la procédure de relevé "
                       f"({PROCEDURE_RELEVE}) sous ce pad-ci, puis reporter "
                       "dans chaque profil ce que l'émulateur a écrit "
                       "lui-même, et son nouveau 'pad_releve'",
                details=("une liaison qui ne correspond à aucun "
                         "périphérique est ignorée en silence ; le symptôme "
                         "est identique avant et après une valeur inventée",
                         f"vu : {premier.vid_pid} {premier.nom}"),
            ))
    return problemes


def _probleme_manettes(manettes: list[Manette]) -> list[Problem]:
    """Un problème par émulateur dont la manette est MESURÉE muette.

    Un seul problème groupé — la forme retenue pour les modes de rendu et pour
    Steam Input — serait ici le mauvais choix : le fichier à ouvrir et la
    section à remplir diffèrent d'un émulateur à l'autre, et un problème sans
    son chemin est une accusation. Ils sont rares par construction : seul un
    émulateur dont quelqu'un a CONSTATÉ la manette muette y figure.

    `inconnu` n'en est pas un : personne n'a regardé, ce n'est pas une panne.
    Il est dit dans la section Manettes, et nulle part ailleurs.

    `releve` n'en est pas un non plus, et c'est le sens même de sa création :
    un émulateur dont un bouton a été VU agir dans un jeu n'a plus de panne à
    signaler. Il reste dit dans la section Manettes — avec le fichier où ses
    liaisons vivent, parce qu'elles peuvent en disparaître.
    """
    return [Problem(
        what=f"{m.profile_id} : aucune liaison de manette n'a été relevée — "
             "la manette restera muette, et l'émulateur ne le dira pas",
        where=m.where,
        action=f"jouer la procédure de relevé ({PROCEDURE_RELEVE}) sur la "
               "console, session ouverte et manette branchée, puis reporter "
               "dans le profil ce que l'émulateur a écrit lui-même",
        # La phrase qui empêche la « correction » qui n'en est pas une. Sans
        # elle, le prochain lecteur recopie un identifiant trouvé dans une
        # recette, relance, et constate le MÊME symptôme qu'avant sans
        # comprendre que sa valeur est simplement ignorée.
        details=("une liaison qui ne correspond à aucun périphérique est "
                 "ignorée en silence : le symptôme est identique avant et "
                 "après une valeur inventée",),
    ) for m in manettes if m.etat == profiles_mod.MAPPING_A_RELEVER]


@dataclasses.dataclass(frozen=True)
class Vibration:
    """Où en est la VIBRATION d'un émulateur, telle que son profil la déclare.

    Cinq états, et il faut les cinq — c'est ce que le champ `[input] rumble`
    porte, et le rapport ne fait que le relayer. Aucune ligne d'ici n'affirme
    qu'une manette vibre : seul `vu` le dit, et un profil ne peut déclarer
    `vu` qu'avec un témoin humain daté, que le chargement exige.

    Avant ce type, `retro status` ne disait RIEN de la vibration — pas une
    section, pas un problème, pas une ligne — alors que la dette D1 la donne
    pour absente PARTOUT. L'aveu vivait dans des commentaires TOML, que
    personne ne lit depuis un canapé : c'est très exactement l'écart que le
    sous-projet E reproche à `steam_input = "required"`.
    """
    profile_id: str
    etat: str
    where: str = ""
    witness: str = ""


def etat_vibrations(profils: dict) -> list[Vibration]:
    """L'état de vibration de chaque profil, tel qu'il se déclare."""
    return [Vibration(profile_id=pid,
                      etat=getattr(profils[pid], "input_rumble",
                                   profiles_mod.RUMBLE_INCONNU),
                      where=getattr(profils[pid], "input_rumble_where", ""),
                      witness=getattr(profils[pid], "input_rumble_witness", ""))
            for pid in sorted(profils)]


def _probleme_vibrations(vibrations: list[Vibration]) -> list[Problem]:
    """Un problème pour le SEUL état `a-relever`, comme pour les manettes.

    C'est le seul des cinq qui dise « quelqu'un a constaté, et il reste un
    geste à faire ». Les quatre autres sont nommés dans la section Vibration,
    et nulle part ailleurs :

    - `inconnu` : personne n'a regardé, ce n'est pas une panne ;
    - `pose` : un réglage EST posé, il n'y a pas de relevé à jouer. Il reste
      dit, AVEC son fichier — personne ne l'a vu agir, et il peut disparaître
      de ce fichier sans un mot ;
    - `vu` : mesuré, et soutenu par un témoin ;
    - `absent` : mesuré aussi — cet émulateur n'a rien à régler.
    """
    return [Problem(
        what=f"{m.profile_id} : aucun réglage de vibration n'a été relevé — "
             "la manette ne vibrera pas, et l'émulateur ne le dira pas",
        where=m.where,
        action=f"jouer la procédure de relevé ({PROCEDURE_RELEVE}) sur la "
               "console : activer la vibration DANS l'interface de "
               "l'émulateur, le fermer, puis recopier dans le profil ce qu'il "
               "a écrit lui-même",
        # La même garde que pour les liaisons de manette, et pour la même
        # raison : le nom d'une clé de rumble n'est pas une propriété de la
        # manette, c'est une propriété de l'émulateur qui la nomme.
        details=("une clé de rumble recopiée d'une documentation est ignorée "
                 "en silence : le symptôme est identique avant et après une "
                 "valeur inventée",),
    ) for m in vibrations if m.etat == profiles_mod.RUMBLE_A_RELEVER]



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
    # La construction du paquet qui a produit CE rapport. Vide veut dire que
    # l'appelant ne l'a pas dite — pas qu'elle vaut celle du module courant :
    # un rapport relu ailleurs mentirait.
    paquet: str = ""
    amorcages: list[Amorcage] = dataclasses.field(default_factory=list)
    manettes: list[Manette] = dataclasses.field(default_factory=list)
    vibrations: list[Vibration] = dataclasses.field(default_factory=list)
    # Les licences PS Vita, une entrée par jeu QUI EN PORTE UNE. Vide veut dire
    # « aucun jeu inventorié n'a de licence à faire poser » — pas « aucune
    # n'est posée ».
    licences: list[licence_mod.EtatLicence] = dataclasses.field(
        default_factory=list)

    # Le témoin du DERNIER lancement. Une date vide veut dire « le lanceur n'a
    # jamais relevé de manette » — ce qui DIFFÈRE de « aucune manette vue »,
    # et les confondre effacerait le plus utile des deux constats.
    pads_date: str = ""
    pads: list = dataclasses.field(default_factory=list)


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
                remplissage=tuple(
                    (nom, choix.remplissage, choix.motif)
                    for nom, choix in (
                        (n, render_mod.resoudre_remplissage(
                            n, m,
                            fill_enforced=rendu.fill_enforced,
                            fill_enforced_where=rendu.fill_enforced_where))
                        for n, m in ((render_mod.NATIVE, rendu.native),
                                     (render_mod.FULL, rendu.full)))),
                remplissage_impose=bool(rendu.fill_enforced),
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


def _probleme_remplissage_non_mesure(etats: list[SystemRender]) -> list[Problem]:
    """Les systèmes dont le TROISIÈME axe n'a jamais été mesuré.

    Groupé, comme les modes manquants. Un système qui n'a pas de remplissage
    RÉGLABLE — DuckStation — n'y figure pas : la question y a été tranchée et
    la réponse est non. Les confondre ferait rouvrir l'enquête à chaque
    passage sur un émulateur qui a déjà répondu.
    """
    muets = sorted({e.system_name for e in etats
                    for _, valeur, _ in e.remplissage
                    if valeur == render_mod.NON_MESURE})
    if not muets:
        return []
    return [Problem(
        what=f"{len(muets)} système(s) ne disent rien du remplissage de "
             "l'écran : l'image y est celle que l'émulateur a choisie seul",
        where="retro/data/profiles/*.toml",
        action="déclarer 'fill' dans chaque mode — le remplissage que ses "
               "arguments produisent — ou 'fill_absent', qui dit que cet "
               "émulateur n'en expose aucun réglage",
        details=tuple(muets),
    )]


def _probleme_lanceur_perime(perime: bool,
                             emulation_root: pathlib.Path) -> list[Problem]:
    """Le binaire en place est plus vieux que la source déposée à côté.

    Un lanceur compilé avant une évolution du plan ignore EN SILENCE les
    lignes qu'il ne connaît pas : rien n'échoue, rien n'est posé, et ce
    rapport annoncerait « pas encore amorcé » après cinquante lancements. La
    section Amorçage, seule, enverrait alors chercher la panne du mauvais
    côté — c'est ici, et pas dans le profil, qu'elle se corrige.
    """
    if not perime:
        return []
    return [Problem(
        what="le lanceur en place est plus ancien que sa source : il ignore "
             "en silence ce que les plans portent de nouveau (l'amorçage des "
             "émulateurs, notamment) — aucune erreur ne le signale",
        # Le chemin, comme pour tout problème de ce rapport : « recompiler »
        # sans dire OÙ envoie chercher un script dans une arborescence que le
        # propriétaire ne connaît pas par cœur.
        where=_joindre(str(emulation_root), launcher_mod.DIR, launcher_mod.EXE),
        action="le recompiler depuis Windows : "
               + _joindre(str(emulation_root), launcher_mod.DIR,
                          launcher_mod.RECOMPILER),
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


def _probleme_dossiers_de_mise_a_jour(dossiers: Sequence[str]) -> list[Problem]:
    """Un dossier d'application qui ressemble à une mise à jour.

    `app_dir_marker` retient tout sous-dossier portant le fichier déclaré, et
    une mise à jour extraite en porte un aussi. Posée à côté de sa base, elle
    donne une SECONDE entrée Steam pour le même jeu — d'apparence normale, et
    qui lance le correctif seul, soit rien de jouable.

    Le scan la garde : il ne peut pas PROUVER qu'il tient une mise à jour sans
    ouvrir le dossier, ce qu'il ne fait jamais, et un jeu retiré sur une
    devinette disparaîtrait sans un mot. C'est donc ici que ça se dit — le
    rapport est le seul endroit du paquet qui s'adresse à une personne.
    """
    if not dossiers:
        return []
    seul = len(dossiers) == 1
    pluriel, porte = ("", "porte") if seul else ("s", "portent")
    return [Problem(
        what=f"{len(dossiers)} dossier{pluriel} de jeu {porte} un nom de mise à "
             "jour : chacun donne une entrée Steam de plus pour un jeu déjà "
             "présent, qui lancerait le correctif seul",
        where="sous la racine des ROMs, celle donnée à --roms",
        action="les sortir de l'arborescence scannée, et les désigner à "
               "l'émulateur autrement — ou, si ce sont de vrais jeux, ignorer "
               "cette ligne : le scan devine sur le NOM, il ne les a pas "
               "ouverts",
        details=tuple(dossiers),
    )]
def _lignes_licences(report: Report) -> list[str]:
    """Où en est la licence de chaque jeu PS Vita qui en porte une.

    Quatre formulations, une par état, et c'est le quatrième qui compte : tant
    que le système de fichiers Vita vit dans le profil Windows, l'hôte ne peut
    RIEN constater, et il doit le dire plutôt que d'annoncer un manque. Un
    rapport qui annonce un manque qu'il ne peut pas constater est le pire des
    états — c'est le raisonnement déjà écrit pour le témoin d'amorçage.
    """
    lignes = []
    for l in report.licences:
        if l.etat == licence_mod.POSEE:
            lignes.append(f"  · {l.jeu} : licence posée ({l.attendue})")
        elif l.etat == licence_mod.ABSENTE:
            lignes.append(f"  · {l.jeu} : licence ABSENTE — attendue en "
                          f"{l.attendue}")
        elif l.etat == licence_mod.HORS_DE_PORTEE:
            lignes.append(f"  · {l.jeu} : porte une licence ; sa présence ne "
                          "peut pas être constatée d'ici")
            lignes.append(f"      {l.detail}")
            lignes.append(f"      elle serait en {l.attendue}")
        else:
            lignes.append(f"  · {l.jeu} : sa licence est illisible")
            lignes.append(f"      {l.detail}")
    return lignes


def _probleme_licences(licences: Sequence[licence_mod.EtatLicence]
                       ) -> list[Problem]:
    """Un problème pour ce qui est CONSTATÉ, jamais pour ce qui est hors de
    portée : l'accuser apprendrait au lecteur à ignorer cette section."""
    problemes = []
    for l in licences:
        if l.etat == licence_mod.ABSENTE:
            problemes.append(Problem(
                what=f"{l.jeu} : sa licence n'est pas posée",
                where=l.attendue,
                # Le geste est NATIF, et le dire évite d'envoyer chercher une
                # conversion qui n'existe pas : main.cpp traite tout
                # content-path nommé « work.bin » comme une licence à poser, et
                # copy_license copie le fichier TEL QUEL sous son nom de .rif.
                action="passer le fichier sce_sys\\package\\work.bin du jeu à "
                       "l'émulateur en ligne de commande : il le pose "
                       "lui-même, sans rien convertir",
                details=("son absence ne bloque pas le jeu : elle fausse un "
                         "seul champ, et l'émulateur ne s'en plaint que dans "
                         "son journal",)))
        elif l.etat == licence_mod.ILLISIBLE:
            problemes.append(Problem(
                what=f"{l.jeu} : le fichier de licence du dump est illisible",
                where="\\".join((str(l.jeu), *licence_mod.LICENCE_DU_DUMP)),
                action="vérifier le dump : ce fichier n'a pas la forme d'une "
                       "licence, et « absente » serait un diagnostic faux",
                details=(l.detail,)))
    return problemes


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
    amorcages: dict[str, list[tuple[str, str]]] | None = None,
    lanceur_perime: bool = False,
    paquet: str = "",
    dossiers_de_mise_a_jour: Sequence[str] = (),
    licences: Sequence[licence_mod.EtatLicence] = (),
    fragments: dict[str, str] | None = None,

    pads_date: str = "",
    pads: Sequence = (),
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

    `lanceur_perime` dit que le binaire en place est plus ancien que la
    source déposée à côté de lui. Un lanceur d'avant ignore en silence ce que
    les plans portent de nouveau : le rapport le dit, sans quoi la section
    Amorçage ci-dessous accuserait les profils d'une panne qui n'est pas la
    leur.

    `dossiers_de_mise_a_jour` porte les dossiers d'application dont le NOM
    évoque une mise à jour — `scan.suspected_update_dirs`. Ils restent dans
    l'inventaire, parce que le scan ne peut pas prouver qu'ils n'en sont pas ;
    ce rapport est le seul endroit où le doublon puisse se dire.

    `paquet` est la construction du paquet qui produit ce rapport. Il est
    CONSTATÉ, jamais reproché : lancer `retro` depuis son arbre source est le
    cas normal de l'hôte, et en faire un problème apprendrait au lecteur à
    ignorer la section « Problèmes ». `status` n'a d'ailleurs aucune référence
    à opposer — savoir quelle identité DEVRAIT être là est le travail de
    l'hôte qui a livré la roue, pas celui d'un rapport.

    `fragments` est le contenu RÉEL des fichiers déposés à côté des plans, lus
    sur le disque de cette machine par `launcher.lire_fragments`. Seul
    « retro scan » les écrit : sans cette confrontation, un `enforced` corrigé
    ici pouvait rester sans le moindre effet là-bas, et le message obtenu
    décrivait le symptôme d'origine — exactement comme si le correctif était
    faux. `None` veut dire que le dossier des plans n'existe pas, et rien n'est
    alors reproché.

    `amorcages` est le témoin que le lanceur écrit sur la machine — profil →
    [(date, cible), …], une entrée par cible posée. `retro status` tourne sur l'hôte, qui n'atteint ni
    `C:\\Users` ni `%APPDATA%` de la console : c'est la seule trace dont il
    dispose pour dire qu'une configuration a bien été posée.
    """
    emulateurs, problemes_emulateurs = _etat_emulateurs(
        install_dirs, emulation_root, ignored_systems, emulator_exes)
    rendu = etat_rendu(profils) if profils else []
    manettes = etat_manettes(profils) if profils else []
    vibrations = etat_vibrations(profils) if profils else []
    deposes = etat_fragments(profils, fragments) if profils else []
    return Report(
        emulators=emulateurs,
        systems=list(systems),
        bios=list(bios_status),
        problems=[*problemes_emulateurs,
                  *_problemes_bios(bios_status, bios_root),
                  *_probleme_sans_modes(rendu),
                  *_probleme_remplissage_non_mesure(rendu),
                  *_probleme_steam_input(steam_input_muets, steam_input_echec),
                  *_probleme_lanceur_perime(lanceur_perime, emulation_root),
                  *_probleme_manettes(manettes),
                  *_probleme_dossiers_de_mise_a_jour(
                      dossiers_de_mise_a_jour),
                  *_probleme_vibrations(vibrations),
                  *_probleme_licences(licences),
                  *_probleme_fragments(deposes, emulation_root),
                  *_problemes_pads(list(pads), manettes)],
        bios_root=bios_root,
        render_mode=render_mode,
        paquet=paquet,
        render=rendu,
        amorcages=etat_amorcage(profils, amorcages or {}) if profils else [],
        manettes=manettes,
        vibrations=vibrations,
        licences=list(licences),

        pads_date=pads_date,
        pads=list(pads),
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
    lignes = [f"  {l}" for l in legende_remplissage()] + [""]
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
            # LE REMPLISSAGE SE DIT ICI AUSSI, et avant les notes. Sortir sans
            # l'imprimer taisait le troisième axe sur le seul émulateur dont
            # la console règle le cadrage par son fichier de réglages
            # (DuckStation) : le rapport laissait croire « rien à régler » sur
            # celui où il y avait justement quelque chose.
            lignes += [f"  {' ' * largeur}    {l}"
                       for l in _lignes_remplissage(e.remplissage,
                                                    e.remplissage_impose)]
            for note in e.notes:
                lignes.append(f"  {' ' * largeur}    {note}")
            continue
        crt = "natif avec CRT" if e.crt else "natif sans CRT"
        lignes.append(f"  {nom}  {crt}  |  auto : {_resume_auto(e.auto)}")
        if not e.crt:
            lignes.append(f"  {' ' * largeur}    ({e.crt_absent})")
        lignes += [f"  {' ' * largeur}    {l}"
                   for l in _lignes_remplissage(e.remplissage,
                                                e.remplissage_impose)]
        for note in e.notes:
            lignes.append(f"  {' ' * largeur}    {note}")
    return lignes


def legende_remplissage() -> list[str]:
    """La politique de remplissage, citée UNE fois en tête de section.

    Une fois, et pas par système : les huit systèmes de RetroArch porteraient
    la même phrase, et dix-huit lignes identiques se lisent zéro fois — c'est
    la règle qui vaut déjà pour les problèmes groupés. Mais elle doit être
    quelque part : un cadrage qui s'appliquerait en silence serait un défaut,
    et des bandes noires ont trois causes possibles que rien ne distingue vu
    du canapé (le ratio d'époque, un agrandissement entier, un cadrage que
    personne n'a réglé).
    """
    return [f"remplissage — {mode} : {render_mod.motif_remplissage(mode)}"
            for mode in render_mod.MODES_DECLARES]


def _lignes_remplissage(remplissage: tuple[tuple[str, str, str], ...],
                        impose: bool = False) -> list[str]:
    """Le troisième axe d'UN système, mode par mode.

    Le motif n'accompagne que ce que la légende n'explique pas : un émulateur
    qui n'expose aucun réglage, un remplissage que personne n'a mesuré — et
    un remplissage IMPOSÉ par l'amorçage.

    Ce dernier porte pourtant une valeur de l'axe, `entier` ou `ajuste` : sans
    `impose`, il passerait pour un remplissage que la légende explique. Elle
    ne l'explique pas — elle cite la politique PAR MODE, et un fragment imposé
    est posé avant que le mode ne soit résolu, donc la même valeur sort des
    deux modes. Taire le motif ferait lire une contradiction avec la légende
    là où il n'y en a pas, et cacherait OÙ la clé est posée.
    """
    if not remplissage:
        return []
    valeurs = ", ".join(f"{mode} {valeur}" for mode, valeur, _ in remplissage)
    lignes = [f"remplissage : {valeurs}"]
    # Dédoublonné : les deux modes d'un émulateur qui n'expose rien portent la
    # même phrase, et l'imprimer deux fois la fait lire zéro. C'est aussi le
    # cas d'un remplissage imposé, qui vaut la même chose des deux côtés.
    vus: list[str] = []
    for _, valeur, motif in remplissage:
        if (impose or valeur not in render_mod.REMPLISSAGES) and motif not in vus:
            vus.append(motif)
    return lignes + [f"  ({m})" for m in vus]


def _lignes_amorcage(report: Report) -> list[str]:
    """Ce que chaque profil a reçu — ou pas — comme configuration.

    Trois formulations, une par état de `Amorcage` : le propriétaire doit
    pouvoir vérifier qu'une configuration a bien été posée sans ouvrir
    l'émulateur, et un profil qui n'en déclare aucune doit être NOMMÉ pour ne
    pas se confondre avec un bloc oublié.
    """
    lignes = []
    for a in report.amorcages:
        if not a.declare:
            lignes.append(f"  · {a.profile_id} : aucune configuration à "
                          "poser (voir son profil)")
        elif a.date:
            lignes.append(f"  · {a.profile_id} : amorcé le {a.date} "
                          f"({a.target})")
        else:
            lignes.append(f"  · {a.profile_id} : pas encore amorcé "
                          f"({a.target}) — sa configuration sera posée au "
                          "premier lancement d'un de ses jeux")
        # Dit à CHAQUE état, y compris « déjà amorcé » : c'est justement
        # l'émulateur déjà amorcé dont le fichier sera rouvert, et le taire
        # là serait le taire au seul endroit où ça compte.
        #
        # Le COMPTE, et pas seulement le fait : « impose 3 clés » et « impose
        # tout le fichier » n'appellent pas la même réaction, et sans le
        # nombre il faudrait ouvrir le profil pour savoir laquelle des deux
        # on lit.
        if a.imposees:
            lignes.append(
                f"      la console y impose {a.imposees} clé(s), reposée(s) à "
                "chaque lancement ; tout le reste du fichier vous appartient "
                "et n'est jamais touché, et une sauvegarde précède chaque "
                "modification")
    return lignes


def _lignes_manettes(report: Report) -> list[str]:
    """Où en est la manette de chaque émulateur.

    Quatre formulations, une par état, sur le modèle de la section Amorçage.
    Celle de `a-relever` NOMME le fichier : c'est là que le propriétaire ira,
    et un rapport qui dit « à relever » sans dire où ne fait que déplacer la
    question. Celle de `releve` le nomme aussi, pour la raison inverse : les
    liaisons y sont reposées à chaque lancement, et c'est le seul endroit où
    vérifier qu'elles y sont encore.
    """
    lignes = []
    for m in report.manettes:
        if m.etat == profiles_mod.MAPPING_AUTO:
            lignes.append(f"  · {m.profile_id} : trouve sa manette seul "
                          "(mesuré)")
        elif m.etat == profiles_mod.MAPPING_A_RELEVER:
            lignes.append(f"  · {m.profile_id} : manette muette, liaison à "
                          f"relever — {m.where}")
        elif m.etat == profiles_mod.MAPPING_RELEVE:
            lignes.append(f"  · {m.profile_id} : liaisons relevées et "
                          f"imposées, réponse vue en jeu — {m.where}")
        else:
            lignes.append(f"  · {m.profile_id} : jamais mesuré — personne n'a "
                          "vérifié que sa manette répond")
        if m.pad:
            lignes.append(f"      relevé sous un pad « {m.pad} » — il ne vaut "
                          "que sous celui-là")
    return lignes + _lignes_dernier_lancement(report)


def _lignes_dernier_lancement(report: Report) -> list[str]:
    """Ce que le lanceur a VU la dernière fois, en quatre formulations.

    Les quatre sont distinctes parce que les quatre situations le sont, et
    que trois d'entre elles se lisaient jusqu'ici comme un même silence :

    - témoin absent : le lanceur n'a pas encore tourné, ou il est trop vieux
      pour savoir écrire ce fichier. PAS un problème — `lanceur_perime` porte
      déjà ce signal, et le redire ici apprendrait à ignorer la section ;
    - zéro manette : il a REGARDÉ et n'a rien vu. Ce n'est pas un problème non
      plus — une session peut s'ouvrir sans pad branché — mais c'est un
      constat, et le confondre avec le précédent effacerait le seul des deux
      qui dise quelque chose de la console ;
    - une manette : son type et son nom, parce que c'est ce qu'on compare ;
    - deux ou plus : dites toutes, et le problème correspondant est levé
      ailleurs. La section MONTRE, la section « Problèmes » ACCUSE.
    """
    if not report.pads_date:
        return ["  · dernier lancement : le lanceur n'a jamais relevé de "
                "manette (il n'a pas encore tourné, ou il précède ce relevé)"]
    if not report.pads:
        return [f"  · dernier lancement ({report.pads_date}) : aucune manette "
                "au dernier lancement — une session peut s'ouvrir sans pad"]
    # 1 prend le singulier : « 1 manette(s) » est de la même famille que le
    # « 1 jeux » et le « Problèmes (1) » déjà corrigés, et une parenthèse de
    # formulaire apprend au lecteur que le texte a été écrit par une machine.
    nb = len(report.pads)
    lignes = [f"  · dernier lancement ({report.pads_date}) : "
              f"{nb} manette{'s' if nb > 1 else ''}"]
    for pad in report.pads:
        # Le vid:pid est dit DANS TOUS LES CAS, reconnu ou non : c'est la
        # seule chose que le rapport sache avec certitude de ce pad, et c'est
        # la valeur exacte à reporter dans la table le jour où elle manque.
        type_vu = profiles_mod.type_de_pad(pad.vid_pid)
        lignes.append(f"      [{pad.index}] {pad.vid_pid} "
                      + (f"« {type_vu} » " if type_vu
                         else "(type inconnu de la table) ")
                      + pad.nom)
    return lignes


def _lignes_vibration(report: Report) -> list[str]:
    """Où en est la vibration de chaque émulateur.

    Cinq formulations, une par état, sur le modèle de la section Manettes. Les
    trois qui nomment un fichier le nomment : celui où le relevé se fera, celui
    où le réglage posé vit et d'où il peut disparaître sans un mot.

    AUCUNE ligne n'affirme que la vibration marche. Le rapport rend ce que les
    profils déclarent, et un profil ne déclare `vu` qu'avec un témoin humain
    daté — que la ligne cite, parce que c'est la seule chose qui distingue une
    mesure d'une affirmation.
    """
    lignes = []
    for v in report.vibrations:
        if v.etat == profiles_mod.RUMBLE_A_RELEVER:
            lignes.append(f"  · {v.profile_id} : ne vibre pas, aucun réglage "
                          f"relevé — {v.where}")
        elif v.etat == profiles_mod.RUMBLE_POSE:
            lignes.append(f"  · {v.profile_id} : un réglage est posé et "
                          f"reposé, jamais vu agir — {v.where}")
        elif v.etat == profiles_mod.RUMBLE_VU:
            lignes.append(f"  · {v.profile_id} : vibration SENTIE en jeu "
                          f"({v.witness}) — {v.where}")
        elif v.etat == profiles_mod.RUMBLE_ABSENT:
            lignes.append(f"  · {v.profile_id} : aucun réglage de vibration à "
                          "poser, mesuré dans sa source")
        else:
            lignes.append(f"  · {v.profile_id} : jamais mesuré — personne n'a "
                          "senti cette manette vibrer")
    return lignes


def format_report(report: Report) -> str:
    """Le texte que l'hôte relaie tel quel au propriétaire."""
    sections: list[str] = []

    # EN PREMIER, et inconditionnelle comme BIOS, Rendu, Amorçage et
    # Manettes : tout ce qui suit a été produit par UNE construction du
    # paquet, et deux roues peuvent porter le même « 0.1.0 » sans contenir le
    # même code. Qui compare deux rapports doit le voir avant de les croire
    # contradictoires. Le repli est atteignable — un appelant qui ne dit pas
    # quelle construction le produit laisse `paquet` vide — et il ne remplit
    # PAS le blanc avec la version du module courant : un rapport relu
    # ailleurs annoncerait alors une identité qui n'est pas la sienne.
    sections += _section(
        "Paquet",
        [f"  {identite_mod.lisible(report.paquet)}"] if report.paquet else [],
        "identité inconnue : ce rapport ne peut pas dire quelle construction "
        "l'a produit")

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

    # INCONDITIONNELLE, comme BIOS et Rendu : une section qui disparaît se lit
    # comme une panne d'affichage, et le repli est la seule chose qui
    # distingue « rien à dire » de « rien n'a été lu ». Il est atteignable —
    # `build_report` rend une liste vide dès qu'on ne lui passe pas de
    # profils, ce que fait tout appelant qui n'a pas pu les charger.
    sections += _section(
        "Amorçage", _lignes_amorcage(report),
        "aucun profil chargé : l'amorçage se lit profil par profil")

    # INCONDITIONNELLE, comme BIOS, Rendu et Amorçage. Elle l'est ici pour une
    # raison de plus : une manette muette ne se constate que le pad en main,
    # devant la télévision, et une section absente serait lue comme « rien à
    # signaler » par quelqu'un qui vient justement de ne pas pouvoir jouer.
    sections += _section(
        "Manettes", _lignes_manettes(report),
        "aucun profil chargé : l'état des manettes se lit profil par profil")

    # INCONDITIONNELLE, pour la raison de la section Manettes portée à son
    # extrême : une manette qui ne vibre pas ne se constate QUE la manette en
    # main, et jusqu'ici le rapport n'en disait pas un mot — l'aveu vivait dans
    # des commentaires TOML que personne ne lit depuis un canapé (dette D1).
    sections += _section(
        "Vibration", _lignes_vibration(report),
        "aucun profil chargé : l'état de la vibration se lit profil par "
        "profil")
    # INCONDITIONNELLE, pour la même raison que les autres : une section qui
    # disparaît se lit comme une panne d'affichage. Le repli dit exactement ce
    # que le vide veut dire — « aucun jeu n'en porte » — et non « aucune n'est
    # posée », qui serait un tout autre constat.
    sections += _section(
        "Licences", _lignes_licences(report),
        "aucun jeu inventorié ne porte de licence à faire poser")

    nb = len(report.problems)
    # 0 et 1 prennent le singulier en français : « Problème (1) », pas
    # « Problèmes (1) ». Même famille que le « 1 jeux » déjà corrigé.
    sections += _section(
        f"Problème{'s' if nb > 1 else ''} ({nb})",
        _lignes_problemes(report.problems),
        "aucun problème détecté — tout est en ordre",
    )

    return "\n".join(sections).rstrip("\n")
