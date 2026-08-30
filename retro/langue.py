"""Quelle langue s'applique, et pourquoi.

Ce module ne connaît AUCUN émulateur. Il dit quelle langue la console veut et
laquelle un émulateur donné peut poser ; ce que cette langue signifie dans un
fichier de réglages reste dans le TOML du profil, comme le reste.

LA LANGUE CANONIQUE EST LE NOM QUE STEAM EMPLOIE — « french », « koreana »,
« brazilian » — et non un code ISO. Steam étant la source par défaut, tout
autre choix imposerait une table de correspondance de plus, donc un endroit de
plus où une langue peut se perdre : une entrée manquante y rendrait « langue
inconnue » sur une langue que Steam sait très bien nommer, et le symptôme
serait un émulateur resté en anglais sans qu'aucune ligne ne dise pourquoi.

Il reste UNE traduction, irréductible : du nom Steam vers la valeur que
l'émulateur attend. Elle vit dans le profil, et nulle part ailleurs.

DEUX RÉSOLUTIONS, et elles ne se confondent pas :

`resoudre`  dit ce que la CONSOLE veut — le fichier `langue.txt`, ou Steam.
`appliquer` dit ce qu'UN ÉMULATEUR pose — la langue voulue si son profil la
            déclare, son repli sinon, rien du tout s'il n'a pas de table.

Les séparer est ce qui permet à `retro status` d'écrire « Steam dit dutch » ET
« PPSSPP ne le déclare pas, repli sur english » : une seule fonction rendrait
l'un des deux faits, et le rapport ne saurait pas dire lequel manque.

LE MOTIF N'EST PAS UN ORNEMENT. Comme pour le rendu, chaque résolution rend sa
raison, parce que le rapport doit pouvoir l'écrire. Une langue choisie en
silence donnerait un jeu en anglais que le propriétaire croirait non traduit.
"""
from __future__ import annotations

import dataclasses

AUTO = "auto"

# Les noms de langue de Steam, RELEVÉS et non devinés (voir le relevé daté
# dans docs/dettes.md). Ce ne sont pas des codes ISO, et la liste n'est pas
# déductible : « koreana » n'est pas « korean », « brazilian » n'est pas
# « portuguese_br », et « latam » ne ressemble à rien d'autre.
LANGUES = (
    "arabic", "bulgarian", "schinese", "tchinese", "czech", "danish",
    "dutch", "english", "finnish", "french", "german", "greek",
    "hungarian", "indonesian", "italian", "japanese", "koreana", "malay",
    "norwegian", "polish", "portuguese", "brazilian", "romanian",
    "russian", "spanish", "latam", "swedish", "thai", "turkish",
    "ukrainian", "vietnamese",
)

# Ce que la commande accepte. `auto` n'est PAS une langue : il n'a pas de
# fragment à lui, il désigne celle de Steam.
VALEURS = (AUTO, *LANGUES)


class LangueError(RuntimeError):
    """Une langue demandée n'existe pas chez Steam."""


@dataclasses.dataclass(frozen=True)
class Decision:
    """La langue retenue, et pourquoi. `langue` vide veut dire « rien à
    poser », et le motif dit toujours laquelle des deux raisons c'est."""
    langue: str
    motif: str


def resoudre(demandee: str, steam: str) -> Decision:
    """La langue que la CONSOLE veut, et pourquoi.

    Un `steam` hors liste vaut un `steam` vide : une valeur qu'aucun profil ne
    peut déclarer ferait chercher un fragment qui n'existe pas. Mieux vaut le
    repli, qui est déclaré, que l'échec au lancement d'un jeu.
    """
    if demandee not in VALEURS:
        raise LangueError(
            f"langue inconnue : « {demandee} ». Les langues sont celles de "
            f"Steam, par leur nom : {', '.join(LANGUES)} — ou « {AUTO} », qui "
            "suit celle de Steam."
        )
    if demandee != AUTO:
        return Decision(demandee, "posée à la main")
    if steam in LANGUES:
        return Decision(steam, f"« {AUTO} » : Steam dit « {steam} »")
    return Decision(
        "",
        f"« {AUTO} » : Steam n'a rien dit — jamais lancé, ou sa langue n'a "
        "pas pu être lue",
    )


def appliquer(voulue: str, declarees: tuple[str, ...], repli: str) -> Decision:
    """Ce que CET émulateur pose, et pourquoi.

    Sans table déclarée, il ne pose RIEN, et c'est un état à part entière :
    « cet émulateur ne suit pas la langue » n'est pas « il la suit mal ». Les
    confondre ferait chercher une mauvaise valeur là où il n'y en a aucune.
    """
    if not declarees:
        return Decision("", "aucune table de langues déclarée")
    if voulue and voulue in declarees:
        return Decision(voulue, "")
    if voulue:
        return Decision(
            repli, f"« {voulue} » n'est pas déclaré ici, repli sur « {repli} »")
    return Decision(repli, f"repli sur « {repli} »")
