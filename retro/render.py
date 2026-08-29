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

TROIS AXES, et ils ne se remplacent pas :

1. la RÉSOLUTION INTERNE — combien de pixels l'émulateur calcule ; c'est ce
   que le mode choisit (1x en natif, {scale} en full) ;
2. le RATIO D'ÉPOQUE — la forme de l'image. Un 4:3 correctement rendu sur un
   16:9 laisse des bandes noires sur les côtés : c'est VOULU, et ce n'est pas
   de la déformation ;
3. le REMPLISSAGE — comment l'image produite est posée sur l'écran. C'est
   l'axe de « occuper le plus possible de l'écran SANS étirer l'image », et
   c'est le seul des trois qui réponde à cette phrase-là. Voir plus bas.

Les confondre est l'erreur que la dette D2 décrit : on croit régler le
cadrage en changeant le ratio, et on obtient une image déformée qu'aucun
message ne signale.
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

# Ce qu'une machine sait faire, du moins au plus capable.
MODESTE, MOYENNE, SOLIDE = "modeste", "moyenne", "solide"
CLASSES = (MODESTE, MOYENNE, SOLIDE)


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
    # Le contenu d'un fichier de configuration à écrire pour ce mode, quand
    # l'émulateur n'a pas d'option pour surcharger un réglage. RetroArch est
    # dans ce cas : il n'accepte qu'un « --appendconfig=FICHIER », et sans ce
    # fichier son shader CRT resterait éteint quoi qu'on lui passe. Le fichier
    # est écrit par la synchronisation, et {render_config} porte son chemin.
    config: str = ""
    # Le TROISIÈME axe, celui du remplissage : `fill` nomme ce que les `args`
    # et le `config` de ce mode produisent RÉELLEMENT — `entier` ou `ajuste` —
    # et `fill_absent` dit que cet émulateur n'expose aucun réglage de cet
    # axe-là. Les deux à la fois ne veulent rien dire ; ni l'un ni l'autre dit
    # « personne n'a encore mesuré », ce que `retro status` nomme.
    #
    # `fill` ne porte pas les arguments : ils sont déjà dans `args`/`config`,
    # et les dédoubler ferait deux endroits où le même réglage se décide. Il
    # porte l'ASSERTION du profil sur leur effet, que `profiles` confronte à
    # la politique ci-dessous — sans quoi un profil pourrait remplir « au plus
    # grand » en mode natif, et la contradiction ne se verrait que sur
    # l'écran, sur une image floue qu'on croirait normale.
    fill: str = ""
    fill_absent: str = ""


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


def arbitrer(classe: str, cout: str) -> str:
    """Le mode que `auto` retient pour ce couple, sans passer par une machine.

    Le plan du lanceur en a besoin pour CHAQUE classe : il y écrit l'arbitrage
    déjà résolu, de sorte que le lanceur classe la machine qu'il mesure et
    lise la réponse, sans jamais rejouer la décision — donc sans pouvoir en
    prendre une autre.
    """
    if classe not in CLASSES:
        raise RenderError(
            f"classe de machine inconnue : « {classe} ». Les classes sont "
            f"{', '.join(CLASSES)}."
        )
    if cout not in COUTS:
        raise RenderError(
            f"coût d'émulation inconnu : « {cout} ». Les coûts sont "
            f"{', '.join(COUTS)}."
        )
    return _ARBITRAGE[(classe, cout)]


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
        arbitrer(classe, cout),
        f"machine {classe} ({machine.vram_mo} Mo de VRAM, {machine.coeurs} "
        f"cœurs), système {cout}",
    )


# --- le troisième axe : le REMPLISSAGE -----------------------------------
#
# Les deux SEULES façons d'agrandir une image sans la déformer, et c'est
# pourquoi cet axe n'a que deux valeurs. L'étirement n'est pas une troisième
# valeur qu'on n'aurait pas retenue : il n'est pas sur cet axe du tout, et
# aucune politique d'ici ne peut le produire.
ENTIER = "entier"   # multiple ENTIER seulement : chaque pixel d'origine reste
                    # un carré de pixels identiques, le reste est de la bande
                    # noire. Occupe moins, ne rééchantillonne rien.
AJUSTE = "ajuste"   # le plus grand agrandissement qui TIENNE, ratio conservé.
                    # Occupe le plus possible, au prix d'un facteur non entier.
REMPLISSAGES = (ENTIER, AJUSTE)
# Le même tuple, sous le nom de ce qu'il garantit. Un jour, quelqu'un
# cherchera « où est-ce qu'on interdit l'étirement ? » : c'est ici.
SANS_DEFORMATION = REMPLISSAGES

