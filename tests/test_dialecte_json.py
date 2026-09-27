"""The JSON dialect: a fragment is a JSON object, and every SCALAR leaf is a
key, its section the path of objects above it ("General" for
{"General": {"console_language": 2}}).

shadPS4 keeps the language games read in user/config.json, and another
emulator in its Config.json: neither has a comment syntax, and both rewrite their whole
file on every save.
"""
import pytest

from retro import dialectes, profiles


def test_les_feuilles_d_un_fragment_json_sont_ses_cles():
    fragment = '{"General": {"console_language": 2, "x": {"y": true}}}'
    assert dialectes.cles_json(fragment) == [
        ("General", "console_language"), ("General/x", "y")]


def test_une_cle_de_premier_niveau_vit_sous_la_section_vide():
    assert dialectes.cles_json('{"system_language": "French"}') == [
        ("", "system_language")]


def test_le_dialecte_d_une_cible_json_est_json():
    assert profiles.dialecte("C:\\x\\Config.json") == "json"
    assert profiles.cles_de("C:\\x\\Config.json", '{"a": 1}') == [("", "a")]


@pytest.mark.parametrize("fragment", [
    "[1, 2]",                       # not an object
    '{"a": [1, 2]}',                # an array would be REPLACED whole
    '{"a": 1',                      # not JSON at all
])
def test_un_fragment_json_qui_ne_se_fusionne_pas_est_refuse(fragment):
    with pytest.raises(ValueError):
        dialectes.valider_json(fragment)


def test_un_fragment_json_valide_passe():
    dialectes.valider_json('{"General": {"console_language": 2}}')
    dialectes.valider_json("{}")


_PROFIL = """
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
target = '%APPDATA%\\\\emu\\\\config.json'
content = '__CONTENU__'
[bootstrap.langue]
repli = "english"
english = '{"General": {"console_language": 1}}'
french = '__FRENCH__'
"""


def _charger(tmp_path, contenu="{}", french='{"General": {"console_language": 2}}'):
    p = tmp_path / "emu.toml"
    p.write_text(_PROFIL.replace("__CONTENU__", contenu)
                 .replace("__FRENCH__", french), encoding="utf-8")
    return profiles.load_profile(p)


def test_une_cible_json_se_passe_d_en_tete_mais_pas_de_json(tmp_path):
    b, = _charger(tmp_path).bootstraps
    assert dict(b.langues)["french"] == '{"General": {"console_language": 2}}'


def test_un_contenu_json_invalide_est_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError, match="content"):
        _charger(tmp_path, contenu="# Écrit par « retro »")


def test_un_fragment_de_langue_json_invalide_est_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError, match="french"):
        _charger(tmp_path, french='{"General": {"console_language": [2]}}')
