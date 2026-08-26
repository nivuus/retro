"""Lecture et écriture de shortcuts.vdf.

Le fichier est un VDF binaire dont la racine est une clé "shortcuts" contenant
un mapping d'index décimaux vers les entrées. Ces index sont purement
positionnels — Steam les renumérote lui-même — donc cette couche les gomme et
expose une liste.
"""
from __future__ import annotations

import pathlib

import vdf

ROOT_KEY = "shortcuts"


class ShortcutsError(RuntimeError):
    """shortcuts.vdf est illisible ou n'a pas la forme attendue."""


def loads_shortcuts(blob: bytes) -> list[dict]:
    try:
        parsed = vdf.binary_loads(blob)
    except Exception as exc:  # la bibliothèque lève des types variés
        raise ShortcutsError(f"VDF binaire illisible : {exc}") from exc
    if ROOT_KEY not in parsed:
        raise ShortcutsError(
            f"racine '{ROOT_KEY}' absente ; clés trouvées : {sorted(parsed)}"
        )
    shortcuts = parsed[ROOT_KEY]
    # Trier numériquement : "10" doit suivre "9", pas "1".
    return [shortcuts[k] for k in sorted(shortcuts, key=int)]


def dumps_shortcuts(entries: list[dict]) -> bytes:
    body = {str(i): entry for i, entry in enumerate(entries)}
    return vdf.binary_dumps({ROOT_KEY: body})


def load_shortcuts(path: pathlib.Path) -> list[dict]:
    """Un fichier absent vaut zéro raccourci : Steam ne le crée qu'au premier."""
    if not path.exists():
        return []
    return loads_shortcuts(path.read_bytes())
