"""Le lanceur commun, et le plan que la synchronisation lui écrit."""
import pathlib

import pytest

from retro import langue as langue_mod
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


# --- la langue choisie -------------------------------------------------

def test_sans_fichier_la_langue_vaut_auto(tmp_path):
    """Le défaut est de suivre Steam : c'est ce que le propriétaire a
    choisi, et un défaut figé ferait mentir la commande qui l'affiche."""
    assert launcher.lire_langue(tmp_path) == langue_mod.AUTO


def test_une_langue_posee_se_relit(tmp_path):
    launcher.ecrire_langue(tmp_path, "japanese")
    assert launcher.lire_langue(tmp_path) == "japanese"


def test_un_fichier_illisible_retombe_sur_auto(tmp_path):
    """Un fichier abîmé ne doit pas empêcher un jeu de se lancer : `auto`
    est le comportement par défaut, pas un aveu."""
    dossier = launcher.local_dir(tmp_path)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / launcher.LANGUE_FICHIER).write_text("n'importe quoi\n",
                                                   encoding="utf-8")
    assert launcher.lire_langue(tmp_path) == langue_mod.AUTO


def test_une_langue_inconnue_est_refusee_a_l_ecriture(tmp_path):
    """Refusée à l'écriture, pas ignorée à la lecture : une coquille posée
    en silence ferait croire à un réglage appliqué."""
    with pytest.raises(langue_mod.LangueError):
        launcher.ecrire_langue(tmp_path, "frensh")


def test_auto_s_ecrit_comme_les_autres(tmp_path):
    launcher.ecrire_langue(tmp_path, "french")
    launcher.ecrire_langue(tmp_path, langue_mod.AUTO)
    assert launcher.lire_langue(tmp_path) == langue_mod.AUTO


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
[[bootstrap]]
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


