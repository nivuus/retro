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
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"))
    assert ("retroarch", "1.22.2") in r.emulators


def test_un_emulateur_absent_est_un_probleme(tmp_path):
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"))
    assert ("retroarch", "absent") in r.emulators
    assert any("retroarch" in p.what for p in r.problems)


def test_les_bios_manquants_sont_des_problemes():
    manquant = bios.SystemBios(
        system_id="psx", system_name="PlayStation",
        files=(bios.BiosFile("scph5501.bin", "abc", True, "absent"),))
    r = status.build_report(install_dirs={}, emulation_root=pathlib.Path("."),
                            systems=[], bios_status=[manquant], bios_root=pathlib.Path("/BIOS"))
    assert any("scph5501.bin" in p.what for p in r.problems)


def test_un_bios_corrompu_se_distingue_d_un_bios_absent():
    """Le propriétaire CROIT l'avoir déposé : le message doit le lui dire."""
    corrompu = bios.SystemBios(
        system_id="psx", system_name="PlayStation",
        files=(bios.BiosFile("scph5501.bin", "abc", True, "corrompu"),))
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[corrompu], bios_root=pathlib.Path("/BIOS")))
    assert "corrompu" in texte.lower()
    assert "scph5501.bin" in texte


def test_le_rapport_compte_les_jeux_par_systeme():
    r = status.build_report(install_dirs={}, emulation_root=pathlib.Path("."),
                            systems=[("Super Nintendo", 142)], bios_status=[], bios_root=pathlib.Path("/BIOS"))
    assert ("Super Nintendo", 142) in r.systems
    assert "142" in status.format_report(r)


def test_un_seul_jeu_accorde_au_singulier():
    """« 1 jeux » : c'est le seul texte du projet qu'un humain lira, depuis son
    canapé. Le test précédent ne mord pas sur l'accord — 142 est pluriel dans
    les deux formes. Celui-ci utilise 1, qui distingue « jeu » de « jeux »."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[("Game Boy", 1)], bios_status=[], bios_root=pathlib.Path("/BIOS")))
    assert "1 jeu" in texte
    assert "1 jeux" not in texte


def test_sans_probleme_le_rapport_le_dit():
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[("Super Nintendo", 1)], bios_status=[], bios_root=pathlib.Path("/BIOS")))
    assert "aucun" in texte.lower()


def test_le_rapport_ne_modifie_rien(tmp_path):
    """`status` est consultatif : rien de ce qu'il touche ne doit changer."""
    avant = sorted(p.name for p in tmp_path.rglob("*"))
    status.build_report(install_dirs={"x": "X"}, emulation_root=tmp_path,
                        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"))
    assert sorted(p.name for p in tmp_path.rglob("*")) == avant


# --- Le rapport doit nommer un chemin, une action, et ce qui va bien ------


def _psx_groupe(etats):
    """Le système PlayStation avec ses trois BIOS interchangeables."""
    noms = [("scph5500.bin", "Japon"), ("scph5501.bin", "Amérique du Nord"),
            ("scph5502.bin", "Europe")]
    return bios.SystemBios(
        system_id="psx", system_name="PlayStation",
        files=tuple(
            bios.BiosFile(nom, "abc", True, etat, group="region", region=region)
            for (nom, region), etat in zip(noms, etats)
        ))


def test_un_groupe_entierement_absent_fait_un_seul_probleme():
    """Trois lignes accusatrices pour un seul manque : le propriétaire part
    chercher trois fichiers alors qu'un seul suffit."""
    r = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[_psx_groupe(("absent",) * 3)],
        bios_root=pathlib.Path("/mnt/bios"))
    assert len(r.problems) == 1
    texte = status.format_report(r)
    assert "un seul suffit" in texte
    for nom in ("scph5500.bin", "scph5501.bin", "scph5502.bin"):
        assert texte.count(nom) == 1, f"{nom} écrit {texte.count(nom)} fois"
    assert "MANQUANT : scph5500.bin" not in texte


