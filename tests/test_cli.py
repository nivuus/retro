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


def test_invocation_en_module_ne_reussit_pas_sans_rien_faire():
    """`python -m retro.cli` est ce qu'un contributeur essaie avant d'installer
    le paquet. Sans bloc __main__, il rendait 0 sans rien faire ni rien dire."""
    racine = pathlib.Path(__file__).parent.parent
    r = subprocess.run([sys.executable, "-m", "retro.cli"],
                       cwd=racine, capture_output=True, text=True)
    assert r.returncode != 0, f"réussite muette : {r.stdout!r}"
    assert "retro" in r.stderr
