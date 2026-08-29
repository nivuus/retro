"""Le manifeste : quels émulateurs installer, depuis quelle URL, sous quelle
empreinte.

Deux fichiers, même schéma. Le noyau est livré avec le paquet et ne référence
que des émulateurs au statut juridique clair, puisque le dépôt est public. Le
manifeste utilisateur vit hors du dépôt et n'a pas cette limite : c'est tout
son objet.

Il est écrit à la main, donc chaque refus doit nommer ce qui ne va pas et où.
"""
from __future__ import annotations

import dataclasses
import pathlib
import tomllib

SCHEMA = 1
ARCHIVES = ("7z", "zip")
# Racine témoin pour la validation d'install_dir. Sa valeur n'a aucune
# importance : elle ne sert qu'à éprouver la jointure.
_TEMOIN = pathlib.PureWindowsPath("D:/__racine__")
_CHAMPS = ("name", "version", "url", "sha256", "archive", "install_dir", "profile")
_CHAMPS_PART = ("url", "sha256", "archive")


class ManifestError(RuntimeError):
    """Un manifeste est illisible, incomplet ou incohérent."""


@dataclasses.dataclass(frozen=True)
class Part:
    """Une archive supplémentaire, extraite dans le même dossier que la
    principale. RetroArch en a besoin : son archive ne contient AUCUN core, et
    un émulateur sans core ne lance aucun jeu."""
    url: str
    sha256: str
    archive: str


@dataclasses.dataclass(frozen=True)
class Emulator:
    key: str
    name: str
    version: str
    url: str
    sha256: str
    archive: str
    install_dir: str
    profile: str
    parts: tuple[Part, ...] = ()


@dataclasses.dataclass(frozen=True)
class BiosSource:
    """D'où le propriétaire fait venir ses BIOS, quand il en déclare une.

    CE PAQUET NE DISTRIBUE AUCUN BIOS, et cette classe ne change rien à cela :
    elle porte une URL QUE LE PROPRIÉTAIRE A ÉCRITE, exactement comme le
    manifeste porte celles des émulateurs. Le manifeste NOYAU, livré avec le
    paquet dans un dépôt public, n'en déclare aucune et ne doit jamais en
    déclarer : pointer un dépôt de BIOS depuis un dépôt public est un acte de
    distribution, le même raisonnement qui tient les émulateurs au statut
    contesté hors d'ici.

    CE QUI REND UNE SOURCE UTILISABLE N'EST PAS SA RÉPUTATION, C'EST
    L'EMPREINTE. Le fichier téléchargé est comparé au md5 que le PROFIL
    déclare — jamais à un md5 fourni par la source elle-même, qui n'attesterait
    que d'elle. Une source qui rend autre chose est refusée en le nommant, et
    rien n'est écrit : un BIOS faux ne se distingue pas d'un BIOS absent avant
    d'être en jeu, sur un canapé, sans clavier.
    """
    base_url: str
    # CE QUE LA SOURCE RANGE AILLEURS QUE SOUS SON NOM.
    #
    # Le nom qu'un profil déclare est celui du fichier DANS VOTRE DOSSIER DE
    # BIOS ; la source, elle, peut le ranger sous un sous-chemin. Mesuré le
    # 2026-08-29 sur un miroir réel : `dc_boot.bin` y vit sous « dc/ », et les
    # BIOS de plateau d'arcade sous « fbneo/ ». Ce n'est pas une lubie du
    # miroir — c'est la disposition que les cores libretro attendent sous leur
    # propre dossier système.
    #
    # Ces deux choses ne se confondent PAS, et c'est pourquoi la table vit ici
    # plutôt que dans le profil : le sous-chemin est une propriété de LA
    # SOURCE, qui change avec elle, pas du BIOS. Le mettre au profil aurait
    # gravé la disposition d'un miroir dans un fichier livré à tout le monde.
    #
    # Rien n'est DEVINÉ. Une source qui range autrement rend 404, et « retro
    # bios » le dit en donnant l'URL essayée : c'est une ligne à écrire ici,
    # pas une heuristique à écrire dans le code.
    paths: tuple[tuple[str, str], ...] = ()

    def url_for(self, nom: str) -> str:
        """L'adresse d'UN fichier. Le nom est celui que le profil déclare ;
        la table `paths` dit où la source le range, quand ce n'est pas là."""
        for declare, chemin in self.paths:
            if declare.lower() == nom.lower():
                nom = chemin
                break
        return f"{self.base_url.rstrip('/')}/{nom.lstrip('/')}"


