"""Identifiant d'un raccourci non-Steam.

Steam le dérive du couple (exe, appname). Il sert à deux choses : le champ
`appid` du VDF, en entier signé, et le nom des fichiers d'artwork, en non signé.
Confondre les deux formes donne de l'artwork que Steam ne trouve jamais.
"""
from __future__ import annotations

import zlib

_HIGH_BIT = 0x80000000
_2POW32 = 0x100000000


def legacy_appid(exe: str, app_name: str) -> int:
    """Forme non signée sur 32 bits. C'est elle qui nomme l'artwork.

    `exe` doit être la chaîne EXACTE du champ exe, guillemets inclus : Steam
    calcule sur ce qu'il a stocké, pas sur un chemin nettoyé.
    """
    return zlib.crc32((exe + app_name).encode("utf-8")) | _HIGH_BIT


def to_signed(legacy: int) -> int:
    """Forme stockée dans le champ `appid`, qui est un int32 signé."""
    return legacy - _2POW32 if legacy >= 0x80000000 else legacy


def to_unsigned(signed: int) -> int:
    return signed + _2POW32 if signed < 0 else signed


def grid_prefixes(legacy: int) -> dict[str, str]:
    """Les CINQ assets du dossier grid\\, en PRÉFIXES sans extension.

    Mesuré sur une installation réelle le 2026-08-26 : `.png`, `.jpg` et `.ico`
    coexistent pour le même rôle — 18 jeux, 5 assets chacun, extensions
    mélangées. Coder une extension en dur ferait retélécharger un asset déjà
    présent sous une autre, à chaque synchronisation, indéfiniment.
    """
    return {
        "portrait": f"{legacy}p",
        "paysage": f"{legacy}",
        "hero": f"{legacy}_hero",
        "logo": f"{legacy}_logo",
        "icone": f"{legacy}_icon",
    }


def existing_asset(grid_dir, prefix: str):
    """Le fichier présent pour ce préfixe, quelle que soit son extension.

    `paysage` a pour préfixe le nombre nu, donc `2398p` et `2398_hero`
    commenceraient aussi par lui : la correspondance porte sur le STEM entier,
    jamais sur un préfixe de chaîne.
    """
    if not grid_dir.is_dir():
        return None
    for f in grid_dir.iterdir():
        if f.stem == prefix:
            return f
    return None
