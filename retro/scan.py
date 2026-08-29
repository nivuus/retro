"""Du disque du propriétaire à l'inventaire.

Le scan tourne sur la machine qui possède les ROMs, mais décrit une machine
Windows : les chemins de l'inventaire sont ceux que verra Steam, pas ceux du
système de fichiers qui scanne.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
from collections.abc import Sequence

from retro import install as install_mod
from retro import launcher as launcher_mod
from retro import profiles as profiles_mod
from retro.steam import entry

# Les conventions No-Intro et Redump : « Titre (Région) (Langues) [flags] ».
# Tout ce qui suit le titre est entre parenthèses ou crochets.
_PARENTHESES = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
# ... à une exception près : le marqueur de disque. Deux disques du même jeu
# donneraient sinon le même titre, donc le même identifiant Steam, et une
# seule entrée survivrait aux deux.
_DISQUE = re.compile(r"\((Disc|Disk|CD)\s*[^\)]*\)", re.IGNORECASE)
# Les mots qui trahissent un dossier de mise à jour ou de contenu additionnel.
# Une DEVINETTE, assumée comme telle : elle ne retire jamais rien de
# l'inventaire, elle ne fait qu'ajouter une ligne au rapport. Voir
# `suspected_update_dirs` pour l'arbitrage.
_MISE_A_JOUR = re.compile(r"\b(update|patch|dlc|maj)\b", re.IGNORECASE)


class ScanError(RuntimeError):
    """La racine des ROMs est inaccessible."""


@dataclasses.dataclass(frozen=True)
class IgnoredSystem:
    """Un système laissé de côté par le scan, faute d'émulateur installé.

    C'est la moitié « et signalé » de l'exigence : ignorer en silence
    remplacerait une bibliothèque morte par une bibliothèque incomplète, tout
    aussi inexplicable pour le propriétaire. Chaque champ sert au message :
    ce qui manque (`system_name`), quoi installer (`profile`), où on a
    cherché (`install_dir`, `emulator`), pourquoi (`reason`, vocabulaire de
    `install.emulator_state`), et ce que ça coûte (`roms`).
    """
    # Le chemin du dossier RELATIF à la racine des ROMs, en séparateurs
    # Windows (« Nintendo\\Gamecube »), et non son seul nom : c'est aussi la
    # clé par laquelle `scan` exclut ce système. Deux constructeurs peuvent
    # ranger un dossier de même nom — le nom seul en aurait exclu deux pour
    # un émulateur manquant, et les jeux de l'autre auraient disparu sans
    # qu'aucun message ne le dise.
    folder: str
    system_name: str
    profile: str
    install_dir: pathlib.Path
    emulator: pathlib.Path
    roms: int
    reason: str


def _tige(nom: str, dossier: bool) -> str:
    """Le nom d'où part un titre, extension retirée.

    Un DOSSIER n'a pas d'extension : le point de « Jeu v1.02 » fait partie de
    son nom, et le retirer comme on retire « .iso » renommerait le jeu dans
    Steam — en silence, puisque le titre resterait plausible.
    """
    return nom if dossier else pathlib.PurePosixPath(nom).stem


def base_title(filename: str, dossier: bool = False) -> str:
    """Le titre SANS son marqueur de disque.

    C'est la clé de regroupement : les trois disques d'un même jeu et le .m3u
    qui les rassemble ont tous le même titre de base.
    """
    return _PARENTHESES.sub("", _tige(filename, dossier)).strip()


def clean_title(filename: str, dossier: bool = False) -> str:
    """Le titre affiché dans Steam, marqueur de disque compris.

    Le marqueur est CONSERVÉ : deux disques du même jeu donneraient sinon le
    même titre, donc le même identifiant Steam, et une seule entrée survivrait
    aux deux.
    """
    tige = _tige(filename, dossier)
    m = _DISQUE.search(tige)
    if not m:
        return base_title(filename, dossier)
    sans_disque = tige[: m.start()] + tige[m.end():]
    return f"{_PARENTHESES.sub('', sans_disque).strip()} {m.group(0)}".strip()


def titre_de_fiche(nom: str) -> str:
    """Le titre affiché pour un nom reconnu dans une base de données.

    Même nettoyage qu'un nom de fichier, et pour les mêmes raisons : la région
    et les drapeaux entre parenthèses ne se lisent pas depuis un canapé, et
    SteamGridDB ne trouve aucune jaquette pour « Super Mario Kart (USA) ». Le
    marqueur de disque, lui, est CONSERVÉ — voir `clean_title`.
    """
    m = _DISQUE.search(nom)
    if not m:
        return _PARENTHESES.sub("", nom).strip()
    sans_disque = nom[: m.start()] + nom[m.end():]
    return f"{_PARENTHESES.sub('', sans_disque).strip()} {m.group(0)}".strip()


def discriminant(filename: str, dossier: bool = False) -> str:
    """Le premier fragment parenthésé d'un nom de fichier — en pratique la
    région. Sert à départager deux fichiers dont le titre nettoyé serait le
    même, et seulement dans ce cas."""
    m = _PARENTHESES.search(_tige(filename, dossier))
    return m.group(0).strip(" ()[]") if m else ""


@dataclasses.dataclass(frozen=True)
class _Candidat:
    """Une ROM retenue, et de quoi la distinguer d'une homonyme."""
    fichier: pathlib.Path
    chemin: str          # relatif à la racine, en séparateurs Windows
    pid: str
    systeme: object
    # Un jeu n'est pas toujours un fichier : sur PS Vita, une application
    # installée est un DOSSIER. Ce qui en découle tient en deux points — le
    # titre ne se coupe pas sur un point (`_tige`), et le chemin donné à
    # l'émulateur est celui du dossier.
    dossier: bool = False
    # LE TITRE QU'UNE BASE A RECONNU, vide s'il n'y en a pas. Il l'emporte sur
    # le nom de fichier : « mslug2 » est un nom de romset, pas un nom de jeu —
    # il ne dit rien au propriétaire et ne trouve aucune jaquette. Vide veut
    # dire « aucune base ne le reconnaît », jamais « pas cherché » : le scan
    # NOMME ceux qui gardent leur nom de fichier.
    titre_reconnu: str = ""


