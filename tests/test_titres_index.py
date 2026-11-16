"""Title resolution: one index per database, streaming hashes, UTF-8 text.

Fixtures are tiny RDB files built byte by byte (see tests/test_rdb.py); no real
database and no console are involved.

RDB text encoding (libretro-db, RetroArch): records are msgpack maps. Text is
msgpack `str`, which the msgpack specification defines as UTF-8. The Lua DAT
converter writes `crc`, `md5`, `sha1` and `serial` as msgpack `bin`. A `bin`
that carries text therefore has no declared encoding of its own; RetroArch
treats every name it handles as UTF-8, so that is how it is decoded here.
"""
import hashlib

import pytest

from retro import lecture, rdb, titres
from tests.test_rdb import base

TABLE = {
    "snes": {"base": "SNES", "serie": ""},
    "arcade": {"base": "Arcade", "serie": ""},
    "saturn": {"base": "Saturn", "serie": "saturn"},
}


def resolver(tmp_path):
    return titres.Resolveur(tmp_path, TABLE)


# --- text encoding ---------------------------------------------------------

JAPANESE = "ファイナルファンタジーVI (Japan)"
ACCENTED = "Pokémon Édition Rouge (France)"


@pytest.mark.parametrize("title", [JAPANESE, ACCENTED])
def test_a_title_stored_as_msgpack_str_keeps_its_script(tmp_path, title):
    # The fixture helper caps msgpack str at 31 bytes: use a short pair.
    short = {"name": title[:8], "rom_name": title[:8] + ".sfc"}
    base(tmp_path, [short], "SNES.rdb")
    rom = tmp_path / short["rom_name"]
    rom.write_bytes(b"x")
    t = resolver(tmp_path).resoudre(rom, "snes")
    assert t is not None and t.nom == short["name"]


@pytest.mark.parametrize("title", ["ファイナル (J)", "Pokémon Rouge (F)"])
def test_a_title_stored_as_msgpack_bin_is_decoded_as_utf8(tmp_path, title):
    """A database that stores names as `bin` must not mangle non-ASCII."""
    base(tmp_path, [{"name": title.encode("utf-8"),
                     "rom_name": (title + ".sfc").encode("utf-8")}],
         "SNES.rdb")
    rom = tmp_path / (title + ".sfc")
    rom.write_bytes(b"x")
    t = resolver(tmp_path).resoudre(rom, "snes")
    assert t is not None
    assert t.nom == title            # a str, not bytes, and not mangled


def test_text_helpers_decode_utf8_bytes():
    assert titres._texte("Pokémon".encode()) == "Pokémon"
    assert titres._texte("ファイナル".encode()) == "ファイナル"
    assert titres.tige_de_fiche("Pokémon (Track 1).bin".encode()) == "pokémon"
    assert titres.normaliser_serie("SLPS-01234".encode()) == "SLPS01234"


def test_invalid_bytes_are_replaced_not_dropped():
    out = titres._texte(b"abc\xffdef")
    assert out.startswith("abc") and out.endswith("def")


# --- one index per database ------------------------------------------------

def test_records_are_indexed_once_not_once_per_game(tmp_path, monkeypatch):
    names = [f"Game {i:03d}" for i in range(30)]
    base(tmp_path, [{"name": n, "rom_name": f"{n}.sfc"} for n in names],
         "SNES.rdb")
    games = []
    for n in names:
        p = tmp_path / f"{n}.sfc"
        p.write_bytes(b"x")
        games.append(p)
    calls = []
    real = titres.tige_de_fiche
    monkeypatch.setattr(titres, "tige_de_fiche",
                        lambda v: calls.append(v) or real(v))
    r = resolver(tmp_path)
    for p in games:
        assert r.resoudre(p, "snes").nom == p.stem
    # Once per record while indexing; never again per game.
    assert len(calls) <= len(names)


def test_first_record_wins_as_before(tmp_path):
    base(tmp_path, [{"name": "First", "rom_name": "dup.sfc"},
                    {"name": "Second", "rom_name": "dup.sfc"}], "SNES.rdb")
    rom = tmp_path / "dup.sfc"
    rom.write_bytes(b"x")
    assert resolver(tmp_path).resoudre(rom, "snes").nom == "First"


def test_track_marker_still_matches_through_the_index(tmp_path):
    base(tmp_path, [{"name": "Bomberman",
                     "rom_name": "Bomberman (1S) (Track 01).bin"}],
         "Saturn.rdb")
    cue = tmp_path / "Bomberman (1S).cue"
    cue.write_text("x")
    assert resolver(tmp_path).resoudre(cue, "saturn").nom == "Bomberman"


# --- streaming hash --------------------------------------------------------

def test_md5_lookup_never_loads_the_file_whole(tmp_path, monkeypatch):
    content = b"cartridge" * 1000
    base(tmp_path, [{"name": "Hashed (USA)", "rom_name": "Hashed (USA).sfc",
                     "md5": hashlib.md5(content).digest()}], "SNES.rdb")
    rom = tmp_path / "unrelated name.sfc"
    rom.write_bytes(content)

    def forbidden(_):
        raise AssertionError("lecture.octets reads the whole file in memory")
    monkeypatch.setattr(lecture, "octets", forbidden)
    t = resolver(tmp_path).resoudre(rom, "snes")
    assert (t.nom, t.source) == ("Hashed (USA)", "empreinte md5")


def test_a_file_is_hashed_once_per_run(tmp_path, monkeypatch):
    base(tmp_path, [{"name": "A", "rom_name": "a.sfc",
                     "md5": hashlib.md5(b"zzz").digest()}], "SNES.rdb")
    rom = tmp_path / "other.sfc"
    rom.write_bytes(b"not in the base")
    hashed = []
    real = lecture.md5
    monkeypatch.setattr(lecture, "md5", lambda p: hashed.append(p) or real(p))
    r = resolver(tmp_path)
    assert r.resoudre(rom, "snes") is None
    assert r.resoudre(rom, "snes") is None
    assert len(hashed) == 1


def test_a_changed_file_is_hashed_again(tmp_path):
    base(tmp_path, [{"name": "A", "rom_name": "a.sfc",
                     "md5": hashlib.md5(b"version two").digest()}],
         "SNES.rdb")
    rom = tmp_path / "other.sfc"
    rom.write_bytes(b"v1")
    r = resolver(tmp_path)
    assert r.resoudre(rom, "snes") is None
    rom.write_bytes(b"version two")   # same path, new size
    assert r.resoudre(rom, "snes").nom == "A"
