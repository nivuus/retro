"""Le rapport lisible. Ne modifie jamais rien."""
import pathlib

import pytest

from retro import bios, install, launcher, profiles, scan, status


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


# --- « l'émulateur n'est pas installé » coûte des jeux ---------------------


def _ignore(tmp_path, roms=3, profil="retroarch", raison=install.ABSENT):
    return scan.IgnoredSystem(
        folder="snes", system_name="Super Nintendo", profile=profil,
        install_dir=tmp_path / "RetroArch",
        emulator=tmp_path / "RetroArch" / "RetroArch-Win64" / "retroarch.exe",
        roms=roms, reason=raison,
    )


def test_les_jeux_ignores_completent_le_probleme_de_l_emulateur(tmp_path):
    """Un problème n'est énoncé qu'UNE fois : l'émulateur absent et les jeux
    qu'il coûte sont le même constat, pas deux. Deux formulations du même
    manque se lisent comme deux pannes distinctes."""
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[("Super Nintendo", 3)], bios_status=[],
        bios_root=pathlib.Path("/BIOS"),
        ignored_systems=[_ignore(tmp_path)])
    concernes = [p for p in r.problems if "retroarch" in p.what]
    assert len(concernes) == 1, [p.what for p in concernes]
    detail = " ".join(concernes[0].details)
    assert "Super Nintendo" in detail and "3 jeux" in detail


def test_un_emulateur_dit_installe_mais_sans_executable_est_un_probleme(tmp_path):
    """Le témoin de version est là, l'exécutable non : un dossier vidé à la
    main, une extraction interrompue. Dire « absent » enverrait le
    propriétaire installer ce qu'il a déjà — le rapport doit dire ce qui
    manque VRAIMENT, et où il a été cherché."""
    emu = tmp_path / "RetroArch"
    emu.mkdir()
    (emu / ".retro-version").write_text("1.22.2\n", encoding="utf-8")
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[("Super Nintendo", 3)], bios_status=[],
        bios_root=pathlib.Path("/BIOS"),
        ignored_systems=[_ignore(tmp_path, raison=install.INCOMPLET)])
    (probleme,) = [p for p in r.problems if "retroarch" in p.what]
    assert "exécutable" in probleme.what
    assert probleme.where == str(emu / "RetroArch-Win64" / "retroarch.exe")
    assert "Super Nintendo" in " ".join(probleme.details)


def test_sans_systeme_ignore_le_rapport_ne_change_pas(tmp_path):
    """Le paramètre est facultatif : les appelants qui ne peuvent pas savoir
    ce qui a été ignoré rendent le rapport d'avant, à l'identique."""
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"))
    assert ("retroarch", "absent") in r.emulators
    assert all(p.details == () for p in r.problems)


def test_les_jeux_ignores_se_lisent_dans_le_rapport(tmp_path):
    texte = status.format_report(status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[("Super Nintendo", 1)], bios_status=[],
        bios_root=pathlib.Path("/BIOS"),
        ignored_systems=[_ignore(tmp_path, roms=1)]))
    assert "1 jeu ignoré" in texte
    assert "1 jeux" not in texte


def test_un_emulateur_pose_a_la_main_est_dit_tel_quel(tmp_path):
    """L'exécutable est là, le témoin non. Dire « n'est pas installé » à qui
    voit son dossier plein l'enverrait douter du rapport ; dire « installé »
    tairait que rien n'atteste sa complétude — `install` ne pose le témoin
    qu'après avoir vérifié TOUTES les archives, cores compris. Le scan et le
    rapport disent désormais la même chose du même disque."""
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[("Super Nintendo", 3)], bios_status=[],
        bios_root=pathlib.Path("/BIOS"),
        ignored_systems=[_ignore(tmp_path, raison=install.SANS_TEMOIN)])
    (probleme,) = [p for p in r.problems if "retroarch" in p.what]
    assert "témoin" in probleme.what
    assert "retro install" in probleme.action
    assert "Super Nintendo" in " ".join(probleme.details)


def test_le_dossier_d_installation_ne_melange_pas_les_separateurs(tmp_path):
    """Un manifeste utilisateur peut mettre un sous-chemin dans install_dir.
    Recopié tel quel sous une racine POSIX, il rendait « /mnt/emus\\R », un
    chemin que personne ne peut ouvrir et que le propriétaire recopierait."""
    r = status.build_report(
        install_dirs={"retroarch": "emus\\RetroArch-1.22"},
        emulation_root=pathlib.Path("/mnt/emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"))
    (probleme,) = r.problems
    assert probleme.where == "/mnt/emulation/emus/RetroArch-1.22"


# --- l'état d'un émulateur ne dépend pas des ROMs du propriétaire ---------

EXE_DOLPHIN = "Dolphin-x64\\Dolphin.exe"


def _poser(racine, *, executable=True, temoin=True):
    dossier = racine / "Dolphin"
    (dossier / "Dolphin-x64").mkdir(parents=True, exist_ok=True)
    if executable:
        (dossier / "Dolphin-x64" / "Dolphin.exe").write_bytes(b"MZ")
    if temoin:
        (dossier / ".retro-version").write_text("2503\n", encoding="utf-8")
    return dossier


def _rapport(tmp_path, ignores=()):
    return status.build_report(
        install_dirs={"dolphin": "Dolphin"}, emulation_root=tmp_path,
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        emulator_exes={"dolphin": EXE_DOLPHIN}, ignored_systems=ignores)


def test_un_executable_absent_se_voit_sans_la_moindre_rom(tmp_path):
    """Le verdict se déduisait de la liste des systèmes ignorés — qui filtre
    les systèmes SANS ROM. L'état d'un émulateur dépendait donc de la présence
    de jeux : sur une console fraîchement provisionnée, avant que le
    propriétaire ait rien déposé, un Dolphin amputé s'annonçait installé.
    C'est le moment le plus probable, et le rapport y mentait."""
    _poser(tmp_path, executable=False)
    r = _rapport(tmp_path)
    assert ("dolphin", "2503, exécutable introuvable") in r.emulators
    assert any("exécutable" in p.what for p in r.problems)


def test_un_emulateur_pose_a_la_main_se_voit_sans_la_moindre_rom(tmp_path):
    """« l'émulateur n'est pas installé » en désignant un dossier qui contient
    l'exécutable est mot pour mot ce que ce module s'interdit d'écrire."""
    _poser(tmp_path, temoin=False)
    r = _rapport(tmp_path)
    assert ("dolphin", "présent, sans témoin de version") in r.emulators
    (probleme,) = r.problems
    assert "témoin" in probleme.what
    assert "n'est pas installé" not in probleme.what


def test_un_emulateur_complet_sans_rom_ne_fait_aucun_probleme(tmp_path):
    _poser(tmp_path)
    r = _rapport(tmp_path)
    assert ("dolphin", "2503") in r.emulators
    assert r.problems == []


def test_le_verdict_est_le_meme_avec_et_sans_roms(tmp_path):
    """La concordance, énoncée comme telle : les jeux du propriétaire chiffrent
    le coût d'une panne, ils ne décident pas de son existence."""
    _poser(tmp_path, temoin=False)
    ignore = scan.IgnoredSystem(
        folder="gamecube", system_name="GameCube", profile="dolphin",
        install_dir=tmp_path / "Dolphin",
        emulator=tmp_path / "Dolphin" / "Dolphin-x64" / "Dolphin.exe",
        roms=3, reason=install.SANS_TEMOIN)
    sans = _rapport(tmp_path)
    avec = _rapport(tmp_path, ignores=[ignore])
    assert sans.emulators == avec.emulators
    assert [p.what for p in sans.problems] == [p.what for p in avec.problems]
    # Seul le COÛT change : c'est ce que les ROMs ajoutent, et rien d'autre.
    assert sans.problems[0].details == ()
    assert "3 jeux" in " ".join(avec.problems[0].details)


def test_le_remede_du_sans_temoin_nomme_les_deux_issues(tmp_path):
    """Un profil hors de tout manifeste ne peut pas être installé par
    « retro install » : lui opposer cette seule commande est un cul-de-sac."""
    _poser(tmp_path, temoin=False)
    (probleme,) = _rapport(tmp_path).problems
    assert "retro install" in probleme.action
    assert "ne peut installer que ce qui y figure" in probleme.action


def test_sans_les_executables_le_rapport_reste_celui_d_avant(tmp_path):
    """`emulator_exes` est facultatif : un appelant qui n'a pas chargé les
    profils ne sait pas quel exécutable chercher, et retombe sur le témoin
    seul — le comportement d'avant, à l'identique."""
    _poser(tmp_path, executable=False)
    r = status.build_report(
        install_dirs={"dolphin": "Dolphin"}, emulation_root=tmp_path,
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"))
    assert ("dolphin", "2503") in r.emulators
    assert r.problems == []


# --- la section « Rendu » -----------------------------------------------

def _profils_rendu(tmp_path):
    from retro import profiles
    (tmp_path / "p.toml").write_text("""
schema = 1
id = "p"
exe = "p.exe"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '{render} "{rom}"'
cost = "light"
bios = []
[system.render.native]
args = "-scale=1"
crt = "-shader=crt"
[system.render.full]
args = "-scale=4"
[[system]]
id = "ps3"
name = "PlayStation 3"
extensions = [".iso"]
launch = '"{rom}"'
bios = []
""", encoding="utf-8")
    return {"p": profiles.load_profile(tmp_path / "p.toml")}


def test_un_systeme_sans_modes_est_nomme(tmp_path):
    """Sans cette ligne, le propriétaire choisirait « full » et obtiendrait,
    pour ce système, exactement ce qu'il avait avant — sans qu'un mot
    l'explique."""
    etats = status.etat_rendu(_profils_rendu(tmp_path))
    muets = [e.system_name for e in etats if not e.declared]
    assert muets == ["PlayStation 3"]


def test_les_systemes_sans_modes_font_UN_probleme_groupe(tmp_path):
    """Dix-sept lignes identiques noieraient les manques qui coûtent des
    jeux ; le silence ferait choisir un mode sans effet."""
    etats = status.etat_rendu(_profils_rendu(tmp_path))
    problemes = status._probleme_sans_modes(etats)
    assert len(problemes) == 1
    assert problemes[0].details == ("PlayStation 3",)


def test_aucun_probleme_quand_tout_est_declare(tmp_path):
    etats = [e for e in status.etat_rendu(_profils_rendu(tmp_path))
             if e.declared]
    assert status._probleme_sans_modes(etats) == []


def test_l_arbitrage_est_rendu_pour_chaque_classe_de_machine(tmp_path):
    """`retro status` tourne sur la machine qui PILOTE, pas sur celle qui
    joue : annoncer un mode d'après le matériel de l'hôte serait une réponse
    fausse et convaincante."""
    from retro import render
    etat = next(e for e in status.etat_rendu(_profils_rendu(tmp_path))
                if e.declared)
    assert [c for c, _ in etat.auto] == list(render.CLASSES)


def test_le_crt_et_son_absence_se_lisent_dans_le_rapport(tmp_path):
    etats = status.etat_rendu(_profils_rendu(tmp_path))
    assert next(e for e in etats if e.declared).crt is True


def test_le_resume_de_l_auto_groupe_par_mode():
    assert status._resume_auto((("modeste", "native"), ("moyenne", "full"),
                                ("solide", "full"))) == \
        "native sur machine modeste ; full sur machine moyenne, solide"


def test_le_resume_d_un_auto_uniforme_est_court():
    assert status._resume_auto((("modeste", "full"), ("moyenne", "full"),
                                ("solide", "full"))) == "full sur toute machine"


def test_les_jeux_dont_steam_input_reste_actif_sont_un_probleme():
    """Steam Input masque la manette à l'émulateur : ces jeux sont muets, et
    rien d'autre ne le dit — ni l'émulateur, ni Steam, ni aucun journal."""
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("/bios"),
        steam_input_muets=["Un jeu", "Un autre"],
    )
    probleme = [p for p in rapport.problems if "Steam Input" in p.what]
    assert len(probleme) == 1
    assert probleme[0].details == ("Un jeu", "Un autre")
    assert "retro sync" in probleme[0].action


