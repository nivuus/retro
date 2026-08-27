"""Trois façons de rendre un jeu, et laquelle s'applique.

Le propriétaire choisit un mode pour toute la console :

- `native` — ce que la console d'origine sortait : résolution interne 1x,
  ratio d'époque, et le shader CRT là où l'émulateur en a un ;
- `full`   — le maximum que la machine sait faire, à la résolution de la
  session en cours ;
- `auto`   — ni l'un ni l'autre en propre : il CHOISIT entre les deux, système
  par système, en croisant le coût d'émulation déclaré dans le profil avec ce
  que la machine offre.

Ce module ne connaît aucun émulateur. Il dit QUEL mode s'applique et compose
la ligne d'arguments à partir de ce que le profil déclare ; ce que ces
arguments signifient reste dans le TOML, comme le reste.

La décision est toujours EXPLICABLE : chaque résolution rend son motif, et
`retro status` l'affiche. Un mode automatique qui déciderait en silence
donnerait un jeu qui rame sans que rien ne dise pourquoi — le propriétaire
croirait son matériel en cause.
"""
from __future__ import annotations

import dataclasses

NATIVE = "native"
AUTO = "auto"
FULL = "full"
MODES = (NATIVE, AUTO, FULL)
# Les modes qu'un profil DÉCLARE. `auto` n'en est pas un : il n'a pas
# d'arguments à lui, il choisit entre les deux autres.
MODES_DECLARES = (NATIVE, FULL)

# Ce que coûte l'émulation d'un système, tel que son profil le déclare.
LEGER, MOYEN, LOURD = "light", "medium", "heavy"
COUTS = (LEGER, MOYEN, LOURD)

# Ce qu'une machine sait faire.
MODESTE, MOYENNE, SOLIDE = "modeste", "moyenne", "solide"


class RenderError(RuntimeError):
    """Un mode demandé n'existe pas, ou une machine est indescriptible."""


@dataclasses.dataclass(frozen=True)
class RenderMode:
    """Ce qu'un système ajoute à sa ligne de commande pour un mode donné.

    `args` peut être VIDE : certains émulateurs n'exposent aucun réglage de
    rendu en ligne de commande, et il n'y a rien à inventer pour eux. Mais un
    `args` vide EXIGE alors une `note` qui dit pourquoi — sans quoi rien ne
    distinguerait « cet émulateur ne sait pas » d'un bloc oublié, et le mode
    choisi n'aurait tout simplement aucun effet, en silence.
    """
    args: str = ""
    note: str = ""
    # Le shader CRT du mode natif. « Ce que la console d'origine fournissait »
    # passait par un tube cathodique : sans lui, le natif est une image
    # propre que cette console n'a jamais produite. Tous les émulateurs n'en
    # ont pas — c'est alors `crt_absent` qui le dit, et le rapport le répète.
    crt: str = ""
    crt_absent: str = ""


@dataclasses.dataclass(frozen=True)
class Render:
    """Les deux modes qu'un système DÉCLARE. `auto` choisit entre eux."""
    native: RenderMode
    full: RenderMode
    # La hauteur que sortait la console d'origine, et jusqu'où multiplier la
    # résolution interne. Exigées dès que {scale} est employé, et seulement
    # alors : sans elles, {scale} ne serait pas calculable.
    native_height: int = 0
    max_scale: int = 0


@dataclasses.dataclass(frozen=True)
class Machine:
    """Ce que la machine offre, mesuré — jamais supposé.

    `largeur` et `hauteur` sont ceux de la SESSION en cours, pas ceux du
    bureau au moment de la synchronisation : un flux Apollo change de
    résolution selon le client qui se connecte, et une résolution figée à la
    synchro produirait une image étirée que rien ne signalerait.
    """
    gpu: str = ""
    vram_mo: int = 0
    coeurs: int = 0
    largeur: int = 0
    hauteur: int = 0

    @property
    def mesuree(self) -> bool:
        """Faux tant que rien n'a été mesuré.

        Une machine à zéro n'est pas une machine modeste : c'est une mesure
        qui n'a pas eu lieu. Les confondre ferait passer `auto` en `native`
        partout, ce qui ressemble à un choix prudent et n'en est pas un.
        """
        return self.vram_mo > 0 and self.coeurs > 0


# Les seuils qui classent une machine. Ils sont arbitraires — aucun chiffre ne
# dit ce qu'un GPU rend sur un jeu donné — donc ils sont ÉCRITS ICI, cités
# dans le rapport, et le propriétaire peut les contredire en choisissant un
# mode explicite. Ce qui est interdit, c'est qu'ils décident sans se montrer.
SEUILS = (
    (SOLIDE, 6144, 8),
    (MOYENNE, 2048, 4),
)


def classe_machine(machine: Machine) -> str:
    """La classe d'une machine mesurée, du plus exigeant au moins exigeant."""
    for nom, vram, coeurs in SEUILS:
        if machine.vram_mo >= vram and machine.coeurs >= coeurs:
            return nom
    return MODESTE