def load_bios_source(core: pathlib.Path,
                     user: pathlib.Path | None = None) -> BiosSource | None:
    """La source de BIOS déclarée, ou None — et None est le cas NORMAL.

    Sans source, `retro bios` ne télécharge rien et le dit ; il ne se tait pas,
    et il n'invente pas d'adresse.
    """
    brut = dict(_lire_table(core, obligatoire=True, table="bios"))
    if user is not None:
        brut.update(_lire_table(user, obligatoire=False, table="bios"))
    if not brut:
        return None
    url = brut.get("base_url")
    if not isinstance(url, str) or not url.strip():
        raise ManifestError(
            "[bios] : 'base_url' manquante ou vide. La table existe donc "
            "quelqu'un a voulu déclarer une source ; vide, elle ne "
            "téléchargerait rien et « aucune source » aurait l'air d'être un "
            "choix alors que c'est une faute de frappe."
        )
    if not url.startswith("https://"):
        raise ManifestError(
            f"[bios] base_url = {url!r} : le téléchargement se fait en HTTPS. "
            "En clair, n'importe qui sur le chemin peut substituer le fichier "
            "— l'empreinte le rattraperait, mais après le transfert, et sans "
            "que rien ne dise que c'est une substitution plutôt qu'un miroir "
            "périmé."
        )
    chemins = brut.get("paths", {})
    if not isinstance(chemins, dict):
        raise ManifestError(
            "[bios.paths] doit être une table « nom déclaré = sous-chemin » "
            '(par exemple : "dc_boot.bin" = "dc/dc_boot.bin"). Un autre type '
            "ne serait comparé à aucun nom, et le fichier serait redemandé à "
            "la racine de la source, où il n'est pas."
        )
    mauvais = [repr(k) for k, v in chemins.items()
               if not isinstance(v, str) or not v.strip()]
    if mauvais:
        raise ManifestError(
            f"[bios.paths] : sous-chemin vide ou non textuel pour "
            f"{', '.join(mauvais)}. Vide, il ferait construire une adresse qui "
            "s'arrête au dossier — une URL d'apparence normale qui ne rend "
            "aucun fichier."
        )
    return BiosSource(base_url=url.strip(),
                      paths=tuple(sorted((k, v.strip())
                                         for k, v in chemins.items())))


def _lire(path: pathlib.Path, obligatoire: bool) -> dict:
    if not path.exists():
        if obligatoire:
            raise ManifestError(f"manifeste introuvable : {path}")
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{path} n'est pas du TOML valide : {exc}") from exc
    schema = data.get("schema")
    if schema != SCHEMA:
        raise ManifestError(
            f"{path} déclare schema = {schema}, ce paquet lit le schéma {SCHEMA}"
        )
    return data.get("emulator", {})


def _lire_table(path: pathlib.Path, obligatoire: bool, table: str) -> dict:
    """Une AUTRE table du même fichier, aux mêmes conditions de schéma.

    `_lire` ci-dessus ne rend que `[emulator]`, et c'est ce qu'il doit faire :
    son appelant construit des émulateurs. Une seconde table se lit par ici
    plutôt qu'en élargissant la première, dont chaque appelant aurait alors à
    trier le contenu.
    """
    if not path.exists():
        if obligatoire:
            raise ManifestError(f"manifeste introuvable : {path}")
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{path} n'est pas du TOML valide : {exc}") from exc
    if data.get("schema") != SCHEMA:
        raise ManifestError(
            f"{path} déclare schema = {data.get('schema')}, ce paquet lit le "
            f"schéma {SCHEMA}"
        )
    return data.get(table, {})


def _valider_install_dir(cle: str, valeur: str) -> None:
    """install_dir est concaténé à la racine d'émulation.

    Un manifeste utilisateur n'est pas de confiance : il est écrit à la main et
    peut être copié depuis n'importe où. Un chemin qui s'échappe y ferait écrire
    hors du volume prévu — sur la partition système, effacée à chaque
    reconstruction de la machine, ou pire.

    La vérification est POSITIVE : la jointure doit rester sous la racine. La
    liste des formes interdites, elle, ne se termine jamais. Mesuré le
    2026-08-26 : un backslash seul en tête, sans lettre de lecteur, a
    is_absolute() faux, drive vide et aucun « .. » dans parts — et la jointure
    écrase pourtant la racine entière.

    Le refus de « .. » reste nécessaire en plus : PureWindowsPath ne normalise
    pas, donc 'D:/racine/..' a bien 'D:/racine' pour parent.
    """
    p = pathlib.PureWindowsPath(valeur)
    if valeur and ".." not in p.parts and _TEMOIN in (_TEMOIN / valeur).parents:
        return
    raise ManifestError(
        f"[emulator.{cle}] install_dir = {valeur!r} : un chemin relatif "
        "simple est attendu, qui reste sous la racine d'émulation"
    )


