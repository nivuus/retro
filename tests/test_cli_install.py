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
    doit savoir le relire sans adaptation.

    TOUS les champs sont vérifiés, pas seulement le titre. N'asserter que
    `title` laissait passer la perte de n'importe quel autre : mesuré le
    2026-08-26, forcer "launch_template": "" dans le JSON écrit gardait la
    suite entière verte. Or c'est exactement ce que `load_profile` refuse au
    niveau du profil — sans gabarit, l'émulateur s'ouvre sur son propre menu,
    sans jeu, et la console a l'air de fonctionner.
    """
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
    manifeste = tmp_path / "core.toml"
    manifeste.write_text("""
schema = 1
[emulator.r]
name        = "R"
version     = "1.0"
url         = "https://exemple.invalid/r.zip"
sha256      = "00"
archive     = "zip"
install_dir = "R-1.0"
profile     = "r"
""", encoding="utf-8")
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu.sfc").write_bytes(b"x")
    sortie = tmp_path / "inv.json"
    cli.main(["scan", "--roms", str(tmp_path / "ROMs"), "--profiles", str(profils),
              "--manifest", str(manifeste), "--roms-windows", "G:\\ROMs",
              "--output", str(sortie), "--emulation-root", "D:\\Emulation"])

    # Le JSON écrit porte exactement les clés que _load_inventory relit : une
    # clé renommée d'un côté casserait le pont, et extra_tags est facultative
    # à la relecture, donc son absence ne se verrait pas ici autrement.
    brut = json.loads(sortie.read_text(encoding="utf-8"))
    assert len(brut) == 1
    assert set(brut[0]) == {"title", "rom_path", "system_name", "emulator_exe",
                            "launch_template", "start_dir", "extra_tags"}

    entries = _load_inventory(sortie)
    assert len(entries) == 1
    e = entries[0]
    assert e.title == "Jeu"
    assert e.rom_path == "G:\\ROMs\\snes\\Jeu.sfc"
    assert e.system_name == "SNES"
    assert e.emulator_exe == "D:\\Emulation\\R-1.0\\r.exe"
    assert e.launch_template == '-f "{rom}"'
    assert e.start_dir == "D:\\Emulation\\R-1.0"
    assert e.extra_tags == ()


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


# --- scan : un émulateur absent est ignoré, et signalé ---------------------

def _profils_deux_systemes(tmp_path):
    """La forme RÉELLE de `exe` : un dossier racine d'archive, en chemin
    Windows. Une fixture au nom plat ne montre rien du seul cas où
    --emulation-root-local a une raison d'être, celui où il ne vaut pas
    --emulation-root."""
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "p.toml").write_text("""
schema = 1
id = "retroarch"
exe = 'RetroArch-Win64\\retroarch.exe'
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-f "{rom}"'
bios = []
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".chd"]
launch = '-f "{rom}"'
bios = []
""", encoding="utf-8")
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu.sfc").write_bytes(b"x")
    return profils


def test_scan_signale_le_systeme_dont_l_emulateur_manque(tmp_path, capsys):
    """Le scan inscrivait des raccourcis vers un exécutable jamais vérifié :
    une installation ratée peuplait Steam d'entrées qui ne démarrent pas. Les
    ignorer ne suffit pas — sans message, le propriétaire hérite d'une
    bibliothèque incomplète qu'aucun écran n'explique.
    """
    profils = _profils_deux_systemes(tmp_path)
    emulation = tmp_path / "Emulation"
    emulation.mkdir()
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--output", str(sortie),
                     "--emulation-root", "D:\\Emulation",
                     "--emulation-root-local", str(emulation)])
    sortie_std = capsys.readouterr()
    assert code == 0, sortie_std.err
    assert json.loads(sortie.read_text(encoding="utf-8")) == []
    assert "Super Nintendo" in sortie_std.err
    assert str(emulation / "RetroArch" / "RetroArch-Win64" / "retroarch.exe") \
        in sortie_std.err
    assert "\\" not in sortie_std.err, "chemin bâtard, mi-POSIX mi-Windows"
    assert "retro install" in sortie_std.err
    # L'hôte peut ne relayer que la sortie standard : le silence y serait le
    # même défaut sous une autre forme.
    assert "ignoré" in sortie_std.out


def test_scan_n_ignore_rien_quand_l_emulateur_est_installe(tmp_path, capsys):
    """Le pendant : la vérification ne doit pas vider la bibliothèque."""
    profils = _profils_deux_systemes(tmp_path)
    exe = tmp_path / "Emulation" / "RetroArch" / "RetroArch-Win64" / "retroarch.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    (tmp_path / "Emulation" / "RetroArch" / ".retro-version").write_text(
        "1.0\n", encoding="utf-8")
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--output", str(sortie),
                     "--emulation-root", "D:\\Emulation",
                     "--emulation-root-local", str(tmp_path / "Emulation")])
    sortie_std = capsys.readouterr()
    assert code == 0, sortie_std.err
    d = json.loads(sortie.read_text(encoding="utf-8"))
    assert [r["title"] for r in d] == ["Jeu"]
    assert "ignoré" not in sortie_std.err


def test_scan_dit_qu_un_emulateur_pose_a_la_main_n_est_pas_atteste(tmp_path, capsys):
    """L'exécutable est là, le témoin non. « cherché : ...\\retroarch.exe »
    enverrait chercher un fichier qui est là : ce qui manque est le témoin,
    donc le dossier — et la raison doit se lire."""
    profils = _profils_deux_systemes(tmp_path)
    dossier = tmp_path / "Emulation" / "RetroArch"
    (dossier / "RetroArch-Win64").mkdir(parents=True)
    (dossier / "RetroArch-Win64" / "retroarch.exe").write_bytes(b"MZ")
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--output", str(sortie),
                     "--emulation-root", "D:\\Emulation",
                     "--emulation-root-local", str(tmp_path / "Emulation")])
    err = capsys.readouterr().err
    assert code == 0, err
    assert json.loads(sortie.read_text(encoding="utf-8")) == []
    assert "témoin" in err
    assert f"dossier : {dossier}" in err


def test_le_scan_ne_calcule_les_systemes_ignores_qu_une_fois(tmp_path, monkeypatch):
    """Le CLI annonce ce qu'il ignore, puis scanne. Calculer deux fois, c'est
    deux vérités possibles sur un disque qui bouge : entre le message et
    l'inventaire, un émulateur qui apparaît ou disparaît les rend
    contradictoires. L'ensemble calculé est passé, pas recalculé."""
    profils = _profils_deux_systemes(tmp_path)
    (tmp_path / "Emulation").mkdir()
    appels = []
    vrai = cli.scan.ignored_systems

    def compter(*a, **k):
        appels.append(a)
        return vrai(*a, **k)

    monkeypatch.setattr(cli.scan, "ignored_systems", compter)
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils),
                     "--output", str(tmp_path / "inv.json"),
                     "--emulation-root", "D:\\Emulation",
                     "--emulation-root-local", str(tmp_path / "Emulation")])
    assert code == 0
    assert len(appels) == 1, f"{len(appels)} calculs, donc autant de vérités"


