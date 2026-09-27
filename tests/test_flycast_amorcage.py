"""Flycast's emu.cfg bootstrap: the three extra Dreamcast ports, and the
language games read. Every value was read in the source at v2.7 (5aa091fd).
"""

import importlib.resources
import pathlib

from retro import profiles

PROFIL = (pathlib.Path(str(importlib.resources.files("retro")))
          / "data" / "profiles" / "flycast.toml")


def _amorcage():
    b, = profiles.load_profile(PROFIL).bootstraps
    return b


def test_flycast_ouvre_les_trois_autres_prises():
    """device2..device4 default to MDT_None (core/cfg/option.cpp): a gamepad
    assigned to port B, C or D reads nothing. 0 is MDT_SegaController
    (core/hw/maple/maple_cfg.h), an INTEGER — the option is loaded with
    loadInt, so a name would silently fall back to None."""
    b = _amorcage()
    assert b.target == "{install_dir}\\emu.cfg"
    lignes = [l.strip() for l in b.enforced.splitlines() if l.strip()]
    assert lignes == ["[input]", "device2 = 0", "device3 = 0",
                      "device4 = 0"], lignes


def test_flycast_pose_le_francais_que_les_jeux_lisent():
    """French is 3 for the Dreamcast, not 2: the index order is JA, EN, DE,
    FR, ES, IT (core/ui/settings_general.cpp). A wrong integer is not an
    invalid value, it is ANOTHER language."""
    langues = dict(_amorcage().langues)
    assert langues["french"] == ("[config]\nDreamcast.Language = 3\n"
                                 "UILanguage = fr")
    assert langues["german"].startswith("[config]\nDreamcast.Language = 2\n")
    systeme = {n: int(f.split("Dreamcast.Language = ")[1].split("\n")[0])
               for n, f in langues.items()}
    # nvmem.cpp only writes values <= 5 into the flash.
    assert all(0 <= v <= 5 for v in systeme.values()), systeme


def test_flycast_retombe_sur_l_anglais():
    """The Dreamcast knows six languages; every other Steam language must
    land on a declared fallback, never on a value Flycast would ignore."""
    assert _amorcage().langue_repli == "english"
