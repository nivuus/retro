"""Quelle construction du paquet tourne réellement ici.

Le paquet ne peut pas répondre en interrogeant un dépôt : sur la console il
n'y en a pas, et git n'y est pas installé. La réponse est donc GRAVÉE dans la
roue à la construction (outils/identite_build.py) et simplement relue ici.

Un arbre source jamais construit le dit, plutôt que d'inventer : c'est le cas
normal de l'hôte, qui lance ce paquet depuis son dépôt.
"""
from __future__ import annotations

import importlib

BASE = "0.1.0"
SOURCE = f"{BASE}+source"


def _lire(importer=importlib.import_module) -> str:
    try:
        return importer("retro._identite").VERSION
    except ImportError:
        return SOURCE


VERSION = _lire()


def lisible(version: str = "") -> str:
    """La version, dite à quelqu'un qui la lit depuis son canapé."""
    v = version or VERSION
    _, _, local = v.partition("+")
    if not local or local == "source":
        return f"{v} — arbre source, jamais construit en roue"
    morceaux = local.split(".")
    h = morceaux[0]
    quand = (f"{h[0:4]}-{h[4:6]}-{h[6:8]} à {h[8:10]}:{h[10:12]} UTC"
             if len(h) == 14 and h.isdigit() else h)
    rev = next((m[1:] for m in morceaux[1:] if m.startswith("g")), "")
    return (f"{v} — construit le {quand}, "
            + (f"révision {rev}" if rev else "révision inconnue"))
