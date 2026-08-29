"""Interface en ligne de commande."""
import json
import pathlib
import subprocess
import sys

from retro import cli, launcher
from retro.steam import appid, entry, vdf_io

PROFIL_AMORCE_CLI = """
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


def test_sync_sans_inventaire_echoue_proprement(tmp_path, capsys):
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--inventory", str(tmp_path / "absent.json")])
    assert code != 0
    assert "absent.json" in capsys.readouterr().err


def test_sync_sans_compte_steam_echoue_proprement(tmp_path, capsys):
    inventaire = tmp_path / "inv.json"
    inventaire.write_text("[]")
    (tmp_path / "userdata").mkdir()
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--inventory", str(inventaire)])
    assert code != 0
    assert "connect" in capsys.readouterr().err.lower()


def test_inventaire_malforme_ne_leve_pas_de_trace(tmp_path, capsys):
    """Une console sans clavier ni écran ne doit jamais rendre de trace Python."""
    (tmp_path / "userdata" / "123" / "config").mkdir(parents=True)
    mauvais = tmp_path / "inv.json"
    mauvais.write_text("{ceci n'est pas du JSON")
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--inventory", str(mauvais)])
    assert code != 0
    assert "Traceback" not in capsys.readouterr().err


def test_sync_complet(tmp_path, capsys):
    (tmp_path / "userdata" / "123" / "config").mkdir(parents=True)
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": "D:\\Emulation\\RetroArch\\retroarch.exe",
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "D:\\Emulation\\RetroArch",
        "extra_tags": ["1995"],
    }]))
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--inventory", str(inventaire)])
    assert code == 0
    assert "Chrono Trigger" in capsys.readouterr().out


def test_sync_shortcuts_illisible_ne_rend_pas_de_trace(tmp_path, capsys):
    """sync.sync_account est le dernier appel de _cmd_sync, hors de tout
    try/except : vdf_io.load_shortcuts lève ShortcutsError sur un
    shortcuts.vdf illisible ou malformé, et cette exception remontait telle
    quelle. `retro sync` est lancé par l'hôte, sans personne devant l'écran,
    et c'est justement le fichier dont la corruption casse la bibliothèque
    Steam du propriétaire : une trace Python y est encore moins acceptable
    qu'ailleurs.
    """
    config = tmp_path / "userdata" / "123" / "config"
    config.mkdir(parents=True)
    (config / "shortcuts.vdf").write_bytes(b"ceci n'est pas du VDF binaire")
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": "D:\\Emulation\\RetroArch\\retroarch.exe",
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "D:\\Emulation\\RetroArch",
    }]))
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--emulation-root", "D:\\Emulation",
                     "--inventory", str(inventaire)])
    err = capsys.readouterr().err
    assert code != 0
    assert "Traceback" not in err


def test_emulation_root_erronee_est_refusee(tmp_path, capsys):
    """Sans cette garde, is_owned est faux pour NOS PROPRES entrées : chaque
    passage les réécrit sans les reconnaître, et trois passages produisent trois
    fois la même entrée en annonçant « + Chrono Trigger » à chaque fois.
    """
    config = tmp_path / "userdata" / "123" / "config"
    config.mkdir(parents=True)
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": "E:\\Autre\\RetroArch\\retroarch.exe",
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "E:\\Autre\\RetroArch",
    }]))
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--emulation-root", "D:\\Emulation",
                     "--inventory", str(inventaire)])
    assert code != 0
    err = capsys.readouterr().err
    assert "--emulation-root" in err and "E:\\Autre\\RetroArch\\retroarch.exe" in err
    assert not (config / "shortcuts.vdf").exists(), "écrit malgré le refus"


def test_emulation_root_juste_ne_bloque_pas(tmp_path, capsys):
    """La garde ne doit pas refuser le cas nominal."""
    (tmp_path / "userdata" / "123" / "config").mkdir(parents=True)
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": "D:\\Emulation\\RetroArch\\retroarch.exe",
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "D:\\Emulation\\RetroArch",
    }]))
    assert cli.main(["sync", "--steam-root", str(tmp_path),
                     "--emulation-root", "D:\\Emulation",
                     "--inventory", str(inventaire)]) == 0


def test_emulation_root_avec_espace_est_acceptee(tmp_path, capsys):
    """entry.is_under_root attend le champ exe au format Steam (guillemeté).

    _cmd_sync doit donc guillemeter rom.emulator_exe avant de le passer à la
    garde, exactement comme build_shortcut le fait pour écrire — sinon une
    racine d'émulation contenant un espace coupe le chemin au premier espace
    et la garde refuse à tort une configuration pourtant valide.
    """
    (tmp_path / "userdata" / "123" / "config").mkdir(parents=True)
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": "D:\\Mes Emulateurs\\RetroArch\\retroarch.exe",
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "D:\\Mes Emulateurs\\RetroArch",
    }]))
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--emulation-root", "D:\\Mes Emulateurs",
                     "--inventory", str(inventaire)])
    assert code == 0, capsys.readouterr().err


def _profil_minimal(tmp_path):
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "p.toml").write_text("""
schema = 1
id = "r"
exe = 'R-x64\\r.exe'
[[system]]
id = "snes"
name = "SNES"
extensions = [".sfc"]
launch = '-f "{rom}"'
bios = []
""", encoding="utf-8")
    return profils


def test_status_bios_qui_leve_ne_rend_pas_de_trace(tmp_path, monkeypatch, capsys):
    """_cmd_status annonce dans sa propre docstring couvrir tout ce qui
    empêche de PRODUIRE le rapport, mais bios.check_bios et les appels à
    status.build_report/format_report vivaient hors du bloc try/except.
    Toute exception qu'ils lèvent remontait donc telle quelle — une trace
    Python sur la seule commande du paquet faite pour être lue par un
    humain, depuis son canapé, sans clavier ni écran.
    """
    profils = _profil_minimal(tmp_path)
    roms = tmp_path / "ROMs"
    roms.mkdir()
    bios_dir = tmp_path / "bios"
    bios_dir.mkdir()

    def _casse(*a, **k):
        raise RuntimeError("panne simulée dans check_bios")

    monkeypatch.setattr(cli.bios, "check_bios", _casse)
    code = cli.main(["status", "--roms", str(roms), "--profiles", str(profils),
                     "--emulation-root", "D:\\Emulation", "--bios", str(bios_dir)])
    err = capsys.readouterr().err
    assert code == 2
    assert "Traceback" not in err
    assert "panne simulée dans check_bios" in err


def test_status_avec_bios_md5_non_textuel_echoue_proprement(tmp_path, capsys):
    """Reproduction du relecteur : md5 sans guillemets se parse en entier
    TOML, et sans validation de type au chargement du profil, `retro status`
    rendait une trace Python complète au lieu du code 2 attendu."""
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "p.toml").write_text("""
schema = 1
id = "r"
exe = "r.exe"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".chd"]
launch = '-f "{rom}"'
bios = [{ file = "scph5501.bin", md5 = 5501, required = true }]
""", encoding="utf-8")
    roms = tmp_path / "ROMs"
    roms.mkdir()
    bios_dir = tmp_path / "bios"
    bios_dir.mkdir()
    code = cli.main(["status", "--roms", str(roms), "--profiles", str(profils),
                     "--emulation-root", "D:\\Emulation", "--bios", str(bios_dir)])
    err = capsys.readouterr().err
    assert code == 2
    assert "Traceback" not in err


def test_invocation_en_module_ne_reussit_pas_sans_rien_faire():
    """`python -m retro.cli` est ce qu'un contributeur essaie avant d'installer
    le paquet. Sans bloc __main__, il rendait 0 sans rien faire ni rien dire."""
    racine = pathlib.Path(__file__).parent.parent
    r = subprocess.run([sys.executable, "-m", "retro.cli"],
                       cwd=racine, capture_output=True, text=True)
    assert r.returncode != 0, f"réussite muette : {r.stdout!r}"
    assert "retro" in r.stderr


def test_sync_renseigne_le_champ_icon(tmp_path, capsys):
    """sync_account sait renseigner le champ icon depuis la tâche 4, mais
    _cmd_sync ne lui passait jamais grid_dir_windows : en production le champ
    restait vide, et Steam affichait un raccourci sans icône alors que le
    fichier était déposé à côté. Le dossier de grille se dérive de
    --steam-root-windows, le chemin par lequel la CONSOLE voit l'installation
    — aucun appel réseau.

    Ce test exigeait « {tmp_path}\\userdata\\... » : il figeait en résultat
    attendu le chemin mi-POSIX mi-Windows que Steam n'ouvre jamais. Le seul
    test de bout en bout du câblage documentait le défaut au lieu d'en
    protéger.
    """
    config = tmp_path / "userdata" / "123" / "config"
    (config / "grid").mkdir(parents=True)
    exe = "D:\\Emulation\\RetroArch\\retroarch.exe"
    legacy = appid.legacy_appid(entry.quote(exe), "Chrono Trigger")
    (config / "grid" / f"{legacy}_icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": exe,
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "D:\\Emulation\\RetroArch",
    }]))
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--steam-root-windows", "D:\\Steam",
                     "--emulation-root", "D:\\Emulation",
                     "--inventory", str(inventaire)])
    assert code == 0, capsys.readouterr().err
    relu = vdf_io.load_shortcuts(config / "shortcuts.vdf")
    attendu = f"D:\\Steam\\userdata\\123\\config\\grid\\{legacy}_icon.png"
    assert relu[0]["icon"] == attendu


def test_sync_laisse_le_champ_icon_vide_sans_fichier(tmp_path, capsys):
    """Le pendant du test précédent : sans icône déposée, rien à référencer.
    Sans lui, un chemin écrit en dur passerait le test qui précède."""
    config = tmp_path / "userdata" / "123" / "config"
    config.mkdir(parents=True)
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": "D:\\Emulation\\RetroArch\\retroarch.exe",
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "D:\\Emulation\\RetroArch",
    }]))
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--emulation-root", "D:\\Emulation",
                     "--inventory", str(inventaire)])
    assert code == 0, capsys.readouterr().err
    relu = vdf_io.load_shortcuts(config / "shortcuts.vdf")
    assert relu[0]["icon"] == ""


# --- --steam-root local / --steam-root-windows -----------------------------


def _inventaire_ct(tmp_path, exe="D:\\Emulation\\RetroArch\\retroarch.exe"):
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": exe,
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "D:\\Emulation\\RetroArch",
    }]))
    return inventaire


def test_le_champ_icon_ne_melange_pas_les_separateurs(tmp_path, capsys):
    """Mesuré : --steam-root /mnt/steam écrivait
    « /mnt/steam\\userdata\\...\\grid\\..._icon.png », mi-POSIX mi-Windows.
    Steam n'affichait jamais l'icône, et le rapport annonçait « + Chrono
    Trigger » avec rc = 0. Le précédent est dans le même fichier : `scan` a
    --roms et --roms-windows pour exactement cette distinction.
    """
    config = tmp_path / "userdata" / "123" / "config"
    (config / "grid").mkdir(parents=True)
    exe = "D:\\Emulation\\RetroArch\\retroarch.exe"
    legacy = appid.legacy_appid(entry.quote(exe), "Chrono Trigger")
    (config / "grid" / f"{legacy}_icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--steam-root-windows", "D:\\Steam",
                     "--emulation-root", "D:\\Emulation",
                     "--inventory", str(_inventaire_ct(tmp_path))])
    assert code == 0, capsys.readouterr().err
    icone = vdf_io.load_shortcuts(config / "shortcuts.vdf")[0]["icon"]
    assert "/" not in icone, f"chemin bâtard : {icone}"
    assert icone == f"D:\\Steam\\userdata\\123\\config\\grid\\{legacy}_icon.png"


def test_une_racine_steam_windows_en_posix_est_refusee(tmp_path, capsys):
    """Donner un chemin POSIX à --steam-root-windows reproduirait le défaut
    en silence : Steam lirait un chemin qu'il ne sait pas ouvrir."""
    (tmp_path / "userdata" / "123" / "config").mkdir(parents=True)
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--steam-root-windows", "/mnt/steam",
                     "--emulation-root", "D:\\Emulation",
                     "--inventory", str(_inventaire_ct(tmp_path))])
    assert code != 0
    err = capsys.readouterr().err
    assert "--steam-root-windows" in err
    assert "Traceback" not in err


