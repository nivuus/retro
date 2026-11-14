"""Le VRAI titre d'un jeu, quand son nom de fichier n'en est pas un.

Aucune base reelle ni aucune ROM n'entre dans ce depot : les fixtures
fabriquent les deux.
"""
import hashlib
import struct
import zipfile

import pytest

from retro import rdb, titres
from tests.test_rdb import base

TABLE = {
    "arcade": {"base": "Arcade", "serie": ""},
    "snes": {"base": "SNES", "serie": ""},
    "gamecube": {"base": "GC", "serie": "disque-nintendo"},
    "saturn": {"base": "Saturn", "serie": "saturn"},
}


def resolveur(tmp_path, table=None):
    return titres.Resolveur(tmp_path, table if table is not None else TABLE)


# --- les trois cles --------------------------------------------------------

def test_le_nom_du_romset_reconnait_un_jeu_d_arcade(tmp_path):
    """« mslug2.zip » EST Metal Slug 2 : pour l'arcade, le nom du romset est
    l'identite meme du jeu, et c'est le seul systeme ou c'est vrai."""
    base(tmp_path, [{"name": "Metal Slug 2", "rom_name": "mslug2.zip"}],
         "Arcade.rdb")
    rom = tmp_path / "mslug2.zip"
    rom.write_bytes(b"peu importe")
    t = resolveur(tmp_path).resoudre(rom, "arcade")
    assert (t.nom, t.source) == ("Metal Slug 2", "nom de fichier")


def test_l_empreinte_reconnait_un_dump_autrement_nomme(tmp_path):
    """La cle la plus forte : elle ne depend d'AUCUN nom. C'est elle qui
    rattrape un dump GoodTools la ou la base porte un nom No-Intro."""
    contenu = b"la cartouche"
    base(tmp_path, [{"name": "Space Invaders (USA)",
                     "rom_name": "Space Invaders (USA).a26",
                     "md5": hashlib.md5(contenu).digest()}], "SNES.rdb")
    rom = tmp_path / "Space Invaders (1978) (Atari) [!].a26"
    rom.write_bytes(contenu)
    t = resolveur(tmp_path).resoudre(rom, "snes")
    assert (t.nom, t.source) == ("Space Invaders (USA)", "empreinte md5")


def test_l_empreinte_se_lit_en_octets_bruts_comme_en_hexadecimal(tmp_path):
    """MESURE, et c'est un piege : les bases ne s'accordent pas. FBNeo stocke
    une chaine hexadecimale, Saturn et DS les SEIZE OCTETS BRUTS. Les lire
    toutes comme du texte donnait du charabia — donc aucune correspondance,
    et l'echec etait muet."""
    brut = hashlib.md5(b"x").digest()
    assert titres.empreinte_fiche(brut) == brut.hex()
    assert titres.empreinte_fiche(brut.hex()) == brut.hex()


def test_la_serie_gravee_dans_l_image_reconnait_un_disque(tmp_path):
    """Ce qui rattrape « Crash Team Racing-PSX-PAL.cue », qu'aucun nom ne
    reconnait : ses octets disent SCES-02105."""
    base(tmp_path, [{"name": "Simpsons, The - Hit & Run (USA)",
                     "rom_name": "autre chose.iso", "serial": "GHQE7D"}],
         "GC.rdb")
    iso = tmp_path / "un nom quelconque.iso"
    iso.write_bytes(b"GHQE7D" + b"\x00" * 100)
    t = resolveur(tmp_path).resoudre(iso, "gamecube")
    assert t.nom == "Simpsons, The - Hit & Run (USA)"
    assert t.source.startswith("série GHQE7D")


# --- ce qui doit REFUSER ---------------------------------------------------