# Ce qui départage deux jeux de même titre, du plus lisible au plus sûr. Un
# qualificatif n'est posé que s'il départage RÉELLEMENT le groupe en
# collision : « Jeu (Super Nintendo) (USA) » enlaidirait le cas courant — deux
# régions d'un même jeu — au nom d'un cas rare que le système ne résout pas.
_QUALIFICATIFS = (
    # Le système d'abord : c'est ce qui distingue le Tetris de la Game Boy de
    # celui de la NES, et c'est ce que le propriétaire lit dans sa
    # bibliothèque.
    lambda c: c.systeme.name,
    # Puis la région, qui départage deux éditions d'un même jeu.
    lambda c: discriminant(c.fichier.name, c.dossier),
    # Puis le nom de fichier entier, extension comprise.
    lambda c: c.fichier.name,
    # Enfin le chemin complet. C'est le SEUL qualificatif qu'un système de
    # fichiers garantit unique : deux dossiers peuvent désigner le même
    # système — « psx\\ » et « PlayStation\\ » répondent tous deux au même
    # profil — et y porter le même nom de fichier.
    lambda c: f"{c.chemin}\\{c.fichier.name}",
)


def _desambiguiser(candidats: list[_Candidat]) -> list[str]:
    """Rend les titres, en ne qualifiant que ceux qui entrent en collision.

    Deux jeux de même titre rendent le même couple (exe, appname), donc le
    même identifiant Steam, donc UNE SEULE entrée : le second écrase le
    premier à l'écriture, et le jeu disparaît de la bibliothèque sans que rien
    ne le signale.

    La comparaison porte sur TOUTE la bibliothèque, jamais sur un dossier à la
    fois. Mesuré le 2026-08-27 : « Tetris » sur PlayStation et sur Super
    Nintendo, deux ROMs, un seul identifiant. Les huit systèmes de RetroArch
    partagent le même exe, donc deux dossiers suffisaient — et le lanceur
    commun, qui donne le MÊME exe à toute la bibliothèque, aurait étendu le
    défaut à n'importe quel homonyme.

    Les titres uniques ne sont jamais touchés : la bibliothèque reste propre
    dans le cas courant, qui est de loin le plus fréquent.
    """
    titres = [titre_de_fiche(c.titre_reconnu) if c.titre_reconnu
              else clean_title(c.fichier.name, c.dossier)
              for c in candidats]
    for extraire in _QUALIFICATIFS:
        groupes: dict[str, list[int]] = {}
        for i, t in enumerate(titres):
            groupes.setdefault(t, []).append(i)
        if all(len(ix) == 1 for ix in groupes.values()):
            break
        for indices in groupes.values():
            if len(indices) == 1:
                continue
            valeurs = [extraire(candidats[i]) for i in indices]
            # Un qualificatif que tout le groupe partage ne départage rien :
            # le poser allongerait le titre sans lever la collision, et la
            # passe suivante s'en chargerait par-dessus.
            if len(set(valeurs)) == 1:
                continue
            for i, v in zip(indices, valeurs):
                if v:
                    titres[i] = f"{titres[i]} ({v})"
    return titres