def test_status_dit_ce_que_l_emulateur_manquant_coute(tmp_path, capsys):
    """« l'émulateur r n'est pas installé » ne dit pas au propriétaire
    pourquoi ses jeux ont disparu de Steam. C'est le seul écran du projet fait
    pour être lu : le coût du manque y a sa place."""
    profils = _profil_minimal(tmp_path)
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu.sfc").write_bytes(b"x")
    bios_dir = tmp_path / "bios"
    bios_dir.mkdir()
    emulation = tmp_path / "Emulation"
    emulation.mkdir()
    code = cli.main(["status", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils),
                     "--emulation-root", str(emulation),
                     "--bios", str(bios_dir)])
    out = capsys.readouterr().out
    assert code == 0
    assert "SNES : 1 jeu ignoré" in out
    assert "retro install" in out


def test_status_ne_reproche_rien_quand_l_emulateur_est_la(tmp_path, capsys):
    """Le pendant : un émulateur installé ne doit produire aucun constat."""
    profils = _profil_minimal(tmp_path)
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu.sfc").write_bytes(b"x")
    bios_dir = tmp_path / "bios"
    bios_dir.mkdir()
    emu = tmp_path / "Emulation" / "r"
    (emu / "R-x64").mkdir(parents=True)
    (emu / "R-x64" / "r.exe").write_bytes(b"MZ")
    (emu / ".retro-version").write_text("1.0\n", encoding="utf-8")
    code = cli.main(["status", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils),
                     "--emulation-root", str(tmp_path / "Emulation"),
                     "--bios", str(bios_dir)])
    out = capsys.readouterr().out
    assert code == 0
    assert "ignoré" not in out
    assert "l'émulateur « r »" not in out