def test_une_serie_ambigue_ne_renomme_rien(tmp_path):
    """Les bases Sega omettent le prefixe de l'editeur, d'ou la tolerance au
    suffixe. Mais deux fiches candidates, c'est une ambiguite — et renommer un
    jeu d'apres une ambiguite est PIRE que ne pas le renommer."""
    piste = tmp_path / "jeu (Track 01).bin"
    piste.write_bytes(b"\x00" * 16 + b"SEGA SEGASATURN" + b"\x00" * 17
                      + b"MK81070   " + b"\x00" * 64)
    base(tmp_path, [{"name": "Un", "rom_name": "un.bin", "serial": "81070"},
                    {"name": "Deux", "rom_name": "deux.bin", "serial": "81070"}],
         "Saturn.rdb")
    cue = tmp_path / "jeu.cue"
    # The cue must name its track, or the refusal would come from finding
    # no track at all rather than from the ambiguity under test.
    cue.write_bytes(b'FILE "jeu (Track 01).bin" BINARY\n')
    assert titres._pistes(cue) == [piste]
    assert resolveur(tmp_path).resoudre(cue, "saturn") is None


def test_un_jeu_inconnu_garde_son_nom_de_fichier(tmp_path):
    base(tmp_path, [{"name": "Autre", "rom_name": "autre.zip"}], "Arcade.rdb")
    rom = tmp_path / "inconnu.zip"
    rom.write_bytes(b"x")
    assert resolveur(tmp_path).resoudre(rom, "arcade") is None


def test_sans_dossier_de_bases_rien_n_est_resolu_et_rien_ne_leve(tmp_path):
    """La console qui n'a pas RetroArch garde ses noms de fichiers : c'est le
    comportement d'avant, et ce n'est pas une panne."""
    rom = tmp_path / "mslug2.zip"
    rom.write_bytes(b"x")
    assert titres.Resolveur(None, TABLE).resoudre(rom, "arcade") is None


def test_une_base_abimee_n_emporte_pas_l_inventaire(tmp_path):
    """Le pire qu'il puisse arriver est que les jeux gardent leur nom."""
    (tmp_path / "Arcade.rdb").write_bytes(b"PAS-UNE-BASE" + b"\x00" * 32)
    rom = tmp_path / "mslug2.zip"
    rom.write_bytes(b"x")
    r = resolveur(tmp_path)
    assert r.resoudre(rom, "arcade") is None
    assert r.echecs and "Arcade" in r.echecs[0]


# --- la table des bases ----------------------------------------------------

def test_la_table_livree_se_charge():
    t = titres.charger_table()
    assert t["arcade"]["base"] == "FBNeo - Arcade Games"
    assert all(v["serie"] in ("",) + titres.SERIES for v in t.values())


def test_une_serie_hors_vocabulaire_est_refusee(tmp_path):
    """Une valeur inconnue serait ignoree en silence, et le jeu resterait sous
    son nom de fichier sans que rien ne l'explique."""
    f = tmp_path / "d.toml"
    f.write_text('schema = 1\n[systeme.x]\nbase = "B"\nserie = "inventee"\n',
                 encoding="utf-8")
    with pytest.raises(titres.TitreError, match="serie"):
        titres.charger_table(f)


def test_une_base_vide_est_refusee(tmp_path):
    f = tmp_path / "d.toml"
    f.write_text('schema = 1\n[systeme.x]\nbase = ""\n', encoding="utf-8")
    with pytest.raises(titres.TitreError, match="'base'"):
        titres.charger_table(f)


def test_chaque_serie_declaree_a_son_extracteur():
    """Une famille declaree sans extracteur ferait echouer la resolution par
    KeyError au milieu d'un scan, sur une seule machine, un seul jeu."""
    assert set(titres.SERIES) == set(titres.EXTRACTEURS)


def test_le_marqueur_de_piste_se_retire_du_nom_de_la_base():
    """Un jeu sur disque y est indexe par sa PISTE 1 alors que le scan voit le
    .cue qui les rassemble. Sans ce retrait, aucun multipiste ne se reconnait."""
    assert titres.tige_de_fiche("Saturn Bomberman (USA) (1S) (Track 01).bin") \
        == "saturn bomberman (usa) (1s)"


def test_deux_series_se_comparent_sans_ponctuation():
    assert titres.normaliser_serie("SLES_527.25") \
        == titres.normaliser_serie("SLES-52725")


# --- descriptor files name their own tracks ---------------------------------

def _saturn_track(path, serial, padding=0):
    path.write_bytes(b"\x00" * 16 + b"SEGA SEGASATURN" + b"\x00" * 17
                     + serial.ljust(10).encode() + b"\x00" * (64 + padding))