def test_le_plan_porte_les_lignes_d_un_amorcage(profils_amorces):
    """Le lanceur ne reconstruit ni le chemin de la source ni la stratégie :
    les deux sont décidées ici. Une seule entrée, mais elle est INDICÉE comme
    les autres — un format qui changerait avec le nombre d'entrées ferait deux
    lecteurs dans le lanceur."""
    systeme = profils_amorces["duckstation"].systems[0]
    texte = launcher.plan_systeme(
        "duckstation", systeme, "D:\\Emulation\\DS\\duckstation-qt.exe",
        "D:\\Emulation\\DS", "D:\\Emulation\\_launcher\\systems",
        bootstraps=profils_amorces["duckstation"].bootstraps)
    l = lignes(texte)
    assert l["bootstrap_count"] == "1"
    assert l["bootstrap_target.1"] == (
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini")
    assert l["bootstrap_source.1"] == (
        "D:\\Emulation\\_launcher\\systems\\duckstation.bootstrap.1.ini")
    assert l["bootstrap_when.1"] == launcher.SI_ABSENT


def test_un_profil_sans_amorcage_ne_porte_aucune_ligne_indicee(profils):
    """Le COMPTE est toujours écrit — le lanceur traite une clé manquante comme
    une faute du plan, et c'est cette propriété qu'on garde. Les lignes
    indicées, elles, n'existent pas : le compte les remplace toutes."""
    l = lignes(plan(profils))
    assert l["bootstrap_count"] == "0"
    assert [c for c in l if c.startswith("bootstrap_")] == ["bootstrap_count"]


def test_le_nom_du_fichier_suit_l_extension_de_la_cible():
    """Un émulateur dont la configuration est un .toml ne reçoit pas un .ini :
    le nom du fichier déposé porte l'extension de sa cible."""
    assert launcher.bootstrap_name(
        "duckstation", 1,
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini"
    ) == "duckstation.bootstrap.1.ini"
    assert launcher.bootstrap_name(
        "xemu", 1, "%APPDATA%\\xemu\\xemu.toml") == "xemu.bootstrap.1.toml"


def test_le_fichier_d_amorcage_est_ecrit(tmp_path, profils_amorces):
    """Le contenu du profil arrive tel quel à côté des plans, là où le lanceur
    ira le chercher."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    depose = (tmp_path / launcher.DIR / launcher.PLAN
              / "duckstation.bootstrap.1.ini")
    assert "SetupWizardIncomplete = false" in depose.read_text(encoding="utf-8")


def test_un_amorcage_perime_est_retire(tmp_path, profils_amorces):
    """Un amorçage resté là après qu'un profil a disparu réécrirait la
    configuration d'un émulateur que plus rien ne décrit."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    dossier = tmp_path / launcher.DIR / launcher.PLAN
    (dossier / "ancien.bootstrap.1.toml").write_text("x", encoding="utf-8")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    assert not (dossier / "ancien.bootstrap.1.toml").exists()
    assert (dossier / "duckstation.bootstrap.1.ini").exists()


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


# --- le témoin d'amorçage --------------------------------------------------

def test_le_temoin_d_amorcage_est_relu(tmp_path):
    """Le lanceur écrit ce qu'il a posé ; l'hôte, qui n'atteint pas C:\\Users,
    n'a que ça pour le savoir."""
    dossier = tmp_path / launcher.DIR
    dossier.mkdir(parents=True)
    (dossier / launcher.TEMOIN_BOOTSTRAP).write_text(
        "duckstation\t2026-08-28 10:27:26\tC:\\Users\\A\\settings.ini\n",
        encoding="utf-8")
    assert launcher.lire_amorcages(tmp_path) == {
        "duckstation": [("2026-08-28 10:27:26", "C:\\Users\\A\\settings.ini")]}


def test_un_temoin_absent_ne_fait_pas_echouer(tmp_path):
    """Aucun jeu n'a encore été lancé : c'est un état normal, pas une panne."""
    assert launcher.lire_amorcages(tmp_path) == {}


# --- un lanceur périmé rend toute la fonctionnalité inerte -----------------

def test_un_lanceur_plus_vieux_que_sa_source_est_perime(tmp_path):
    """Le binaire est LÀ, `est_installe` dit oui, et pourtant il ignore en
    silence les lignes de plan qu'il ne connaît pas : ni erreur, ni amorçage.
    C'est l'état du jour même de la livraison."""
    import os
    dossier = tmp_path / launcher.DIR
    dossier.mkdir(parents=True)
    (dossier / launcher.EXE).write_bytes(b"MZ")
    os.utime(dossier / launcher.EXE, (1_000_000, 1_000_000))
    (dossier / launcher.SOURCE).write_text("// neuf", encoding="utf-8")
    os.utime(dossier / launcher.SOURCE, (2_000_000, 2_000_000))
    assert launcher.est_installe(tmp_path)
    assert launcher.lanceur_perime(tmp_path)


def test_un_lanceur_recompile_n_est_plus_perime(tmp_path):
    """Le constat doit s'éteindre tout seul après `compiler.cmd`, sinon
    personne ne le lira plus."""
    import os
    dossier = tmp_path / launcher.DIR
    dossier.mkdir(parents=True)
    (dossier / launcher.SOURCE).write_text("// neuf", encoding="utf-8")
    os.utime(dossier / launcher.SOURCE, (1_000_000, 1_000_000))
    (dossier / launcher.EXE).write_bytes(b"MZ")
    os.utime(dossier / launcher.EXE, (2_000_000, 2_000_000))
    assert not launcher.lanceur_perime(tmp_path)


def test_redeposer_la_source_ne_perime_pas_un_lanceur_a_jour(tmp_path):
    """`deposer_source` copie la source AVEC sa date : sans cela, chaque
    dépôt réestampillait la source à l'instant présent et déclarait périmé un
    lanceur qu'on venait de recompiler — un avertissement qui crie à tort est
    un avertissement qu'on cesse de lire."""
    import os
    launcher.deposer_source(tmp_path)
    dossier = tmp_path / launcher.DIR
    # La source livrée avec le paquet, et un binaire compilé une seconde après
    # elle : ce lanceur est à jour, définitivement.
    livree = (launcher.SOURCES / launcher.SOURCE).stat().st_mtime
    assert (dossier / launcher.SOURCE).stat().st_mtime == livree, (
        "la source déposée doit garder la date de celle du paquet")
    (dossier / launcher.EXE).write_bytes(b"MZ")
    os.utime(dossier / launcher.EXE, (livree + 1, livree + 1))
    launcher.deposer_source(tmp_path)   # un second passage, plus tard
    assert not launcher.lanceur_perime(tmp_path)


def test_un_lanceur_sans_source_deposee_n_est_pas_dit_perime(tmp_path):
    """Sans source à côté, il n'y a rien à comparer : `est_installe` dit déjà
    l'absence du binaire, et inventer une péremption ferait réclamer une
    recompilation que rien ne motive."""
    dossier = tmp_path / launcher.DIR
    dossier.mkdir(parents=True)
    (dossier / launcher.EXE).write_bytes(b"MZ")
    assert not launcher.lanceur_perime(tmp_path)


# --- les clés imposées : le second régime ---------------------------------

PROFIL_IMPOSE = PROFIL + """
[[bootstrap]]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose
; à chaque lancement, ce qu'il a posé UNE FOIS, et le reste, qui est à vous.
[Main]
ConfirmPowerOff = false
'''
enforced = '''
[Main]
SetupWizardIncomplete = false
'''
"""


@pytest.fixture
def profils_imposes(tmp_path):
    p = tmp_path / "duckstation-impose.toml"
    p.write_text(PROFIL_IMPOSE, encoding="utf-8")
    return {"duckstation": profiles.load_profile(p)}


def test_le_plan_porte_le_fichier_des_cles_imposees(profils_imposes):
    """Deux fichiers pour une seule cible : celui qu'on pose si elle est
    absente, celui qu'on refusionne à chaque lancement."""
    profil = profils_imposes["duckstation"]
    l = lignes(launcher.plan_systeme(
        "duckstation", profil.systems[0], "D:\\E\\d.exe", "D:\\E",
        "D:\\E\\_launcher\\systems", bootstraps=profil.bootstraps))
    assert l["bootstrap_source.1"] == (
        "D:\\E\\_launcher\\systems\\duckstation.bootstrap.1.ini")
    assert l["bootstrap_enforced.1"] == (
        "D:\\E\\_launcher\\systems\\duckstation.impose.1.ini")
    assert l["bootstrap_when.1"] == launcher.SI_ABSENT


def test_un_amorcage_qui_n_impose_rien_porte_la_ligne_vide(profils_amorces):
    """Vide, jamais absente : c'est ce qui distingue une entrée qui n'impose
    rien de celle qui impose, sans que le lanceur ait à ouvrir un fichier."""
    profil = profils_amorces["duckstation"]
    l = lignes(launcher.plan_systeme(
        "duckstation", profil.systems[0], "D:\\E\\d.exe", "D:\\E",
        "D:\\E\\_launcher\\systems", bootstraps=profil.bootstraps))
    assert l["bootstrap_enforced.1"] == ""


def test_le_fichier_des_cles_imposees_est_depose(tmp_path, profils_imposes):
    dossier = launcher.local_dir(tmp_path) / launcher.PLAN
    launcher.ecrire_plan(tmp_path, "D:\\E", profils_imposes,
                         {"duckstation": "DS"})
    impose = dossier / "duckstation.impose.1.ini"
    assert impose.is_file()
    assert "SetupWizardIncomplete" in impose.read_text(encoding="utf-8")
    # Et le fichier « posé une fois » reste à côté, distinct.
    assert "ConfirmPowerOff" in (
        dossier / "duckstation.bootstrap.1.ini").read_text(encoding="utf-8")


def test_les_deux_fichiers_d_une_entree_ne_se_confondent_pas():
    assert launcher.enforced_name("duckstation", 1, "x.ini") \
        != launcher.bootstrap_name("duckstation", 1, "x.ini")


# --- le jeton du dossier d'installation -----------------------------------

# Le dossier d'installation porte un nom réel, et la cible des ANTISLASHS
# INTERNES : une fixture à nom plat masquerait une substitution qui perd le
# reste du chemin. C'est le défaut qui a déjà coûté une bibliothèque entière.
PROFIL_JETON = PROFIL.replace('id = "duckstation"', 'id = "vita3k"') + """
[[bootstrap]]
target = '{install_dir}\\gui-configs\\CurrentSettings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[MainWindow]
warnAdminPrivileges=false
'''
"""


@pytest.fixture
def profils_jeton(tmp_path):
    p = tmp_path / "vita3k-jeton.toml"
    p.write_text(PROFIL_JETON, encoding="utf-8")
    return {"vita3k": profiles.load_profile(p)}


def test_le_plan_substitue_le_dossier_d_installation(profils_jeton):
    """Le jeton est résolu À L'ÉCRITURE DU PLAN, comme {render_config} : le
    lanceur ne reconstruit aucune convention de nommage, et un jeton qui lui
    arriverait tel quel ferait créer un dossier « {install_dir} »."""
    profil = profils_jeton["vita3k"]
    l = lignes(launcher.plan_systeme(
        "vita3k", profil.systems[0], "D:\\Emulation\\Vita3K\\Vita3K.exe",
        "D:\\Emulation\\Vita3K", "D:\\Emulation\\_launcher\\systems",
        bootstraps=profil.bootstraps))
    assert l["bootstrap_target.1"] == (
        "D:\\Emulation\\Vita3K\\gui-configs\\CurrentSettings.ini")


def test_le_nom_du_fichier_depose_suit_la_cible_brute(tmp_path, profils_jeton):
    """Le fichier déposé, et la ligne du plan qui le nomme, dérivent de la
    cible BRUTE — son extension, qui ne change pas à la substitution. Les deux
    doivent s'accorder : un plan qui nomme une source que « retro scan » n'a
    pas écrite fait échouer l'amorçage devant la télévision.

    La cible, elle, est substituée dans le même plan. Les deux propriétés se
    tiennent ensemble, et c'est pourquoi ce test les regarde ensemble."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_jeton,
                         {"vita3k": "Vita3K"})
    dossier = launcher.local_dir(tmp_path) / launcher.PLAN
    depose = dossier / "vita3k.bootstrap.1.ini"
    assert depose.is_file(), sorted(p.name for p in dossier.iterdir())
    l = lignes((dossier / "vita3k.psx.ini").read_text(encoding="utf-8"))
    assert l["bootstrap_source.1"].endswith("\\vita3k.bootstrap.1.ini")
    assert l["bootstrap_target.1"] == (
        "D:\\Emulation\\Vita3K\\gui-configs\\CurrentSettings.ini")


# --- plusieurs amorçages dans un même plan --------------------------------

# Deux cibles, deux formats, et des ANTISLASHS INTERNES dans les deux : c'est
# la forme réelle de RPCS3, dont le second fichier est du YAML que la fusion ne
# connaît pas — elle n'a pas à le connaître, « si-absent » copie des octets.
PROFIL_DEUX = PROFIL.replace('id = "duckstation"', 'id = "rpcs3"') + """
[[bootstrap]]
target = '{install_dir}\\GuiConfigs\\CurrentSettings.ini'
content = '''
; Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose
; à chaque lancement, ce qu'il a posé UNE FOIS, et le reste, qui est à vous.
[main_window]
infoBoxEnabledInstallPUP=false
'''
enforced = '''
[main_window]
confirmationBoxBootGame=false
'''
[[bootstrap]]
target = '{install_dir}\\config\\input_configs\\global\\Default.yml'
content = '''
# Écrit par « retro » au premier lancement, parce que ce fichier était absent.
Player 1 Input:
  Handler: XInput
  Device: "XInput Pad #1"
'''
"""


@pytest.fixture
def profils_deux(tmp_path):
    p = tmp_path / "rpcs3-deux.toml"
    p.write_text(PROFIL_DEUX, encoding="utf-8")
    return {"rpcs3": profiles.load_profile(p)}


def test_le_plan_porte_une_ligne_par_amorcage(profils_deux):
    """Un compte, puis des lignes indicées : le lanceur boucle de 1 à N et
    n'invente rien. Sans l'indice, deux cibles se disputeraient une clé et la
    seconde disparaîtrait du plan sans un mot."""
    profil = profils_deux["rpcs3"]
    l = lignes(launcher.plan_systeme(
        "rpcs3", profil.systems[0], "D:\\Emulation\\RPCS3\\rpcs3.exe",
        "D:\\Emulation\\RPCS3", "D:\\Emulation\\_launcher\\systems",
        bootstraps=profil.bootstraps))
    assert l["bootstrap_count"] == "2"
    assert l["bootstrap_target.1"] == (
        "D:\\Emulation\\RPCS3\\GuiConfigs\\CurrentSettings.ini")
    assert l["bootstrap_source.1"] == (
        "D:\\Emulation\\_launcher\\systems\\rpcs3.bootstrap.1.ini")
    assert l["bootstrap_when.1"] == launcher.SI_ABSENT
    assert l["bootstrap_enforced.1"] == (
        "D:\\Emulation\\_launcher\\systems\\rpcs3.impose.1.ini")
    assert l["bootstrap_target.2"] == (
        "D:\\Emulation\\RPCS3\\config\\input_configs\\global\\Default.yml")
    assert l["bootstrap_source.2"] == (
        "D:\\Emulation\\_launcher\\systems\\rpcs3.bootstrap.2.yml")
    assert l["bootstrap_when.2"] == launcher.SI_ABSENT
    assert l["bootstrap_enforced.2"] == ""


def test_un_profil_sans_amorcage_porte_un_compte_nul(profils):
    """Le compte suffit désormais à porter « cet émulateur n'a rien à
    recevoir » : les lignes indicées sont ABSENTES, et `Valeur()` continue de
    traiter une clé absente comme une faute du plan."""
    l = lignes(plan(profils))
    assert l["bootstrap_count"] == "0"
    assert "bootstrap_target.1" not in l


def test_les_deux_amorcages_d_un_profil_ne_se_confondent_pas(tmp_path,
                                                             profils_deux):
    """Quatre fichiers déposés pour un seul profil : deux à poser, un imposé,
    et ils doivent être deux à deux distincts. Un nom partagé ferait poser le
    contenu d'une cible dans l'autre — un YAML dans un INI, sans un mot."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_deux,
                         {"rpcs3": "RPCS3"})
    dossier = launcher.local_dir(tmp_path) / launcher.PLAN
    noms = sorted(p.name for p in dossier.iterdir()
                  if launcher.BOOTSTRAP in p.name or launcher.IMPOSE in p.name)
    assert noms == ["rpcs3.bootstrap.1.ini", "rpcs3.bootstrap.2.yml",
                    "rpcs3.impose.1.ini"]
    assert "Handler: XInput" in (
        dossier / "rpcs3.bootstrap.2.yml").read_text(encoding="utf-8")
    assert "confirmationBoxBootGame" in (
        dossier / "rpcs3.impose.1.ini").read_text(encoding="utf-8")