def test_status_dit_la_meme_chose_avec_ou_sans_rom(tmp_path, capsys):
    """Les deux exécutions doivent concorder.

    Le verdict se déduisait de la liste des systèmes ignorés, qui filtre les
    systèmes sans ROM : le même disque rendait « r  absent » sur des dossiers
    vides et « r  présent, sans témoin » dès qu'une ROM y tombait. C'est faux
    au moment le plus probable — une console fraîchement provisionnée, avant
    que le propriétaire ait rien déposé.
    """
    profils = _profil_minimal(tmp_path)
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    bios_dir = tmp_path / "bios"
    bios_dir.mkdir()
    emu = tmp_path / "Emulation" / "r" / "R-x64"
    emu.mkdir(parents=True)
    (emu / "r.exe").write_bytes(b"MZ")  # posé à la main : pas de témoin

    argv = ["status", "--roms", str(tmp_path / "ROMs"),
            "--profiles", str(profils),
            "--emulation-root", str(tmp_path / "Emulation"),
            "--bios", str(bios_dir)]
    assert cli.main(argv) == 0
    vide = capsys.readouterr().out
    (roms / "Jeu.sfc").write_bytes(b"x")
    assert cli.main(argv) == 0
    plein = capsys.readouterr().out

    def verdict(texte):
        return [l for l in texte.splitlines() if l.strip().startswith("r ")]

    assert verdict(vide) == verdict(plein), f"{verdict(vide)} != {verdict(plein)}"
    assert "sans témoin" in vide
    assert "l'émulateur « r » n'est pas installé" not in vide


