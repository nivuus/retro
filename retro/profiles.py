"""Comment on parle à un émulateur.

Un profil décrit les systèmes qu'un émulateur couvre, les extensions de ROM
qu'il accepte, la ligne de commande qui lance un jeu, les BIOS qu'il exige et
la façon d'en sortir à la manette.

Tout ce qui est propre à un émulateur vit ici, dans son TOML, jamais dans le
code : c'est ce qui permet d'en ajouter un sans rouvrir un module.
"""
from __future__ import annotations

import dataclasses
import pathlib
import tomllib

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


@dataclasses.dataclass(frozen=True)
class Profile:
    id: str
    exe: str
    systems: tuple[System, ...]
    exit_native: str
    exit_fallback: str
    steam_input: str


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

        systemes.append(System(
            id=sid, name=brut["name"], extensions=exts, launch=brut["launch"],
            bios=tuple(brut.get("bios", ())),
        ))

    if not systemes:
        raise ProfileError(f"{path} : aucun système déclaré")

    sortie = data.get("exit", {})
    entree = data.get("input", {})
    return Profile(
        id=data["id"], exe=data["exe"], systems=tuple(systemes),
        exit_native=sortie.get("native", ""),
        exit_fallback=sortie.get("fallback", "alt+f4"),
        steam_input=entree.get("steam_input", "required"),
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
    """Dans UNE source, un système n'est servi que par un profil.

    Deux profils du même dossier qui revendiquent 'psx' se disputent le même
    dossier de ROMs. Rien dans le résultat ne le dirait : `scan` retient le
    premier profil par ordre alphabétique, donc renommer un fichier suffirait
    à changer l'émulateur qui lance les jeux — et le TOML fautif, lui, reste
    là. C'est le défaut que `load_profile` refuse déjà À L'INTÉRIEUR d'un
    profil ; entre profils d'une même source, il n'était vérifié que sur les
    données livrées, par un test, et jamais sur celles du propriétaire.

    Entre les DEUX sources, la règle est autre : voir `load_profiles`.
    """
    servi: dict[str, tuple[str, pathlib.Path]] = {}
    for pid in sorted(source):
        profil, fichier = source[pid]
        for s in profil.systems:
            if s.id in servi:
                autre_pid, autre_fichier = servi[s.id]
                raise ProfileError(
                    f"le système '{s.id}' est revendiqué par deux profils du "
                    f"même dossier : '{autre_pid}' ({autre_fichier.name}) et "
                    f"'{pid}' ({fichier.name}). Un seul dossier de ROMs porte "
                    "ce nom : les deux profils se le disputeraient, et le "
                    "scan trancherait par ordre alphabétique — renommer un "
                    "fichier suffirait alors à changer l'émulateur qui lance "
                    "ces jeux, sans qu'aucun message ne le dise. Retirer ce "
                    "système de l'un des deux profils, ou — pour remplacer un "
                    "émulateur livré — déclarer le vôtre dans le dossier de "
                    "profils du propriétaire, qui l'emporte."
                )
            servi[s.id] = (pid, fichier)


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

    revendiques = {s.id for profil, _ in miens.values() for s in profil.systems}
    fusionnes: dict[str, Profile] = {}
    for pid, (profil, _) in livres.items():
        restants = tuple(s for s in profil.systems if s.id not in revendiques)
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
