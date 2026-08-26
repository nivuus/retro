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
_CHAMPS = ("name", "version", "url", "sha256", "archive", "install_dir", "profile")


class ManifestError(RuntimeError):
    """Un manifeste est illisible, incomplet ou incohérent."""


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
    peut être copié depuis n'importe où. Un « .. » ou un chemin absolu y ferait
    écrire hors du volume prévu — sur C:, qui est effacée à chaque
    reconstruction, ou pire.
    """
    p = pathlib.PureWindowsPath(valeur)
    if p.is_absolute() or p.drive or ".." in p.parts or valeur.startswith("/"):
        raise ManifestError(
            f"[emulator.{cle}] install_dir = {valeur!r} : un chemin relatif "
            "simple est attendu, sans '..' ni racine"
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
        emulateurs[cle] = Emulator(key=cle, **{c: champs[c] for c in _CHAMPS})
    return emulateurs
