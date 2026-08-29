"""Le lecteur de bases RetroArch.

AUCUNE BASE REELLE N'ENTRE DANS CE DEPOT : les fixtures en FABRIQUENT une,
octet par octet, selon la structure relevee sur la machine. C'est aussi ce qui
rend ces tests lisibles — on voit ce qu'on encode.
"""
import struct

import pytest

from retro import rdb


def _map(paires: dict) -> bytes:
    """Une map msgpack, en fixmap si elle est assez petite."""
    assert len(paires) <= 15
    out = bytes([0x80 | len(paires)])
    for k, v in paires.items():
        out += _val(k) + _val(v)
    return out


def _val(v) -> bytes:
    if isinstance(v, str):
        b = v.encode("utf-8")
        assert len(b) <= 31
        return bytes([0xa0 | len(b)]) + b
    if isinstance(v, bytes):
        return bytes([0xc4, len(v)]) + v
    if isinstance(v, int) and 0 <= v <= 127:
        return bytes([v])
    raise AssertionError(v)


def base(tmp_path, fiches, nom="t.rdb"):
    corps = b"".join(_map(f) for f in fiches)
    p = tmp_path / nom
    p.write_bytes(rdb.SIGNATURE + struct.pack(">Q", 16 + len(corps)) + corps
                  + b"\x00" * 8)   # de la metadonnee, ignoree
    return p


def test_les_fiches_se_lisent_dans_l_ordre(tmp_path):
    p = base(tmp_path, [{"name": "Un", "rom_name": "un.zip"},
                        {"name": "Deux", "rom_name": "deux.zip"}])
    fiches = rdb.lire(p)
    assert [f["name"] for f in fiches] == ["Un", "Deux"]


def test_ce_qui_suit_l_offset_annonce_est_ignore(tmp_path):
    """La base porte une zone de metadonnees apres ses fiches. La lire comme
    une fiche donnerait un jeu fantome, ou ferait echouer tout le fichier."""
    p = base(tmp_path, [{"name": "Un", "rom_name": "un.zip"}])
    assert len(rdb.lire(p)) == 1


def test_un_fichier_sans_signature_est_refuse(tmp_path):
    p = tmp_path / "faux.rdb"
    p.write_bytes(b"PAS-UNE-BASE" + b"\x00" * 32)
    with pytest.raises(rdb.RdbError, match="RARCHDB"):
        rdb.lire(p)


def test_un_offset_hors_du_fichier_est_refuse(tmp_path):
    """Sans cette garde, la boucle lisait au-dela du tampon et rendait des
    fiches inventees — un titre faux se lit exactement comme un titre juste."""
    p = tmp_path / "t.rdb"
    p.write_bytes(rdb.SIGNATURE + struct.pack(">Q", 1 << 40))
    with pytest.raises(rdb.RdbError, match="offset"):
        rdb.lire(p)


def test_un_type_msgpack_inconnu_leve(tmp_path):
    """Rendre les fiches deja lues donnerait un titre a certains jeux et pas
    a d'autres, sans que rien n'explique la difference."""
    corps = bytes([0xc1])          # jamais employe par msgpack
    p = tmp_path / "t.rdb"
    p.write_bytes(rdb.SIGNATURE + struct.pack(">Q", 16 + len(corps)) + corps)
    with pytest.raises(rdb.RdbError, match="inconnu"):
        rdb.lire(p)