# Jusqu'où descendre sous la racine avant de renoncer. Une bibliothèque
# réelle s'organise « Constructeur\\Système », parfois sous un dossier
# chapeau de plus ; au-delà, ce qu'on parcourt n'est plus un rangement mais
# l'intérieur d'un jeu — des dossiers d'extras, de sauvegardes ou de disques
# qu'il ne faut pas confondre avec des systèmes. Une limite, plutôt qu'une
# descente libre, parce qu'un partage réseau profond se parcourt lentement et
# qu'un scan qui traîne sans fin ressemble à un scan qui a planté.
_PROFONDEUR_MAX = 3


def _systeme_par_dossier(profils):
    """Chaque nom de dossier qui désigne un système, normalisé, vers ce système.

    Un système répond à son identifiant, à son nom, et aux `folders` que son
    profil déclare : le propriétaire range « Playstation\\ », pas « psx\\ », et
    ce n'est pas à lui de renommer sa bibliothèque pour convenir à l'outil.

    Un même nom ne peut être servi que par un profil : le premier dans l'ordre
    alphabétique gagne, ce qui rend le résultat indépendant de l'ordre de
    chargement. `profiles._refuser_systemes_partages` interdit déjà le cas à
    l'intérieur d'une source ; ce `setdefault` couvre ce qui reste, la
    collision entre un profil livré et celui du propriétaire.
    """
    table = {}
    for pid in sorted(profils):
        for s in profils[pid].systems:
            for nom in profiles_mod.folder_claims(s):
                table.setdefault(nom, (pid, s))
    return table


def _verifier_racine(roms_root: pathlib.Path) -> None:
    if not roms_root.is_dir():
        raise ScanError(
            f"racine des ROMs introuvable : {roms_root}. Le partage est-il monté ?"
        )


