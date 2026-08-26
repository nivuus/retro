"""Les profils : comment on parle à un émulateur.

C'est l'abstraction qui doit permettre au sous-projet D d'ajouter dix
émulateurs sans rouvrir une ligne de code. Tout ce qui est propre à un
émulateur vit dans son TOML.
"""
import pathlib

import pytest

from retro import profiles

RETROARCH = """
schema = 1
id = "retroarch"
exe = "retroarch.exe"

[input]
steam_input = "required"

[exit]
native = "Select+Start"
fallback = "alt+f4"

[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue", ".chd", ".m3u"]
launch = '-L "cores\\\\swanstation_libretro.dll" -f "{rom}"'
bios = [{ file = "scph5501.bin", sha1 = "abc", required = true }]

[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc", ".smc"]
launch = '-L "cores\\\\snes9x_libretro.dll" -f "{rom}"'
bios = []
"""


def ecrire(tmp_path, nom, contenu):
    p = tmp_path / nom
    p.write_text(contenu, encoding="utf-8")
    return p


def test_charge_un_profil(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "retroarch.toml", RETROARCH))
    assert p.id == "retroarch"
    assert p.exe == "retroarch.exe"
    assert len(p.systems) == 2


def test_les_systemes_portent_leurs_extensions(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    psx = next(s for s in p.systems if s.id == "psx")
    assert psx.extensions == (".cue", ".chd", ".m3u")
    assert psx.name == "PlayStation"


def test_les_bios_sont_declares(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    psx = next(s for s in p.systems if s.id == "psx")
    assert psx.bios[0]["file"] == "scph5501.bin"
    snes = next(s for s in p.systems if s.id == "snes")
    assert snes.bios == ()


def test_la_sortie_est_declaree(tmp_path):
    """Sans hotkey de sortie, un émulateur lancé à la manette immobilise la
    console jusqu'au redémarrage de la VM."""
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    assert p.exit_native == "Select+Start"
    assert p.exit_fallback == "alt+f4"


def test_launch_sans_rom_est_refuse(tmp_path):
    """Un gabarit sans {rom} lance l'émulateur sans jeu : il s'ouvre sur son
    propre menu, la console a l'air de marcher, et rien ne le signale."""
    mauvais = RETROARCH.replace('-f "{rom}"', "-f")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "{rom}" in str(exc.value) and "psx" in str(exc.value)


def test_extensions_vides_refusees(tmp_path):
    """Un système sans extension ne peut rien matcher : il serait absent de la
    bibliothèque sans que rien ne le dise."""
    mauvais = RETROARCH.replace('extensions = [".sfc", ".smc"]', "extensions = []")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "snes" in str(exc.value)


def test_extension_sans_point_refusee(tmp_path):
    """Le scan compare à Path.suffix, qui porte toujours son point."""
    mauvais = RETROARCH.replace('[".sfc", ".smc"]', '["sfc"]')
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "sfc" in str(exc.value)


def test_deux_systemes_de_meme_id_refuses(tmp_path):
    mauvais = RETROARCH.replace('id = "snes"', 'id = "psx"')
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))


def test_schema_inconnu_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "r.toml", "schema = 99\nid = 'x'\n"))


def test_charge_un_dossier(tmp_path):
    d = tmp_path / "profiles"
    d.mkdir()
    (d / "retroarch.toml").write_text(RETROARCH, encoding="utf-8")
    (d / "notes.txt").write_text("ignoré", encoding="utf-8")
    tous = profiles.load_profiles(d)
    assert set(tous) == {"retroarch"}


def test_dossier_vide_leve(tmp_path):
    """Aucun profil = aucun jeu ne peut être lancé. Ce n'est pas un état
    normal, c'est un paquet cassé."""
    d = tmp_path / "vide"
    d.mkdir()
    with pytest.raises(profiles.ProfileError):
        profiles.load_profiles(d)