def test_passer_de_deux_amorcages_a_un_retire_le_second(tmp_path, profils_deux,
                                                        profils_amorces):
    """Retirer une entrée d'un profil doit EFFACER ses fichiers déposés. Les
    laisser ne se verrait pas — ils ne sont plus nommés par aucun plan — mais
    un ré-amorçage ultérieur reposerait une configuration d'un autre âge sur
    une cible que plus rien ne décrit."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_deux,
                         {"rpcs3": "RPCS3"})
    dossier = launcher.local_dir(tmp_path) / launcher.PLAN
    assert (dossier / "rpcs3.bootstrap.2.yml").is_file()

    p = tmp_path / "rpcs3-un.toml"
    p.write_text(PROFIL_DEUX[:PROFIL_DEUX.index(
        "[[bootstrap]]", PROFIL_DEUX.index("[[bootstrap]]") + 1)],
        encoding="utf-8")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation",
                         {"rpcs3": profiles.load_profile(p)},
                         {"rpcs3": "RPCS3"})
    assert not (dossier / "rpcs3.bootstrap.2.yml").exists()
    assert (dossier / "rpcs3.bootstrap.1.ini").is_file()
    assert (dossier / "rpcs3.impose.1.ini").is_file()


def test_un_profil_reste_amorcable_avec_des_amorcages_indices(tmp_path,
                                                              profils_deux):
    """`profils_amorcables` coupe le nom du fichier sur « .bootstrap » pour
    retrouver l'identifiant. L'indice se place APRÈS : le vérifier par un test
    plutôt que par lecture — un identifiant mal recoupé rendrait
    « retro launcher --reamorcer » aveugle à un profil pourtant amorçable, et
    il faudrait relire le lanceur pour comprendre."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_deux,
                         {"rpcs3": "RPCS3"})
    assert launcher.profils_amorcables(tmp_path) == ["rpcs3"]
    assert launcher.ordonner_reamorcage(tmp_path, "rpcs3").is_file()


