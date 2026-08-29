"""Les sous-commandes install et scan."""
import json
import pathlib

import pytest

from retro import acquire, cli, launcher


def poser_lanceur(racine):
    """Le lanceur commun, sans lequel `scan` refuse d'inventorier : chaque
    raccourci Steam pointe sur lui."""
    dossier = pathlib.Path(racine) / launcher.DIR
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / launcher.EXE).write_bytes(b"MZ")
    return pathlib.Path(racine)



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
    # Le raccourci appelle le lanceur commun ; c'est le dossier d'installation
    # — versionné — qui prouve ici que le manifeste a été suivi. L'exécutable
    # de l'émulateur, lui, part dans le plan que lit le lanceur.
    assert e.emulator_exe == "D:\\Emulation\\_launcher\\retro-launch.exe"
    assert e.start_dir == "D:\\Emulation\\R-1.0"
    # Le raccourci ne porte plus la commande de l'émulateur, mais le système
    # et la ROM : la commande vit dans le plan que lit le lanceur.
    assert e.launch_template == 'r.snes "{rom}"' 
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
    assert d[0]["start_dir"] == "D:\\Emulation\\DuckStation-v0.1"
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
    emulation = poser_lanceur(tmp_path / "Emulation")
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
    poser_lanceur(tmp_path / "Emulation")
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
    poser_lanceur(tmp_path / "Emulation")
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
    poser_lanceur(tmp_path / "Emulation")
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
    emulation = poser_lanceur(tmp_path / "Emulation")
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
    poser_lanceur(tmp_path / "Emulation")
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
    poser_lanceur(tmp_path / "Emulation")
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


# --- scan : les profils du propriétaire ------------------------------------
#
# Déclarer un émulateur au manifeste utilisateur ne suffit pas à s'en servir :
# il lui faut un profil. `--profiles` ne prenait qu'un dossier, et y pointer
# ailleurs perdait ceux du paquet — l'extension utilisateur était donc
# incomplète.

# La forme RÉELLE de `exe` : un dossier racine d'archive, en chemin Windows.
PROFIL_PAQUET = """
schema = 1
id = "retroarch"
exe = 'RetroArch-Win64\\retroarch.exe'
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-L "RetroArch-Win64\\cores\\snes9x_libretro.dll" -f "{rom}"'
bios = []
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".chd"]
launch = '-L "RetroArch-Win64\\cores\\swanstation_libretro.dll" -f "{rom}"'
bios = []
"""

PROFIL_MIEN = """
schema = 1
id = "duckstation"
exe = 'DuckStation-x64\\duckstation-qt-x64-ReleaseLTCG.exe'
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".chd"]
launch = '-fullscreen -nogui "{rom}"'
bios = []
"""


def _deux_sources(tmp_path):
    """Les profils du paquet, ceux du propriétaire, les ROMs et les manifestes."""
    paquet = tmp_path / "profiles"
    paquet.mkdir()
    (paquet / "retroarch.toml").write_text(PROFIL_PAQUET, encoding="utf-8")
    mien = tmp_path / "mes-profils"
    mien.mkdir()
    (mien / "duckstation.toml").write_text(PROFIL_MIEN, encoding="utf-8")
    for systeme, rom in (("snes", "Chrono Trigger (USA).sfc"),
                         ("psx", "Tekken 3 (Europe).chd")):
        d = tmp_path / "ROMs" / systeme
        d.mkdir(parents=True)
        (d / rom).write_bytes(b"x")
    noyau = tmp_path / "core.toml"
    noyau.write_text(MANIFESTE_NOYAU, encoding="utf-8")
    utilisateur = tmp_path / "emulators.toml"
    utilisateur.write_text(MANIFESTE_UTILISATEUR, encoding="utf-8")
    return paquet, mien, noyau, utilisateur


def test_scan_fusionne_les_profils_du_proprietaire(tmp_path, capsys):
    """Les deux dossiers servent, et à système disputé le sien l'emporte.

    Le propriétaire ajoute Duckstation pour que « psx » passe par lui plutôt
    que par le core de RetroArch. Remplacer --profiles perdrait « snes » avec
    le profil livré ; ne rien faire laisserait deux profils se disputer le
    dossier psx\\, et le scan trancherait par ordre alphabétique.
    """
    paquet, mien, noyau, utilisateur = _deux_sources(tmp_path)
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(paquet), "--user-profiles", str(mien),
                     "--manifest", str(noyau),
                     "--user-manifest", str(utilisateur),
                     "--output", str(sortie),
                     "--emulation-root", "D:\\Emulation"])
    assert code == 0
    assert capsys.readouterr().err == ""
    par_systeme = {d["system_name"]: d
                   for d in json.loads(sortie.read_text(encoding="utf-8"))}
    # Le profil livré survit à l'ajout : « snes » est toujours là.
    assert par_systeme["Super Nintendo"]["start_dir"] == "D:\\Emulation\\RetroArch"
    # Et « psx » passe par l'émulateur du propriétaire, chemin ET gabarit.
    psx = par_systeme["PlayStation"]
    assert psx["start_dir"] == "D:\\Emulation\\DuckStation-v0.1"
    # Le raccourci désigne SON profil ; le plan que lit le lanceur portera
    # sa commande.
    assert psx["launch_template"] == 'duckstation.psx "{rom}"'


