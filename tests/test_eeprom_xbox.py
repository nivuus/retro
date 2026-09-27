"""The Xbox EEPROM: a `.bin` target whose language the launcher patches.

xemu reads the language games see from its EEPROM image, which it
generates itself with the console's serial number and hard-disk key. An
entry aimed at it therefore carries a language table and nothing else, and
its fragments are "language = <XC_LANGUAGE code>".
"""
import pathlib

import pytest

from retro import dialectes, launcher, profiles

PROFILS = pathlib.Path(__file__).parent.parent / "retro" / "data" / "profiles"

PROFIL = """
schema = 1
id = "emu"
exe = "emu.exe"

[input]
steam_input = "required"

[exit]
native = ""
fallback = "alt+f4"

[[system]]
id = "xbox"
name = "Xbox"
extensions = [".iso"]
launch = '-dvd_path "{rom}"'
bios = []

[[bootstrap]]
target = '%APPDATA%\\\\emu\\\\eeprom.bin'
__EXTRA__
[bootstrap.langue]
repli = "english"
english = "language = 1"
french = "language = 4"
"""


def _profil(tmp_path, extra="", texte=None):
    p = tmp_path / "emu.toml"
    p.write_text(texte or PROFIL.replace("__EXTRA__", extra), encoding="utf-8")
    return profiles.load_profile(p)


def test_le_dialecte_d_une_cible_bin_est_l_eeprom_xbox():
    assert profiles.dialecte("C:\\x\\eeprom.bin") == "xbox-eeprom"


@pytest.mark.parametrize("fragment", [
    "language = 0", "language = 10", "language = fr", "language = -4",
    "video = 1", "language = 4\nvideo = 1", "[user]\nlanguage = 4", ""])
def test_un_fragment_d_eeprom_hors_de_la_seule_cle_langue_est_refuse(fragment):
    with pytest.raises(ValueError):
        dialectes.valider_eeprom(fragment)


def test_chaque_code_xc_language_passe():
    for code in dialectes.XBOX_LANGUAGES:
        dialectes.valider_eeprom(f"language = {code}")


def test_une_entree_eeprom_ne_porte_qu_une_table_de_langues(tmp_path):
    b, = _profil(tmp_path).bootstraps
    assert b.content == "" and b.enforced == ""
    assert dict(b.langues)["french"] == "language = 4"


@pytest.mark.parametrize("extra", [
    "content = '; Written by retro'", "enforced = 'language = 4'",
    'content = ""', 'enforced = ""', 'langue_absente = ""'])
def test_une_eeprom_ne_se_pose_ni_ne_s_impose(tmp_path, extra):
    """xemu generates the image with this console's keys: a posed one would
    carry none, and the launcher writes nothing but the language."""
    with pytest.raises(profiles.ProfileError, match="EEPROM"):
        _profil(tmp_path, extra)


def test_une_eeprom_sans_table_de_langues_est_refusee(tmp_path):
    texte = PROFIL.replace("__EXTRA__", "")
    texte = texte[:texte.index("[bootstrap.langue]")]
    with pytest.raises(profiles.ProfileError, match="langue"):
        _profil(tmp_path, texte=texte)


def test_un_code_hors_table_est_refuse_a_la_lecture_du_profil(tmp_path):
    texte = PROFIL.replace("__EXTRA__", "").replace(
        'french = "language = 4"', 'french = "language = 12"')
    with pytest.raises(profiles.ProfileError, match="XC_LANGUAGE"):
        _profil(tmp_path, texte=texte)


def test_le_plan_n_a_aucun_fichier_a_poser_et_des_fragments_texte(tmp_path):
    pr = _profil(tmp_path)
    plan = launcher.plan_systeme("emu", pr.systems[0], "D:\\Emu\\emu.exe",
                                 "D:\\Emu", "D:\\Plans",
                                 bootstraps=pr.bootstraps)
    lignes = dict(l.split("=", 1) for l in plan.splitlines() if "=" in l)
    assert lignes["bootstrap_source.1"] == ""
    assert lignes["bootstrap_enforced.1"] == ""
    assert lignes["bootstrap_langue.1.french"] == \
        "D:\\Plans\\emu.langue.1.french.txt"
    fragments = launcher.fragments_attendus("emu", 1, pr.bootstraps[0])
    assert all(not nom.endswith(".bin") for nom, _ in fragments)


def test_le_profil_xemu_pose_la_langue_de_l_eeprom():
    xemu = profiles.load_profiles(PROFILS)["xemu"]
    b, = xemu.bootstraps
    assert b.target.endswith("\\xemu\\xemu\\eeprom.bin")
    langues = dict(b.langues)
    assert langues["french"] == "language = 4"
    assert langues["english"] == "language = 1"
    assert b.langue_repli == "english"


def test_le_lanceur_ne_touche_que_la_langue_et_sa_somme():
    """Read in the source: no C# compiler on this host. The offsets are
    xemu's (hw/xbox/eeprom_generation.h): user checksum at 0x60 over the
    0x5C bytes from 0x64, language at 0x90."""
    src = (launcher.SOURCES / launcher.SOURCE_EEPROM).read_text(
        encoding="utf-8-sig")
    for constante in ("SOMME_UTILISATEUR = 0x60", "SECTION_UTILISATEUR = 0x64",
                      "LONGUEUR_UTILISATEUR = 0x5C", "LANGUE = 0x90"):
        assert constante in src
    assert launcher.SOURCE_EEPROM in launcher.SOURCES_CS


def test_une_table_de_langue_qui_n_est_pas_une_table_est_une_erreur_de_profil(
        tmp_path):
    texte = PROFIL.replace("__EXTRA__", "")
    texte = texte[:texte.index("[bootstrap.langue]")] + 'langue = "french"\n'
    with pytest.raises(profiles.ProfileError):
        _profil(tmp_path, texte=texte)
