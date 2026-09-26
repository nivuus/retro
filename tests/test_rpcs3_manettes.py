"""RPCS3 poses four players, and only the first one was seen responding.

Kept apart from test_donnees.py, which already holds far more than one
concern. The frozen content of Default.yml is guarded there, by
`RPCS3_MANETTE`; this file guards what the profile SAYS about it.
"""

import importlib.resources
import pathlib

from retro import profiles

PROFIL = (pathlib.Path(str(importlib.resources.files("retro")))
          / "data" / "profiles" / "rpcs3.toml")


def test_rpcs3_dit_que_seul_le_joueur_1_a_ete_vu():
    """`releve` requires a human witness, and there was one for player 1
    only. Players 2 to 4 are merely posed; `mapping` holds one value per
    profile, so the reservation lives in `mapping_where`, which
    `retro status` prints verbatim. Dropping it would claim a measurement
    nobody made."""
    p = profiles.load_profile(PROFIL)
    assert p.input_mapping == profiles.MAPPING_RELEVE
    reserve = ("seul le joueur 1 a été VU répondre, les joueurs 2 à 4 sont "
               "posés et jamais essayés")
    assert reserve in p.input_mapping_where, (
        "rpcs3.toml: mapping_where no longer says that players 2 to 4 were "
        f"never seen responding — {p.input_mapping_where}")