def test_scan_sans_dossier_de_profils_du_proprietaire(tmp_path, capsys):
    """Son absence est NORMALE : il vit sur un partage qui n'est pas monté au
    moment du provisionnement. Une erreur ici casserait la première
    installation d'une machine neuve."""
    paquet, _, noyau, _ = _deux_sources(tmp_path)
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(paquet),
                     "--user-profiles", str(tmp_path / "jamais-monte"),
                     "--manifest", str(noyau),
                     "--output", str(sortie),
                     "--emulation-root", "D:\\Emulation"])
    assert code == 0
    err = capsys.readouterr().err
    assert "Traceback" not in err
    systemes = {d["system_name"]
                for d in json.loads(sortie.read_text(encoding="utf-8"))}
    assert systemes == {"Super Nintendo", "PlayStation"}


def test_scan_refuse_deux_profils_du_proprietaire_sur_un_meme_systeme(tmp_path, capsys):
    """La préséance ne départage que les deux SOURCES. Deux profils du même
    dossier qui revendiquent « psx » se disputeraient le même dossier de
    ROMs, et le message doit dire lequel corriger."""
    paquet, mien, noyau, utilisateur = _deux_sources(tmp_path)
    (mien / "zz-duck.toml").write_text(
        PROFIL_MIEN.replace('id = "duckstation"', 'id = "duckstation-nightly"'),
        encoding="utf-8")
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(paquet), "--user-profiles", str(mien),
                     "--manifest", str(noyau),
                     "--user-manifest", str(utilisateur),
                     "--output", str(tmp_path / "inv.json"),
                     "--emulation-root", "D:\\Emulation"])
    assert code != 0
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "psx" in err
    assert "duckstation.toml" in err and "zz-duck.toml" in err


# --- le lanceur commun et le mode de rendu ------------------------------

def test_launcher_depose_la_source_et_dit_comment_la_compiler(tmp_path, capsys):
    """Le binaire n'est jamais livré tout fait : un dépôt public n'a pas à
    faire confiance à un exécutable qu'on ne peut pas relire."""
    emulation = tmp_path / "Emulation"
    code = cli.main(["launcher", "--emulation-root-local", str(emulation),
                     "--emulation-root", "D:\\Emulation"])
    dossier = emulation / launcher.DIR
    assert (dossier / launcher.SOURCE).is_file()
    assert (dossier / "compiler.cmd").is_file()
    # PAS zéro : sans binaire, `retro scan` refusera d'inventorier. Rendre 0
    # ferait croire à une étape terminée, et la panne apparaîtrait deux
    # commandes plus loin.
    assert code == 1
    assert "compiler.cmd" in capsys.readouterr().err


def test_launcher_rend_zero_quand_le_binaire_est_la(tmp_path, capsys):
    emulation = poser_lanceur(tmp_path / "Emulation")
    code = cli.main(["launcher", "--emulation-root-local", str(emulation)])
    assert code == 0
    assert "compilé et en place" in capsys.readouterr().out


def test_render_sans_mode_affiche_le_mode_courant(tmp_path, capsys):
    emulation = poser_lanceur(tmp_path / "Emulation")
    assert cli.main(["render", "--emulation-root-local", str(emulation)]) == 0
    assert capsys.readouterr().out.strip() == "auto"


def test_render_pose_le_mode(tmp_path, capsys):
    emulation = poser_lanceur(tmp_path / "Emulation")
    assert cli.main(["render", "--emulation-root-local", str(emulation),
                     "--mode", "full"]) == 0
    capsys.readouterr()
    cli.main(["render", "--emulation-root-local", str(emulation)])
    assert capsys.readouterr().out.strip() == "full"


def test_render_signale_que_personne_ne_lira_le_mode(tmp_path, capsys):
    """Le mode est bien posé, mais sans lanceur rien ne le lit. Le taire
    ferait croire au propriétaire que son choix s'applique."""
    emulation = tmp_path / "Emulation"
    code = cli.main(["render", "--emulation-root-local", str(emulation),
                     "--mode", "native"])
    assert code == 1
    assert "ne sera lu par personne" in capsys.readouterr().err


def test_render_refuse_un_mode_inconnu(tmp_path, capsys):
    """argparse tranche avant nous : un mode inventé ne doit pas atteindre le
    fichier, où il ferait silencieusement retomber le lanceur sur `auto`."""
    emulation = poser_lanceur(tmp_path / "Emulation")
    with pytest.raises(SystemExit):
        cli.main(["render", "--emulation-root-local", str(emulation),
                  "--mode", "maximum"])