def test_status_lit_aussi_les_profils_du_proprietaire(tmp_path, capsys):
    """`status` et `scan` doivent voir les MÊMES émulateurs.

    Les donner à l'un et pas à l'autre reproduirait le défaut des manifestes :
    une commande rapporte l'état d'un parc que l'autre n'inventorie pas, et le
    propriétaire n'a aucun moyen de trancher. Un émulateur du propriétaire
    déclaré au manifeste mais dont le profil n'était pas lu était en outre
    accusé d'être « deviné » : le rapport réclamait de déclarer ce qui l'était
    déjà.
    """
    profils = _profil_minimal(tmp_path)
    mien = tmp_path / "mes-profils"
    mien.mkdir()
    (mien / "duckstation.toml").write_text("""
schema = 1
id = "duckstation"
exe = 'DuckStation-x64\\duckstation-qt-x64-ReleaseLTCG.exe'
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".chd"]
launch = '-fullscreen "{rom}"'
bios = []
""", encoding="utf-8")
    roms = tmp_path / "ROMs" / "psx"
    roms.mkdir(parents=True)
    (roms / "Tekken 3 (Europe).chd").write_bytes(b"x")
    bios_dir = tmp_path / "bios"
    bios_dir.mkdir()
    code = cli.main(["status", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--user-profiles", str(mien),
                     "--emulation-root", str(tmp_path / "Emulation"),
                     "--bios", str(bios_dir)])
    out = capsys.readouterr().out
    assert code == 0
    assert "PlayStation : 1 jeu ignoré" in out
    assert "duckstation" in out