def test_le_message_groupe_par_emulateur(tmp_path, capsys):
    """Un RetroArch amputé sert neuf systèmes dans le profil livré. Répéter
    neuf blocs identiques — même motif, même chemin de cent caractères — pour
    UNE panne, c'est ce que le module de rapport s'interdit à lui-même. Le
    coût, lui, se compte par système."""
    profils = _profils_deux_systemes(tmp_path)
    psx = tmp_path / "ROMs" / "psx"
    psx.mkdir(parents=True)
    (psx / "Jeu.chd").write_bytes(b"x")
    emulation = tmp_path / "Emulation"
    emulation.mkdir()
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils),
                     "--output", str(tmp_path / "inv.json"),
                     "--emulation-root", "D:\\Emulation",
                     "--emulation-root-local", str(emulation)])
    err = capsys.readouterr().err
    assert code == 0, err
    chemin = str(emulation / "RetroArch" / "RetroArch-Win64" / "retroarch.exe")
    assert err.count(chemin) == 1, f"chemin répété :\n{err}"
    assert err.count("« retroarch »") == 1, f"émulateur répété :\n{err}"
    assert "Super Nintendo" in err and "PlayStation" in err


def test_la_ligne_de_sortie_standard_ne_ment_pas(tmp_path, capsys):
    """« faute d'émulateur installé » alors que l'exécutable est là, et que le
    détail dit « l'installation n'est pas attestée ». C'est la seule ligne que
    l'hôte relaie."""
    profils = _profils_deux_systemes(tmp_path)
    dossier = tmp_path / "Emulation" / "RetroArch" / "RetroArch-Win64"
    dossier.mkdir(parents=True)
    (dossier / "retroarch.exe").write_bytes(b"MZ")
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils),
                     "--output", str(tmp_path / "inv.json"),
                     "--emulation-root", "D:\\Emulation",
                     "--emulation-root-local", str(tmp_path / "Emulation")])
    sortie = capsys.readouterr()
    assert code == 0, sortie.err
    assert "faute d'émulateur installé" not in sortie.out
    assert "utilisable" in sortie.out


def test_le_motif_sans_temoin_nomme_les_deux_issues(tmp_path, capsys):
    """`retro install` ne peut installer que ce qui est AU MANIFESTE : un
    profil hors de tout manifeste, exécutable posé à la main, recevait un
    remède qui ne peut rien faire. Les deux issues doivent se lire."""
    profils = _profils_deux_systemes(tmp_path)
    # Aucun manifeste ne décrit cet émulateur : `retro install` n'a rien à
    # installer, et le dossier d'installation est DEVINÉ d'après le profil.
    vide = tmp_path / "vide.toml"
    vide.write_text("schema = 1\n", encoding="utf-8")
    dossier = tmp_path / "Emulation" / "retroarch" / "RetroArch-Win64"
    dossier.mkdir(parents=True)
    (dossier / "retroarch.exe").write_bytes(b"MZ")
    cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
              "--profiles", str(profils), "--manifest", str(vide),
              "--output", str(tmp_path / "inv.json"),
              "--emulation-root", "D:\\Emulation",
              "--emulation-root-local", str(tmp_path / "Emulation")])
    err = capsys.readouterr().err
    # Un fragment PROPRE au remède : « --user-manifest » seul serait déjà
    # satisfait par l'avertissement sur les dossiers d'installation devinés,
    # et ce test ne prouverait rien.
    assert "ne peut installer que ce qui y figure" in err
    assert "témoin" in err
