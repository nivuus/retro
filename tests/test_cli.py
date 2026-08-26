"""Interface en ligne de commande."""
import json
import pathlib
import subprocess
import sys

from retro import cli


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
exe = "r.exe"
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