# --- « 0 ROM répertoriée » doit dire POURQUOI ------------------------------

_PROFIL_MIN = """
schema = 1
id = "retroarch"
exe = 'retroarch.exe'
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-f "{rom}"'
bios = []
"""
_MANIFESTE_MIN = """
schema = 1
[emulator.retroarch]
name        = "RetroArch"
version     = "1"
url         = "https://example.invalid/ra.7z"
sha256      = "0000000000000000000000000000000000000000000000000000000000000000"
archive     = "7z"
install_dir = "RetroArch"
profile     = "retroarch"
"""


def _scan_sur(tmp_path, arborescence):
    """Lance `retro scan` sur une arborescence donnée et rend sa sortie."""
    for chemin in arborescence:
        f = tmp_path / "ROMs" / chemin
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    (tmp_path / "ROMs").mkdir(exist_ok=True)
    prof = tmp_path / "profiles"
    prof.mkdir()
    (prof / "ra.toml").write_text(_PROFIL_MIN, encoding="utf-8")
    man = tmp_path / "core.toml"
    man.write_text(_MANIFESTE_MIN, encoding="utf-8")
    return cli.main([
        "scan", "--roms", str(tmp_path / "ROMs"), "--profiles", str(prof),
        "--manifest", str(man), "--output", str(tmp_path / "inv.json"),
    ])


def test_scan_annonce_le_paquet_en_premiere_ligne(tmp_path, capsys):
    """`scan` est la commande dont deux exécutions ont rendu deux résultats
    différents le 2026-08-29. Qui compare deux scans doit voir d'un coup
    d'œil qu'ils ne viennent pas du même paquet — donc en PREMIÈRE ligne."""
    from retro import identite as identite_mod
    assert _scan_sur(tmp_path, ["Snes/Zelda.sfc"]) == 0
    premiere = capsys.readouterr().out.splitlines()[0]
    assert premiere == f"paquet : {identite_mod.VERSION}"


def test_scan_vide_explique_ce_qu_il_a_vu_et_attendu(tmp_path, capsys):
    """« 0 ROM répertoriée » est vrai et inutile : la bibliothèque est-elle
    vide, mal montée, ou rangée sous d'autres noms ? Mesuré sur une
    bibliothèque réelle et bien remplie."""
    assert _scan_sur(tmp_path, ["Atari/5200/jeu.a52"]) == 0
    sortie = capsys.readouterr().out
    assert "Atari\\5200" in sortie          # ce qui a été vu
    assert "Super Nintendo" in sortie       # ce qui était attendu
    assert "folders" in sortie              # quoi faire


def test_scan_partiel_ne_tait_pas_les_dossiers_ignores(tmp_path, capsys):
    """Le piège : trois systèmes reconnus suffisaient à faire taire les trois
    autres, et l'inventaire amputé s'annonçait complet."""
    assert _scan_sur(tmp_path, ["Snes/Zelda.sfc", "Atari/5200/jeu.a52"]) == 0
    sortie = capsys.readouterr().out
    assert "1 ROM(s) répertoriée(s)" in sortie
    assert "Atari\\5200" in sortie