def test_a_cue_sheet_is_read_from_the_tracks_it_names(tmp_path):
    """Two games share a folder. The unrecognised cue names the SMALLER image:
    picking the largest image of the folder would title it after its
    neighbour."""
    _saturn_track(tmp_path / "game a (Track 01).bin", "T-1111")
    _saturn_track(tmp_path / "game b (Track 01).bin", "T-2222", padding=4096)
    base(tmp_path, [{"name": "Game A (Japan)", "rom_name": "x.bin", "serial": "T-1111"},
                    {"name": "Game B (Japan)", "rom_name": "y.bin", "serial": "T-2222"}],
         "Saturn.rdb")
    cue = tmp_path / "unknown dump.cue"
    cue.write_text('FILE "game a (Track 01).bin" BINARY\n'
                   '  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n')
    t = resolveur(tmp_path).resoudre(cue, "saturn")
    assert t is not None and t.nom == "Game A (Japan)"


def test_cue_file_entries_are_listed_in_order(tmp_path):
    for name in ("d1.bin", "d2 audio.bin"):
        (tmp_path / name).write_bytes(b"x")
    cue = tmp_path / "g.cue"
    cue.write_text('﻿FILE "d1.bin" BINARY\n  TRACK 01 MODE2/2352\n'
                   'file "d2 audio.bin" BINARY\n  TRACK 02 AUDIO\n'
                   'FILE "missing.bin" BINARY\n')
    assert [p.name for p in titres._pistes(cue)] == ["d1.bin", "d2 audio.bin"]


def test_cue_names_in_any_script_are_read(tmp_path):
    name = "ゲーム (Track 01).bin"
    (tmp_path / name).write_bytes(b"x")
    cue = tmp_path / "g.cue"
    cue.write_text(f'FILE "{name}" BINARY\n', encoding="utf-8")
    assert [p.name for p in titres._pistes(cue)] == [name]


def test_a_gdi_is_read_from_its_file_column(tmp_path):
    for name, size in (("track01.bin", 10), ("track 02.raw", 50), ("track03.bin", 30)):
        (tmp_path / name).write_bytes(b"x" * size)
    (tmp_path / "other game.bin").write_bytes(b"x" * 999)
    gdi = tmp_path / "g.gdi"
    gdi.write_text('3\n1 0 4 2352 track01.bin 0\n'
                   '2 756 0 2352 "track 02.raw" 0\n'
                   '3 45000 4 2352 track03.bin 0\n')
    # Largest first among the descriptor's own files, as before.
    assert [p.name for p in titres._pistes(gdi)] == [
        "track 02.raw", "track03.bin", "track01.bin"]


def test_an_m3u_is_read_from_the_discs_it_lists(tmp_path):
    (tmp_path / "disc1.bin").write_bytes(b"x")
    (tmp_path / "disc2.bin").write_bytes(b"x" * 100)
    (tmp_path / "disc1.cue").write_text('FILE "disc1.bin" BINARY\n')
    (tmp_path / "disc2.cue").write_text('FILE "disc2.bin" BINARY\n')
    m3u = tmp_path / "g.m3u"
    m3u.write_text("#EXTM3U\ndisc1.cue\n\ndisc2.cue\n")
    assert [p.name for p in titres._pistes(m3u)] == ["disc1.bin", "disc2.bin"]


def test_a_ccd_is_read_from_its_same_stem_image(tmp_path):
    (tmp_path / "g.img").write_bytes(b"x")
    (tmp_path / "other.img").write_bytes(b"x" * 100)
    ccd = tmp_path / "g.ccd"
    ccd.write_text("[CloneCD]\nVersion=3\n")
    assert [p.name for p in titres._pistes(ccd)] == ["g.img"]


def test_a_descriptor_naming_nothing_falls_back_to_same_stem_images(tmp_path):
    (tmp_path / "g.bin").write_bytes(b"x")
    (tmp_path / "neighbour.bin").write_bytes(b"x" * 100)
    cue = tmp_path / "g.cue"
    cue.write_bytes(b"\xff\xfe garbage")
    assert [p.name for p in titres._pistes(cue)] == ["g.bin"]