def _explorer(base: pathlib.Path, table: dict, parents: tuple[str, ...],
              profondeur: int) -> tuple[list, list]:
    """Descend sous `base` et sépare ce qui est reconnu de ce qui ne l'est pas.

    Un dossier reconnu est rendu TEL QUEL et n'est pas ouvert : ce qu'il
    contient, ce sont des ROMs, pas d'autres systèmes. Un dossier inconnu est
    traversé — c'est un constructeur, « Nintendo », « Sony » — et n'est
    signalé que si RIEN sous lui n'a été reconnu. Sans cette dernière
    condition, une bibliothèque parfaitement rangée ferait tout de même la
    liste de ses dossiers de constructeur comme autant de problèmes.
    """
    couverts, orphelins = [], []
    try:
        enfants = sorted(p for p in base.iterdir() if p.is_dir())
    except OSError:
        # Un dossier illisible — permission, partage tombé — n'arrête pas le
        # scan du reste, mais ne se tait pas non plus : il ressort comme non
        # reconnu, ce qu'il est de fait, plutôt que de retirer des jeux de la
        # bibliothèque sans un mot.
        return couverts, orphelins

    for enfant in enfants:
        chemin = parents + (enfant.name,)
        trouve = table.get(profiles_mod.folder_key(enfant.name))
        if trouve:
            couverts.append((enfant, chemin, trouve[0], trouve[1]))
            continue
        # On ne TRAVERSE pas un lien : un lien qui remonte vers un ancêtre —
        # ou une jonction Windows, qui se comporte pareil — fait retrouver
        # les mêmes ROMs par un second chemin, et chacune reçoit alors deux
        # entrées Steam pour le même jeu. La profondeur maximale borne
        # l'explosion mais pas le doublon. Un lien RECONNU reste accepté
        # (bloc au-dessus) : ranger un système sur un autre volume et le
        # relier ici est un usage légitime, et il ne crée aucun cycle
        # puisqu'un dossier reconnu n'est jamais ouvert plus loin.
        if profondeur < _PROFONDEUR_MAX and not enfant.is_symlink():
            sous_couverts, sous_orphelins = _explorer(
                enfant, table, chemin, profondeur + 1)
            if sous_couverts or sous_orphelins:
                # Ce qui remonte, ce sont les FEUILLES, jamais le dossier
                # traversé. « Atari » ne dit rien au propriétaire — il ne
                # renommera pas son dossier de constructeur ; « Atari\\5200 »
                # nomme le dossier exact à déclarer ou à renommer.
                couverts.extend(sous_couverts)
                orphelins.extend(sous_orphelins)
                continue
        orphelins.append("\\".join(chemin))
    return couverts, orphelins


def _parcourir(roms_root: pathlib.Path, profils: dict) -> tuple[list, list]:
    """Le parcours du disque, couverts et orphelins.

    Partagé par `scan`, `ignored_systems` et `unmatched_folders` : tous
    doivent parcourir le MÊME disque de la même façon, sinon le rapport
    annoncerait des systèmes que le scan n'a pas ignorés, ou tairait ceux
    qu'il a ignorés.
    """
    return _explorer(roms_root, _systeme_par_dossier(profils), (), 1)


def _dossiers_couverts(roms_root: pathlib.Path, profils: dict):
    """Les dossiers de ROMs qu'un profil couvre, dans un ordre stable.

    Rend, pour chacun : le dossier, son chemin RELATIF vu de Windows, le
    profil qui le sert et le système. Le chemin relatif — et non le seul nom —
    parce que c'est lui qui construit l'adresse de la ROM que Steam lancera :
    un jeu rangé sous « Nintendo\\Gamecube » adressé par « Gamecube » seul
    donnerait une entrée d'apparence normale qui ne démarrerait jamais.
    """
    couverts, _ = _parcourir(roms_root, profils)
    for dossier, chemin, pid, systeme in couverts:
        yield dossier, "\\".join(chemin), pid, systeme


def unmatched_folders(roms_root: pathlib.Path,
                      profils: dict) -> tuple[list[str], list[str]]:
    """Les dossiers qu'aucun profil ne reconnaît, et les noms attendus.

    « 0 ROM répertoriée » est vrai et inutile : le propriétaire ne peut pas
    savoir si sa bibliothèque est vide, mal montée, ou simplement rangée
    autrement que ce que l'outil cherche. Mesuré sur une bibliothèque réelle
    le 2026-08-26 : dix-sept systèmes attendus, quatre dossiers de
    constructeur sur le disque, zéro rencontre, et pas un mot pour le dire.

    Rend ce qui a été VU d'un côté, ce qui était ATTENDU de l'autre : c'est
    de la comparaison des deux que le propriétaire tire quoi faire —
    renommer un dossier, ou déclarer son nom dans `folders`.
    """
    _verifier_racine(roms_root)
    _, orphelins = _parcourir(roms_root, profils)
    attendus = sorted({s.name for p in profils.values() for s in p.systems})
    return orphelins, attendus