def test_aucun_plan_ecrit_ne_porte_de_jeton_non_substitue(tmp_path):
    """La moitié Python du garde que le lanceur porte en C#.

    Un jeton qui survit à l'écriture du plan ferait créer par Windows un
    dossier portant LITTÉRALEMENT « {install_dir} » : le fichier y serait posé,
    l'émulateur n'y lirait jamais rien, et rien ne le dirait. Le lanceur lève
    plutôt que d'écrire à côté ; ici, on vérifie qu'il n'a jamais à le faire
    pour les profils LIVRÉS."""
    profils = profiles.load_profiles(
        pathlib.Path(__file__).parent.parent / "retro" / "data" / "profiles")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils,
                         {pid: pid.capitalize() for pid in profils})
    fautives = []
    for fichier in sorted((launcher.local_dir(tmp_path)
                           / launcher.PLAN).glob("*.ini")):
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if ligne.startswith("bootstrap_target.") and "{" in ligne:
                fautives.append(f"{fichier.name} : {ligne}")
    assert fautives == [], (
        "des plans portent un jeton non substitué : " + " | ".join(fautives))


# --- D11 : ce que le dépôt impose n'est PAS ce que la console applique -----
#
# `ecrire_plan` est le SEUL geste qui dépose ces fragments, et `retro scan` son
# seul appelant. Changer `enforced` dans un profil, voir la suite verte et ne
# pas re-scanner laisse donc la console fusionner l'ANCIEN fragment — sans un
# mot, et avec pour symptôme le réglage d'origine, c'est-à-dire le défaut qu'on
# croyait corrigé.