def test_sans_jeu_muet_aucun_probleme_de_steam_input():
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("/bios"),
        steam_input_muets=[],
    )
    assert [p for p in rapport.problems if "Steam Input" in p.what] == []


# --- ce qui est amorcé, et ce qui ne l'est pas encore ----------------------

PROFIL_STATUS_AMORCE = """
schema = 1
id = "duckstation"
exe = 'duckstation-qt.exe'
[[bootstrap]]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[Main]
SetupWizardIncomplete = false
'''
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{rom}"'
"""


@pytest.fixture
def profils_amorces_status(tmp_path):
    p = tmp_path / "duckstation.toml"
    p.write_text(PROFIL_STATUS_AMORCE, encoding="utf-8")
    return {"duckstation": profiles.load_profile(p)}


@pytest.fixture
def profils_sans_amorcage_status(tmp_path):
    texte = (PROFIL_STATUS_AMORCE[:PROFIL_STATUS_AMORCE.index("[[bootstrap]]")]
             + PROFIL_STATUS_AMORCE[PROFIL_STATUS_AMORCE.index("[[system]]"):])
    p = tmp_path / "duckstation.toml"
    p.write_text(texte, encoding="utf-8")
    return {"duckstation": profiles.load_profile(p)}


def test_le_rapport_dit_ce_qui_est_amorce(profils_amorces_status):
    """« amorcé le … » : le propriétaire doit pouvoir vérifier qu'une
    configuration a bien été posée sans ouvrir l'émulateur."""
    etats = status.etat_amorcage(
        profils_amorces_status,
        {"duckstation": [("2026-08-28 10:27:26", "C:\\Users\\A\\settings.ini")]})
    assert [(e.profile_id, e.declare, e.date) for e in etats] == [
        ("duckstation", True, "2026-08-28 10:27:26")]


def test_le_rapport_dit_ce_qui_n_est_pas_encore_amorce(profils_amorces_status):
    """Aucun jeu de cet émulateur n'a encore été lancé. Ce n'est pas un
    problème — c'est un état à dire, pas à taire."""
    etats = status.etat_amorcage(profils_amorces_status, {})
    assert etats[0].declare and etats[0].date == ""


def test_un_profil_sans_bloc_est_nomme(profils_sans_amorcage_status):
    """« cet émulateur se débrouille » et « le bloc a été oublié » ne se
    distinguent que si le rapport nomme les profils sans amorçage."""
    etats = status.etat_amorcage(profils_sans_amorcage_status, {})
    assert etats[0].declare is False


def test_la_section_amorcage_figure_dans_le_texte(profils_amorces_status):
    """Un état que le rapport calcule sans l'imprimer ne sert à personne."""
    rapport = status.build_report(
        install_dirs={"duckstation": "DS"},
        emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        profils=profils_amorces_status,
        amorcages={"duckstation": [("2026-08-28 10:27:26",
                                    "C:\\Users\\A\\settings.ini")]},
    )
    texte = status.format_report(rapport)
    assert "Amorçage" in texte and "2026-08-28 10:27:26" in texte


def test_la_section_amorcage_s_affiche_meme_sans_profil():
    """Les sections BIOS et Rendu s'affichent toujours, avec un texte de
    repli ; l'Amorçage disparaissait quand la liste était vide. Une section
    qui disparaît se lit comme une panne d'affichage, et son repli — jamais
    atteignable tant qu'elle était conditionnelle — est la seule chose qui
    distingue « rien à dire » de « rien n'a été lu »."""
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"))
    assert rapport.amorcages == []
    texte = status.format_report(rapport)
    assert "Amorçage" in texte and "aucun profil chargé" in texte


def test_un_lanceur_perime_est_un_probleme():
    """Un binaire compilé avant les plans qu'il lit n'échoue pas : il ignore
    les lignes qu'il ne connaît pas. Sans ce problème, la section Amorçage
    dirait « pas encore amorcé » indéfiniment et enverrait chercher la panne
    dans les profils."""
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        lanceur_perime=True)
    perimes = [p for p in rapport.problems if "plus ancien que sa source" in p.what]
    assert len(perimes) == 1
    # Le geste ET le chemin, pas seulement le constat : c'est la règle du
    # module, et « recompiler » sans dire où n'aide personne.
    assert "compiler.cmd" in perimes[0].action
    assert "D:\\Emulation\\_launcher\\compiler.cmd" in perimes[0].action
    assert "/" not in perimes[0].where, perimes[0].where


def test_un_lanceur_a_jour_ne_produit_aucun_probleme():
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        lanceur_perime=False)
    assert [p for p in rapport.problems if "plus ancien" in p.what] == []


# --- la section « Rendu » : le remplissage -------------------------------

def _profils_remplissage(tmp_path):
    """Trois systèmes, un par état du troisième axe : réglé, non réglable
    faute d'option, et jamais mesuré."""
    (tmp_path / "q.toml").write_text("""
schema = 1
id = "q"
exe = "q.exe"
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '{render} "{rom}"'
cost = "light"
bios = []
[system.render.native]
args = "-scale=1 -integer=yes"
crt = "-shader=crt"
fill = "entier"
[system.render.full]
args = "-scale=4 -integer=no"
fill = "ajuste"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '{render} "{rom}"'
cost = "light"
bios = []
[system.render.native]
args = ""
note = "dix-sept arguments, aucun de rendu"
crt_absent = "aucun shader en ligne de commande"
[system.render.full]
args = ""
note = "même raison qu'en mode natif"
[[system]]
id = "n64"
name = "Nintendo 64"
extensions = [".z64"]
launch = '{render} "{rom}"'
cost = "medium"
bios = []
[system.render.native]
args = "-scale=1"
crt_absent = "aucun shader"
[system.render.full]
args = "-scale=2"
""", encoding="utf-8")
    return {"q": profiles.load_profile(tmp_path / "q.toml")}


def test_le_remplissage_de_chaque_mode_se_lit_dans_le_rapport(tmp_path):
    """Le troisième axe suit la même règle que les deux autres : un réglage
    qui s'appliquerait en silence est un défaut."""
    from retro import render
    etat = next(e for e in status.etat_rendu(_profils_remplissage(tmp_path))
                if e.system_name == "Super Nintendo")
    valeurs = {mode: valeur for mode, valeur, _ in etat.remplissage}
    assert valeurs == {render.NATIVE: render.ENTIER,
                       render.FULL: render.AJUSTE}
    assert all(motif.strip() for _, _, motif in etat.remplissage)


def test_un_systeme_dont_le_remplissage_n_est_pas_mesure_est_nomme(tmp_path):
    """Sans cette ligne, l'image est ce que l'émulateur a décidé tout seul, et
    rien ne dit que personne n'a regardé."""
    etats = status.etat_rendu(_profils_remplissage(tmp_path))
    problemes = status._probleme_remplissage_non_mesure(etats)
    assert len(problemes) == 1
    assert problemes[0].details == ("Nintendo 64",)


def test_un_emulateur_qui_ne_pilote_rien_n_est_pas_un_remplissage_a_mesurer(tmp_path):
    """DuckStation a déjà répondu : la question est tranchée, la réponse est
    non. Le ranger parmi les mesures à faire ferait rouvrir l'enquête à
    chaque passage."""
    from retro import render
    etat = next(e for e in status.etat_rendu(_profils_remplissage(tmp_path))
                if e.system_name == "PlayStation")
    assert all(valeur == render.NON_REGLABLE
               for _, valeur, _ in etat.remplissage)
    problemes = status._probleme_remplissage_non_mesure([etat])
    assert problemes == []


def test_le_rapport_imprime_le_remplissage(tmp_path):
    etats = status.etat_rendu(_profils_remplissage(tmp_path))
    lignes = "\n".join(status._lignes_rendu(status.Report(
        emulators=[], systems=[], bios=[], problems=[],
        bios_root=pathlib.Path("/BIOS"), render=etats)))
    assert "remplissage" in lignes
    assert "entier" in lignes and "ajuste" in lignes


def test_la_politique_de_remplissage_est_citee_une_seule_fois(tmp_path):
    """Écrite dans `render`, citée dans le rapport — mais en légende, pas par
    système : les huit systèmes de RetroArch porteraient la même phrase, et
    dix-huit lignes identiques se lisent zéro fois."""
    from retro import render
    lignes = status._lignes_rendu(status.Report(
        emulators=[], systems=[], bios=[], problems=[],
        bios_root=pathlib.Path("/BIOS"),
        render=status.etat_rendu(_profils_remplissage(tmp_path))))
    motif = render.motif_remplissage(render.NATIVE)
    assert sum(motif in l for l in lignes) == 1


def test_un_emulateur_sans_reglage_de_remplissage_dit_pourquoi_sur_sa_ligne(tmp_path):
    """La légende explique la POLITIQUE ; elle ne peut rien dire d'un
    émulateur qui n'expose aucun réglage. Ce motif-là reste sur sa ligne."""
    lignes = status._lignes_remplissage(
        (("native", "non-reglable", "aucun réglage — pas de clé Integer"),
         ("full", "non-reglable", "aucun réglage — pas de clé Integer")))
    assert sum("pas de clé Integer" in l for l in lignes) == 1


# --- la section « Amorçage » : ce que la console IMPOSE --------------------

def _profils_imposes(tmp_path, enforced: bool):
    bloc = """
enforced = '''
[Main]
SetupWizardIncomplete = false
StartFullscreen = true
'''
""" if enforced else ""
    (tmp_path / "d.toml").write_text('''
schema = 1
id = "d"
exe = "d.exe"
[[bootstrap]]
target = 'C:\\d\\settings.ini'
content = """
; Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose
; à chaque lancement, ce qu'il a posé UNE FOIS, et le reste, qui est à vous.
[Main]
ConfirmPowerOff = false
"""''' + bloc + '''
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '"{rom}"'
''', encoding="utf-8")
    return {"d": profiles.load_profile(tmp_path / "d.toml")}


