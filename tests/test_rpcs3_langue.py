"""RPCS3's system language: the one a PS3 game reads, under "System:" in
config.yml. Read at the pinned revision 6567a5a2."""

import importlib.resources
import pathlib

from retro import profiles

PROFIL = (pathlib.Path(str(importlib.resources.files("retro")))
          / "data" / "profiles" / "rpcs3.toml")

# fmt_class_string<CellSysutilLang>::format, Emu/Cell/Modules/cellSysutil.cpp.
# An unknown string is logged and the previous value KEPT: a typo is a game
# in English with one line in RPCS3.log.
VALEURS_RPCS3 = frozenset({
    "Japanese", "English (US)", "French", "Spanish", "German", "Italian",
    "Dutch", "Portuguese (Portugal)", "Russian", "Korean",
    "Chinese (Traditional)", "Chinese (Simplified)", "Finnish", "Swedish",
    "Danish", "Norwegian", "Polish", "English (UK)", "Portuguese (Brazil)",
    "Turkish"})


def _config_yml():
    b, = [b for b in profiles.load_profile(PROFIL).bootstraps
          if b.target.endswith("\\config\\config.yml")]
    return b


def test_rpcs3_pose_la_langue_systeme_sous_la_section_system():
    b = _config_yml()
    for nom, fragment in b.langues:
        assert profiles.cles_de(b.target, fragment) == [
            ("System", "Language")], (nom, fragment)
    assert dict(b.langues)["french"] == "System:\n  Language: French"


def test_rpcs3_ne_pose_que_des_langues_que_rpcs3_connait():
    valeurs = {n: f.split("Language: ", 1)[1]
               for n, f in _config_yml().langues}
    hors = {n: v for n, v in valeurs.items() if v not in VALEURS_RPCS3}
    assert hors == {}, f"rpcs3.toml: strings RPCS3 would ignore: {hors}"
    assert _config_yml().langue_repli == "english"
