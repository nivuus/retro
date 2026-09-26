"""DuckStation poses two ports, and only the first one was seen responding.

The frozen [Pad1]/[Pad2] content is guarded in test_donnees.py
(`DUCKSTATION_IMPOSE`); this file guards what the profile SAYS about it.
"""

import importlib.resources
import pathlib

from retro import profiles

PROFIL = (pathlib.Path(str(importlib.resources.files("retro")))
          / "data" / "profiles" / "duckstation.toml")


def test_duckstation_dit_que_seul_le_joueur_1_a_ete_vu():
    """`releve` requires a human witness, and there was one for player 1
    only (Crash Team Racing, 2026-08-29). Port 2 is merely posed; the
    reservation lives in `mapping_where`, which `retro status` prints
    verbatim."""
    p = profiles.load_profile(PROFIL)
    assert p.input_mapping == profiles.MAPPING_RELEVE
    reserve = ("seul le joueur 1 a été VU répondre, le joueur 2 est posé et "
               "jamais essayé")
    assert reserve in p.input_mapping_where, (
        "duckstation.toml: mapping_where no longer says that player 2 was "
        f"never seen responding — {p.input_mapping_where}")