def _texte_amorcage(profils):
    return "\n".join(status._lignes_amorcage(status.Report(
        emulators=[], systems=[], bios=[], problems=[],
        bios_root=pathlib.Path("/BIOS"),
        amorcages=status.etat_amorcage(profils, {}))))


def test_le_rapport_dit_combien_de_cles_la_console_impose(tmp_path):
    """Le propriétaire doit lire AVANT, pas découvrir après, que deux de ses
    réglages reviendront à chaque lancement. Le compte évite d'avoir à ouvrir
    le profil pour savoir si c'est « une clé » ou « tout le fichier »."""
    texte = _texte_amorcage(_profils_imposes(tmp_path, enforced=True))
    assert "impose" in texte.lower()
    assert "2" in texte


def test_un_profil_qui_n_impose_rien_ne_le_dit_pas(tmp_path):
    """Huit profils livrés n'imposent rien : leur ajouter une ligne muette
    noierait celui qui, lui, impose."""
    texte = _texte_amorcage(_profils_imposes(tmp_path, enforced=False))
    assert "impose" not in texte.lower()


# --- Manettes : la panne qui ne se voit que le pad en main ----------------
#
# Dette D3. « Le seul émulateur PlayStation de la console est injouable, et
# rien dans `retro status` ne le dit. » L'émulateur, lui, ne dira jamais rien :
# une liaison qui ne correspond à aucun périphérique est ignorée EN SILENCE, et
# la manette reste muette exactement comme si le fichier était vide.

_PROFIL_MANETTE = """
schema = 1
id = "{pid}"
exe = '{pid}.exe'

[input]
mapping = "{mapping}"
{ou}

[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{{rom}}"'
"""


def _profil_manette(tmp_path, pid, mapping, ou="", pad=""):
    """Un profil de fixture, et le pad sous lequel son relevé a été fait.

    `pad` est EXPLICITE et non deviné : un relevé clos l'exige, et le laisser
    se remplir tout seul reviendrait à tester une valeur que la fixture aurait
    inventée plutôt que celle qu'un profil déclare.
    """
    lignes = [f"mapping_where = '{ou}'" if ou else "",
              f'pad_releve = "{pad}"' if pad else ""]
    p = tmp_path / f"{pid}.toml"
    p.write_text(_PROFIL_MANETTE.format(
        pid=pid, mapping=mapping,
        ou="\n".join(l for l in lignes if l)), encoding="utf-8")
    return {pid: profiles.load_profile(p)}


def _rapport_manette(profils):
    return status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        profils=profils)


def test_une_manette_a_relever_est_un_probleme(tmp_path):
    """C'est le constat de D3 : le jeu démarre, la manette ne répond pas, et
    aucun journal — ni celui de Steam, ni celui de l'émulateur — n'en dit un
    mot. Si le rapport se tait aussi, la panne n'existe nulle part ailleurs
    que devant la télévision."""
    profils = _profil_manette(
        tmp_path, "duckstation", "a-relever",
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini, section [Pad1]")
    problemes = [p for p in _rapport_manette(profils).problems
                 if "duckstation" in p.what]
    assert len(problemes) == 1
    # Le constat, le chemin, le geste : la règle du module. Un « la manette ne
    # répond pas » sans le fichier à ouvrir ni la procédure à jouer est une
    # accusation, pas un diagnostic.
    assert "[Pad1]" in problemes[0].where
    assert "releve-manettes" in problemes[0].action


def test_un_emulateur_qui_trouve_sa_manette_seul_est_dit_sans_etre_accuse(tmp_path):
    """Deux moitiés du même fait, et aucune ne se suffit : ne pas accuser sans
    rien dire laisserait ce profil invisible, indiscernable d'un profil oublié.
    """
    profils = _profil_manette(tmp_path, "retroarch", "auto")
    rapport = _rapport_manette(profils)
    assert [p for p in rapport.problems if "manette" in p.what] == []
    assert [(m.profile_id, m.etat) for m in rapport.manettes] == [
        ("retroarch", profiles.MAPPING_AUTO)]


def test_un_releve_clos_n_est_plus_un_probleme_mais_reste_dit(tmp_path):
    """La clôture de D3, le 2026-08-29, vue du rapport.

    Deux moitiés, et les deux comptent. Ne plus accuser : `retro status`
    annoncerait sinon « manette muette » sur le seul émulateur dont un bouton
    ait été VU agir, et le propriétaire apprendrait à ignorer la section.
    Continuer de le dire, AVEC son fichier : les vingt-huit clés de [Pad1] sont
    reposées à chaque lancement, et elles peuvent cesser d'être trouvées sans
    un mot — « SDL-0 » est un index, et un pad de plus branché avant celui
    d'Apollo ramène exactement le symptôme d'origine.
    """
    profils = _profil_manette(
        tmp_path, "duckstation", "releve",
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini, section [Pad1]",
        pad="x360")
    rapport = _rapport_manette(profils)
    assert [p for p in rapport.problems if "manette" in p.what] == []
    assert [(m.profile_id, m.etat) for m in rapport.manettes] == [
        ("duckstation", profiles.MAPPING_RELEVE)]
    ligne = [l for l in status.format_report(rapport).splitlines()
             if "duckstation" in l and "relev" in l]
    assert len(ligne) == 1
    assert "[Pad1]" in ligne[0], (
        "le rapport dit le relevé clos sans dire où ses liaisons vivent : "
        "il n'y a plus rien à ouvrir le jour où elles cessent d'agir"
    )
    assert "seul" not in ligne[0], (
        "le rapport laisse croire que DuckStation trouve sa manette seul, ce "
        "que D3 a réfuté : il ne la trouve que parce que la console impose"
    )


def test_un_mapping_jamais_mesure_est_nomme_sans_etre_accuse(tmp_path):
    """« personne n'a regardé » n'est pas « c'est cassé ». Le confondre ferait
    huit accusations sans mesure, et noierait la seule qui en a une — mais le
    taire ferait croire que ces huit émulateurs ont été vérifiés."""
    profils = _profil_manette(tmp_path, "cemu", "inconnu")
    rapport = _rapport_manette(profils)
    assert [p for p in rapport.problems if "manette" in p.what] == []
    assert [(m.profile_id, m.etat) for m in rapport.manettes] == [
        ("cemu", profiles.MAPPING_INCONNU)]


def test_les_trois_etats_de_manette_se_lisent_dans_le_texte(tmp_path):
    """Trois formulations, comme la section Amorçage : un état calculé sans
    être imprimé ne sert à personne, et « jamais mesuré » doit se distinguer
    de « il se débrouille »."""
    profils = {}
    profils.update(_profil_manette(tmp_path, "retroarch", "auto"))
    profils.update(_profil_manette(tmp_path, "cemu", "inconnu"))
    profils.update(_profil_manette(
        tmp_path, "duckstation", "a-relever",
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini, section [Pad1]"))
    texte = status.format_report(_rapport_manette(profils))
    assert "Manettes" in texte
    # La lecture est BORNÉE à la section Manettes : depuis que Vibration
    # existe, chaque profil a deux lignes dans le rapport, et un relevé fait
    # sur tout le texte rendait la seconde — celle de la vibration — pour la
    # première. Un test qui lit la mauvaise ligne serait vert quoi qu'il
    # arrive à celle qu'il croit contrôler.
    corps = texte.split("Manettes\n", 1)[1].split("\n\n", 1)[0]
    ligne = {l.strip().split(" : ")[0].lstrip("· ").strip(): l
             for l in corps.splitlines() if " : " in l}
    assert "trouve sa manette seul" in ligne["retroarch"]
    assert "jamais mesuré" in ligne["cemu"]
    assert "[Pad1]" in ligne["duckstation"]


def test_la_section_manettes_s_affiche_meme_sans_profil():
    """Comme BIOS, Rendu et Amorçage : une section qui disparaît se lit comme
    une panne d'affichage, et son repli est la seule chose qui distingue
    « rien à dire » de « rien n'a été lu »."""
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"))
    assert rapport.manettes == []
    texte = status.format_report(rapport)
    assert "Manettes" in texte and "aucun profil chargé" in texte


# --- Vibration : l'axe sur lequel le rapport se taisait entierement --------
#
# Dette D1. « retro status ne dit RIEN de la vibration — aucune section, aucun
# probleme, aucune ligne. » L'aveu vivait dans des commentaires TOML, que
# personne ne lit depuis un canape : c'est exactement l'ecart que le
# sous-projet E reproche a `steam_input = "required"`, un etat consigne la ou
# il ne sert a rien.

_PROFIL_VIBRATION = """
schema = 1
id = "{pid}"
exe = '{pid}.exe'

[input]
rumble = "{rumble}"
{ou}
{temoin}

[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{{rom}}"'
"""


def _profil_vibration(tmp_path, pid, rumble, ou="", temoin=""):
    p = tmp_path / f"{pid}.toml"
    p.write_text(_PROFIL_VIBRATION.format(
        pid=pid, rumble=rumble,
        ou=f"rumble_where = '{ou}'" if ou else "",
        temoin=f"rumble_witness = '{temoin}'" if temoin else ""),
        encoding="utf-8")
    return {pid: profiles.load_profile(p)}


def _ligne_vibration(rapport, pid):
    """La ligne que la section Vibration consacre a ce profil."""
    texte = status.format_report(rapport).split("Vibration\n", 1)[1]
    corps = texte.split("\n\n", 1)[0]
    return [l for l in corps.splitlines() if pid in l]


def test_une_vibration_a_relever_est_un_probleme(tmp_path):
    """Le seul des cinq etats qui dise « quelqu'un a constate, et il reste un
    geste a faire ». Sans probleme leve, cette panne-la n'existerait nulle part
    ailleurs que devant la television : la manette ne vibre pas, et ni Steam ni
    l'emulateur n'en disent un mot."""
    profils = _profil_vibration(
        tmp_path, "flycast", "a-relever", "emu.cfg, section [input]")
    problemes = [p for p in _rapport_manette(profils).problems
                 if "vibr" in p.what]
    assert len(problemes) == 1
    assert "emu.cfg" in problemes[0].where
    assert "releve-manettes" in problemes[0].action


def test_un_reglage_de_vibration_pose_est_dit_sans_etre_accuse(tmp_path):
    """L'etat de DuckStation, et celui qu'aucun rapport ne savait dire.

    Deux moities, et aucune ne se suffit. Ne pas accuser : un reglage EST
    pose, il n'y a pas de geste de relevé a faire. Le dire quand meme, AVEC
    son fichier : personne ne l'a vu agir, et il peut disparaitre de son
    fichier sans un mot. Et surtout, ne jamais laisser croire que ca vibre.
    """
    profils = _profil_vibration(
        tmp_path, "duckstation", "pose",
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini, section [Pad1]")
    rapport = _rapport_manette(profils)
    assert [p for p in rapport.problems if "vibr" in p.what] == []
    ligne, = _ligne_vibration(rapport, "duckstation")
    assert "[Pad1]" in ligne
    assert "jamais vu" in ligne, (
        "le rapport annonce un reglage de vibration sans dire que personne ne "
        "l'a vu agir : il laisse croire que la manette vibre"
    )


def test_une_vibration_jamais_mesuree_est_nommee_sans_etre_accusee(tmp_path):
    """« personne n'a regarde » n'est pas « c'est casse ». Le confondre ferait
    neuf accusations sans mesure ; le taire ferait croire que ces neuf
    emulateurs vibrent tout seuls."""
    profils = _profil_vibration(tmp_path, "cemu", "inconnu")
    rapport = _rapport_manette(profils)
    assert [p for p in rapport.problems if "vibr" in p.what] == []
    ligne, = _ligne_vibration(rapport, "cemu")
    assert "jamais mesuré" in ligne


def test_une_vibration_mesuree_absente_est_dite_sans_fichier(tmp_path):
    """« il n'y a rien a regler, et c'est mesure » n'est pas « personne n'a
    regarde » : sans cet etat, un emulateur sans rumble resterait indefiniment
    dans la liste de ce qui reste a faire."""
    profils = _profil_vibration(tmp_path, "xemu", "absent")
    rapport = _rapport_manette(profils)
    assert [p for p in rapport.problems if "vibr" in p.what] == []
    ligne, = _ligne_vibration(rapport, "xemu")
    assert "aucun réglage" in ligne


def test_une_vibration_vue_est_dite_avec_son_temoin(tmp_path):
    """Le seul etat que le rapport peut lire comme « ca marche », et il ne le
    dit qu'avec le temoin qui le soutient — la seule chose qui distingue une
    mesure d'une affirmation."""
    profils = _profil_vibration(
        tmp_path, "duckstation", "vu", "settings.ini, section [Pad1]",
        "le propriétaire, 2026-08-29, sur Crash Team Racing")
    rapport = _rapport_manette(profils)
    assert [p for p in rapport.problems if "vibr" in p.what] == []
    ligne, = _ligne_vibration(rapport, "duckstation")
    assert "2026-08-29" in ligne, (
        "le rapport affirme que la manette vibre sans nommer le temoin qui "
        "l'a sentie : c'est une affirmation, pas une mesure"
    )


def test_la_section_vibration_s_affiche_meme_sans_profil():
    """Comme BIOS, Rendu, Amorcage et Manettes : une section qui disparait se
    lit comme « rien a signaler » par quelqu'un qui vient justement de ne rien
    sentir vibrer."""
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"))
    assert rapport.vibrations == []
    texte = status.format_report(rapport)
    assert "Vibration" in texte and "aucun profil chargé" in texte


def test_le_probleme_de_manette_dit_qu_une_liaison_fausse_est_muette(tmp_path):
    """La garde de D3. Sans cette phrase, le prochain lecteur recopiera un
    identifiant trouvé dans une recette et croira avoir corrigé la panne : le
    symptôme est le MÊME — manette muette — avant et après."""
    profils = _profil_manette(
        tmp_path, "duckstation", "a-relever",
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini, section [Pad1]")
    problemes = [p for p in _rapport_manette(profils).problems
                 if "duckstation" in p.what]
    assert len(problemes) == 1
    dit = " ".join((problemes[0].what, problemes[0].action,
                    *problemes[0].details)).lower()
    assert "silence" in dit


# --- L'identité du paquet qui a produit le rapport ---------------------------

def test_le_rapport_nomme_le_paquet():
    """Deux roues peuvent porter le même « 0.1.0 » et ne pas contenir le même
    code : sans cette section, un rapport ne dit pas quelle construction l'a
    produit, et deux rapports contradictoires sont indiscernables."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."), systems=[],
        bios_status=[], bios_root=pathlib.Path("/BIOS"),
        paquet="0.1.0+20260829143512.a1b2c3d4.g9f8e7d6"))
    assert "Paquet" in texte
    assert "20260829143512" in texte
    assert "2026-08-29" in texte and "9f8e7d6" in texte


def test_la_section_paquet_est_inconditionnelle():
    """Comme BIOS, Rendu, Amorçage et Manettes : une section qui disparaît se
    lit comme une panne d'affichage."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."), systems=[],
        bios_status=[], bios_root=pathlib.Path("/BIOS")))
    assert "Paquet" in texte


def test_un_arbre_source_n_est_pas_un_probleme():
    """Lancer le paquet depuis son dépôt est le cas NORMAL de l'hôte. En faire
    une accusation apprendrait au lecteur à ignorer la section Problèmes — et
    `status` n'a de toute façon aucune référence à opposer."""
    r = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."), systems=[],
        bios_status=[], bios_root=pathlib.Path("/BIOS"),
        paquet="0.1.0+source")
    assert not any("paquet" in p.what.lower() for p in r.problems)


# --- Le dossier de mise à jour, qui doublerait un jeu ----------------------

def test_un_dossier_de_mise_a_jour_est_un_probleme():
    """Deux dossiers portant le marqueur donnent deux entrées Steam pour le
    même jeu, et la seconde lance le correctif seul — soit rien de jouable.
    Le scan a fait son travail : personne d'autre que ce rapport ne peut le
    dire."""
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        dossiers_de_mise_a_jour=["Sony\\PS4\\CUSA07410-UPDATE"])
    doublons = [p for p in rapport.problems if "mise à jour" in p.what]
    assert len(doublons) == 1
    # Nommément : le propriétaire doit savoir QUEL dossier sortir.
    assert doublons[0].details == ("Sony\\PS4\\CUSA07410-UPDATE",)
    assert doublons[0].action
    texte = status.format_report(rapport)
    assert "CUSA07410-UPDATE" in texte


def test_sans_dossier_suspect_aucun_probleme():
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"))
    assert [p for p in rapport.problems if "mise à jour" in p.what] == []


def test_un_seul_dossier_de_mise_a_jour_se_dit_au_singulier():
    """« 1 dossier(s) ... portent » : le rapport est le seul écran de ce
    paquet fait pour être lu, et `_cout` accorde déjà ses comptes."""
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        dossiers_de_mise_a_jour=["vita\\CUSA07410-UPDATE"])
    what = [p.what for p in rapport.problems if "mise à jour" in p.what][0]
    assert what.startswith("1 dossier de jeu porte un nom de mise à jour")


