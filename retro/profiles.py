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
    # Les noms de dossier USUELS de ce système, en plus de son identifiant et
    # de son nom. Le propriétaire range « Playstation\ », pas « psx\ », et
    # ce n'est pas à lui de renommer sa bibliothèque pour convenir à l'outil.
    # Déclaratif, dans le TOML : une liste d'exceptions dans le code
    # rouvrirait un module à chaque collection rencontrée.
    folders: tuple[str, ...] = ()


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
            folders=tuple(declares),
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
