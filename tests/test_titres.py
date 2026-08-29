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
    cue.write_bytes(b"FILE")
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