def test_deux_dossiers_de_mise_a_jour_se_disent_au_pluriel():
    rapport = status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        dossiers_de_mise_a_jour=["vita\\A-UPDATE", "vita\\B-PATCH"])
    what = [p.what for p in rapport.problems if "mise à jour" in p.what][0]
    assert what.startswith("2 dossiers de jeu portent un nom de mise à jour")

# --- le rapport ne doit pas se taire sur un émulateur qui ne pilote rien --

def test_le_rapport_dit_le_remplissage_d_un_emulateur_qui_ne_pilote_rien(
        tmp_path):
    """`_lignes_rendu` sortait tôt quand `pilote` est faux : DuckStation ne
    disait RIEN de son remplissage, alors que la console règle son cadrage
    dans son settings.ini. Un rapport qui se tait sur le seul émulateur dont
    la question est ouverte est pire qu'un rapport qui n'en parle pas du
    tout."""
    lignes = status._lignes_rendu(status.Report(
        emulators=[], systems=[], bios=[], problems=[],
        bios_root=pathlib.Path("/BIOS"),
        render=status.etat_rendu(_profils_remplissage(tmp_path))))
    psx = [l for l in lignes if "PlayStation" in l]
    assert psx, "la PlayStation doit avoir sa ligne"
    debut = lignes.index(psx[0])
    # Le bloc de la PlayStation SEUL : jusqu'à la ligne du système suivant,
    # sinon le « remplissage » de la Super Nintendo ferait passer ce test.
    bloc = [lignes[debut]]
    for ligne in lignes[debut + 1:]:
        if "Nintendo" in ligne:
            break
        bloc.append(ligne)
    assert any("remplissage" in l for l in bloc), (
        "le remplissage de la PlayStation n'est imprimé nulle part : "
        f"{bloc}")


def _profils_impose(tmp_path):
    """Un profil dont le remplissage est IMPOSÉ par l'amorçage — le cas
    DuckStation : deux modes vides, la clé posée dans son settings.ini."""
    (tmp_path / "i.toml").write_text('''
schema = 1
id = "i"
exe = "i.exe"
[[bootstrap]]
target = 'C:\\\\i\\\\settings.ini'
content = """
; Écrit par « retro », qui distingue ce qu'il IMPOSE et repose à chaque
; lancement, ce qu'il a posé UNE FOIS et ne retouche plus, et le reste.
[Main]
ConfirmPowerOff = false
"""
enforced = """
[Display]
Scaling = ValeurRelevee
"""
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '{render} "{rom}"'
cost = "light"
bios = []
[system.render.native]
args = ""
note = "dix-sept arguments, aucun de rendu"
crt_absent = "aucun shader en ligne de commande"
[system.render.full]
args = ""
note = "même raison qu'en mode natif"
[system.render]
fill_enforced = "entier"
fill_enforced_where = "[Display] Scaling = ValeurRelevee — relevé le 2026-01-01"
''', encoding="utf-8")
    return {"i": profiles.load_profile(tmp_path / "i.toml")}


def test_un_remplissage_impose_par_l_amorcage_arrive_jusqu_au_rapport(tmp_path):
    """Bout en bout : le profil le déclare, `etat_rendu` le résout, et le
    rapport l'imprime — sur un émulateur qui ne pilote RIEN en ligne de
    commande."""
    from retro import render
    etat = next(iter(status.etat_rendu(_profils_impose(tmp_path))))
    assert all(valeur == render.ENTIER for _, valeur, _ in etat.remplissage)
    lignes = "\n".join(status._lignes_rendu(status.Report(
        emulators=[], systems=[], bios=[], problems=[],
        bios_root=pathlib.Path("/BIOS"), render=[etat])))
    assert "entier" in lignes
    assert "[Display] Scaling" in lignes

PROFIL_DEUX_CIBLES = """
schema = 1
id = "rpcs3"
exe = 'rpcs3.exe'
[[bootstrap]]
target = '{install_dir}\\\\GuiConfigs\\\\CurrentSettings.ini'
content = '''
; Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose
; à chaque lancement, ce qu'il a posé UNE FOIS, et le reste, qui est à vous.
'''
enforced = '''
[main_window]
confirmationBoxBootGame=false
'''
[[bootstrap]]
target = '{install_dir}\\\\config\\\\input_configs\\\\global\\\\Default.yml'
content = '''
# Écrit par « retro ».
Player 1 Input:
  Handler: XInput
'''
[[system]]
id = "ps3"
name = "PlayStation 3"
extensions = [".iso"]
launch = '"{rom}"'
"""


@pytest.fixture
def profil_a_deux_cibles(tmp_path):
    p = tmp_path / "rpcs3.toml"
    p.write_text(PROFIL_DEUX_CIBLES, encoding="utf-8")
    return {"rpcs3": profiles.load_profile(p)}


