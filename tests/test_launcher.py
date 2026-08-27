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