def test_scan_racine_sans_aucun_dossier_le_dit(tmp_path, capsys):
    assert _scan_sur(tmp_path, []) == 0
    assert "vide" in capsys.readouterr().out


# --- Steam Input dans le rapport --------------------------------------------

def _compte_steam(tmp_path, raccourcis, localconfig=None):
    """Un compte Steam local, avec ses raccourcis et ses réglages."""
    config = tmp_path / "steam" / "userdata" / "123" / "config"
    config.mkdir(parents=True)
    (config / "shortcuts.vdf").write_bytes(vdf_io.dumps_shortcuts(raccourcis))
    if localconfig is not None:
        (config / "localconfig.vdf").write_text(localconfig, encoding="utf-8")
    return tmp_path / "steam"


def _entree_retro(appid, titre):
    return {
        "appid": appid, "appname": titre,
        "exe": '"D:\\Emulation\\_launcher\\retro-launch.exe"',
        "StartDir": '"D:\\Emulation\\_launcher"', "icon": "",
        "ShortcutPath": "", "LaunchOptions": "r.snes \"G:\\x.sfc\"",
        "IsHidden": 0, "AllowDesktopConfig": 1, "AllowOverlay": 1, "OpenVR": 0,
        "Devkit": 0, "DevkitGameID": "", "DevkitOverrideAppID": 0,
        "LastPlayTime": 0, "tags": {"0": "Rétro"},
    }


LOCALCONFIG_TOUT_ACTIF = '"UserLocalConfigStore"\n{\n\t"apps"\n\t{\n\t}\n}\n'


def _status(tmp_path, steam_root=None):
    roms = tmp_path / "ROMs"
    roms.mkdir(exist_ok=True)
    bios_dir = tmp_path / "bios"
    bios_dir.mkdir(exist_ok=True)
    argv = ["status", "--roms", str(roms), "--profiles", str(_profil_minimal(tmp_path)),
            "--emulation-root", "D:\\Emulation", "--bios", str(bios_dir)]
    if steam_root is not None:
        argv += ["--steam-root", str(steam_root)]
    return cli.main(argv)


def test_status_signale_les_jeux_dont_steam_input_est_actif(tmp_path, capsys):
    """Sans cela, une manette muette ne se découvre que le pad en main."""
    racine = _compte_steam(tmp_path, [_entree_retro(-77, "Muet")],
                           LOCALCONFIG_TOUT_ACTIF)
    assert _status(tmp_path, racine) == 0
    sortie = capsys.readouterr().out
    assert "Steam Input" in sortie and "Muet" in sortie


def test_status_ignore_les_jeux_qui_ne_sont_pas_de_retro(tmp_path, capsys):
    """localconfig.vdf porte les réglages du propriétaire : ses jeux à lui
    n'ont pas à être reprochés par un rapport qui parle d'émulation."""
    etranger = dict(_entree_retro(-88, "Jeu perso"),
                    exe='"C:\\Jeux\\perso.exe"', tags={"0": "Favoris"})
    racine = _compte_steam(tmp_path, [etranger], LOCALCONFIG_TOUT_ACTIF)
    assert _status(tmp_path, racine) == 0
    assert "Jeu perso" not in capsys.readouterr().out


def test_status_sans_steam_root_ne_parle_pas_de_steam_input(tmp_path, capsys):
    """L'option est facultative : un rapport doit rester rendable sans Steam."""
    assert _status(tmp_path) == 0
    assert "Steam Input" not in capsys.readouterr().out


def test_status_dit_ce_qui_l_empeche_de_verifier_steam_input(tmp_path, capsys):
    """localconfig.vdf absent : le rapport le dit plutôt que de se taire, et
    il rend quand même tout le reste — c'est une consultation."""
    racine = _compte_steam(tmp_path, [_entree_retro(-77, "Muet")])  # sans localconfig
    assert _status(tmp_path, racine) == 0
    sortie = capsys.readouterr().out
    assert "localconfig.vdf" in sortie