def _est_application(candidat: pathlib.Path, marqueur: str) -> bool:
    """Ce dossier est-il une application installée, et non un dossier quelconque ?

    La réponse est le fichier que le profil DÉCLARE : une application PS Vita
    porte son eboot.bin à sa racine, un dossier de sauvegardes n'en a pas.
    Sans cette condition, « savedata » deviendrait une entrée de la
    bibliothèque, qui ne lancerait rien.

    La comparaison ignore la casse, comme `folder_key` : ce scan tourne sous
    Linux mais décrit une machine Windows, où « EBOOT.BIN » et « eboot.bin »
    sont le même fichier. Sans cela, un dumper qui majuscule ses noms perdrait
    toute sa bibliothèque.
    """
    cle = marqueur.strip().casefold()
    try:
        return any(e.name.casefold() == cle and e.is_file()
                   for e in candidat.iterdir())
    except OSError:
        # Un dossier illisible ne peut pas être ATTESTÉ comme un jeu ; le
        # déclarer tel produirait une entrée Steam dont rien ne garantit
        # qu'elle lance quoi que ce soit. Comme dans `_explorer`, l'ennui d'un
        # dossier n'arrête pas le scan des autres.
        return False


def _retenus(dossier: pathlib.Path, systeme) -> list[tuple[pathlib.Path, bool]]:
    """Ce que ce dossier de système offre à Steam, et sous quelle forme.

    Rend des couples (chemin, est-un-dossier). Deux formes cohabitent :

    - les FICHIERS, à l'extension déclarée. Un .m3u regroupe les disques d'un
      même jeu : lancer un disque isolé alors qu'un .m3u existe est une erreur,
      le jeu réclamerait le disque suivant sans pouvoir l'obtenir. Le titre de
      BASE est la clé de regroupement — il ignore le marqueur de disque, que le
      titre affiché conserve ;
    - les DOSSIERS d'application, quand le profil déclare à quoi ils se
      reconnaissent. Une bibliothèque PS Vita en est faite. Le dossier est
      rendu TEL QUEL et n'est jamais ouvert : ce qu'il contient est le jeu, pas
      une liste de jeux — l'inventorier ferait une entrée Steam par fichier du
      jeu, ce qui était exactement le risque de cette dette.

    Sans `app_dir_marker` — les neuf profils livrés — rien ne change : aucun
    dossier n'est jamais retenu.
    """
    fichiers = sorted(f for f in dossier.iterdir()
                      if f.is_file() and f.suffix.lower() in
                      tuple(e.lower() for e in systeme.extensions))
    titres_m3u = {base_title(f.name) for f in fichiers
                  if f.suffix.lower() == ".m3u"}
    retenus = [(f, False) for f in fichiers
               if f.suffix.lower() == ".m3u"
               or base_title(f.name) not in titres_m3u]
    if systeme.app_dir_marker:
        retenus += [(d, True) for d in sorted(dossier.iterdir())
                    if d.is_dir()
                    and _est_application(d, systeme.app_dir_marker)]
    return retenus


def suspected_update_dirs(roms_root: pathlib.Path,
                          profils: dict) -> list[str]:
    """Les dossiers d'application qui ressemblent à une MISE À JOUR.

    `app_dir_marker` retient tout sous-dossier portant le fichier déclaré. Une
    mise à jour extraite en porte un aussi : posée à côté de sa base, elle
    donne une SECONDE entrée Steam pour le même jeu, d'apparence normale, qui
    lance le correctif seul — soit rien de jouable. Personne ne le
    signalerait : le scan aurait fait exactement son travail.

    SIGNALÉ, et non écarté. C'est l'arbitrage, et voici sa raison : le scan ne
    sait pas distinguer une base d'une mise à jour. Il faudrait pour cela
    OUVRIR le dossier — lire son `param.sfo` — et un dossier d'application
    n'est jamais ouvert, par construction (voir `_retenus`) ; le nom, lui, ne
    prouve rien, c'est le propriétaire qui l'a choisi. Les deux erreurs
    possibles n'ont donc pas le même prix : écarter à tort coûte un JEU, retiré
    de la bibliothèque sans un mot — exactement la panne que tout ce module
    refuse ; signaler à tort coûte une ligne de rapport, que le propriétaire
    lit et écarte. L'asymétrie tranche.

    La reconnaissance porte sur des MOTS du nom de dossier, jamais sur des
    sous-chaînes : « Dispatch » contient « patch », et accuser un vrai jeu
    apprendrait au lecteur à ignorer la section « Problèmes ».

    Rend des chemins RELATIFS à la racine, en séparateurs Windows — c'est ce
    que le propriétaire doit renommer ou sortir de l'arborescence scannée, et
    le nom seul serait ambigu entre deux systèmes.

    Sans `app_dir_marker` — les profils livrés — la liste est toujours vide :
    aucun dossier n'est jamais retenu, donc aucun ne peut doubler un jeu.
    """
    _verifier_racine(roms_root)
    suspects = []
    for dossier, chemin, _pid, systeme in _dossiers_couverts(
            roms_root, profils):
        if not systeme.app_dir_marker:
            continue
        for retenu, est_dossier in _retenus(dossier, systeme):
            if est_dossier and _MISE_A_JOUR.search(retenu.name):
                suspects.append(f"{chemin}\\{retenu.name}")
    return sorted(suspects)