def test_deux_cibles_non_amorcees_ne_donnent_pas_deux_lignes_identiques(
        profil_a_deux_cibles):
    """RPCS3 est le premier profil livré à porter DEUX cibles, et le rapport
    en imprimait deux lignes mot pour mot identiques.

    Deux lignes identiques ne se lisent pas comme deux cibles : elles se
    lisent comme un doublon d'affichage, donc comme un défaut du rapport. Or
    l'une des deux porte huit clés imposées et l'autre aucune — les confondre,
    c'est perdre l'information au moment précis où elle sert. Tant qu'aucun
    jeu n'a été lancé, le témoin ne dit rien : la cible affichée est alors
    celle que le PROFIL déclare, jeton compris.
    """
    lignes = status._lignes_amorcage(status.Report(
        emulators=[], systems=[], bios=[], problems=[],
        bios_root=pathlib.Path("/BIOS"),
        amorcages=status.etat_amorcage(profil_a_deux_cibles, {})))
    dites = [l for l in lignes if "pas encore amorcé" in l]
    assert len(dites) == 2, lignes
    assert dites[0] != dites[1], dites
    assert "CurrentSettings.ini" in dites[0]
    assert "Default.yml" in dites[1]

PROFIL_STATUS_YAML = """
schema = 1
id = "vita3k"
exe = 'Vita3K.exe'
[[bootstrap]]
target = '{install_dir}\\config.yml'
content = '''
# Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose
# à chaque lancement, ce qu'il a posé UNE FOIS et ne retouche plus, et tout le
# reste, qui vous appartient.
'''
enforced = '''
warn-missing-firmware: false
'''
[[system]]
id = "vita"
name = "PS Vita"
extensions = [".vpk"]
launch = '--fullscreen "{rom}"'
"""


def test_le_rapport_compte_les_cles_imposees_d_une_cible_yaml(tmp_path):
    """Le rapport annonce au propriétaire combien de réglages la console lui
    reprend. Compté avec l'analyseur INI seul, un YAML rendait ZÉRO — le
    rapport aurait dit « aucun réglage imposé » sur le seul profil qui en
    impose un hors INI, et le propriétaire aurait cherché ailleurs la raison
    pour laquelle son réglage revient.
    """
    p = tmp_path / "vita3k.toml"
    p.write_text(PROFIL_STATUS_YAML, encoding="utf-8")
    etats = status.etat_amorcage({"vita3k": profiles.load_profile(p)}, {})
    assert [e.imposees for e in etats] == [1]


# --- les licences PS Vita : ce que le rapport peut dire, et à quel titre ----

def _rapport_licences(etats):
    return status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("/E"), systems=[],
        bios_status=[], bios_root=pathlib.Path("/BIOS"), licences=etats)


def test_le_rapport_dit_ou_la_licence_d_un_jeu_vita_est_attendue():
    """L'absence d'une licence ne bloque rien : `get_license` journalise un
    avertissement et fausse un seul champ. Personne ne s'en aperçoit avant
    d'être en jeu, dans un journal qu'on ne lit pas depuis un canapé — c'est
    exactement ce qu'un rapport existe pour dire."""
    from retro import licence
    texte = status.format_report(_rapport_licences([licence.EtatLicence(
        jeu="Un jeu", etat=licence.ABSENTE,
        attendue="ux0\\license\\PCSF00012\\EP9000-PCSF00012_00-0000000000000000.rif")]))
    assert "Licences" in texte
    assert "Un jeu" in texte
    assert "ux0\\license\\PCSF00012" in texte


def test_une_licence_hors_de_portee_n_est_pas_comptee_comme_un_manque():
    """Un rapport qui annonce un manque qu'il ne peut pas constater est le
    pire des états. Tant que le système de fichiers Vita vit dans le profil
    Windows, l'hôte ne peut RIEN en dire — et il doit dire cela, pas
    « licence absente »."""
    from retro import licence
    r = _rapport_licences([licence.EtatLicence(
        jeu="Un jeu", etat=licence.HORS_DE_PORTEE, attendue="ux0\\license\\x",
        detail="la console range son système de fichiers Vita dans le profil "
               "Windows, que cet hôte n'atteint pas")])
    assert r.problems == []
    texte = status.format_report(r)
    assert "n'atteint pas" in texte


def test_une_licence_absente_est_un_probleme_qui_nomme_son_geste():
    """Le geste est NATIF : main.cpp traite tout content-path nommé work.bin
    comme une licence à poser. Un problème qui ne le dirait pas enverrait
    chercher une conversion qui n'existe pas."""
    from retro import licence
    r = _rapport_licences([licence.EtatLicence(
        jeu="Un jeu", etat=licence.ABSENTE, attendue="ux0\\license\\x.rif")])
    fautifs = [p for p in r.problems if "licence" in p.what.lower()]
    assert len(fautifs) == 1, r.problems
    assert "work.bin" in fautifs[0].action

# --- D11 : le fragment déposé n'est plus celui que le profil décrit -------
#
# Le symptôme est le RÉGLAGE D'ORIGINE, c'est-à-dire le défaut qu'on croyait
# corrigé : indiscernable, vu du canapé, d'un correctif qui serait faux. Seul
# `retro scan` redépose ces fichiers, et rien ne faisait le lien.

def _rapport_fragments(tmp_path, profils, fragments):
    return status.build_report(
        install_dirs={}, emulation_root=tmp_path, systems=[], bios_status=[],
        bios_root=pathlib.Path("/BIOS"), profils=profils,
        fragments=fragments)


def _fragments_conformes(profils):
    from retro import launcher
    return {nom: texte
            for pid, profil in profils.items()
            for rang, amorcage in enumerate(profil.bootstraps, 1)
            for nom, texte in launcher.fragments_attendus(pid, rang, amorcage)}


def test_un_fragment_conforme_ne_produit_aucun_probleme(tmp_path):
    profils = _profils_imposes(tmp_path, enforced=True)
    r = _rapport_fragments(tmp_path, profils, _fragments_conformes(profils))
    assert not any("amorçage" in p.what.lower() for p in r.problems)


def test_un_fragment_impose_perime_devient_un_probleme_nomme(tmp_path):
    """C'est la dette D11 elle-même : `enforced` a changé dans le profil, la
    suite est verte, et personne n'a re-scanné. La console fusionne encore
    l'ancien fragment, sans un mot."""
    profils = _profils_imposes(tmp_path, enforced=True)
    fragments = _fragments_conformes(profils)
    fragments["d.impose.1.ini"] = "[Main]\nSetupWizardIncomplete = true\n"
    r = _rapport_fragments(tmp_path, profils, fragments)
    fautifs = [p for p in r.problems if "d.impose.1.ini" in " ".join(p.details)]
    assert len(fautifs) == 1
    assert "retro scan" in fautifs[0].action


def test_un_fragment_absent_alors_que_le_scan_a_tourne_est_un_probleme(
        tmp_path):
    """Un `enforced` ajouté à un profil dont le fragment n'a jamais été
    déposé : le lanceur lève « fichier introuvable » devant la télévision,
    au clic, et le rapport ne le voyait pas venir."""
    profils = _profils_imposes(tmp_path, enforced=True)
    fragments = _fragments_conformes(profils)
    del fragments["d.impose.1.ini"]
    r = _rapport_fragments(tmp_path, profils, fragments)
    assert any("d.impose.1.ini" in " ".join(p.details) for p in r.problems)


def test_un_fragment_pose_une_fois_est_controle_lui_aussi(tmp_path):
    """`content` vieillit exactement comme `enforced` — il sera posé tel quel
    sur la prochaine console neuve, avec le contenu d'un autre âge."""
    profils = _profils_imposes(tmp_path, enforced=True)
    fragments = _fragments_conformes(profils)
    fragments["d.bootstrap.1.ini"] = "; d'un autre âge\n"
    r = _rapport_fragments(tmp_path, profils, fragments)
    assert any("d.bootstrap.1.ini" in " ".join(p.details) for p in r.problems)


def test_sans_plan_depose_aucun_fragment_n_est_reproche(tmp_path):
    """`retro scan` n'a jamais tourné ici — l'hôte qui consulte le rapport
    sans voir le disque de la console est dans ce cas. Accuser dix profils
    apprendrait au lecteur à ignorer la section Problèmes."""
    profils = _profils_imposes(tmp_path, enforced=True)
    r = _rapport_fragments(tmp_path, profils, None)
    assert not any("amorçage" in p.what.lower() for p in r.problems)


def test_les_fragments_perimes_tiennent_dans_UN_seul_probleme(tmp_path):
    """Dix lignes pour une seule cause — un scan à rejouer — noieraient les
    autres problèmes du rapport. Même groupement que les modes de rendu."""
    profils = _profils_imposes(tmp_path, enforced=True)
    fragments = {nom: "; périmé\n" for nom in _fragments_conformes(profils)}
    r = _rapport_fragments(tmp_path, profils, fragments)
    groupes = [p for p in r.problems if "d.impose.1.ini" in " ".join(p.details)]
    assert len(groupes) == 1
    assert "d.bootstrap.1.ini" in " ".join(groupes[0].details)

# --- le témoin des manettes, vu du rapport ---------------------------------
#
# Le filet de D4. Il ne répare rien : il rend CONSTATABLE, depuis l'hôte, ce
# qui ne se voyait qu'en s'asseyant devant la télévision avec un pad muet.


def _rapport_pads(profils, date="", pads=(), **kw):
    return status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        profils=profils, pads_date=date, pads=list(pads), **kw)


def _pad(index, vid_pid, nom):
    return launcher.Pad(index=index, vid_pid=vid_pid, nom=nom)


def _duckstation_releve(tmp_path, pad="x360"):
    return _profil_manette(
        tmp_path, "duckstation", "releve",
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini, section [Pad1]",
        pad=pad)


def test_un_temoin_de_manettes_absent_n_est_pas_un_probleme(tmp_path):
    """« Le lanceur n'a jamais relevé de manette » n'accuse personne : c'est
    l'état d'une console où il n'a pas encore tourné, ou d'un lanceur trop
    vieux pour savoir le faire. Ce signal-là est déjà porté par
    `lanceur_perime`, et le redire en problème apprendrait au propriétaire à
    ignorer la section."""
    rapport = _rapport_pads(_duckstation_releve(tmp_path))
    texte = status.format_report(rapport)
    assert "jamais relevé de manette" in texte
    assert [p for p in rapport.problems if "manette" in p.what.lower()] == []


def test_zero_manette_au_dernier_lancement_n_est_pas_un_probleme(tmp_path):
    """Une session peut s'ouvrir sans manette — le propriétaire regarde ses
    jeux depuis son téléphone, ou le pad n'est pas encore branché. En faire un
    problème rendrait la section fausse la moitié du temps.

    Mais ce constat DIFFÈRE du témoin absent, et le rapport doit les
    distinguer : ici le lanceur a regardé et n'a rien vu."""
    rapport = _rapport_pads(_duckstation_releve(tmp_path),
                            date="2026-09-01 21:14:33", pads=[])
    texte = status.format_report(rapport)
    assert "aucune manette au dernier lancement" in texte.lower()
    assert "jamais relevé de manette" not in texte
    assert [p for p in rapport.problems if "manette" in p.what.lower()] == []