def test_scan_ecrit_le_plan_de_lancement(tmp_path, capsys):
    """Sans plan, le lanceur ne saurait quoi lancer — et l'entrée Steam aurait
    l'air parfaitement normale."""
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
    emulation = poser_lanceur(tmp_path / "Emulation")
    (emulation / "r").mkdir()
    (emulation / "r" / "r.exe").write_bytes(b"MZ")
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils),
                     "--output", str(tmp_path / "inv.json"),
                     "--emulation-root", "D:\\Emulation",
                     "--emulation-root-local", str(emulation)])
    assert code == 0, capsys.readouterr().err
    plan = emulation / launcher.DIR / launcher.PLAN / "r.snes.ini"
    assert plan.is_file()
    assert 'launch=-f "{rom}"' in plan.read_text(encoding="utf-8")


# --- `retro install` nomme ce qu'il vient d'effacer ------------------------

def _manifeste_d_un(tmp_path, cle="rpcs3", profil="rpcs3"):
    """Un manifeste minimal à une seule entrée, épinglée."""
    f = tmp_path / "m.toml"
    f.write_text(f"""
schema = 1
[emulator.{cle}]
name        = "Un émulateur"
version     = "1.0"
url         = "https://exemple.invalid/e.zip"
sha256      = "{'0' * 64}"
archive     = "zip"
install_dir = "Dossier"
profile     = "{profil}"
""", encoding="utf-8")
    return f


def _profils_d_un(tmp_path, pid, cible):
    """Un dossier de profils à un seul profil, dont l'amorçage vise `cible`."""
    dossier = tmp_path / "profiles"
    dossier.mkdir(exist_ok=True)
    (dossier / f"{pid}.toml").write_text(f"""
schema = 1
id = "{pid}"
exe = "x.exe"

[[bootstrap]]
target = '{cible}'
content = '''
; Écrit par « retro »
'''

[[system]]
id = "{pid}-s"
name = "Un système"
extensions = [".rom"]
launch = '"{{rom}}"'
bios = []
""", encoding="utf-8")
    return dossier


def test_retro_install_dit_ce_qu_il_a_efface(tmp_path, capsys, monkeypatch):
    """La moitié manquante de la dette D7.

    Les deux fichiers de RPCS3 vivent sous son dossier d'installation, que
    `retro install` supprime à chaque montée de version. Le régime « si-absent »
    les repose au lancement suivant — mais entre les deux, la manette ne répond
    pas, et cela ne ressemble EN RIEN à une mise à jour. Sans cette phrase, on
    cherche du côté du pad, des pilotes ou de Steam ; le seul endroit où c'est
    écrit doit être la sortie de la commande qui vient de l'effacer.
    """
    cible = "{install_dir}\\config\\input_configs\\global\\Default.yml"
    monkeypatch.setattr(acquire, "acquire", lambda *a, **k: "réinstallé")
    code = cli.main(["install",
                     "--manifest", str(_manifeste_d_un(tmp_path)),
                     "--profiles", str(_profils_d_un(tmp_path, "rpcs3", cible)),
                     "--emulation-root", str(tmp_path / "Emu")])
    assert code == 0
    sortie = capsys.readouterr().out
    assert "rpcs3" in sortie
    assert "Default.yml" in sortie
    # La cible est écrite telle qu'elle vit dans le profil, jeton compris : au
    # moment de l'installation, le dossier d'émulation n'est pas encore résolu
    # pour Windows, et inventer un chemin ici en ferait un faux à copier-coller.
    assert "{install_dir}" in sortie


def test_une_installation_a_jour_n_annonce_rien_d_efface(tmp_path, capsys,
                                                         monkeypatch):
    """« à jour » n'a rien touché. Un message qui crie à chaque installation
    ne se lit plus le jour où il est vrai."""
    cible = "{install_dir}\\config\\input_configs\\global\\Default.yml"
    monkeypatch.setattr(acquire, "acquire", lambda *a, **k: "à jour")
    code = cli.main(["install",
                     "--manifest", str(_manifeste_d_un(tmp_path)),
                     "--profiles", str(_profils_d_un(tmp_path, "rpcs3", cible)),
                     "--emulation-root", str(tmp_path / "Emu")])
    assert code == 0
    assert "Default.yml" not in capsys.readouterr().out


def test_un_dossier_de_profils_du_proprietaire_absent_reste_normal(
        tmp_path, capsys, monkeypatch):
    """Il vit sur un partage qui n'est pas toujours monté. Une installation
    qui échouerait pour cette raison serait une panne inventée."""
    monkeypatch.setattr(acquire, "acquire", lambda *a, **k: "réinstallé")
    code = cli.main(["install",
                     "--manifest", str(_manifeste_d_un(tmp_path)),
                     "--profiles", str(_profils_d_un(
                         tmp_path, "rpcs3", "{install_dir}\\x.ini")),
                     "--user-profiles", str(tmp_path / "jamais-monte"),
                     "--emulation-root", str(tmp_path / "Emu")])
    assert code == 0
    assert "x.ini" in capsys.readouterr().out
