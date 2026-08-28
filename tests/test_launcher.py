"""Le lanceur commun, et le plan que la synchronisation lui écrit."""
import pathlib

import pytest

from retro import launcher, profiles, render


PROFIL = """
schema = 1
id = "duckstation"
exe = 'duckstation-qt.exe'
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch {render} "{rom}"'
cost = "light"
bios = []
[system.render.native]
args = "-scale=1"
crt = "-shader=crt-geom"
[system.render.full]
args = "-scale={scale}"
[system.render]
native_height = 240
max_scale = 8
[[system]]
id = "ps3"
name = "PlayStation 3"
extensions = [".iso"]
launch = '--no-gui "{rom}"'
bios = []
"""


@pytest.fixture
def profils(tmp_path):
    p = tmp_path / "duckstation.toml"
    p.write_text(PROFIL, encoding="utf-8")
    return {"duckstation": profiles.load_profile(p)}


def plan(profils, sid="psx"):
    systeme = next(s for s in profils["duckstation"].systems if s.id == sid)
    return launcher.plan_systeme("duckstation", systeme,
                                 "D:\\Emulation\\DS\\duckstation-qt.exe",
                                 "D:\\Emulation\\DS")


def lignes(texte):
    return dict(l.split("=", 1) for l in texte.splitlines()
                if "=" in l and not l.startswith("#"))


# --- le plan d'un système -----------------------------------------------

def test_le_crt_est_joint_au_gabarit_natif(profils):
    """Le lanceur reçoit un seul gabarit par mode : c'est ici que le shader
    rejoint les arguments du natif, pas dans le lanceur."""
    assert lignes(plan(profils))["native"] == "-scale=1 -shader=crt-geom"


def test_le_gabarit_full_ignore_le_crt(profils):
    assert lignes(plan(profils))["full"] == "-scale={scale}"


def test_les_variables_ne_sont_pas_substituees_dans_le_plan(profils):
    """Le plan est écrit une fois, la session change à chaque connexion : les
    variables doivent arriver INTACTES au lanceur, qui seul mesure."""
    assert "{scale}" in lignes(plan(profils))["full"]


def test_le_plan_porte_la_commande_et_l_emulateur(profils):
    l = lignes(plan(profils))
    assert l["emulator"] == "D:\\Emulation\\DS\\duckstation-qt.exe"
    assert l["workdir"] == "D:\\Emulation\\DS"
    assert l["launch"] == '-batch {render} "{rom}"'


@pytest.mark.parametrize("classe", render.CLASSES)
def test_le_plan_dit_le_meme_arbitrage_que_la_politique(profils, classe):
    """C'est LE point du plan : le lanceur ne rejoue aucune décision.

    S'il classait la machine puis choisissait lui-même, sa table aurait
    divergé de celle-ci au premier changement, et rien n'aurait dit laquelle
    des deux s'appliquait à un jeu qui rame.
    """
    systeme = profils["duckstation"].systems[0]
    assert lignes(plan(profils))[f"auto_{classe}"] == \
        render.arbitrer(classe, systeme.cost)


def test_le_plan_porte_les_seuils_de_classement(profils):
    """Sans eux, le lanceur ne saurait pas classer la machine qu'il mesure."""
    l = lignes(plan(profils))
    for nom, vram, coeurs in render.SEUILS:
        assert l[f"threshold_{nom}"] == f"{vram},{coeurs}"


def test_un_systeme_sans_bloc_de_rendu_donne_un_plan_neutre(profils):
    """Les modes se remplissent émulateur par émulateur. En attendant, les
    trois lancent la même commande — et le plan le dit, plutôt que de laisser
    le lanceur déduire quoi que ce soit d'une ligne vide."""
    l = lignes(plan(profils, sid="ps3"))
    assert l["native"] == "" and l["full"] == ""
    assert {l[f"auto_{c}"] for c in render.CLASSES} == {render.NATIVE}


# --- écrire et nettoyer le plan -----------------------------------------

def test_un_fichier_par_systeme(tmp_path, profils):
    ecrits = launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils,
                                  {"duckstation": "DS"})
    assert sorted(ecrits) == ["duckstation.ps3", "duckstation.psx"]
    dossier = tmp_path / launcher.DIR / launcher.PLAN
    # Le contenu, pas seulement le fichier : c'est ici que le dossier
    # d'installation du manifeste rejoint l'exécutable du profil, et cette
    # jonction ne se voit plus dans l'inventaire depuis que le raccourci
    # appelle le lanceur.
    l = lignes((dossier / "duckstation.psx.ini").read_text(encoding="utf-8"))
    assert l["emulator"] == "D:\\Emulation\\DS\\duckstation-qt.exe"
    assert l["workdir"] == "D:\\Emulation\\DS"


def test_un_plan_perime_est_retire(tmp_path, profils):
    """Un plan resté là après qu'un système a changé d'émulateur ferait lancer
    l'ANCIEN, avec l'ancienne ligne de commande, sur une entrée Steam
    d'apparence parfaitement normale."""
    dossier = tmp_path / launcher.DIR / launcher.PLAN
    dossier.mkdir(parents=True)
    (dossier / "vieux.sys.ini").write_text("emulator=X\n", encoding="utf-8")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils,
                         {"duckstation": "DS"})
    assert not (dossier / "vieux.sys.ini").exists()


