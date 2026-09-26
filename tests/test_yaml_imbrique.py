"""The YAML dialect reads TWO levels: a top-level mapping of mappings, the
shape of RPCS3's config.yml ("System:" then "  Language: French").

Flat YAML (Vita3K's config.yml) must read exactly as before: a top-level
"key: value" stays under the empty section, and "key:" followed by a
sequence stays a key.
"""

from retro import profiles


def test_une_section_yaml_porte_ses_cles_indentees():
    fragment = "System:\n  Language: French\n  License Area: SCEE\n"
    assert profiles.cles_yaml(fragment) == [
        ("System", "Language"), ("System", "License Area")]


def test_un_troisieme_niveau_n_est_pas_une_cle_de_la_section():
    """"    Adapter: X" under "  Vulkan:" belongs to Vulkan, not to Video.
    Reading it as (Video, Adapter) would pose a key no reader attaches
    there — the silent failure the flat dialect was written against."""
    fragment = ("Video:\n  Renderer: Vulkan\n  Vulkan:\n"
                "    Adapter: X\n  Frame limit: Auto\n")
    assert profiles.cles_yaml(fragment) == [
        ("Video", "Renderer"), ("Video", "Vulkan"), ("Video", "Frame limit")]


def test_une_cle_plate_apres_une_section_revient_a_la_section_vide():
    fragment = "System:\n  Language: French\nwarn-missing-firmware: false\n"
    assert profiles.cles_yaml(fragment) == [
        ("System", "Language"), ("", "warn-missing-firmware")]


def test_une_cle_suivie_d_une_sequence_reste_une_cle_plate():
    assert profiles.cles_yaml("lle-modules:\n  - libscemp4\n") == [
        ("", "lle-modules")]


def test_une_cle_vide_en_fin_de_fragment_reste_une_cle_plate():
    assert profiles.cles_yaml("pref-path:\n") == [("", "pref-path")]
