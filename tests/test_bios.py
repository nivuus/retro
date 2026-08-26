"""Vérification des BIOS que les émulateurs exigent.

Aucun BIOS n'entre dans ce dépôt : les fixtures fabriquent des fichiers
quelconques et calculent leur empreinte à la volée.
"""
import hashlib
import pathlib

import pytest

from retro import bios, profiles

PROFIL = """
schema = 1
id = "retroarch"
exe = "retroarch.exe"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-f "{rom}"'
bios = [
  { file = "scph5501.bin", md5 = "{md5_a}", required = true },
  { file = "scph5502.bin", md5 = "{md5_b}", required = false },
]
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-f "{{rom}}"'
bios = []
"""


def empreinte(contenu: bytes) -> str:
    return hashlib.md5(contenu).hexdigest()


@pytest.fixture
def contexte(tmp_path):
    """Un profil dont les empreintes correspondent à de vrais fichiers."""
    a, b = b"contenu-a", b"contenu-b"
    p = tmp_path / "retroarch.toml"
    p.write_text(
        PROFIL.replace("{md5_a}", empreinte(a)).replace("{md5_b}", empreinte(b)),
        encoding="utf-8",
    )
    racine = tmp_path / "BIOS"
    racine.mkdir()
    return {"retroarch": profiles.load_profile(p)}, racine, a, b


def test_tout_present_est_ok(contexte):
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(a)
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok
    assert psx.missing_required == ()


def test_un_bios_requis_absent(contexte):
    profils, racine, a, b = contexte
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert not psx.ok
    assert psx.missing_required == ("scph5501.bin",)


def test_un_bios_optionnel_absent_ne_bloque_pas(contexte):
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(a)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok
    optionnel = next(f for f in psx.files if f.name == "scph5502.bin")
    assert optionnel.state == "absent"


def test_un_bios_present_mais_faux_est_signale_a_part(contexte):
    """« Corrompu » n'est pas « absent » : le propriétaire CROIT l'avoir mis.
    Lui dire qu'il manque l'enverrait chercher un fichier qui est déjà là."""
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(b"ce n'est pas le bon fichier")
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    requis = next(f for f in psx.files if f.name == "scph5501.bin")
    assert requis.state == "corrompu"
    assert not psx.ok
    assert psx.missing_required == ("scph5501.bin",)


def test_un_systeme_sans_bios_est_toujours_ok(contexte):
    profils, racine, _, _ = contexte
    snes = next(s for s in bios.check_bios(profils, racine) if s.system_id == "snes")
    assert snes.ok and snes.files == ()


def test_racine_absente_rend_tout_absent(contexte):
    """G:\\ non monté est une panne réelle sur cette machine : elle ne doit pas
    lever, elle doit se voir dans le rapport."""
    profils, racine, _, _ = contexte
    psx = next(s for s in bios.check_bios(profils, racine / "jamais")
               if s.system_id == "psx")
    assert not psx.ok
    assert all(f.state == "absent" for f in psx.files)


def test_l_empreinte_est_insensible_a_la_casse(contexte):
    """Les md5 publiés le sont tantôt en majuscules, tantôt en minuscules."""
    profils, racine, a, b = contexte
    for s in profils["retroarch"].systems:
        for f in s.bios:
            f["md5"] = f["md5"].upper()
    (racine / "scph5501.bin").write_bytes(a)
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok


def test_le_nom_de_fichier_est_insensible_a_la_casse(contexte, tmp_path):
    """Le propriétaire dépose ses fichiers depuis Windows, qui ne distingue pas
    la casse ; le scan tourne peut-être sur un système qui la distingue."""
    profils, racine, a, b = contexte
    (racine / "SCPH5501.BIN").write_bytes(a)
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok


def test_un_bios_illisible_ne_leve_pas(contexte):
    """La garantie centrale du module. Un fichier présent mais illisible —
    permissions refusées, partage qui répond sans servir — ne doit pas faire
    échouer le rapport ENTIER pour un seul fichier.

    En root les permissions ne bloquent rien : le test saute plutôt que de
    prétendre vérifier ce qu'il ne vérifie pas.
    """
    import os
    if os.geteuid() == 0:
        pytest.skip("root ignore les permissions : ce test ne prouverait rien")
    profils, racine, a, b = contexte
    illisible = racine / "scph5501.bin"
    illisible.write_bytes(a)
    illisible.chmod(0o000)
    try:
        psx = next(s for s in bios.check_bios(profils, racine)
                   if s.system_id == "psx")
        requis = next(f for f in psx.files if f.name == "scph5501.bin")
        assert requis.state == "corrompu"
    finally:
        illisible.chmod(0o644)


def test_une_racine_illisible_ne_leve_pas(contexte):
    import os
    if os.geteuid() == 0:
        pytest.skip("root ignore les permissions : ce test ne prouverait rien")
    profils, racine, _, _ = contexte
    racine.chmod(0o000)
    try:
        psx = next(s for s in bios.check_bios(profils, racine)
                   if s.system_id == "psx")
        assert all(f.state == "absent" for f in psx.files)
    finally:
        racine.chmod(0o755)


def test_une_racine_qui_est_un_fichier_ne_leve_pas(contexte, tmp_path):
    """Cas réel : le propriétaire crée un fichier au lieu d'un dossier."""
    profils, _, _, _ = contexte
    faux = tmp_path / "BIOS-fichier"
    faux.write_text("pas un dossier", encoding="utf-8")
    psx = next(s for s in bios.check_bios(profils, faux) if s.system_id == "psx")
    assert all(f.state == "absent" for f in psx.files)


def test_un_dossier_portant_le_nom_d_un_bios_ne_compte_pas(contexte):
    profils, racine, _, b = contexte
    (racine / "scph5501.bin").mkdir()
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    requis = next(f for f in psx.files if f.name == "scph5501.bin")
    assert requis.state == "absent"


def test_tous_les_systemes_sont_rendus(contexte):
    profils, racine, _, _ = contexte
    assert {s.system_id for s in bios.check_bios(profils, racine)} == {"psx", "snes"}