def test_les_fragments_attendus_disent_les_deux_fichiers_d_une_entree(
        profils_imposes):
    """UNE seule définition de ce qu'une entrée d'amorçage dépose. Deux
    divergeraient, et le contrôle finirait par bénir un fragment périmé."""
    amorcage = profils_imposes["duckstation"].bootstraps[0]
    noms = dict(launcher.fragments_attendus("duckstation", 1, amorcage))
    assert set(noms) == {"duckstation.bootstrap.1.ini",
                         "duckstation.impose.1.ini"}
    assert "SetupWizardIncomplete" in noms["duckstation.impose.1.ini"]
    assert "ConfirmPowerOff" in noms["duckstation.bootstrap.1.ini"]


def test_le_fragment_attendu_est_exactement_celui_qui_est_depose(
        tmp_path, profils_imposes):
    """À l'octet près : c'est la comparaison que `retro status` fera, et une
    différence de fin de ligne y crierait au loup à chaque passage."""
    launcher.ecrire_plan(tmp_path, "D:\\E", profils_imposes,
                         {"duckstation": "DS"})
    dossier = launcher.local_dir(tmp_path) / launcher.PLAN
    amorcage = profils_imposes["duckstation"].bootstraps[0]
    for nom, attendu in launcher.fragments_attendus("duckstation", 1, amorcage):
        assert (dossier / nom).read_text(encoding="utf-8") == attendu


def test_une_entree_qui_n_impose_rien_n_attend_qu_un_fragment(profils_amorces):
    amorcage = profils_amorces["duckstation"].bootstraps[0]
    noms = [n for n, _ in launcher.fragments_attendus("duckstation", 1,
                                                      amorcage)]
    assert noms == ["duckstation.bootstrap.1.ini"]


def test_les_fragments_deposes_se_relisent_par_leur_nom(tmp_path,
                                                        profils_imposes):
    launcher.ecrire_plan(tmp_path, "D:\\E", profils_imposes,
                         {"duckstation": "DS"})
    lus = launcher.lire_fragments(tmp_path)
    assert "SetupWizardIncomplete" in lus["duckstation.impose.1.ini"]


def test_aucun_plan_depose_ne_se_lit_pas_comme_un_dossier_vide(tmp_path):
    """`None` et `{}` ne disent pas la même chose : le premier veut dire que
    « retro scan » n'a jamais tourné ici — l'hôte qui consulte le rapport sans
    voir le disque de la console est dans ce cas —, le second qu'il a tourné et
    n'a rien eu à déposer. Les confondre ferait accuser tous les profils d'un
    fragment périmé sur une machine où il n'y a rien à reprocher."""
    assert launcher.lire_fragments(tmp_path) is None

# --- le témoin des manettes : ce que le lanceur a VU au dernier lancement ---
#
# Le filet de D4. Il ne répare rien : il permet de CONSTATER qu'une manette a
# changé, ou qu'il y en a une de plus, autrement qu'en s'asseyant devant la
# télévision avec un pad qui ne répond pas. Même partage des rôles que
# bootstrap.txt — le lanceur écrit, `retro status` lit — et la même règle :
# c'est une TRACE, jamais une source de vérité.


def _ecrire_pads(tmp_path, texte):
    dossier = launcher.local_dir(tmp_path)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / launcher.TEMOIN_PADS).write_text(texte, encoding="utf-8")
    return tmp_path


def test_le_temoin_des_manettes_rend_la_date_et_chaque_pad_vu(tmp_path):
    racine = _ecrire_pads(tmp_path, (
        "2026-09-01 21:14:33\t2\n"
        "0\t045e:028e\tController (Xbox 360 Controller for Windows)\n"
        "1\t054c:05c4\tWireless Controller\n"))
    date, pads = launcher.lire_pads(racine)
    assert date == "2026-09-01 21:14:33"
    assert [(p.index, p.vid_pid, p.nom) for p in pads] == [
        (0, "045e:028e", "Controller (Xbox 360 Controller for Windows)"),
        (1, "054c:05c4", "Wireless Controller"),
    ]