# Qui gagne, entre le coût d'un système et la classe d'une machine. Une case
# par croisement, écrite en clair : une formule serait plus courte et
# personne ne pourrait dire, en la lisant, ce que sa PS3 va faire.
_ARBITRAGE = {
    (SOLIDE, LEGER): FULL,
    (SOLIDE, MOYEN): FULL,
    (SOLIDE, LOURD): FULL,
    (MOYENNE, LEGER): FULL,
    (MOYENNE, MOYEN): FULL,
    (MOYENNE, LOURD): NATIVE,
    (MODESTE, LEGER): FULL,
    (MODESTE, MOYEN): NATIVE,
    (MODESTE, LOURD): NATIVE,
}


@dataclasses.dataclass(frozen=True)
class Decision:
    """Le mode retenu, et pourquoi. Le motif n'est pas un ornement : sans lui,
    `auto` est une boîte noire, et un jeu qui rame ressemble à du matériel
    insuffisant plutôt qu'à un arbitrage qu'on peut contredire."""
    mode: str
    motif: str


def resoudre(demande: str, cout: str, machine: Machine) -> Decision:
    """Le mode qui s'applique RÉELLEMENT à un système.

    `native` et `full` se rendent eux-mêmes : le propriétaire a choisi, il n'y
    a rien à arbitrer. `auto` croise le coût et la machine.

    Une machine non mesurée ne fait pas retomber `auto` sur un choix prudent :
    elle rend `native` ET LE DIT. Choisir en silence sur une mesure absente,
    c'est décider sur des zéros.
    """
    if demande not in MODES:
        raise RenderError(
            f"mode de rendu inconnu : « {demande} ». Les modes sont "
            f"{', '.join(MODES)}."
        )
    if demande != AUTO:
        return Decision(demande, "choisi explicitement")
    if cout not in COUTS:
        raise RenderError(
            f"coût d'émulation inconnu : « {cout} ». Les coûts sont "
            f"{', '.join(COUTS)}."
        )
    if not machine.mesuree:
        return Decision(
            NATIVE,
            "machine non mesurée — le mode automatique n'a rien sur quoi "
            "décider, donc il ne prétend pas décider",
        )
    classe = classe_machine(machine)
    return Decision(
        _ARBITRAGE[(classe, cout)],
        f"machine {classe} ({machine.vram_mo} Mo de VRAM, {machine.coeurs} "
        f"cœurs), système {cout}",
    )


def echelle(hauteur_session: int, hauteur_native: int, maximum: int) -> int:
    """Combien de fois la résolution d'origine tient dans celle de la session.

    Bornée à `maximum` parce qu'au-delà l'émulateur refuse, ou accepte et rame
    — et un jeu qui rame est le genre de panne qu'on ne diagnostique pas
    depuis un canapé. Jamais sous 1 : une session plus basse que la console
    d'origine ne peut pas demander une demi-résolution interne.
    """
    if hauteur_native <= 0 or maximum <= 0:
        raise RenderError(
            "hauteur native et échelle maximale doivent être positives : "
            f"reçu hauteur_native={hauteur_native}, maximum={maximum}"
        )
    return max(1, min(maximum, hauteur_session // hauteur_native))


def composer(rendu: Render, mode: str, machine: Machine) -> str:
    """Les arguments de rendu d'un système, variables substituées.

    Le shader CRT du mode natif est ajouté aux arguments : il fait partie de
    « ce que la console d'origine fournissait », qui passait par un tube
    cathodique. Un système dont l'émulateur n'en a pas rend simplement ses
    arguments — `crt_absent` dit pourquoi, et le rapport le répète.

    Rend une chaîne VIDE quand le mode ne pilote rien, ce qui est une réponse
    et non une panne : certains émulateurs n'exposent aucun réglage en ligne
    de commande, et leur profil le déclare par une `note`.
    """
    import re
    if mode not in MODES_DECLARES:
        raise RenderError(
            f"« {mode} » n'est pas un mode déclarable. Les modes qu'un profil "
            f"déclare sont {', '.join(MODES_DECLARES)} ; `auto` choisit entre "
            "eux et n'a pas d'arguments à lui."
        )
    m = rendu.native if mode == NATIVE else rendu.full
    gabarit = " ".join(x for x in (m.args, m.crt if mode == NATIVE else "") if x)
    if not gabarit:
        return ""

    besoins = set(re.findall(r"\{(\w+)\}", gabarit))
    # Substituer une résolution non mesurée écrirait « 0x0 » sur la ligne de
    # commande : l'émulateur refuserait de démarrer, ou pire, démarrerait dans
    # une taille absurde. Zéro n'est pas une mesure.
    if besoins & {"width", "height", "scale"} and not (machine.largeur
                                                       and machine.hauteur):
        raise RenderError(
            f"le mode « {mode} » demande la résolution de la session "
            f"({', '.join('{' + b + '}' for b in sorted(besoins))}), mais elle "
            f"n'a pas été mesurée (largeur={machine.largeur}, "
            f"hauteur={machine.hauteur}). Zéro n'est pas une résolution : "
            "substituer ces valeurs donnerait une commande que l'émulateur "
            "refuserait, ou une image dans une taille absurde."
        )
    valeurs = {"width": machine.largeur, "height": machine.hauteur}
    if "scale" in besoins:
        valeurs["scale"] = echelle(machine.hauteur, rendu.native_height,
                                   rendu.max_scale)
    for nom, valeur in valeurs.items():
        gabarit = gabarit.replace("{" + nom + "}", str(valeur))
    return gabarit
