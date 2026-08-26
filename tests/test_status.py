"""Le rapport lisible. Ne modifie jamais rien."""
import pathlib

import pytest

from retro import bios, status


def test_un_emulateur_installe_est_signale_avec_sa_version(tmp_path):
    emu = tmp_path / "RetroArch"
    emu.mkdir()
    (emu / ".retro-version").write_text("1.22.2\n", encoding="utf-8")
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[], bios_status=[])
    assert ("retroarch", "1.22.2") in r.emulators


def test_un_emulateur_absent_est_un_probleme(tmp_path):
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[], bios_status=[])
    assert ("retroarch", "absent") in r.emulators
    assert any("retroarch" in p for p in r.problems)


def test_les_bios_manquants_sont_des_problemes():
    manquant = bios.SystemBios(
        system_id="psx", system_name="PlayStation",
        files=(bios.BiosFile("scph5501.bin", "abc", True, "absent"),))
    r = status.build_report(install_dirs={}, emulation_root=pathlib.Path("."),
                            systems=[], bios_status=[manquant])
    assert any("scph5501.bin" in p for p in r.problems)


def test_un_bios_corrompu_se_distingue_d_un_bios_absent():
    """Le propriétaire CROIT l'avoir déposé : le message doit le lui dire."""
    corrompu = bios.SystemBios(
        system_id="psx", system_name="PlayStation",
        files=(bios.BiosFile("scph5501.bin", "abc", True, "corrompu"),))
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[corrompu]))
    assert "corrompu" in texte.lower()
    assert "scph5501.bin" in texte


def test_le_rapport_compte_les_jeux_par_systeme():
    r = status.build_report(install_dirs={}, emulation_root=pathlib.Path("."),
                            systems=[("Super Nintendo", 142)], bios_status=[])
    assert ("Super Nintendo", 142) in r.systems
    assert "142" in status.format_report(r)


def test_sans_probleme_le_rapport_le_dit():
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[("Super Nintendo", 1)], bios_status=[]))
    assert "aucun" in texte.lower()


def test_le_rapport_ne_modifie_rien(tmp_path):
    """`status` est consultatif : rien de ce qu'il touche ne doit changer."""
    avant = sorted(p.name for p in tmp_path.rglob("*"))
    status.build_report(install_dirs={"x": "X"}, emulation_root=tmp_path,
                        systems=[], bios_status=[])
    assert sorted(p.name for p in tmp_path.rglob("*")) == avant