# --- le mode choisi -----------------------------------------------------

def test_le_mode_par_defaut_est_auto(tmp_path):
    assert launcher.lire_mode(tmp_path) == render.AUTO


def test_le_mode_ecrit_est_relu(tmp_path):
    launcher.ecrire_mode(tmp_path, render.FULL)
    assert launcher.lire_mode(tmp_path) == render.FULL


def test_un_mode_illisible_retombe_sur_auto(tmp_path):
    """Un fichier abîmé ne doit pas empêcher les jeux de se lancer : `auto`
    est le comportement par défaut, pas une panne."""
    dossier = tmp_path / launcher.DIR
    dossier.mkdir(parents=True)
    (dossier / launcher.MODE).write_text("maximum\n", encoding="utf-8")
    assert launcher.lire_mode(tmp_path) == render.AUTO


def test_ecrire_un_mode_inconnu_est_refuse(tmp_path):
    with pytest.raises(render.RenderError, match="mode de rendu inconnu"):
        launcher.ecrire_mode(tmp_path, "maximum")


def test_changer_de_mode_ne_touche_pas_aux_options_de_lancement(tmp_path):
    """L'identifiant d'un raccourci dérive de ses options : y écrire le mode
    ferait changer d'identifiant à toute la bibliothèque à chaque changement,
    et tout l'artwork serait à retélécharger pour un réglage."""
    launcher.ecrire_mode(tmp_path, render.FULL)
    assert (tmp_path / launcher.DIR / launcher.MODE).is_file()


# --- le lanceur doit exister --------------------------------------------

def test_un_lanceur_absent_se_voit(tmp_path):
    """Chaque raccourci pointe sur lui : absent, c'est toute la bibliothèque
    qui ne démarre plus, et l'erreur de Steam ne nomme aucun jeu."""
    assert not launcher.est_installe(tmp_path)
    dossier = tmp_path / launcher.DIR
    dossier.mkdir(parents=True)
    (dossier / launcher.EXE).write_bytes(b"MZ")
    assert launcher.est_installe(tmp_path)


def test_le_lanceur_est_sous_la_racine_d_emulation():
    """La propriété d'une entrée Steam se prouve par son tag ET par un exe
    SOUS cette racine. Hors d'elle, la réconciliation ne reconnaîtrait plus
    ses propres entrées et les recréerait à chaque passage."""
    from retro.steam import entry
    exe = launcher.launcher_exe("D:\\Emulation")
    assert entry.is_under_root(entry.quote(exe), "D:\\Emulation")


# --- les fichiers de réglages ------------------------------------------

PROFIL_CONFIG = """
schema = 1
id = "retroarch"
exe = 'retroarch.exe'
[[system]]
id = "gb"
name = "Game Boy"
extensions = [".gb"]
launch = '-L "core.dll" {render} -f "{rom}"'
cost = "light"
bios = []
[system.render.native]
args = '--appendconfig "{render_config}"'
crt = '--set-shader "crt/crt-geom.slangp"'
config = 'video_shader_enable = "true"'
[system.render.full]
args = '--appendconfig "{render_config}"'
config = 'video_shader_enable = "false"'
"""


@pytest.fixture
def profils_config(tmp_path):
    p = tmp_path / "retroarch.toml"
    p.write_text(PROFIL_CONFIG, encoding="utf-8")
    return {"retroarch": profiles.load_profile(p)}


