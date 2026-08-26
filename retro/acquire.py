"""Télécharger, vérifier, extraire.

Deux risques distincts, et aucun ne se voit après coup :

1. Installer un binaire qui n'est pas celui qu'on croit. L'empreinte est donc
   vérifiée AVANT toute extraction, et un échec ne laisse rien derrière lui.
2. Laisser une archive écrire hors du dossier qu'on lui a désigné. Une archive
   venue d'Internet peut contenir « ../ » ou un chemin absolu ; l'extraire
   naïvement écrit n'importe où sur le disque, et le dossier de destination
   n'en garde aucune trace.
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import tempfile
import zipfile

TEMOIN = ".retro-version"


class AcquireError(RuntimeError):
    """L'émulateur n'a pas pu être installé, et rien n'a été laissé à moitié."""


def _fetch(url: str) -> bytes:
    import requests
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.content


def _membres_surs(noms, destination: pathlib.Path):
    """Refuse tout membre dont le chemin résolu sort de la destination."""
    racine = destination.resolve()
    for nom in noms:
        cible = (destination / nom).resolve()
        if cible != racine and racine not in cible.parents:
            raise AcquireError(
                f"l'archive contient un chemin qui sort de sa destination : "
                f"{nom!r} — extraction refusée"
            )


def safe_extract(archive: pathlib.Path, kind: str,
                 destination: pathlib.Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if kind == "zip":
        with zipfile.ZipFile(archive) as z:
            _membres_surs(z.namelist(), destination)
            z.extractall(destination)
    elif kind == "7z":
        try:
            import py7zr
        except ImportError as exc:  # pragma: no cover - dépendance déclarée
            raise AcquireError("py7zr est requis pour les archives 7z") from exc
        with py7zr.SevenZipFile(archive) as z:
            _membres_surs(z.getnames(), destination)
            z.extractall(destination)
    else:
        raise AcquireError(f"format d'archive inconnu : {kind!r}")


def acquire(emu, emulation_root: pathlib.Path, fetch=_fetch) -> str:
    """Installe l'émulateur s'il manque ou si sa version a changé.

    Rend « installé », « à jour » ou « réinstallé ». Le témoin de version est
    ce qui rend l'opération idempotente : le provisionnement rejoue cette
    étape à chaque reconstruction, et retélécharger des gigaoctets déjà
    présents serait une panne à lui seul.
    """
    cible = emulation_root / emu.install_dir
    temoin = cible / TEMOIN
    if temoin.exists() and temoin.read_text(encoding="utf-8").strip() == emu.version:
        return "à jour"
    deja = cible.exists()

    try:
        blob = fetch(emu.url)
    except Exception as exc:  # noqa: BLE001 - toute panne réseau, nommée
        raise AcquireError(f"{emu.name} : téléchargement impossible ({exc})") from exc

    empreinte = hashlib.sha256(blob).hexdigest()
    if empreinte != emu.sha256:
        raise AcquireError(
            f"{emu.name} {emu.version} : empreinte SHA256 inattendue.\n"
            f"  attendue : {emu.sha256}\n  obtenue  : {empreinte}\n"
            "Rien n'a été installé."
        )

    with tempfile.TemporaryDirectory() as tmp:
        archive = pathlib.Path(tmp) / f"{emu.key}.{emu.archive}"
        archive.write_bytes(blob)
        extrait = pathlib.Path(tmp) / "extrait"
        # Extraire à côté, puis basculer : une extraction qui échoue à
        # mi-chemin ne doit pas laisser une installation à moitié écrasée.
        safe_extract(archive, emu.archive, extrait)
        if cible.exists():
            shutil.rmtree(cible)
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extrait), str(cible))

    temoin.write_text(emu.version + "\n", encoding="utf-8")
    return "réinstallé" if deja else "installé"