def ignored_systems(roms_root: pathlib.Path, profils: dict,
                    install_dirs: dict[str, str],
                    emulation_root_local: pathlib.Path | str,
                    ) -> list[IgnoredSystem]:
    """Les systèmes que `scan` laisse de côté parce que leur émulateur manque.

    « Un système présent dans un profil mais absent de D:\\Emulation est ignoré
    par le scan, ET SIGNALÉ » : voici de quoi le signaler.

    Un dossier de ROMs vide ne compte pas. Un émulateur non installé dont le
    propriétaire n'a aucun jeu n'est pas son problème, et le lui annoncer
    noierait les manques qui, eux, lui coûtent des jeux.
    """
    _verifier_racine(roms_root)
    ignores = []
    for dossier, chemin, pid, systeme in _dossiers_couverts(roms_root, profils):
        # La MÊME notion d'« installé » que `retro status` et `retro install`,
        # lue au même endroit : l'une inventoriait ce que l'autre déclarait
        # absent, sur le même disque, et le propriétaire n'avait aucun moyen
        # de trancher.
        etat = install_mod.emulator_state(
            emulation_root_local, install_dirs[pid], profils[pid].exe)
        if etat == install_mod.OK:
            continue
        jeux = len(_retenus(dossier, systeme))
        if jeux:
            ignores.append(IgnoredSystem(
                folder=chemin, system_name=systeme.name, profile=pid,
                install_dir=install_mod.install_path(
                    emulation_root_local, install_dirs[pid]),
                emulator=install_mod.emulator_exe(
                    emulation_root_local, install_dirs[pid], profils[pid].exe),
                roms=jeux, reason=etat,
            ))
    return ignores


