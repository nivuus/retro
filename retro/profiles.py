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


def load_profiles(directory: pathlib.Path) -> dict[str, Profile]:
    """Tous les profils d'un dossier, indexés par identifiant.

    Deux profils de même 'id' sont REFUSÉS. L'affectation seule laissait le
    dernier chargé écraser l'autre, qui disparaissait entièrement : un profil
    copié sans changer son 'id' a remplacé les neuf systèmes de RetroArch par
    deux, `retro scan` a rendu 0 en annonçant un inventaire plus court, puis la
    synchronisation a supprimé les entrées devenues orphelines. Ajouter des
    profils par copie est le chemin nominal, donc l'oubli l'est aussi.

    `load_profile` refuse déjà deux systèmes de même 'id' à l'intérieur d'un
    profil ; c'est la même garde, entre profils.
    """
    profils = {}
    origines: dict[str, pathlib.Path] = {}
    for f in sorted(directory.glob("*.toml")):
        p = load_profile(f)
        if p.id in profils:
            raise ProfileError(
                f"le profil '{p.id}' est déclaré deux fois : {origines[p.id].name} "
                f"et {f.name}. Le second effacerait le premier en silence, avec "
                "tous ses systèmes — les ROMs correspondantes disparaîtraient de "
                "Steam sans qu'aucun message ne le dise. Donner un 'id' distinct "
                "à chaque profil."
            )
        profils[p.id] = p
        origines[p.id] = f
    if not profils:
        raise ProfileError(
            f"aucun profil dans {directory} : aucun jeu ne pourrait être lancé"
        )
    return profils