def test_un_temoin_de_manettes_absent_ne_leve_pas(tmp_path):
    """Exactement la tolérance de `lire_amorcages`, et pour la même raison :
    c'est une trace. Un témoin absent doit faire dire « le lanceur n'a jamais
    relevé de manette » — pas planter `retro status`, qui deviendrait alors
    inutilisable sur toute machine où le lanceur n'a pas encore tourné."""
    assert launcher.lire_pads(tmp_path) == ("", [])


def test_un_temoin_de_manettes_illisible_ne_leve_pas(tmp_path):
    """Une ligne tronquée, un index qui n'est pas un nombre : le fichier est
    écrit par un autre langage sur une autre machine, et rien ne garantit sa
    forme. Ce qui se lit se lit, le reste est ignoré — un rapport qui refuse
    de se rendre en dit moins qu'un rapport partiel."""
    racine = _ecrire_pads(tmp_path, (
        "2026-09-01 21:14:33\t2\n"
        "pas-un-index\t045e:028e\tbruit\n"
        "1\t054c:05c4\tWireless Controller\n"))
    date, pads = launcher.lire_pads(racine)
    assert date == "2026-09-01 21:14:33"
    assert [p.index for p in pads] == [1]


def test_un_temoin_a_zero_manette_n_est_pas_un_temoin_absent(tmp_path):
    """DEUX CONSTATS DIFFÉRENTS, et les confondre efface le plus utile.

    « Le lanceur n'a jamais relevé de manette » veut dire qu'il n'a pas encore
    tourné, ou qu'il est trop vieux pour savoir le faire. « Aucune manette au
    dernier lancement » veut dire qu'il a regardé et n'a rien vu — ce qui, sur
    une console où le propriétaire vient de jouer, est un fait.
    """
    racine = _ecrire_pads(tmp_path, "2026-09-01 21:14:33\t0\n")
    date, pads = launcher.lire_pads(racine)
    assert date == "2026-09-01 21:14:33"
    assert pads == []
    assert (date, pads) != launcher.lire_pads(tmp_path / "ailleurs")


def test_un_nom_de_manette_a_tabulation_ne_perd_pas_sa_fin(tmp_path):
    """Le nom est le DERNIER champ, et il est pris en entier. Le découper sur
    toutes les tabulations tronquerait un nom qui en contient une, et le
    rapport nommerait un périphérique qui n'existe pas."""
    racine = _ecrire_pads(tmp_path, (
        "2026-09-01 21:14:33\t1\n"
        "0\t045e:028e\tController\t(Xbox 360)\n"))
    _, pads = launcher.lire_pads(racine)
    assert pads[0].nom == "Controller\t(Xbox 360)"


def test_le_lanceur_accepte_un_jeu_qui_est_un_dossier():
    """UN JEU N'EST PAS TOUJOURS UN FICHIER. Sur PS Vita, PS4 et PS5, une
    application installee est un DOSSIER — c'est exactement ce que le profil
    declare par son `app_dir_marker`, et `scan` l'inventorie comme tel.

    `File.Exists` rend FAUX sur un dossier : le lanceur refusait donc tous ces
    jeux avec « La ROM est introuvable », en designant un chemin parfaitement
    present. Mesure le 2026-08-29 sur Ratchet & Clank (PPSA01474) — le dossier
    existait, Steam affichait son entree, et le lanceur envoyait verifier un
    partage qui etait monte.

    Ce test lit la SOURCE : aucun compilateur C# n'existe sur cette machine, et
    la garde doit tout de meme se voir en revue.
    """
    src = (launcher.SOURCES / launcher.SOURCE).read_text(encoding="utf-8-sig")
    assert "Directory.Exists(rom)" in src, (
        "le lanceur ne teste que File.Exists(rom) : tout jeu qui est un "
        "dossier (Vita, PS4, PS5) serait refuse alors qu'il est present"
    )
    garde = next(l for l in src.splitlines() if "File.Exists(rom)" in l)
    assert "!Directory.Exists(rom)" in garde, (
        f"les deux tests doivent etre sur la MEME condition : {garde.strip()}"
    )


# --- les fragments de langue ----------------------------------------------

def test_le_nom_d_un_fragment_de_langue_porte_le_rang_ET_la_langue():
    """Sans le rang, les deux cibles d'un même profil se disputeraient un
    nom ; sans la langue, les fragments s'écraseraient entre eux."""
    assert launcher.langue_name(
        "retroarch", 2, "french", r"{install_dir}\config\melonDS\melonDS.opt"
    ) == "retroarch.langue.2.french.opt"


def test_un_fragment_de_langue_est_attendu_par_langue_declaree():
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n",
        langues=(("english", "[Main]\nLanguage = en\n"),
                 ("french", "[Main]\nLanguage = fr\n")),
        langue_repli="english",
    )
    noms = dict(launcher.fragments_attendus("duckstation", 1, amorcage))
    assert "duckstation.langue.1.english.ini" in noms
    assert "duckstation.langue.1.french.ini" in noms
    assert noms["duckstation.langue.1.french.ini"] == "[Main]\nLanguage = fr\n"


def test_un_fragment_de_langue_se_termine_par_un_saut_de_ligne():
    """Le contrôle de conformité compare à l'octet près : sans ce saut, il
    crierait au loup sur un fragment tout neuf."""
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n",
        langues=(("english", "[Main]\nLanguage = en"),),
        langue_repli="english",
    )
    noms = dict(launcher.fragments_attendus("duckstation", 1, amorcage))
    assert noms["duckstation.langue.1.english.ini"].endswith("\n")