def test_une_manette_du_type_attendu_est_dite_avec_son_nom(tmp_path):
    rapport = _rapport_pads(
        _duckstation_releve(tmp_path), date="2026-09-01 21:14:33",
        pads=[_pad(0, "045e:028e",
                   "Controller (Xbox 360 Controller for Windows)")])
    texte = status.format_report(rapport)
    assert "x360" in texte
    assert "Controller (Xbox 360 Controller for Windows)" in texte
    assert [p for p in rapport.problems if "manette" in p.what.lower()] == []


def test_plus_d_une_manette_est_un_probleme_qui_nomme_les_profils(tmp_path):
    """LE PREMIER DES DEUX PROBLÈMES, et c'est la FRAGILITÉ 1 de DuckStation
    rendue visible.

    Ses vingt-sept liaisons visent « SDL-0 », c'est-à-dire un INDEX. Un pad de
    plus énuméré avant celui d'Apollo les fait toutes viser un périphérique
    qui n'est pas là, et DuckStation ne le dira pas : le symptôme est
    exactement celui d'avant le relevé, manette muette et rien au journal.
    """
    rapport = _rapport_pads(
        _duckstation_releve(tmp_path), date="2026-09-01 21:14:33",
        pads=[_pad(0, "054c:05c4", "Wireless Controller"),
              _pad(1, "045e:028e", "Controller (Xbox 360)")])
    problemes = [p for p in rapport.problems
                 if "plus d'une manette" in p.what.lower()
                 or "2 manettes" in p.what.lower()]
    assert len(problemes) == 1, [p.what for p in rapport.problems]
    assert "duckstation" in problemes[0].what
    assert "[Pad1]" in problemes[0].where, (
        "le problème n'offre rien à ouvrir : un constat sans chemin est une "
        "accusation, pas un diagnostic")


def test_un_pad_d_un_autre_type_que_le_releve_est_un_probleme(tmp_path):
    """LE SECOND, et c'est la panne que D4 existe pour empêcher.

    Le relevé a été fait sous un Xbox 360 ; le pad d'index 0 est une
    DualShock. Tout identifiant que la configuration d'entrée contiendrait
    dépend du VID/PID, donc vient de changer.
    """
    rapport = _rapport_pads(
        _duckstation_releve(tmp_path), date="2026-09-01 21:14:33",
        pads=[_pad(0, "054c:05c4", "Wireless Controller")])
    problemes = [p for p in rapport.problems if "ds4" in p.what
                 and "x360" in p.what]
    assert len(problemes) == 1, [p.what for p in rapport.problems]
    assert "duckstation" in problemes[0].what
    assert "[Pad1]" in problemes[0].where
    # La phrase qui empêche la fausse correction. Sans elle, le prochain
    # lecteur recopie un identifiant trouvé dans une recette et constate le
    # MÊME symptôme, sans comprendre que sa valeur est simplement ignorée.
    detail = " ".join(problemes[0].details)
    assert "silence" in detail and "identique" in detail


def test_un_pad_inconnu_de_la_table_ne_declenche_aucun_probleme(tmp_path):
    """Accuser sur une table incomplète serait pire que se taire : la table
    est courte et gelée par construction, et un vid:pid qu'elle ne connaît pas
    ne prouve RIEN sur le type de la manette. Il s'affiche brut."""
    rapport = _rapport_pads(
        _duckstation_releve(tmp_path), date="2026-09-01 21:14:33",
        pads=[_pad(0, "1234:abcd", "Un pad quelconque")])
    assert [p for p in rapport.problems if "manette" in p.what.lower()] == []
    texte = status.format_report(rapport)
    assert "1234:abcd" in texte, (
        "un vid:pid inconnu doit s'afficher BRUT : c'est la seule chose que "
        "le rapport sache de lui, et la taire prive le propriétaire de la "
        "valeur exacte à reporter dans la table")


def test_un_profil_sans_releve_clos_n_est_accuse_d_aucune_discordance(tmp_path):
    """Un profil dont la manette n'a jamais été relevée n'a rien qui puisse
    cesser d'être vrai. L'inscrire au problème noierait les deux profils qui,
    eux, ont quelque chose à perdre."""
    profils = _profil_manette(tmp_path, "cemu", "inconnu")
    rapport = _rapport_pads(
        profils, date="2026-09-01 21:14:33",
        pads=[_pad(0, "054c:05c4", "Wireless Controller")])
    assert [p for p in rapport.problems if "cemu" in p.what] == []


def test_le_dernier_lancement_accorde_le_pluriel_des_manettes(tmp_path):
    """Même famille que le « 1 jeux » déjà corrigé, et que le « Problème (1) ».

    Ce rapport est lu depuis un canapé, sans clavier, par le propriétaire de
    la console. Un « 1 manette(s) » y fait exactement ce qu'une parenthèse de
    formulaire fait partout : il apprend au lecteur que le texte a été écrit
    par une machine, et que ce qu'il dit est approximatif.
    """
    profils = _duckstation_releve(tmp_path)
    un = status.format_report(_rapport_pads(
        profils, date="2026-09-01 21:14:33",
        pads=[_pad(0, "045e:028e", "X")]))
    assert "1 manette " in un or un.count("1 manette\n") == 1
    assert "manette(s)" not in un
    deux = status.format_report(_rapport_pads(
        profils, date="2026-09-01 21:14:33",
        pads=[_pad(0, "045e:028e", "X"), _pad(1, "045e:028e", "Y")]))
    assert "2 manettes" in deux


# --- Mesuré sur la console le 2026-08-29 : le rapport montrait un JETON -----
#
# « rpcs3 : pas encore amorcé ({install_dir}\GuiConfigs\CurrentSettings.ini) ».
# `{install_dir}` ne veut rien dire pour qui lit depuis un canapé : c'est une
# convention interne, et le rapport est le seul écran de ce paquet fait pour
# être lu. Le chemin réel est connu — la racine d'émulation et le dossier que
# le manifeste nomme —, donc le taire était un choix, pas une fatalité.

def test_une_cible_pas_encore_amorcee_montre_un_chemin_et_non_un_jeton():
    class Amorce:
        target = "{install_dir}\\GuiConfigs\\CurrentSettings.ini"
        content = ""
        enforced = ""
        # Le doublon PORTE les champs de langue, plutôt que `etat_amorcage`
        # ne les lise par `getattr` : c'est exactement la panne de D7 —
        # `getattr(profil, "bootstrap", None)` rendait « aucun amorçage
        # déclaré » pour tous les profils, sans erreur ni symptôme.
        langues = ()
        langue_repli = ""

    class Profil:
        bootstraps = [Amorce()]

    etats = status.etat_amorcage(
        {"rpcs3": Profil()}, {},
        install_dirs={"rpcs3": "RPCS3"},
        emulation_root_windows="D:\\Emulation")
    assert len(etats) == 1
    assert etats[0].target == "D:\\Emulation\\RPCS3\\GuiConfigs\\CurrentSettings.ini", (
        "le rapport montre encore le jeton brut au propriétaire : "
        f"{etats[0].target}")


def test_un_jeton_sans_dossier_connu_reste_lisible():
    """Un émulateur absent du manifeste n'a pas de dossier d'installation. Le
    rapport doit alors rendre la cible DÉCLARÉE plutôt que de fabriquer un
    chemin faux — dire « je ne sais pas où » vaut mieux que désigner ailleurs.
    """
    class Amorce:
        target = "{install_dir}\\config.yml"
        content = ""
        enforced = ""
        langues = ()
        langue_repli = ""

    class Profil:
        bootstraps = [Amorce()]

    etats = status.etat_amorcage({"inconnu": Profil()}, {}, install_dirs={},
                                 emulation_root_windows="D:\\Emulation")
    assert etats[0].target == "{install_dir}\\config.yml"


# --- la section Langue -----------------------------------------------------
#
# Elle porte trois choses qu'aucune autre section ne porte : la langue
# DEMANDÉE et son motif, la valeur brute lue chez Steam au dernier lancement —
# même quand elle ne sert pas — et, par entrée d'amorçage, lequel des trois
# états s'applique. Le troisième est celui qui compte : « aucune table
# déclarée » et « une table qui pose autre chose » se lisent à l'écran de la
# même façon, un jeu en anglais.

PROFIL_STATUS_LANGUE = """
schema = 1
id = "duckstation"
exe = 'duckstation-qt.exe'
[[bootstrap]]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose
; à chaque lancement, ce qu'il a posé une fois, et ce qui vous appartient.
[Main]
Theme = dark
'''
[bootstrap.langue]
repli = "english"
english = '''
[Main]
Language = en
'''
french = '''
[Main]
Language = fr
'''
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{rom}"'
"""

# Le témoin de l'état qui compte : une entrée d'amorçage sans la moindre table
# de langues. Cet émulateur ne suit pas la langue DU TOUT, ce qui n'est pas
# « il la suit mal ».
PROFIL_STATUS_SANS_LANGUE = """
schema = 1
id = "ppsspp"
exe = 'PPSSPPWindows64.exe'
[[bootstrap]]
target = '{install_dir}\\memstick\\PSP\\SYSTEM\\ppsspp.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[General]
CheckForNewVersion = False
'''
[[system]]
id = "psp"
name = "PSP"
extensions = [".iso"]
launch = '"{rom}"'
"""


@pytest.fixture
def profils_avec_langues(tmp_path):
    """Un profil qui déclare une table de langues, un profil qui n'en a pas."""
    avec = tmp_path / "duckstation-langue.toml"
    avec.write_text(PROFIL_STATUS_LANGUE, encoding="utf-8")
    sans = tmp_path / "ppsspp-langue.toml"
    sans.write_text(PROFIL_STATUS_SANS_LANGUE, encoding="utf-8")
    return {"duckstation": profiles.load_profile(avec),
            "ppsspp": profiles.load_profile(sans)}


def test_un_temoin_absent_ne_fait_supposer_aucune_langue(tmp_path):
    """Le seul état sous lequel l'absence n'accuse personne : aucun jeu n'a
    encore été lancé depuis que ce mécanisme existe."""
    assert launcher.lire_temoin_langue(tmp_path) is None


def test_le_temoin_se_relit(tmp_path):
    dossier = launcher.local_dir(tmp_path)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / launcher.TEMOIN_LANGUE).write_text(
        "steam=french\nlangue=french\nmotif=« auto » : Steam dit « french »\n",
        encoding="utf-8")
    temoin = launcher.lire_temoin_langue(tmp_path)
    assert temoin["steam"] == "french"
    assert temoin["langue"] == "french"


