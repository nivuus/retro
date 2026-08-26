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


PROFIL_DUCKSTATION = """
schema = 1
id = "duckstation"
exe = "duckstation-qt-x64-ReleaseLTCG.exe"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".chd"]
launch = '-fullscreen "{rom}"'
bios = []
"""

MANIFESTE_NOYAU = """
schema = 1
[emulator.retroarch]
name        = "RetroArch"
version     = "1.0"
url         = "https://exemple.invalid/RetroArch.7z"
sha256      = "00"
archive     = "7z"
install_dir = "RetroArch"
profile     = "retroarch"
"""

MANIFESTE_UTILISATEUR = """
schema = 1
[emulator.duckstation]
name        = "DuckStation"
version     = "0.1"
url         = "https://exemple.invalid/duckstation.zip"
sha256      = "00"
archive     = "zip"
install_dir = "DuckStation-v0.1"
profile     = "duckstation"
"""


def _prepare_duckstation(tmp_path):
    """Un profil hors noyau, sa ROM, et les deux manifestes qui vont avec."""
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "duckstation.toml").write_text(PROFIL_DUCKSTATION, encoding="utf-8")
    roms = tmp_path / "ROMs" / "psx"
    roms.mkdir(parents=True)
    (roms / "Tekken 3 (Europe).chd").write_bytes(b"x")
    noyau = tmp_path / "core.toml"
    noyau.write_text(MANIFESTE_NOYAU, encoding="utf-8")
    utilisateur = tmp_path / "emulators.toml"
    utilisateur.write_text(MANIFESTE_UTILISATEUR, encoding="utf-8")
    return profils, noyau, utilisateur


def test_scan_honore_le_manifeste_utilisateur(tmp_path, capsys):
    """Le manifeste utilisateur est l'échappatoire juridique du projet.

    Le dépôt public ne référence aucun émulateur au statut contesté ; le
    propriétaire ajoute les siens hors dépôt. `scan` ignorait ce fichier et
    retombait sur l'identifiant du profil : un emulators.toml déclarant
    install_dir = "DuckStation-v0.1" s'installait bien là, mais l'inventaire
    pointait D:\\Emulation\\duckstation\\..., un chemin qui n'existe pas. La
    garde de `sync` le laissait passer — il est bien sous la racine — Steam
    créait l'entrée, le rapport annonçait « + Tekken 3 », et rien ne se
    lançait.
    """
    profils, noyau, utilisateur = _prepare_duckstation(tmp_path)
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--output", str(sortie),
                     "--manifest", str(noyau),
                     "--user-manifest", str(utilisateur),
                     "--emulation-root", "D:\\Emulation"])
    assert code == 0
    d = json.loads(sortie.read_text(encoding="utf-8"))
    assert d[0]["emulator_exe"] == (
        "D:\\Emulation\\DuckStation-v0.1\\duckstation-qt-x64-ReleaseLTCG.exe")
    assert d[0]["start_dir"] == "D:\\Emulation\\DuckStation-v0.1"


def test_scan_avertit_quand_aucun_manifeste_ne_couvre_un_profil(tmp_path, capsys):
    """Le repli sur l'identifiant du profil produit un raccourci invalide.

    Sans entrée de manifeste, rien ne dit où l'émulateur est installé. Le repli
    devine un dossier ; la garde de `sync` ne le rattrape pas, puisque le
    chemin deviné reste sous la racine d'émulation. Steam créerait l'entrée et
    elle ne lancerait rien : ça doit au moins s'entendre.
    """
    profils, noyau, _ = _prepare_duckstation(tmp_path)
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--output", str(sortie),
                     "--manifest", str(noyau),
                     "--emulation-root", "D:\\Emulation"])
    assert code == 0
    err = capsys.readouterr().err
    assert "duckstation" in err
    assert "manifest" in err.lower()


def test_scan_ne_previent_pas_quand_le_manifeste_couvre_tout(tmp_path, capsys):
    """L'avertissement doit rester rare, sinon il ne se lit plus."""
    profils, noyau, utilisateur = _prepare_duckstation(tmp_path)
    cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
              "--profiles", str(profils), "--output", str(tmp_path / "inv.json"),
              "--manifest", str(noyau), "--user-manifest", str(utilisateur),
              "--emulation-root", "D:\\Emulation"])
    assert capsys.readouterr().err == ""