# Deux états qui ne sont PAS des valeurs de l'axe, et qui ne se confondent ni
# entre eux ni avec elles :
NON_REGLABLE = "non-reglable"  # mesuré : cet émulateur n'expose rien
NON_MESURE = "non-mesure"      # personne n'a encore regardé

# LA POLITIQUE. Une case par mode, écrite en clair, comme _ARBITRAGE : une
# règle implicite serait plus courte et personne ne pourrait dire, en la
# lisant, ce que sa Super Nintendo va faire sur la télévision.
_REMPLISSAGE_PAR_MODE = {
    NATIVE: ENTIER,
    FULL: AJUSTE,
}
_MOTIF_PAR_MODE = {
    NATIVE: "le mode natif rend la trame de la console à 1x ; seul un "
            "multiple entier l'agrandit sans la rééchantillonner, et c'est "
            "cette trame que le mode natif existe pour préserver",
    FULL: "le mode full a déjà monté la résolution interne à la session : il "
          "n'y a plus de trame à préserver, et l'écran se remplit au plus "
          "grand agrandissement qui conserve le ratio",
}

# ARBITRAGE EN ATTENTE — DuckStation, le cas dur de la dette D2.
#
# ÉTABLI, et cette fois SUR LE BINAIRE ÉPINGLÉ, pas sur une note du dépôt :
# la révision v0.1-11609 n'accepte aucun réglage de rendu en ligne de
# commande. Les chaînes de duckstation-qt-x64-ReleaseLTCG.exe ont été lues sur
# la console le 2026-08-29 (invité en provision_version=B1). On y trouve
# « Usage: %s [parameters] [--] [boot filename] », les quinze options de son
# bloc d'aide — -help, -version, -nogui, -statefile, -bios, -fullscreen,
# -earlyconsole, -slowboot, -fastboot, -nofullscreen, -state, -resume, -exe,
# -bigpicture, -batch — plus -setupwizard, -updatecleanup et « -- ». Aucune
# n'est un réglage de rendu. C'est exactement ce que disait duckstation.toml,
# désormais vérifié plutôt que recopié.
#
# ÉTABLI AUSSI, et c'est ce qui rend la question réelle plutôt que théorique :
# DuckStation SAIT remplir en entier. Le même binaire porte le type
# DisplayScalingMode et les valeurs « NearestInteger » et « BilinearInteger »,
# étiquetées « Nearest-Neighbor (Integer) » et « Bilinear (Integer) » dans son
# interface. Il y a donc quelque chose à régler, et c'est le seul émulateur
# livré dans ce cas.
#
# PAS ÉTABLI : le NOM DE LA CLÉ dans son settings.ini. Le binaire porte le nom
# du widget (« displayScaling ») mais pas le couple section/clé sous une forme
# lisible. Or une clé qui ne correspond à rien y est ignorée EN SILENCE —
# mesuré le 2026-08-28 sur cet émulateur, une clé inventée survit à un
# aller-retour sans rien faire. Aucune valeur n'entre donc ici avant d'avoir
# été relevée dans un settings.ini que DuckStation a lui-même écrit.
#
# Et ce fichier-là est difficile à obtenir : relevé le 2026-08-29 par un autre
# agent, DuckStation lancé « -batch -nogui » — le seul mode que la console
# emploie — NE RÉÉCRIT JAMAIS son settings.ini. Deux conséquences opposées,
# qui pèsent toutes deux sur la réponse :
#   - le relevé exige de l'ouvrir une fois HORS du chemin de la console ;
#   - mais ce que « retro » y écrirait serait durable : l'émulateur ne le
#     réécrira pas par-dessus au premier jeu.
#
# Reste ce qui n'est pas une question technique. Le remplissage se poserait
# dans %USERPROFILE%\Documents\DuckStation\settings.ini, donc par le mécanisme
# d'amorçage — lequel ne pose son fichier QUE S'IL EST ABSENT
# (launcher.SI_ABSENT). Sur toute console déjà jouée, le poser là n'aurait
# aucun effet ; l'y forcer reviendrait à réécrire un fichier que le
# propriétaire a peut-être réglé lui-même, ce que cet outil ne fait pas
# (README, « Ça ne retouche jamais la configuration d'un émulateur »). La
# question appartient donc au propriétaire, et elle n'est pas tranchée ici :
#
#   « Autorisez-vous « retro » à modifier un settings.ini DuckStation qui
#     existe déjà, pour y poser le remplissage — oui ou non ? »
#
#   Si OUI : relever d'abord le nom de la clé sur la machine, puis une
#     seconde stratégie d'écriture à côté de SI_ABSENT — fusion clé à clé avec
#     sauvegarde — qui vaudra aussi pour la manette (dette D3), laquelle bute
#     exactement sur le même mur.
#   Si NON : DuckStation reste au cadrage qu'il choisit seul, et `retro
#     status` continue de le DIRE plutôt que de le laisser deviner.
#
# Tant que la réponse n'est pas donnée, DuckStation rend NON_REGLABLE, ses
# deux modes étant déclarés vides avec leur note, et `retro status` le dit.