def scan(roms_root: pathlib.Path, profils: dict, emulation_root: str,
         install_dirs: dict[str, str],
         roms_root_windows: str = "G:\\ROMs",
         emulation_root_local: pathlib.Path | str | None = None,
         ignored: Sequence[IgnoredSystem] | None = None,
         resolveur=None,
         ) -> list[entry.RomEntry]:
    """L'inventaire des ROMs, tel que Steam le verra.

    `emulation_root_local` est le chemin par lequel CETTE machine atteint les
    émulateurs, quand `emulation_root` est celui par lequel la console les
    verra — la même paire que `--roms` et `--roms-windows`. Donné, il fait
    vérifier que l'exécutable de chaque émulateur existe VRAIMENT, et ignorer
    les systèmes dont il manque : sans cela, une installation ratée peuple la
    bibliothèque du propriétaire d'entrées qui ne démarrent pas, et la garde
    de `sync` ne peut rien y voir puisque le chemin fabriqué reste, lui, bien
    sous la racine d'émulation.

    Facultatif, parce qu'un appelant peut préparer l'inventaire d'une machine
    qu'il n'atteint pas. Absent, rien n'est vérifié ni ignoré : le
    comportement d'avant, à l'identique.

    `ignored` est pour l'appelant qui a DÉJÀ appelé `ignored_systems` — le
    CLI, qui doit annoncer ce qu'il ignore. Son ensemble fait alors foi et
    rien n'est recalculé : deux calculs, c'est deux vérités possibles sur un
    disque qui bouge, et un message qui contredit l'inventaire qu'il
    accompagne. Un ensemble vide est une réponse, pas une absence de réponse.
    """
    _verifier_racine(roms_root)
    # Chaque raccourci pointera sur le lanceur commun. Absent, c'est TOUTE la
    # bibliothèque qui ne démarre plus, et l'erreur que Steam affiche ne nomme
    # aucun jeu — la panne la moins diagnosticable que cette console puisse
    # produire. La même exigence que pour un émulateur, et pour la même
    # raison : un inventaire qui pointe sur un exécutable absent est un
    # inventaire qui a l'air normal.
    if emulation_root_local is not None \
            and not launcher_mod.est_installe(emulation_root_local):
        raise ScanError(
            f"le lanceur commun est introuvable : "
            f"{launcher_mod.local_dir(emulation_root_local) / launcher_mod.EXE}. "
            "C'est lui que Steam appelle pour chaque jeu — sans lui, aucune "
            "entrée de la bibliothèque ne démarrerait, et Steam ne dirait pas "
            "pourquoi. Le déposer et le compiler : « retro launcher »."
        )
    if ignored is None and emulation_root_local is not None:
        ignored = ignored_systems(roms_root, profils, install_dirs,
                                  emulation_root_local)
    ignores = {i.folder for i in ignored or ()}

    # Toute la bibliothèque est collectée AVANT que le moindre titre ne soit
    # arrêté : deux jeux homonymes rangés sous deux systèmes différents ne se
    # rencontraient jamais, et l'un des deux disparaissait de Steam.
    candidats = [
        _Candidat(fichier=f, chemin=chemin, pid=pid, systeme=systeme,
                  dossier=est_dossier)
        for dossier, chemin, pid, systeme in _dossiers_couverts(roms_root, profils)
        # émulateur absent : ces jeux ne se lanceraient pas
        if chemin not in ignores
        for f, est_dossier in _retenus(dossier, systeme)
    ]

    # LE VRAI TITRE, quand une base le reconnaît. Fait ICI et non plus haut :
    # les candidats sont déjà tous connus, et la désambiguïsation qui suit doit
    # comparer les titres FINAUX — deux jeux dont seuls les noms de fichiers
    # diffèrent peuvent porter le même titre reconnu, et c'est exactement la
    # collision que `_desambiguiser` existe pour attraper.
    if resolveur is not None:
        reconnus = []
        for c in candidats:
            t = resolveur.resoudre(c.fichier, c.systeme.id)
            if t is None:
                # NOMMÉ, jamais compté en silence : « 2 jeux gardent leur nom
                # de fichier » laisse chercher lesquels.
                resolveur.non_reconnus.append(f"{c.systeme.name} : {c.fichier.name}")
            reconnus.append(dataclasses.replace(
                c, titre_reconnu=(t.nom if t else "")))
        candidats = reconnus

    # Steam n'appelle PAS l'émulateur : il appelle le lanceur commun, qui
    # mesure la session et compose la commande au moment du clic. Le raccourci
    # ne porte donc plus que le système et la ROM — et changer de mode de
    # rendu ne touche plus à une seule option de lancement, donc à aucun
    # identifiant, donc à aucune vignette.
    lanceur = launcher_mod.launcher_exe(emulation_root)
    return [
        entry.RomEntry(
            title=titre,
            rom_path=f"{roms_root_windows}\\{c.chemin}\\{c.fichier.name}",
            system_name=c.systeme.name,
            emulator_exe=lanceur,
            launch_template=(f"{launcher_mod.system_key(c.pid, c.systeme.id)} "
                             '"{rom}"'),
            start_dir=f"{emulation_root}\\{install_dirs[c.pid]}",
            extra_tags=(),
        )
        for c, titre in zip(candidats, _desambiguiser(candidats))
    ]
