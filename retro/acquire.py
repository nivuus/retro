"""Télécharger, vérifier, extraire.

Deux risques distincts, et aucun ne se voit après coup :

1. Installer un binaire qui n'est pas celui qu'on croit. L'empreinte est donc
   vérifiée AVANT toute extraction, et un échec ne laisse rien derrière lui.
2. Laisser une archive écrire hors du dossier qu'on lui a désigné. Une archive
   venue d'Internet peut contenir « ../ » ou un chemin absolu ; l'extraire
   naïvement écrit n'importe où sur le disque, et le dossier de destination
   n'en garde aucune trace.

Un émulateur peut être livré en plusieurs archives qui se déversent dans le
même dossier. Toutes sont téléchargées et vérifiées avant que la moindre
écriture ne touche à l'installation existante : un émulateur amputé d'une de
ses parties est pire qu'un émulateur absent, parce qu'il paraît installé et ne
lance rien.
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
    """Extrait une archive sans la laisser écrire hors de sa destination.

    `_membres_surs` ne regarde que les NOMS de membres. La protection contre un
    lien symbolique dont la cible sort de la destination repose, elle, sur les
    bibliothèques d'extraction : zipfile ne matérialise jamais de vrai lien, et
    py7zr refuse lui-même « Symlink point out of target directory ». C'est de la
    défense en profondeur réelle, mais elle est portée par du code que nous
    n'écrivons pas — d'où cette note, pour qu'un futur changement de
    bibliothèque ne rouvre pas le trou en silence.

    Toute exception est enveloppée : sur une machine de provisionnement sans
    clavier ni écran, une trace Python brute remplace le message qui nommerait
    l'archive fautive.
    """
    if kind not in ("zip", "7z"):
        raise AcquireError(f"format d'archive inconnu : {kind!r}")
    destination.mkdir(parents=True, exist_ok=True)
    try:
        if kind == "zip":
            with zipfile.ZipFile(archive) as z:
                _membres_surs(z.namelist(), destination)
                z.extractall(destination)
        else:
            try:
                import py7zr
            except ImportError as exc:  # pragma: no cover - dépendance déclarée
                raise AcquireError("py7zr est requis pour les archives 7z") from exc
            with py7zr.SevenZipFile(archive) as z:
                _membres_surs(z.getnames(), destination)
                z.extractall(destination)
    except AcquireError:
        raise
    except Exception as exc:  # noqa: BLE001 - volontairement large, voir docstring
        raise AcquireError(
            f"extraction de {archive.name} impossible : {type(exc).__name__}: {exc}"
        ) from exc


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

    # Les archives supplémentaires sont téléchargées et vérifiées AVANT que
    # quoi que ce soit ne touche à l'installation existante : une seconde
    # archive dont l'empreinte est fausse ne doit pas laisser un émulateur
    # amputé. RetroArch en dépend — son archive principale ne contient aucun
    # core, et un émulateur sans core s'installe sans rien pouvoir lancer.
    # Un émulateur amputé est pire qu'un émulateur absent : il paraît installé.
    supplements = []
    for i, part in enumerate(emu.parts):
        try:
            b = fetch(part.url)
        except Exception as exc:  # noqa: BLE001 - toute panne réseau, nommée
            raise AcquireError(
                f"{emu.name} : téléchargement de l'archive supplémentaire "
                f"{i + 1} impossible ({exc})"
            ) from exc
        h = hashlib.sha256(b).hexdigest()
        if h != part.sha256:
            raise AcquireError(
                f"{emu.name} {emu.version}, archive supplémentaire {i + 1} : "
                f"empreinte SHA256 inattendue.\n  attendue : {part.sha256}\n"
                f"  obtenue  : {h}\nRien n'a été installé."
            )
        supplements.append((b, part.archive))

    with tempfile.TemporaryDirectory() as tmp:
        racine = pathlib.Path(tmp)
        archive = racine / f"{emu.key}.{emu.archive}"
        archive.write_bytes(blob)
        extrait = racine / "extrait"
        # Extraire à côté, puis basculer : une extraction qui échoue à
        # mi-chemin ne doit pas laisser une installation à moitié écrasée.
        safe_extract(archive, emu.archive, extrait)
        # Les supplémentaires se déversent dans le MÊME dossier : c'est ce qui
        # fait cohabiter l'émulateur et ses cores.
        for i, (b, kind) in enumerate(supplements):
            sup = racine / f"{emu.key}-part{i}.{kind}"
            sup.write_bytes(b)
            safe_extract(sup, kind, extrait)
        if cible.exists():
            shutil.rmtree(cible)
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extrait), str(cible))

    temoin.write_text(emu.version + "\n", encoding="utf-8")
    return "réinstallé" if deja else "installé"