def _lire_parts(cle: str, champs: dict) -> tuple[Part, ...]:
    """Les archives supplémentaires d'un émulateur, éventuellement aucune.

    Un émulateur peut être livré en plusieurs morceaux qui se déversent dans le
    même dossier. C'est le cas de RetroArch : son archive principale ne contient
    AUCUN core, et un émulateur sans core s'installe sans rien pouvoir lancer.

    Chaque morceau est validé comme l'entrée principale — une empreinte
    manquante ici vaudrait un binaire non vérifié.
    """
    parts = []
    for i, brute in enumerate(champs.get("parts", ())):
        manquants = [c for c in _CHAMPS_PART if c not in brute]
        if manquants:
            raise ManifestError(
                f"[emulator.{cle}] parts[{i}] : champ(s) manquant(s) "
                f"{', '.join(manquants)}"
            )
        if brute["archive"] not in ARCHIVES:
            raise ManifestError(
                f"[emulator.{cle}] parts[{i}] archive = "
                f"{brute['archive']!r} : connu(s) {', '.join(ARCHIVES)}"
            )
        parts.append(Part(**{c: brute[c] for c in _CHAMPS_PART}))
    return tuple(parts)


def _refuser_profils_partages(emulateurs: dict) -> None:
    """Deux entrées ne peuvent pas viser le même profil.

    `cli._install_dirs_pour` indexe les émulateurs PAR PROFIL —
    `{emu.profile: emu.install_dir}`. Deux entrées qui déclarent le même
    `profile` s'y écrasent donc l'une l'autre, en silence et selon l'ordre
    d'itération : les jeux de ce profil se voient attribuer le dossier
    d'installation de l'autre entrée. Steam crée les raccourcis, le rapport
    annonce « + <titre> », et rien ne démarre — ni Steam ni ce paquet ne le
    signalent.

    Le refus vaut au CHARGEMENT, parce que c'est le seul endroit où les deux
    entrées sont encore visibles ensemble : plus bas, l'une a déjà disparu.

    Remplacer une entrée livrée se fait en REPRENANT SA CLÉ — le manifeste
    utilisateur surcharge par clé — et non en ajoutant une seconde entrée qui
    viserait le même profil. Le message le dit, sans quoi le refus n'indique
    aucune sortie.
    """
    par_profil: dict[str, list[str]] = {}
    for cle in sorted(emulateurs):
        par_profil.setdefault(emulateurs[cle].profile, []).append(cle)
    for profil, cles in sorted(par_profil.items()):
        if len(cles) > 1:
            raise ManifestError(
                f"profile = {profil!r} est déclaré par {len(cles)} entrées : "
                f"{', '.join(f'[emulator.{c}]' for c in cles)}. Un profil ne "
                "peut avoir qu'un dossier d'installation ; deux entrées le "
                "revendiquent et la dernière lue gagnerait sans un mot. Pour "
                "remplacer une entrée, reprendre SA CLÉ dans le manifeste "
                "utilisateur ; pour en ajouter une autre, lui donner un "
                "profile distinct."
            )


def load_manifest(core: pathlib.Path,
                  user: pathlib.Path | None = None) -> dict[str, Emulator]:
    """Le noyau, surchargé par le manifeste utilisateur s'il existe.

    L'absence du manifeste utilisateur est NORMALE : il vit sur le partage du
    propriétaire, qui n'est pas monté au moment du provisionnement.
    """
    brut = dict(_lire(core, obligatoire=True))
    if user is not None:
        brut.update(_lire(user, obligatoire=False))

    emulateurs = {}
    for cle, champs in brut.items():
        manquants = [c for c in _CHAMPS if c not in champs]
        if manquants:
            raise ManifestError(
                f"[emulator.{cle}] : champ(s) manquant(s) {', '.join(manquants)}"
            )
        if champs["archive"] not in ARCHIVES:
            raise ManifestError(
                f"[emulator.{cle}] archive = {champs['archive']!r} : "
                f"connu(s) {', '.join(ARCHIVES)}"
            )
        _valider_install_dir(cle, champs["install_dir"])
        emulateurs[cle] = Emulator(key=cle, parts=_lire_parts(cle, champs),
                                   **{c: champs[c] for c in _CHAMPS})
    _refuser_profils_partages(emulateurs)
    return emulateurs