def remplissage_attendu(mode: str) -> str:
    """Le remplissage que la politique retient pour un mode DÉCLARÉ.

    `auto` n'en a pas : il choisit un mode et hérite du remplissage de celui
    qu'il retient. Lui en donner un serait un quatrième réglage, qui pourrait
    contredire les deux autres sans que rien ne le dise.
    """
    if mode not in _REMPLISSAGE_PAR_MODE:
        raise RenderError(
            f"« {mode} » n'a pas de remplissage à lui. Les modes qui en "
            f"déclarent un sont {', '.join(MODES_DECLARES)} ; « {AUTO} » "
            "hérite de celui du mode qu'il retient."
        )
    return _REMPLISSAGE_PAR_MODE[mode]


def motif_remplissage(mode: str) -> str:
    """Pourquoi ce mode remplit ainsi. Cité par `retro status`."""
    remplissage_attendu(mode)
    return _MOTIF_PAR_MODE[mode]


@dataclasses.dataclass(frozen=True)
class ChoixRemplissage:
    """Le remplissage d'un mode, et pourquoi. Même exigence que `Decision` :
    un réglage de cadrage qui s'appliquerait en silence serait un défaut, pas
    une fonctionnalité — le propriétaire verrait des bandes noires sans savoir
    si elles sont voulues."""
    remplissage: str
    motif: str


def resoudre_remplissage(mode_nom: str, mode: RenderMode) -> ChoixRemplissage:
    """Ce que ce mode fait RÉELLEMENT du troisième axe, et ce qu'on en dit.

    Quatre états, dans cet ordre, parce qu'ils se recouvrent :

    - `fill_absent` : mesuré, cet émulateur n'expose aucun réglage de cet axe ;
    - un mode qui ne passe RIEN — ni argument ni fichier de réglages — n'a
      aucun axe à régler, celui-ci compris. Sa `note` dit déjà pourquoi, et
      c'est le cas de DuckStation : le déduire ici évite de redemander à son
      profil une seconde fois la même réponse ;
    - `fill` : le profil a tranché, et `profiles` a vérifié qu'il s'accorde
      avec la politique ;
    - sinon : personne n'a mesuré. Ce n'est PAS « cet émulateur n'en a pas » —
      les confondre ferait rouvrir l'enquête à chaque passage, ou pire,
      attendre un effet qui ne viendra jamais.
    """
    if mode.fill_absent:
        return ChoixRemplissage(
            NON_REGLABLE, f"aucun réglage de remplissage — {mode.fill_absent}")
    if not mode.args.strip() and not mode.config.strip():
        return ChoixRemplissage(
            NON_REGLABLE,
            "ce mode ne passe rien à l'émulateur, remplissage compris"
            + (f" — {mode.note}" if mode.note else ""))
    if mode.fill:
        return ChoixRemplissage(
            mode.fill, f"{mode.fill} : {motif_remplissage(mode_nom)}")
    return ChoixRemplissage(
        NON_MESURE,
        "remplissage jamais mesuré sur cet émulateur — l'image est celle "
        "qu'il a choisie tout seul")


# La substitution des variables et le calcul de l'échelle NE SONT PAS ICI.
#
# Ils vivaient dans ce module, testés, complets — et appelés par leurs seuls
# tests. La hauteur de la session n'est connue qu'au lancement, donc le
# lanceur les faisait déjà, en C# ; cette version-ci était un second exemplaire
# que rien n'exécutait, et dont personne n'aurait vu la divergence. Le doublon
# est exactement ce que le plan pré-résolu existe pour éviter : la faute était
# ici, pas dans le lanceur.
#
# Ce que ce module garde est ce qu'il est SEUL à faire, et qui est réellement
# lu : l'arbitrage de `auto` — écrit dans le plan pour chaque classe — et les
# seuils qui classent une machine, écrits dans le plan eux aussi. Le lanceur
# se vérifie, lui, par « retro-launch.exe --explain », qui compose et imprime
# sans rien lancer.