def test_un_profil_sans_table_est_NOMME_et_non_tu(profils_avec_langues):
    """L'état qui compte. Sans lui, un émulateur qui ne suit pas la langue
    serait indiscernable d'un émulateur qui la suit mal — et les deux se
    lisent à l'écran de la même façon : un jeu en anglais."""
    etats = status.etat_langues(profils_avec_langues, voulue="french")
    muets = [e for e in etats if not e.declared]
    assert muets, "aucun profil muet n'a été nommé"


def test_un_repli_est_nomme_avec_sa_raison(profils_avec_langues):
    etats = status.etat_langues(profils_avec_langues, voulue="dutch")
    replis = [e for e in etats if e.declared and e.motif]
    assert replis
    assert "dutch" in replis[0].motif and "english" in replis[0].motif


def test_une_langue_declaree_est_posee_sans_motif(profils_avec_langues):
    """Le premier des trois états : la langue voulue est déclarée ici, elle
    est posée telle quelle. Pas de motif — il n'y a rien à expliquer."""
    etats = status.etat_langues(profils_avec_langues, voulue="french")
    poses = [e for e in etats if e.declared]
    assert [(e.profile_id, e.langue, e.motif) for e in poses] == [
        ("duckstation", "french", "")]


def test_le_rapport_ecrit_la_valeur_brute_de_steam():
    """Même quand elle ne sert pas : la langue est posée à la main, Steam dit
    autre chose, et le rapport doit porter les DEUX. C'est ce qui rend le
    relevé du registre vérifiable depuis le canapé — sans quoi il n'existe
    aucun moyen de savoir si le lanceur lit vraiment quelque chose."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        langue="japanese",
        langue_temoin={"steam": "french", "langue": "japanese",
                       "motif": "posée à la main"}))
    assert "japanese" in texte
    assert "french" in texte, (
        "le rapport tait ce que Steam disait : rien ne permet alors de "
        "vérifier que le lanceur lit sa langue")


def test_sans_temoin_le_rapport_ne_suppose_aucune_langue_de_steam():
    """Le seul état sous lequel une absence n'accuse personne : aucun jeu
    n'a encore été lancé. Le confondre avec « Steam n'a rien dit » enverrait
    chercher une panne là où il n'y a qu'une console qui n'a pas joué."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        langue="auto", langue_temoin=None))
    assert "aucun jeu" in texte.lower()


def test_le_rapport_dit_que_ces_cles_sont_reposees_a_chaque_lancement():
    """La contrepartie de la décision 4 du spec. Le propriétaire qui change
    sa langue dans DuckStation et la voit revenir doit lire POURQUOI, et le
    rapport est le seul endroit où il peut le lire."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        langue="french", langue_temoin={"steam": "french"}))
    assert "chaque lancement" in texte


def test_le_rapport_dit_la_langue_DEMANDEE_et_jamais_posee():
    """Le témoin porte la langue DEMANDÉE : le lanceur l'écrit AVANT
    d'amorcer, et une seule ligne ne pourrait de toute façon pas résumer ce
    qui a été posé sur N cibles, chacune passant par son propre repli. Écrire
    « posée » ferait affirmer qu'un émulateur a reçu une langue qu'il n'a
    jamais reçue."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        langue="auto", langue_temoin={"steam": "french", "langue": "french"}))
    ligne = next(l for l in texte.splitlines() if "Steam dit" in l)
    assert "demandée" in ligne, ligne


def test_la_section_langue_nomme_les_trois_etats(profils_avec_langues):
    """Les trois états, sur trois lignes distinctes : ce qui est posé, le
    repli AVEC sa raison, et l'entrée qui n'a aucune table. Le troisième dit
    « cet émulateur ne suit pas la langue », qui n'est pas « il la suit
    mal »."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        profils=profils_avec_langues, langue="dutch",
        langue_temoin={"steam": "english", "langue": "dutch",
                       "motif": "posée à la main"}))
    assert "repli sur « english »" in texte
    assert "aucune table de langues déclarée" in texte
    assert "ppsspp" in texte


def test_la_section_langue_ne_montre_pas_de_jeton_de_chemin(
        profils_avec_langues):
    """Le jeton `{install_dir}` ne veut rien dire pour qui lit depuis un
    canapé — c'est la faute déjà corrigée dans la section Amorçage, et la
    section Langue nomme les mêmes cibles."""
    etats = status.etat_langues(
        profils_avec_langues, voulue="french",
        install_dirs={"ppsspp": "PPSSPP"},
        emulation_root_windows="D:\\Emulation")
    muet = next(e for e in etats if e.profile_id == "ppsspp")
    assert muet.cible == (
        "D:\\Emulation\\PPSSPP\\memstick\\PSP\\SYSTEM\\ppsspp.ini")


def test_sans_langue_lue_la_section_ne_disparait_pas():
    """Une section qui disparaît se lit comme une panne d'affichage : c'est
    la règle de tout ce rapport. Un appelant qui n'a pas lu la langue le dit,
    plutôt que de laisser un blanc."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS")))
    assert "Langue" in texte


# --- la section Langue : le TEXTE produit, branche par branche --------------
#
# Les six cas du rapport de tâche étaient écrits à la main, et trois branches
# du rendu n'avaient aucune assertion de texte — dont celle qui, mesurée par le
# relecteur, disait trois choses dont deux étaient fausses. Chacune repart
# d'ici avec le texte qu'elle produit, asservi.

def _section_langue(texte: str) -> str:
    """La section Langue d'un rapport rendu, sans son titre ni le vide final."""
    lignes = texte.splitlines()
    debut = next(n for n, l in enumerate(lignes) if l.startswith("Langue"))
    return "\n".join(lignes[debut:lignes.index("", debut)])


def _rapport_langue(profils=None, **kwargs) -> str:
    return status.format_report(status.build_report(
        install_dirs={"ppsspp": "PPSSPP"},
        emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("D:\\BIOS"),
        profils=profils, **kwargs))


def test_une_langue_de_steam_hors_liste_est_nommee_et_non_prise_pour_un_silence(
        profils_avec_langues):
    """Steam peut ajouter une langue : le registre en porterait le nom dès le
    lendemain, sur un plan écrit la veille — le lanceur l'anticipe
    explicitement. Le rapport disait alors « Steam n'a rien dit » (faux),
    « Steam disait klingon » (vrai) et « le réglage a changé depuis » (faux),
    sans jamais nommer la cause : « retro » ne connaît pas ce nom. Une console
    muette et une console qu'on ne comprend pas n'appellent pas le même geste.
    """
    texte = _rapport_langue(
        profils_avec_langues, langue="auto",
        langue_temoin={"steam": "klingon", "langue": "klingon",
                       "motif": "auto : Steam dit klingon"})
    assert _section_langue(texte) == "\n".join([
        "Langue — réglage « auto »",
        "  · aucune langue demandée — « auto » : Steam dit « klingon », un nom "
        "que « retro » ne connaît pas — aucun profil ne peut le déclarer, et "
        "Steam a pu l'ajouter depuis",
        "      chaque émulateur pose alors le repli de son profil, quand il en "
        "déclare un",
        "  · au dernier lancement, Steam disait « klingon »",
        "  ce que chaque entrée d'amorçage posera au prochain jeu, si Steam "
        "dit toujours « klingon » — c'est ce qu'il disait au dernier "
        "lancement, et l'hôte ne lit pas ce registre :",
        "  · duckstation (%USERPROFILE%\\Documents\\DuckStation\\settings.ini) "
        ": repli sur « english »",
        "  · ppsspp (D:\\Emulation\\PPSSPP\\memstick\\PSP\\SYSTEM\\ppsspp.ini) "
        ": aucune table de langues déclarée",
        "  un émulateur sans table pose ses propres défauts : ses jeux "
        "resteront dans SA langue, quoi que la console demande. Ce n'est pas "
        "« il la suit mal », c'est « il ne la suit pas ».",
        "  toute table de langues déclarée est reposée à chaque lancement, par "
        "la même fusion que les clés imposées : la langue échappe au "
        "propriétaire — changée dans l'émulateur, elle reviendra au prochain "
        "jeu. « retro langue » est l'endroit où elle se change.",
    ])
    assert "Steam n'a rien dit" not in texte
    assert "le réglage a changé" not in texte


def test_un_temoin_illisible_ne_se_lit_pas_comme_un_temoin_absent(tmp_path):
    """`None` et `{}` ne disent pas la même chose, comme pour les fragments :
    le fichier manque, ou il est là et on n'en tire rien. Les confondre ferait
    dire « aucun jeu lancé depuis » d'une console qui a joué — innocenter un
    témoin corrompu."""
    dossier = launcher.local_dir(tmp_path)
    dossier.mkdir(parents=True, exist_ok=True)
    # Des octets qui ne sont pas de l'UTF-8 : ce que ce fichier ne devrait
    # jamais être, et ce qu'un disque qui a lâché en plein milieu produit.
    (dossier / launcher.TEMOIN_LANGUE).write_bytes(b"steam=fr\xff\xfench\n")
    assert launcher.lire_temoin_langue(tmp_path) == {}, (
        "un témoin illisible se lit encore comme un témoin absent")


def test_un_temoin_illisible_est_dit_comme_tel_dans_le_rapport():
    texte = _rapport_langue(langue="auto", langue_temoin={})
    assert ("  · le témoin du dernier lancement est illisible : la console a "
            "joué, mais ce qu'elle a lu chez Steam ne peut pas être dit ici — "
            "ce n'est pas « aucun jeu lancé depuis »") in texte
    assert "aucun jeu lancé depuis que ce mécanisme existe" not in texte


def test_les_lignes_par_entree_sont_au_futur(profils_avec_langues):
    """« duckstation : pose « french » » deux lignes sous « aucun jeu lancé
    depuis » se lit comme un fait accompli. Rien n'a été posé : le témoin porte
    la langue DEMANDÉE, et cette exigence-là fuyait des lignes de synthèse vers
    les lignes de détail. La section Amorçage a réglé le même problème avec
    « pas encore amorcé »."""
    texte = _rapport_langue(profils_avec_langues, langue="french",
                            langue_temoin=None)
    assert _section_langue(texte) == "\n".join([
        "Langue — réglage « french »",
        "  · langue demandée : « french » — posée à la main",
        "  · aucun jeu lancé depuis que ce mécanisme existe : la console n'a "
        "encore rien lu chez Steam",
        "  ce que chaque entrée d'amorçage posera au prochain jeu :",
        "  · duckstation (%USERPROFILE%\\Documents\\DuckStation\\settings.ini) "
        ": « french »",
        "  · ppsspp (D:\\Emulation\\PPSSPP\\memstick\\PSP\\SYSTEM\\ppsspp.ini) "
        ": aucune table de langues déclarée",
        "  un émulateur sans table pose ses propres défauts : ses jeux "
        "resteront dans SA langue, quoi que la console demande. Ce n'est pas "
        "« il la suit mal », c'est « il ne la suit pas ».",
        "  toute table de langues déclarée est reposée à chaque lancement, par "
        "la même fusion que les clés imposées : la langue échappe au "
        "propriétaire — changée dans l'émulateur, elle reviendra au prochain "
        "jeu. « retro langue » est l'endroit où elle se change.",
    ])
    assert "pose « french »" not in texte, (
        "une langue jamais posée est annoncée à l'indicatif présent")