# --- retro launcher --reamorcer ---------------------------------------------

def test_launcher_reamorcer(tmp_path, capsys):
    """Le geste est disponible depuis la ligne de commande, et il nomme le
    fichier écrit — sans quoi rien ne dit que l'ordre est parti."""
    from retro import launcher, profiles
    profil = tmp_path / "duckstation.toml"
    profil.write_text(PROFIL_AMORCE_CLI, encoding="utf-8")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation",
                         {"duckstation": profiles.load_profile(profil)},
                         {"duckstation": "DS"})
    code = cli.main(["launcher", "--emulation-root-local", str(tmp_path),
                     "--reamorcer", "duckstation"])
    assert code == 0
    assert "duckstation" in capsys.readouterr().out


def test_launcher_reamorcer_un_inconnu_echoue(tmp_path, capsys):
    """Un profil mal orthographié doit s'entendre dire, pas se taire."""
    code = cli.main(["launcher", "--emulation-root-local", str(tmp_path),
                     "--reamorcer", "duckstaton"])
    assert code == 2
    assert "duckstaton" in capsys.readouterr().err


def test_launcher_dit_qu_un_binaire_perime_est_a_recompiler(tmp_path, capsys):
    """« le lanceur est compilé et en place » était vrai et trompeur : un
    binaire d'avant ignore en silence les nouvelles lignes du plan. Ne pas
    rendre 0 — la panne apparaîtrait sinon devant la télévision."""
    import os
    from retro import launcher
    dossier = tmp_path / launcher.DIR
    dossier.mkdir(parents=True)
    (dossier / launcher.EXE).write_bytes(b"MZ")
    os.utime(dossier / launcher.EXE, (1_000_000, 1_000_000))
    code = cli.main(["launcher", "--emulation-root-local", str(tmp_path)])
    sortie = capsys.readouterr()
    assert code == 1
    assert "plus ancien que sa source" in sortie.err
    assert "compiler.cmd" in sortie.err
    assert "compilé et en place" not in sortie.out


# --- L'identité du paquet ---------------------------------------------------

def test_identite_rend_une_seule_ligne(capsys):
    """Une seule ligne, la version nue : c'est l'hôte qui la lit à travers
    WinRM pour la comparer à la roue qu'il a livrée, et une deuxième ligne
    « pour le confort » serait un piège d'analyse payé une fois, tard."""
    from retro import identite as identite_mod
    assert cli.main(["identite"]) == 0
    lignes = capsys.readouterr().out.splitlines()
    assert lignes == [identite_mod.VERSION]


def test_status_lit_le_temoin_des_manettes_ecrit_par_le_lanceur(tmp_path, capsys):
    """Le filet de D4 branché de bout en bout.

    `launcher.lire_pads` peut être parfait et `status` savoir le rendre : si
    `retro status` ne les relie pas, le fichier est écrit à chaque lancement,
    lu par personne, et la fonctionnalité entière est INERTE — sans un mot, ce
    qui est très exactement la faute que ce dépôt passe son temps à traquer.

    C'est le même contrat que `lire_amorcages`, et il n'a pas d'autre gardien
    que ce test : les deux moitiés vivent dans deux langages.
    """
    roms = tmp_path / "ROMs"
    roms.mkdir(exist_ok=True)
    bios_dir = tmp_path / "bios"
    bios_dir.mkdir(exist_ok=True)
    racine = tmp_path / "Emulation"
    dossier = launcher.local_dir(racine)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / launcher.TEMOIN_PADS).write_text(
        "2026-09-01 21:14:33\t1\n"
        "0\t045e:028e\tController (Xbox 360 Controller for Windows)\n",
        encoding="utf-8")
    code = cli.main(["status", "--roms", str(roms),
                     "--profiles", str(_profil_minimal(tmp_path)),
                     "--emulation-root", str(racine), "--bios", str(bios_dir)])
    assert code == 0
    texte = capsys.readouterr().out
    assert "2026-09-01 21:14:33" in texte
    assert "045e:028e" in texte
    assert "Controller (Xbox 360 Controller for Windows)" in texte
