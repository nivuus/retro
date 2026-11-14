"""TOML is not INI.

The INI merge writes a marker line starting with ";" (retro-launch.cs), which
a TOML reader rejects, and it knows nothing of TOML strings, arrays or
dotted keys. Until a TOML-aware merge exists, a .toml target is refused when
the profile loads, rather than merged as INI and broken on the console.
"""
import pytest

from retro import profiles

_PROFILE = """
schema = 1
id = "emu"
exe = "emu.exe"
[input]
steam_input = "required"
[exit]
native = ""
fallback = "alt+f4"
[[system]]
id = "ps4"
name = "PlayStation 4"
extensions = [".bin"]
launch = '"{rom}"'
bios = []
[[bootstrap]]
target = '%APPDATA%\\emu\\TARGET'
# The header the package demands of a merged file, as in ppsspp.toml.
content = '''
; Écrit par « retro ». Ce fichier porte TROIS sortes de réglages : ce que la
; console IMPOSE et repose à chaque lancement (la langue), ce qu'elle a posé
; UNE FOIS et ne retouche plus — rien, pour PPSSPP —, et tout le reste, qui
; vous appartient : PPSSPP le réécrit lui-même, et ces commentaires avec.
'''
# A merge, not a one-off copy: only a merged target needs a dialect.
enforced = '''
[General]
x = 1
'''
"""


def _load(tmp_path, target):
    p = tmp_path / "profile.toml"
    p.write_text(_PROFILE.replace("TARGET", target), encoding="utf-8")
    return profiles.load_profile(p)


def test_the_same_profile_with_an_ini_target_loads(tmp_path):
    """Control: only the target's extension differs in the next test."""
    b, = _load(tmp_path, "emu.ini").bootstraps
    assert b.target.endswith("emu.ini")


def test_a_profile_targeting_a_toml_file_is_refused_at_load(tmp_path):
    # The message the package raises for an undeclared extension.
    with pytest.raises(profiles.ProfileError, match="extension inconnue"):
        _load(tmp_path, "emu.toml")


def test_the_dialect_of_a_toml_target_is_unknown():
    with pytest.raises(profiles.ProfileError, match="xemu.toml"):
        profiles.dialecte("%APPDATA%\\xemu\\xemu.toml")