def test_le_titre_et_la_premiere_ligne_n_emploient_pas_le_meme_mot():
    """Le titre porte le RÉGLAGE brut (« auto »), la première ligne la valeur
    RÉSOLUE. Le même mot pour les deux faisait surmonter « aucune langue
    demandée » d'un « Langue — demandée « auto » » : deux référents, lus comme
    une contradiction."""
    texte = _rapport_langue(langue="auto", langue_temoin=None)
    assert "Langue — réglage « auto »" in texte
    assert "Langue — demandée" not in texte
    assert "  · aucune langue demandée — " in texte


def test_le_motif_ecrit_par_le_lanceur_est_lu_et_rendu():
    """Le témoin porte un `motif=` que rien ne lisait côté Python. C'est la
    seule chose qui dise pourquoi LE DERNIER jeu est parti dans cette
    langue-là — cité tel quel, sans accents : c'est le lanceur qui parle."""
    texte = _rapport_langue(
        langue="japanese",
        langue_temoin={"steam": "french", "langue": "french",
                       "motif": "auto : Steam dit french"})
    assert ("      le dernier jeu a demandé « french » (le lanceur a noté : "
            "« auto : Steam dit french ») : le réglage a changé depuis, le "
            "prochain suivra la ligne ci-dessus") in texte


def test_une_langue_manuelle_explique_la_valeur_de_steam_meme_hors_liste():
    """La combinaison qu'aucun autre test ne couvrait, et qu'une garde de trop
    avait rendue muette : langue posée à la main, témoin portant un nom que
    « retro » ne connaît pas.

    La valeur brute reste affichée — c'est l'exigence — mais l'annotation qui
    dit pourquoi elle ne sert pas avait disparu, au motif que ce nom serait
    « dit plus haut ». Il ne l'est pas : la ligne qui nomme un nom inconnu
    n'existe que lorsque la console n'a AUCUNE langue à demander, et une
    langue posée à la main en donne toujours une. Les deux faits doivent tenir
    sur l'écran ensemble, quelle que soit la valeur du témoin.
    """
    texte = _rapport_langue(
        langue="japanese",
        langue_temoin={"steam": "klingon", "langue": "japanese",
                       "motif": "posee a la main"})
    assert ("  · au dernier lancement, Steam disait « klingon » — la langue "
            "étant posée à la main, cette valeur ne sert pas ; elle est dite "
            "pour que ce relevé reste vérifiable") in texte


# --- les clés de langue SONT des clés imposées ------------------------------
#
# `profiles.py` les classe comme telles et leur applique la garde d'en-tête à
# ce titre : le fichier promet au propriétaire trois catégories parce que la
# langue en occupe une. Les compter là et pas ici faisait dire deux choses
# différentes du même fichier par deux juges.

def test_les_cles_de_langue_comptent_parmi_les_cles_imposees(
        profils_avec_langues):
    """L'entrée de `duckstation` n'a AUCUN champ `enforced` — rien que sa
    table de langues. Elle rendait `imposees == 0`, donc « aucun réglage
    imposé », alors que la console repose `[Main] Language` à chaque
    lancement."""
    etats = status.etat_amorcage(profils_avec_langues, {})
    compte = {e.profile_id: e.imposees for e in etats}
    assert compte["duckstation"] == 1, (
        "les clés de langue ne sont pas comptées : le rapport promet un "
        "fichier que le lanceur va pourtant reprendre")
    assert compte["ppsspp"] == 0


def test_une_seule_langue_est_comptee_et_non_toutes(profils_avec_langues):
    """Deux langues déclarées, la MÊME clé chacune — `_lire_langues` l'exige.
    Les additionner rendrait 2 sur un fichier qui n'en reprend qu'une."""
    amorcage = profils_avec_langues["duckstation"].bootstraps[0]
    assert len(amorcage.langues) == 2
    assert status._cles_imposees(amorcage) == 1


def test_la_ligne_des_cles_imposees_parait_pour_une_entree_de_langue_seule(
        profils_avec_langues):
    """La ligne du rapport, et pas seulement le compte : c'est elle qui
    disparaissait de la section Amorçage."""
    lignes = status._lignes_amorcage(status.Report(
        emulators=[], systems=[], bios=[], problems=[],
        bios_root=pathlib.Path("/BIOS"),
        amorcages=status.etat_amorcage(profils_avec_langues, {})))
    assert [l for l in lignes if "impose 1 clé(s)" in l], lignes


def test_sous_auto_la_prevision_dit_DE_QUOI_elle_depend(profils_avec_langues):
    """Les lignes par entrée sont au futur, mais sous « auto » elles dérivent
    d'une mesure PASSÉE — la valeur que le lanceur a lue chez Steam au dernier
    lancement. Le propriétaire qui change sa langue dans Steam lisait
    « duckstation : « french » » alors que son prochain jeu partirait en
    japonais.

    Le qualificatif est corrigé, pas la mécanique : l'hôte n'atteint pas ce
    registre, et c'est la raison d'être du témoin."""
    texte = _rapport_langue(
        profils_avec_langues, langue="auto",
        langue_temoin={"steam": "french", "langue": "french",
                       "motif": "auto : Steam dit french"})
    assert ("  ce que chaque entrée d'amorçage posera au prochain jeu, si "
            "Steam dit toujours « french » — c'est ce qu'il disait au dernier "
            "lancement, et l'hôte ne lit pas ce registre :") in texte, texte


def test_une_langue_posee_a_la_main_ne_depend_de_rien(profils_avec_langues):
    """Elle vient de `langue.txt`, qui est lu ICI et maintenant : ajouter une
    condition ferait douter d'une prévision qui, elle, est certaine."""
    texte = _rapport_langue(
        profils_avec_langues, langue="french",
        langue_temoin={"steam": "japanese", "langue": "french",
                       "motif": "posee a la main"})
    assert "  ce que chaque entrée d'amorçage posera au prochain jeu :" in texte


def test_sous_auto_sans_valeur_de_steam_la_prevision_le_dit_aussi(
        profils_avec_langues):
    """Steam muet vaut « le repli partout » — mais le prochain lancement peut
    très bien lire une valeur. La prévision reste conditionnelle."""
    texte = _rapport_langue(profils_avec_langues, langue="auto",
                            langue_temoin=None)
    assert ("  ce que chaque entrée d'amorçage posera au prochain jeu, si "
            "Steam n'en dit toujours rien — l'hôte ne lit pas ce registre, il "
            "ne sait que ce que le dernier lancement en a rapporté :") in texte


# --- le QUATRIÈME état : « mesuré, cet émulateur n'a rien à régler » --------
#
# `langue_absente` est au rapport ce que `fill_absent` est à la section Rendu.
# Les trois états précédents en cachaient deux dans un seul : « aucune table de
# langues déclarée » se disait aussi bien d'un fichier qui n'a AUCUN réglage de
# langue que d'une table que personne n'a relevée. Les deux se lisent à l'écran
# de la même façon — un jeu en anglais — et n'appellent pas le même geste :
# l'une est finie, l'autre est un relevé qui reste dû.

PROFIL_STATUS_LANGUE_ABSENTE = """
schema = 1
id = "rpcs3"
exe = 'rpcs3.exe'
[[bootstrap]]
target = '{install_dir}\\config\\input_configs\\global\\Default.yml'
content = '''
# Écrit par « retro » au premier lancement, parce que ce fichier était absent.
Player 1 Input:
  Handler: XInput
'''
langue_absente = "ce fichier ne porte que le gestionnaire de manette"
[[system]]
id = "ps3"
name = "PlayStation 3"
extensions = [".bin"]
launch = '"{rom}"'
"""


@pytest.fixture
def profils_avec_langue_absente(tmp_path):
    """Les trois états d'entrée côte à côte : une table, un aveu d'absence,
    et une entrée que personne n'a relevée."""
    avec = tmp_path / "duckstation-langue.toml"
    avec.write_text(PROFIL_STATUS_LANGUE, encoding="utf-8")
    sans = tmp_path / "ppsspp-langue.toml"
    sans.write_text(PROFIL_STATUS_SANS_LANGUE, encoding="utf-8")
    absente = tmp_path / "rpcs3-langue.toml"
    absente.write_text(PROFIL_STATUS_LANGUE_ABSENTE, encoding="utf-8")
    return {"duckstation": profiles.load_profile(avec),
            "ppsspp": profiles.load_profile(sans),
            "rpcs3": profiles.load_profile(absente)}


def test_une_entree_sans_reglage_de_langue_porte_sa_raison(
        profils_avec_langue_absente):
    """`etat_langues` doit rendre la RAISON, pas seulement un booléen de
    plus : c'est elle que le rapport affiche, et sans elle le quatrième état
    ne se distingue du troisième que par une nuance de formulation."""
    etats = status.etat_langues(profils_avec_langue_absente, voulue="french")
    muet = next(e for e in etats if e.profile_id == "rpcs3")
    assert not muet.declared
    assert muet.absente == "ce fichier ne porte que le gestionnaire de manette"


def test_le_rapport_distingue_un_releve_du_a_un_constat_d_impossibilite(
        profils_avec_langue_absente):
    """Les deux phrases doivent DIFFÉRER dans le rapport. Sans cela, un oubli
    de relevé a exactement la même trace à l'écran qu'un constat
    d'impossibilité, et le rapport dit des deux la même chose."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        profils=profils_avec_langue_absente, langue="french",
        langue_temoin={"steam": "french", "langue": "french",
                       "motif": "posée à la main"}))
    section = _section_langue(texte)
    # Le relevé qui reste dû garde sa phrase — c'est celle que D12 tient en
    # vue, et la changer ferait disparaître la dette du rapport.
    assert "ppsspp" in section and "aucune table de langues déclarée" in section
    # Le constat, lui, porte SA raison, et ne se dit pas « déclarée » : il
    # n'y a rien à déclarer.
    assert "ce fichier ne porte que le gestionnaire de manette" in section
    ligne_rpcs3 = next(l for l in section.splitlines() if "rpcs3" in l)
    assert "aucune table de langues déclarée" not in ligne_rpcs3


def test_un_constat_d_impossibilite_n_appelle_aucun_releve(
        profils_avec_langue_absente):
    """La conséquence collective — « un émulateur sans table pose ses propres
    défauts » — vaut pour les deux. Ce qui ne vaut que pour l'un est le
    GESTE : une entrée dont l'absence est mesurée est FINIE, et le rapport ne
    doit pas envoyer relever ce qui a déjà été relevé."""
    etats = status.etat_langues(profils_avec_langue_absente, voulue="french")
    a_relever = [e.profile_id for e in etats
                 if not e.declared and not e.absente]
    assert a_relever == ["ppsspp"]
