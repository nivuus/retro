"""Backend de construction : grave l'identité de la roue avant de déléguer.

Il existe parce qu'une identité qu'on peut oublier de calculer est exactement
celle qui manquait le 2026-08-29 : la roue avait été reconstruite à la main.
Ici, toute construction la porte — `pip wheel`, `python -m build`, un pip
install éditable, ou la main.
"""
from __future__ import annotations

import hashlib
import pathlib
import time

from setuptools import build_meta as _setuptools

BASE = "0.1.0"
GENERE = pathlib.Path("retro") / "_identite.py"
# Ce qui part dans la roue, et rien d'autre : les tests et la documentation
# changent sans que le code installé change, et une version qui bougerait pour
# eux ferait réinstaller la console pour rien.
SOURCES = ("retro", "pyproject.toml")
# `_identite.py` est exclu des DEUX calculs, sans quoi graver changerait la
# valeur qu'on vient de graver et deux appels ne s'accorderaient jamais.
IGNORES = ("__pycache__", "_identite.py")


def fichiers(racine: pathlib.Path) -> list[pathlib.Path]:
    trouves = []
    for nom in SOURCES:
        chemin = racine / nom
        if chemin.is_file():
            trouves.append(chemin)
            continue
        for f in chemin.rglob("*"):
            if f.is_file() and not any(p in IGNORES for p in f.parts):
                trouves.append(f)
    return sorted(trouves)


def horodatage(racine: pathlib.Path) -> str:
    """La mtime la plus récente des fichiers embarqués, en UTC.

    Pas l'heure courante : pip appelle chaque hook PEP 517 dans un processus
    séparé, et deux lectures d'horloge donneraient deux versions que pip
    rejetterait pour incohérence de métadonnée.
    """
    recente = max((f.stat().st_mtime for f in fichiers(racine)), default=0.0)
    return time.strftime("%Y%m%d%H%M%S", time.gmtime(int(recente)))


def empreinte(racine: pathlib.Path) -> str:
    """Ce que la roue contient, en huit caractères. Diagnostic seul : deux
    constructions d'un contenu identique se reconnaissent d'un coup d'œil."""
    h = hashlib.sha256()
    for f in fichiers(racine):
        h.update(f.relative_to(racine).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:8]


def revision(racine: pathlib.Path) -> str:
    """Le SHA court, LU DANS .git, sans le binaire git.

    Un CONFORT, jamais la garantie : un arbre modifié sans commit garde le
    même SHA, et c'est l'horodatage qui fait bouger la version. Lu à la main
    parce que la construction peut tourner là où git n'est pas installé, et
    parce qu'un arbre de travail lié (git worktree) porte un `.git` FICHIER —
    c'est le cas de l'agent qui exécutera ce plan.
    """
    try:
        point = racine / ".git"
        if point.is_file():
            texte = point.read_text(encoding="utf-8").strip()
            if not texte.startswith("gitdir:"):
                return ""
            point = pathlib.Path(texte.split(":", 1)[1].strip())
            if not point.is_absolute():
                point = (racine / point).resolve()
        if not point.is_dir():
            return ""
        tete = (point / "HEAD").read_text(encoding="utf-8").strip()
        if not tete.startswith("ref:"):
            return tete[:7]
        ref = tete.split(":", 1)[1].strip()
        bases = [point]
        commun = point / "commondir"
        if commun.is_file():
            bases.append((point / commun.read_text(encoding="utf-8").strip()).resolve())
        for base in bases:
            libre = base / ref
            if libre.is_file():
                return libre.read_text(encoding="utf-8").strip()[:7]
            paquet = base / "packed-refs"
            if paquet.is_file():
                for ligne in paquet.read_text(encoding="utf-8").splitlines():
                    if ligne.startswith(("#", "^")):
                        continue
                    sha, _, nom = ligne.partition(" ")
                    if nom.strip() == ref:
                        return sha[:7]
    except OSError:
        return ""
    return ""


def version(racine: pathlib.Path) -> str:
    """« 0.1.0+20260829143512.a1b2c3d4.g9f8e7d6 ».

    L'horodatage EN PREMIER : les segments locaux PEP 440 se comparent
    segment par segment, un segment numérique numériquement. Mis ailleurs, une
    construction plus récente pourrait se classer AVANT une plus ancienne et
    `pip --upgrade` refuserait de l'installer.
    """
    parties = [horodatage(racine), empreinte(racine)]
    sha = revision(racine)
    if sha:
        parties.append("g" + sha)
    return f"{BASE}+{'.'.join(parties)}"


def graver(racine: pathlib.Path) -> str:
    v = version(racine)
    (racine / GENERE).write_text(
        '"""Écrit à la construction par outils/identite_build.py.\n\n'
        'NE PAS ÉDITER, NE PAS VERSIONNER : sa valeur décrit UNE roue.\n'
        '"""\n'
        f'VERSION = "{v}"\n', encoding="utf-8")
    return v


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    graver(pathlib.Path.cwd())
    return _setuptools.build_wheel(wheel_directory, config_settings,
                                   metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    graver(pathlib.Path.cwd())
    return _setuptools.build_sdist(sdist_directory, config_settings)


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    graver(pathlib.Path.cwd())
    return _setuptools.prepare_metadata_for_build_wheel(
        metadata_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    graver(pathlib.Path.cwd())
    return _setuptools.build_editable(wheel_directory, config_settings,
                                      metadata_directory)


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    graver(pathlib.Path.cwd())
    return _setuptools.prepare_metadata_for_build_editable(
        metadata_directory, config_settings)


get_requires_for_build_wheel = _setuptools.get_requires_for_build_wheel
get_requires_for_build_sdist = _setuptools.get_requires_for_build_sdist
get_requires_for_build_editable = _setuptools.get_requires_for_build_editable