def test_le_chemin_du_fichier_de_reglages_est_resolu_dans_le_plan(
        tmp_path, profils_config):
    """{render_config} est résolu à l'ÉCRITURE, pas au lancement : le chemin
    d'un fichier ne dépend pas de la session, et le laisser au lanceur lui
    aurait fait reconstruire la convention de nommage — un second endroit où
    le nom du fichier serait décidé."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_config,
                         {"retroarch": "RetroArch"})
    plan = (tmp_path / launcher.DIR / launcher.PLAN / "retroarch.gb.ini")
    l = lignes(plan.read_text(encoding="utf-8"))
    assert l["native"] == ('--appendconfig "D:\\Emulation\\_launcher\\systems'
                           '\\retroarch.gb.native.cfg" '
                           '--set-shader "crt/crt-geom.slangp"')
    assert "{render_config}" not in l["full"]


def test_le_fichier_de_reglages_est_ecrit(tmp_path, profils_config):
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_config,
                         {"retroarch": "RetroArch"})
    dossier = tmp_path / launcher.DIR / launcher.PLAN
    assert (dossier / "retroarch.gb.native.cfg").read_text(encoding="utf-8") \
        == 'video_shader_enable = "true"'
    assert (dossier / "retroarch.gb.full.cfg").is_file()


def test_un_fichier_de_reglages_perime_est_retire(tmp_path, profils_config):
    """Un réglage resté là après qu'un système a changé d'émulateur
    s'appliquerait encore, sur une entrée Steam d'apparence normale."""
    dossier = tmp_path / launcher.DIR / launcher.PLAN
    dossier.mkdir(parents=True)
    (dossier / "vieux.sys.native.cfg").write_text("x = 1", encoding="utf-8")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_config,
                         {"retroarch": "RetroArch"})
    assert not (dossier / "vieux.sys.native.cfg").exists()


# --- l'amorçage -----------------------------------------------------------

# La chaîne Python est délimitée par des guillemets doubles triples, et le
# `content` du TOML par des guillemets SIMPLES triples : la chaîne littérale
# de TOML, qui n'interprète aucun échappement. C'est ce qu'il faut pour un
# fichier de configuration Windows, plein d'antislashs.
PROFIL_AMORCE = PROFIL + """
[bootstrap]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[Main]
SetupWizardIncomplete = false
'''
"""


@pytest.fixture
def profils_amorces(tmp_path):
    p = tmp_path / "duckstation-amorce.toml"
    p.write_text(PROFIL_AMORCE, encoding="utf-8")
    return {"duckstation": profiles.load_profile(p)}


def test_le_plan_porte_les_trois_lignes_d_amorcage(profils_amorces):
    """Le lanceur ne reconstruit ni le chemin de la source ni la stratégie :
    les deux sont décidées ici."""
    systeme = profils_amorces["duckstation"].systems[0]
    texte = launcher.plan_systeme(
        "duckstation", systeme, "D:\\Emulation\\DS\\duckstation-qt.exe",
        "D:\\Emulation\\DS", "D:\\Emulation\\_launcher\\systems",
        bootstrap=profils_amorces["duckstation"].bootstrap)
    l = lignes(texte)
    assert l["bootstrap_target"] == (
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini")
    assert l["bootstrap_source"] == (
        "D:\\Emulation\\_launcher\\systems\\duckstation.bootstrap.ini")
    assert l["bootstrap_when"] == launcher.SI_ABSENT


def test_un_profil_sans_amorcage_porte_les_lignes_vides(profils):
    """Vides, jamais absentes : le lanceur traite une clé manquante comme une
    faute du plan, et c'est une propriété qu'on garde."""
    l = lignes(plan(profils))
    assert l["bootstrap_target"] == ""
    assert l["bootstrap_source"] == ""
    assert l["bootstrap_when"] == ""


def test_le_nom_du_fichier_suit_l_extension_de_la_cible():
    """Un émulateur dont la configuration est un .toml ne reçoit pas un .ini :
    le nom du fichier déposé porte l'extension de sa cible."""
    assert launcher.bootstrap_name(
        "duckstation", "%USERPROFILE%\\Documents\\DuckStation\\settings.ini"
    ) == "duckstation.bootstrap.ini"
    assert launcher.bootstrap_name(
        "xemu", "%APPDATA%\\xemu\\xemu.toml") == "xemu.bootstrap.toml"


def test_le_fichier_d_amorcage_est_ecrit(tmp_path, profils_amorces):
    """Le contenu du profil arrive tel quel à côté des plans, là où le lanceur
    ira le chercher."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    depose = (tmp_path / launcher.DIR / launcher.PLAN
              / "duckstation.bootstrap.ini")
    assert "SetupWizardIncomplete = false" in depose.read_text(encoding="utf-8")


def test_un_amorcage_perime_est_retire(tmp_path, profils_amorces):
    """Un amorçage resté là après qu'un profil a disparu réécrirait la
    configuration d'un émulateur que plus rien ne décrit."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    dossier = tmp_path / launcher.DIR / launcher.PLAN
    (dossier / "ancien.bootstrap.toml").write_text("x", encoding="utf-8")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    assert not (dossier / "ancien.bootstrap.toml").exists()
    assert (dossier / "duckstation.bootstrap.ini").exists()


# --- l'ordre de ré-amorçage ----------------------------------------------

def test_l_ordre_de_reamorcage_est_ecrit(tmp_path, profils_amorces):
    """« retro » n'atteint pas C:\\Users : forcer n'est pas une écriture, c'est
    un ordre que le lanceur exécutera là où il est."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    fichier = launcher.ordonner_reamorcage(tmp_path, "duckstation")
    assert fichier.read_text(encoding="utf-8").split() == ["duckstation"]


def test_un_ordre_ne_s_ecrit_pas_deux_fois(tmp_path, profils_amorces):
    """Deux ordres pour le même profil feraient deux sauvegardes et une
    réécriture de plus, sans rien apporter."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    launcher.ordonner_reamorcage(tmp_path, "duckstation")
    fichier = launcher.ordonner_reamorcage(tmp_path, "duckstation")
    assert fichier.read_text(encoding="utf-8").split() == ["duckstation"]


def test_reamorcer_un_profil_inconnu_est_refuse(tmp_path, profils_amorces):
    """Un ordre qui nomme un profil sans amorçage ne serait jamais consommé :
    il resterait dans le fichier, et le propriétaire attendrait un effet qui
    ne vient pas."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    with pytest.raises(launcher.AmorcageError) as e:
        launcher.ordonner_reamorcage(tmp_path, "pcsx2")
    assert "duckstation" in str(e.value)
