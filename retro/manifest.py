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
    return emulateurs
