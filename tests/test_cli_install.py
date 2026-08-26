"""Les sous-commandes install et scan."""
import json

from retro import cli


def test_install_sans_manifeste_echoue_proprement(tmp_path, capsys):
    code = cli.main(["install", "--manifest", str(tmp_path / "absent.toml"),
                     "--emulation-root", str(tmp_path / "Emu")])
    assert code != 0
    err = capsys.readouterr().err
    assert "absent.toml" in err and "Traceback" not in err


def test_scan_ecrit_un_inventaire(tmp_path, capsys):
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "p.toml").write_text("""
schema = 1
id = "retroarch"
exe = "retroarch.exe"
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-f "{rom}"'
bios = []
""", encoding="utf-8")
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu (USA).sfc").write_bytes(b"x")
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--output", str(sortie),
                     "--emulation-root", "D:\\Emulation"])
    assert code == 0
    d = json.loads(sortie.read_text(encoding="utf-8"))
    assert d[0]["title"] == "Jeu"
    assert d[0]["system_name"] == "Super Nintendo"


def test_scan_vers_un_dossier_absent_echoue_proprement(tmp_path, capsys):
    """L'écriture de l'inventaire est aussi faillible que le scan.

    Hors du try, un --output dont le dossier parent n'existe pas levait
    FileNotFoundError telle quelle : sur une console sans clavier ni écran, une
    trace Python n'est lisible par personne.
    """
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "p.toml").write_text("""
schema = 1
id = "retroarch"
exe = "retroarch.exe"
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-f "{rom}"'
bios = []
""", encoding="utf-8")
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu.sfc").write_bytes(b"x")
    sortie = tmp_path / "jamais-cree" / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--output", str(sortie),
                     "--emulation-root", "D:\\Emulation"])
    assert code != 0
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "inventaire" in err


def test_scan_sur_racine_absente_echoue_proprement(tmp_path, capsys):
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
    code = cli.main(["scan", "--roms", str(tmp_path / "jamais"),
                     "--profiles", str(profils),
                     "--output", str(tmp_path / "o.json"),
                     "--emulation-root", "D:\\Emulation"])
    assert code != 0
    assert "Traceback" not in capsys.readouterr().err


def test_l_inventaire_produit_est_lisible_par_sync(tmp_path):
    """Le contrat entre les deux sous-projets : ce que `scan` écrit, `sync`
    doit savoir le relire sans adaptation."""
    from retro.cli import _load_inventory
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
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu.sfc").write_bytes(b"x")
    sortie = tmp_path / "inv.json"
    cli.main(["scan", "--roms", str(tmp_path / "ROMs"), "--profiles", str(profils),
              "--output", str(sortie), "--emulation-root", "D:\\Emulation"])
    entries = _load_inventory(sortie)
    assert entries[0].title == "Jeu"