def test_une_entree_sans_langues_n_attend_aucun_fragment_de_langue():
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n",
    )
    noms = [n for n, _ in launcher.fragments_attendus("duckstation", 1, amorcage)]
    assert not [n for n in noms if ".langue." in n]


def test_le_lanceur_substitue_l_identifiant_du_jeu():
    """{rom_id} rend le NOM du jeu, sans chemin ni extension.

    Il existe pour les emulateurs qui ne se lancent PAS sur un chemin. Vita3K
    en est un : son argument positionnel signifie « installer ET lancer », si
    bien que lui passer le dossier d'une application deja installee la
    reinstalle par-dessus elle-meme. Mesure le 2026-08-30 : apres ce
    lancement, l'application avait perdu son eboot.bin et son param.sfo, et
    ne demarrait plus. Un lancement qui DETRUIT ce qu'il devait lancer.

    Ce test lit la SOURCE, faute de compilateur C# sur cette machine.
    """
    src = (launcher.SOURCES / launcher.SOURCE).read_text(encoding="utf-8-sig")
    assert '"{rom_id}"' in src, (
        "le lanceur ne substitue pas {rom_id} : un gabarit qui le porte "
        "passerait le jeton LITTERAL a l'emulateur, qui ne lancerait rien"
    )
    assert "GetFileNameWithoutExtension" in src, (
        "{rom_id} doit etre le nom SEUL : un chemin complet ferait "
        "reinstaller le jeu au lieu de le lancer"
    )
    # L'ordre compte : {rom_id} avant {rom}, sinon « {rom} » remplacerait le
    # debut de « {rom_id} » et laisserait un « _id » colle au chemin.
    assert src.index('"{rom_id}"') < src.index('.Replace("{rom}", rom)'), (
        "{rom_id} doit etre substitue AVANT {rom}"
    )


# --- les lignes de langue du plan ------------------------------------------

def _plan_avec_langues():
    """Un plan écrit pour une entrée qui déclare english et french.

    `profiles.System` exige `extensions` et `bios` — ni l'un ni l'autre
    n'a de défaut dans le dataclass — d'où leur présence ici : les omettre
    lèverait un `TypeError` avant même d'atteindre le plan.
    """
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n",
        langues=(("english", "[Main]\nLanguage = en\n"),
                 ("french", "[Main]\nLanguage = fr\n")),
        langue_repli="english",
    )
    systeme = profiles.System(
        id="psx", name="PlayStation", extensions=(".cue",), launch="{rom}",
        bios=())
    texte = launcher.plan_systeme(
        "duckstation", systeme, "E:\\D\\duck.exe", "E:\\D",
        plan_dir="E:\\_launcher\\systems", bootstraps=(amorcage,))
    return dict(l.split("=", 1) for l in texte.splitlines()
                if "=" in l and not l.startswith("#"))


def test_le_plan_porte_une_ligne_par_langue_de_steam():
    """TOUTES les langues, pas seulement celles que le profil déclare : le
    lanceur doit trouver une ligne quoi que Steam dise, sinon `Valeur()`
    lèverait sur une langue parfaitement légitime."""
    l = _plan_avec_langues()
    for nom in langue_mod.LANGUES:
        assert f"bootstrap_langue.1.{nom}" in l


def test_une_langue_declaree_pointe_vers_son_propre_fragment():
    l = _plan_avec_langues()
    assert l["bootstrap_langue.1.french"] == (
        "E:\\_launcher\\systems\\duckstation.langue.1.french.ini")


def test_une_langue_non_declaree_pointe_vers_LE_REPLI_deja_resolu():
    """C'est tout le principe : Python résout, le lanceur lit une ligne. Un
    lanceur qui calculerait le repli pourrait en choisir un autre que celui
    que `retro status` annonce, et les deux ne se contrediraient jamais à
    voix haute."""
    l = _plan_avec_langues()
    assert l["bootstrap_langue.1.dutch"] == (
        "E:\\_launcher\\systems\\duckstation.langue.1.english.ini")


def test_le_plan_porte_un_defaut_pour_un_steam_muet():
    """Le seul cas que Python ne peut pas pré-résoudre. Une clé absente
    resterait une faute du plan, et `Valeur()` lèverait devant la
    télévision."""
    l = _plan_avec_langues()
    assert l["bootstrap_langue.1.defaut"] == (
        "E:\\_launcher\\systems\\duckstation.langue.1.english.ini")


def test_une_entree_sans_table_n_ecrit_aucune_ligne_de_langue():
    """Sur le modèle de `bootstrap_count=0` : écrire trente lignes vides
    ferait boucler le lanceur sur du rien."""
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n")
    systeme = profiles.System(
        id="psx", name="PlayStation", extensions=(".cue",), launch="{rom}",
        bios=())
    texte = launcher.plan_systeme(
        "duckstation", systeme, "E:\\D\\duck.exe", "E:\\D",
        plan_dir="E:\\_launcher\\systems", bootstraps=(amorcage,))
    assert "bootstrap_langue." not in texte


# --- la langue, côté lanceur : la source, faute de compilateur -------------

def _source_du_lanceur() -> str:
    """La SOURCE, faute de compilateur C# sur cette machine — c'est le motif
    qu'emploient déjà les tests voisins de ce fichier."""
    return (launcher.SOURCES / launcher.SOURCE).read_text(encoding="utf-8-sig")