def test_un_groupe_satisfait_est_confirme_et_ne_pose_aucun_probleme():
    """Le propriétaire qui a fait le bon geste doit VOIR que ça a marché."""
    r = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[_psx_groupe(("absent", "ok", "absent"))],
        bios_root=pathlib.Path("/mnt/bios"))
    assert r.problems == []
    texte = status.format_report(r)
    assert "scph5501.bin" in texte
    assert "scph5500.bin" not in texte, "accuse un fichier dont il n'a pas besoin"
    assert "scph5502.bin" not in texte


def test_chaque_probleme_nomme_un_chemin_et_une_action():
    """« MANQUANT : scph5500.bin » ne dit pas OÙ déposer le fichier, et
    « dolphin n'est pas installé » ne dit pas `retro install`."""
    r = status.build_report(
        install_dirs={"dolphin": "Dolphin-x64"},
        emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[_psx_groupe(("absent",) * 3)],
        bios_root=pathlib.Path("/mnt/bios"))
    assert len(r.problems) == 2
    for p in r.problems:
        assert p.where, f"problème sans chemin : {p.what}"
        assert p.action, f"problème sans action : {p.what}"
    texte = status.format_report(r)
    assert "/mnt/bios" in texte
    assert "retro install" in texte
    assert "D:\\Emulation\\Dolphin-x64" in texte


def test_le_chemin_d_un_emulateur_ne_melange_pas_les_separateurs():
    """pathlib.Path(« D:\\Emulation ») / « Dolphin » rend
    « D:\\Emulation/Dolphin » sur Linux : mi-POSIX mi-Windows, un chemin que
    personne ne peut ouvrir."""
    r = status.build_report(
        install_dirs={"dolphin": "Dolphin-x64"},
        emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("/mnt/bios"))
    chemin = r.problems[0].where
    assert "/" not in chemin, chemin


def test_un_probleme_n_est_ecrit_qu_une_fois():
    """Le même manque était écrit deux fois, dans deux formulations : section
    BIOS puis section Problèmes. Un lecteur y voyait deux constats."""
    r = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[],
        bios_status=[bios.SystemBios(
            system_id="psx", system_name="PlayStation",
            files=(bios.BiosFile("scph5501.bin", "abc", True, "corrompu"),))],
        bios_root=pathlib.Path("/mnt/bios"))
    texte = status.format_report(r)
    assert texte.count("scph5501.bin") == 2, (
        "attendu : une fois dans le constat, une fois dans l'action\n" + texte)


def test_la_section_bios_signale_qu_il_y_a_des_problemes():
    """Une section BIOS sans ligne de défaut ne doit pas se lire comme « tout
    va bien » quand un BIOS requis manque."""
    r = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[_psx_groupe(("absent",) * 3)],
        bios_root=pathlib.Path("/mnt/bios"))
    bloc = status.format_report(r).split("BIOS\n")[1].split("\n\n")[0]
    assert "aucun problème" not in bloc.lower()
    assert "Problèmes" in bloc


def test_un_seul_probleme_s_accorde_au_singulier():
    """« Problèmes (1) » : même famille que le « 1 jeux » déjà corrigé."""
    r = status.build_report(
        install_dirs={"dolphin": "Dolphin-x64"},
        emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("/mnt/bios"))
    texte = status.format_report(r)
    assert "Problème (1)" in texte
    assert "Problèmes (1)" not in texte


def test_un_bios_facultatif_absent_n_est_pas_un_probleme_mais_se_voit():
    """disksys.rom n'est requis que pour le Famicom Disk System. Le taire
    laisserait croire à un oubli du programme ; l'accuser serait faux."""
    r = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"), systems=[],
        bios_status=[bios.SystemBios(
            system_id="nes", system_name="NES",
            files=(bios.BiosFile("disksys.rom", "abc", False, "absent"),))],
        bios_root=pathlib.Path("/mnt/bios"))
    assert r.problems == []
    texte = status.format_report(r)
    assert "disksys.rom" in texte
    assert "facultatif" in texte.lower()
