"""PPSSPP's language bootstrap: one table drives the interface and, through
GameLanguage = -1, the language games read. Read at v1.20.4 (fa50bb1)."""

import importlib.resources
import pathlib

from retro import langue, profiles

PROFIL = (pathlib.Path(str(importlib.resources.files("retro")))
          / "data" / "profiles" / "ppsspp.toml")

# assets\lang\*.ini of the pinned install, listed on the console on
# 2026-09-26. A code outside this list names no translation: PPSSPP falls
# back to English and nothing says why.
LANGUES_LIVREES = frozenset("""
ar_AE az_AZ be_BY bg_BG ca_ES cz_CZ da_DK de_DE dr_ID en_US es_ES es_LA
fa_IR fi_FI fr_FR gl_ES gr_EL he_IL he_IL_invert hr_HR hu_HU id_ID it_IT
ja_JP jv_ID ko_KR ku_SO lo_LA lt-LT ms_MY nl_NL no_NO pl_PL pt_BR pt_PT
ro_RO ru_RU sv_SE tg_PH th_TH tr_TR uk_UA vi_VN zh_CN zh_TW
""".split())


def _amorcage():
    b, = profiles.load_profile(PROFIL).bootstraps
    return b


def test_ppsspp_couvre_toutes_les_langues_de_steam_par_un_fichier_livre():
    langues = dict(_amorcage().langues)
    assert sorted(langues) == sorted(langue.LANGUES), (
        "ppsspp.toml: the table no longer covers every Steam language")
    codes = {n: f.split("Language = ")[1] for n, f in langues.items()}
    hors = {n: c for n, c in codes.items() if c not in LANGUES_LIVREES}
    assert hors == {}, f"ppsspp.toml: codes with no shipped file: {hors}"
    assert codes["french"] == "fr_FR"


def test_ppsspp_laisse_le_jeu_suivre_l_interface():
    """GameLanguage = -1 is what makes the interface table reach the games
    (GetPSPLanguage, langregion.ini). A fixed value would win over the
    console's language."""
    b = _amorcage()
    assert b.target == "{install_dir}\\memstick\\PSP\\SYSTEM\\ppsspp.ini"
    lignes = [l.strip() for l in b.enforced.splitlines() if l.strip()]
    assert lignes == ["[SystemParam]", "GameLanguage = -1"], lignes