def test_le_lanceur_lit_le_fichier_de_langue():
    src = _source_du_lanceur()
    assert launcher.LANGUE_FICHIER in src, (
        "le lanceur ne lit pas langue.txt : la commande « retro langue » "
        "poserait un fichier que personne ne lit")


def test_le_lanceur_lit_la_langue_de_steam_dans_le_registre():
    """Le relevé du 2026-08-30 sur l'invité dit où : `HKCU\\Software\\Valve\\
    Steam`, valeur `Language`, un REG_SZ en minuscules. Si ce test doit
    changer, c'est que le relevé a dit autre chose — et alors le SPEC change
    aussi."""
    src = _source_du_lanceur()
    assert "Software\\\\Valve\\\\Steam" in src or "Software\\Valve\\Steam" in src
    assert "\"Language\"" in src


def test_le_lanceur_cherche_la_ligne_de_langue_du_plan():
    src = _source_du_lanceur()
    assert "bootstrap_langue." in src, (
        "sans cette clé, le lanceur ne trouverait aucun fragment de langue "
        "et n'en poserait aucun, en silence")


def test_le_lanceur_retombe_sur_defaut_quand_steam_est_muet():
    src = _source_du_lanceur()
    assert "\"defaut\"" in src, (
        "un Steam muet ferait chercher « bootstrap_langue.1. » sans langue, "
        "et Valeur() lèverait devant la télévision")


def test_le_lanceur_ne_porte_AUCUN_nom_de_langue_en_dur():
    """Le repli est résolu par Python et écrit dans le plan. Un nom de langue
    codé dans le lanceur serait forcément une décision qu'il prend seul — un
    « si la langue est inconnue, mettre english » —, et il pourrait alors
    poser autre chose que ce que `retro status` annonce. Deux juges qui se
    contredisent ne se contredisent jamais à voix haute."""
    src = _source_du_lanceur().lower()
    en_dur = [nom for nom in langue_mod.LANGUES if '"' + nom + '"' in src]
    assert not en_dur, (
        f"le lanceur porte {en_dur} en dur : la résolution doit rester côté "
        "Python, qui écrit une ligne de plan par langue")


def test_le_lanceur_ecrit_le_temoin_de_langue():
    """`retro status` tourne AUSSI sur l'hôte, qui n'atteint pas le registre
    de l'invité. Sans témoin, le rapport ne pourrait rien dire de la langue
    de Steam — ou dirait autre chose selon la machine qui l'exécute."""
    src = _source_du_lanceur()
    assert launcher.TEMOIN_LANGUE in src


def test_le_temoin_de_langue_porte_ses_trois_lignes():
    """Les trois, et sous ces noms : la tâche suivante les relit tels quels.
    Une ligne manquante ferait dire au rapport « Steam n'a rien dit » d'un
    Steam qui a parfaitement répondu."""
    src = _source_du_lanceur()
    for ligne in ('"steam="', '"langue="', '"motif="'):
        assert ligne in src, f"le témoin ne porte pas {ligne}"


def test_le_temoin_de_langue_n_empeche_jamais_un_jeu_de_se_lancer():
    """Un témoin est une trace, pas une condition. Ce qui l'écrit est
    enveloppé : un disque plein ou un fichier verrouillé ne doit pas rendre
    la main à Steam, ce qui ressemblerait à un jeu qu'on vient de quitter."""
    src = _source_du_lanceur()
    debut = src.index("static void EcrireTemoinLangue")
    corps = src[debut:src.index("\n    }", debut)]
    assert "try" in corps and "catch (Exception)" in corps, (
        "l'écriture du témoin n'est pas rattrapée : une console dont le "
        "disque est plein ne lancerait plus aucun jeu")


def test_le_temoin_de_langue_est_ecrit_une_fois_par_lancement():
    """Une fois, PAS par entrée d'amorçage : un profil à deux cibles
    l'écrirait deux fois, et un profil sans amorçage jamais — le rapport ne
    dirait alors rien de la langue de Steam sur une console qui joue."""
    src = _source_du_lanceur()
    appels = src.count("EcrireTemoinLangue(")
    assert appels == 2, (
        f"{appels} occurrences de EcrireTemoinLangue : la définition et UN "
        "seul appel sont attendus")
    assert src.index("EcrireTemoinLangue(", src.index("static int Lancer()")) \
        < src.index("static string ApresExecutable"), (
        "l'appel doit vivre dans Lancer(), là où le lancement est décidé")


def test_la_langue_est_fusionnee_APRES_les_cles_imposees():
    """L'ordre est fixé pour que deux exécutions rendent le même fichier à
    l'octet près, et pour que le journal se lise."""
    src = _source_du_lanceur()
    impose = src.index("bootstrap_enforced.")
    langue = src.index("bootstrap_langue.")
    assert impose < langue


def test_les_deux_fusions_passent_par_LE_MEME_chemin():
    """Deux copies du bloc de fusion divergeraient : le jour où la première
    gagnerait une sauvegarde, la seconde poserait la langue sans."""
    src = _source_du_lanceur()
    assert src.count("EcrireAtomique(cible, fusionne, bomCible)") == 1, (
        "le fichier fusionné est écrit à deux endroits : les clés imposées "
        "et la langue doivent passer par la même méthode")
    assert src.count("FusionnerFragment(") == 3, (
        "attendu : la définition et DEUX appels — l'imposé, puis la langue")
