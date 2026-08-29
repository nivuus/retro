"""Lire une base de données RetroArch (« RARCHDB »).

CE FICHIER N'INVENTE AUCUN FORMAT. Une base `.rdb` est livrée AVEC l'archive
de RetroArch que le manifeste épingle, donc son contenu est reproductible :
n'importe qui peut rouvrir les mêmes octets. Sa structure, relevée le
2026-08-29 sur `FBNeo - Arcade Games.rdb` de la révision 1.22.2 :

    0x00  « RARCHDB\\0 »          la signature
    0x08  uint64 gros-boutiste   l'offset où les fiches s'arrêtent
    0x10  ...                    une suite de maps msgpack, une par jeu

Il n'y a ni index ni compression : on lit les fiches d'affilée jusqu'à
l'offset annoncé. Le lecteur msgpack ci-dessous est minimal ET COMPLET pour
ce que ces bases emploient — un type non reconnu LÈVE plutôt que de rendre
une fiche tronquée, parce qu'une fiche tronquée donnerait un mauvais titre à
un jeu sans que rien ne le dise.
"""
from __future__ import annotations

import pathlib
import struct

SIGNATURE = b"RARCHDB\x00"


class RdbError(RuntimeError):
    """La base n'est pas lisible, et on le dit plutôt que de rendre zéro fiche."""


class _Lecteur:
    """Un décodeur msgpack, borné au fichier qu'on lui donne."""

    def __init__(self, octets: bytes, i: int = 0):
        self.b, self.i = octets, i

    def _u(self, n: int) -> int:
        v = int.from_bytes(self.b[self.i:self.i + n], "big")
        self.i += n
        return v

    def _texte(self, n: int) -> str:
        v = self.b[self.i:self.i + n].decode("utf-8", "replace")
        self.i += n
        return v

    def _binaire(self, n: int) -> bytes:
        v = self.b[self.i:self.i + n]
        self.i += n
        return v

    def valeur(self):
        c = self.b[self.i]
        self.i += 1
        if c <= 0x7f:
            return c
        if c >= 0xe0:
            return c - 256
        if 0x80 <= c <= 0x8f:
            return {self.valeur(): self.valeur() for _ in range(c & 0xf)}
        if 0x90 <= c <= 0x9f:
            return [self.valeur() for _ in range(c & 0xf)]
        if 0xa0 <= c <= 0xbf:
            return self._texte(c & 0x1f)
        if c == 0xc0:
            return None
        if c == 0xc2:
            return False
        if c == 0xc3:
            return True
        if c in (0xc4, 0xc5, 0xc6):
            return self._binaire(self._u(1 << (c - 0xc4)))
        if c == 0xca:
            v = struct.unpack(">f", self.b[self.i:self.i + 4])[0]
            self.i += 4
            return v
        if c == 0xcb:
            v = struct.unpack(">d", self.b[self.i:self.i + 8])[0]
            self.i += 8
            return v
        if c in (0xcc, 0xcd, 0xce, 0xcf):
            return self._u(1 << (c - 0xcc))
        if c in (0xd0, 0xd1, 0xd2, 0xd3):
            n = 1 << (c - 0xd0)
            v = self._u(n)
            return v - (1 << (8 * n)) if v >= 1 << (8 * n - 1) else v
        if c in (0xd9, 0xda, 0xdb):
            return self._texte(self._u(1 << (c - 0xd9)))
        if c in (0xdc, 0xdd):
            return [self.valeur() for _ in range(self._u(2 << (c - 0xdc)))]
        if c in (0xde, 0xdf):
            return {self.valeur(): self.valeur()
                    for _ in range(self._u(2 << (c - 0xde)))}
        raise RdbError(
            f"octet msgpack inconnu 0x{c:02x} à la position {self.i - 1}. La "
            "base n'a pas la forme attendue ; rendre les fiches déjà lues "
            "donnerait un titre à certains jeux et pas à d'autres, sans que "
            "rien n'explique la différence."
        )


def lire(chemin: pathlib.Path) -> list[dict]:
    """Les fiches d'une base, dans l'ordre du fichier."""
    octets = chemin.read_bytes()
    if octets[:8] != SIGNATURE:
        raise RdbError(
            f"{chemin} ne commence pas par « RARCHDB » : ce n'est pas une base "
            f"RetroArch (reçu {octets[:8]!r})."
        )
    fin = struct.unpack(">Q", octets[8:16])[0]
    if not 16 <= fin <= len(octets):
        raise RdbError(
            f"{chemin} annonce que ses fiches s'arrêtent à l'offset {fin}, "
            f"hors d'un fichier de {len(octets)} octets."
        )
    lecteur = _Lecteur(octets, 16)
    fiches = []
    while lecteur.i < fin:
        v = lecteur.valeur()
        if isinstance(v, dict):
            fiches.append(v)
    return fiches
