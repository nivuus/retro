"""A launch option that follows the console language: `{langue}` in a
system's `launch`, and the `[system.langue]` table that says what it becomes.

Some emulators take their language only on the command line — Dolphin's
Wii reads its NAND, not Dolphin.ini (`-C SYSCONF.IPL.LNG=`), KytyPS5 reads
`--console-language`. The table is resolved in Python for EVERY Steam
language, fallback included, exactly like the bootstrap language lines: the
launcher reads one line and decides nothing.
"""
import pathlib

import pytest

from retro import launcher, profiles

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
id = "wii"
name = "Wii"
extensions = [".iso"]
launch = '-b {langue} -e "{rom}"'
bios = []
__LANGUE__
"""

TABLE = """
[system.langue]
repli = "english"
english = "-C SYSCONF.IPL.LNG=1"
french = "-C SYSCONF.IPL.LNG=3"
"""


def _profil(tmp_path, launch=None, table=TABLE):
    texte = PROFIL.replace("__LANGUE__", table)
    if launch is not None:
        texte = texte.replace("-b {langue} -e \"{rom}\"", launch)
    p = tmp_path / "emu.toml"
    p.write_text(texte, encoding="utf-8")
    return profiles.load_profile(p)


def test_la_table_de_langue_d_un_systeme_est_lue(tmp_path):
    s, = _profil(tmp_path).systems
    assert dict(s.langue_args) == {"english": "-C SYSCONF.IPL.LNG=1",
                                   "french": "-C SYSCONF.IPL.LNG=3"}
    assert s.langue_repli == "english"


def test_un_jeton_langue_sans_table_est_refuse(tmp_path):
    """The token would reach the emulator's command line as is."""
    with pytest.raises(profiles.ProfileError, match="langue"):
        _profil(tmp_path, table="")


def test_une_table_sans_jeton_langue_est_refusee(tmp_path):
    """A table nothing reads looks like a language that follows Steam."""
    with pytest.raises(profiles.ProfileError, match="langue"):
        _profil(tmp_path, launch='-b -e "{rom}"')


def test_un_nom_qui_n_est_pas_une_langue_de_steam_est_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError, match="fr"):
        _profil(tmp_path, table=TABLE + 'fr = "-C SYSCONF.IPL.LNG=3"\n')


def test_un_repli_non_declare_est_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError, match="repli"):
        _profil(tmp_path, table=TABLE.replace('repli = "english"',
                                              'repli = "german"'))


def test_une_option_vide_est_refusee(tmp_path):
    """An empty value would launch the game with the emulator's own
    language while `retro status` announces the table's."""
    with pytest.raises(profiles.ProfileError, match="empty"):
        _profil(tmp_path, table=TABLE + 'german = ""\n')


def test_le_plan_porte_une_ligne_par_langue_de_steam_replis_resolus(tmp_path):
    s, = _profil(tmp_path).systems
    plan = launcher.plan_systeme("emu", s, "D:\\Emu\\emu.exe", "D:\\Emu")
    lignes = dict(l.split("=", 1) for l in plan.splitlines()
                  if l.startswith("langue_args."))
    assert lignes["langue_args.french"] == "-C SYSCONF.IPL.LNG=3"
    # Not declared: the fallback, already resolved.
    assert lignes["langue_args.german"] == "-C SYSCONF.IPL.LNG=1"
    # Steam silent.
    assert lignes["langue_args.defaut"] == "-C SYSCONF.IPL.LNG=1"
    from retro import langue
    assert len(lignes) == len(langue.LANGUES) + 1


def test_un_systeme_sans_table_n_ecrit_aucune_ligne(tmp_path):
    s, = _profil(tmp_path, launch='-b -e "{rom}"', table="").systems
    plan = launcher.plan_systeme("emu", s, "D:\\Emu\\emu.exe", "D:\\Emu")
    assert not [l for l in plan.splitlines() if l.startswith("langue_args.")]


def test_le_lanceur_substitue_le_jeton_langue():
    """Read in the source: no C# compiler on this host. The substitution
    must happen in the same chain as {render}, before the double spaces are
    collapsed, and read the plan line — never decide a fallback."""
    src = (launcher.SOURCES / launcher.SOURCE).read_text(encoding="utf-8-sig")
    chaine = src[src.index('string commande = Valeur(p, "launch")'):]
    chaine = chaine[:chaine.index(";")]
    assert '.Replace("{langue}", ArgumentsDeLangue(p, langueDuLancement))' \
        in chaine
    assert chaine.index("{langue}") < chaine.index('.Replace("  ", " ")')
    assert '"langue_args."' in src


def test_le_rapport_dit_la_langue_de_l_option_de_lancement():
    """Dolphin's Wii language lives on its command line; without its own
    line, the report would only show Dolphin.ini — the GameCube's."""
    from retro import status
    profils = profiles.load_profiles(
        pathlib.Path(__file__).parent.parent / "retro" / "data" / "profiles")
    etats = status.etat_langues(profils, "french")
    wii = [e for e in etats if e.profile_id == "dolphin"
           and "option de lancement" in e.cible]
    assert [(e.cible, e.langue) for e in wii] == [
        ("option de lancement, Wii", "french")]
