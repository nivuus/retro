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
                profile_id=pid, declare=True, date=date, target=cible,
                imposees=len(profiles_mod.cles_ini(amorcage.enforced))))
    return etats


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
                        (n, render_mod.resoudre_remplissage(n, m))
                        for n, m in ((render_mod.NATIVE, rendu.native),
                                     (render_mod.FULL, rendu.full)))),
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

    `paquet` est la construction du paquet qui produit ce rapport. Il est
    CONSTATÉ, jamais reproché : lancer `retro` depuis son arbre source est le
    cas normal de l'hôte, et en faire un problème apprendrait au lecteur à
    ignorer la section « Problèmes ». `status` n'a d'ailleurs aucune référence
    à opposer — savoir quelle identité DEVRAIT être là est le travail de
    l'hôte qui a livré la roue, pas celui d'un rapport.

    `amorcages` est le témoin que le lanceur écrit sur la machine — profil →
    [(date, cible), …], une entrée par cible posée. `retro status` tourne sur l'hôte, qui n'atteint ni
    `C:\\Users` ni `%APPDATA%` de la console : c'est la seule trace dont il
    dispose pour dire qu'une configuration a bien été posée.
    """
    emulateurs, problemes_emulateurs = _etat_emulateurs(
        install_dirs, emulation_root, ignored_systems, emulator_exes)
    rendu = etat_rendu(profils) if profils else []
    manettes = etat_manettes(profils) if profils else []
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
                  *_problemes_pads(list(pads), manettes)],
        bios_root=bios_root,
        render_mode=render_mode,
        paquet=paquet,
        render=rendu,
        amorcages=etat_amorcage(profils, amorcages or {}) if profils else [],
        manettes=manettes,
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
            for note in e.notes:
                lignes.append(f"  {' ' * largeur}    {note}")
            continue
        crt = "natif avec CRT" if e.crt else "natif sans CRT"
        lignes.append(f"  {nom}  {crt}  |  auto : {_resume_auto(e.auto)}")
        if not e.crt:
            lignes.append(f"  {' ' * largeur}    ({e.crt_absent})")
        lignes += [f"  {' ' * largeur}    {l}"
                   for l in _lignes_remplissage(e.remplissage)]
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


def _lignes_remplissage(remplissage: tuple[tuple[str, str, str], ...]) -> list[str]:
    """Le troisième axe d'UN système, mode par mode.

    Le motif n'accompagne que ce que la légende n'explique pas : un émulateur
    qui n'expose aucun réglage, ou un remplissage que personne n'a mesuré.
    """
    if not remplissage:
        return []
    valeurs = ", ".join(f"{mode} {valeur}" for mode, valeur, _ in remplissage)
    lignes = [f"remplissage : {valeurs}"]
    # Dédoublonné : les deux modes d'un émulateur qui n'expose rien portent la
    # même phrase, et l'imprimer deux fois la fait lire zéro.
    vus: list[str] = []
    for _, valeur, motif in remplissage:
        if valeur not in render_mod.REMPLISSAGES and motif not in vus:
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
            lignes.append(f"  · {a.profile_id} : pas encore amorcé — sa "
                          "configuration sera posée au premier lancement "
                          "d'un de ses jeux")
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

    nb = len(report.problems)
    # 0 et 1 prennent le singulier en français : « Problème (1) », pas
    # « Problèmes (1) ». Même famille que le « 1 jeux » déjà corrigé.
    sections += _section(
        f"Problème{'s' if nb > 1 else ''} ({nb})",
        _lignes_problemes(report.problems),
        "aucun problème détecté — tout est en ordre",
    )

    return "\n".join(sections).rstrip("\n")
