"""Steam Input par jeu, dans localconfig.vdf.

Steam Input masque la manette à l'émulateur — mesuré sur la console le
2026-08-28 — et il se désactive jeu par jeu. Une bibliothèque de cinquante
jeux ne se règle pas cinquante fois à la main, et un jeu oublié est un jeu
muet que rien ne signale.
"""
import pathlib

import pytest
import vdf

from retro.steam import steam_input

FIXTURE = pathlib.Path(__file__).parent.parent / "fixtures" / "localconfig-extrait.vdf"

DEJA_DESACTIVE = -1117161211
ACTIF = -2000000000
SANS_LA_CLE = 730
ABSENT_DU_FICHIER = -42


@pytest.fixture
def local(tmp_path):
    cible = tmp_path / "localconfig.vdf"
    cible.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    return cible


def test_lit_letat_de_chaque_jeu(local):
    assert steam_input.etats(local) == {
        DEJA_DESACTIVE: "0",
        ACTIF: "2",
    }


def test_un_jeu_sans_la_cle_compte_comme_actif(local):
    """Absent du fichier ou présent sans la clé : Steam Input s'applique.

    C'est le défaut de Steam, et c'est le cas de TOUS les raccourcis fraîchement
    créés — donc le cas normal, pas le cas rare."""
    assert steam_input.actifs(local, [SANS_LA_CLE, ABSENT_DU_FICHIER]) == [
        SANS_LA_CLE, ABSENT_DU_FICHIER,
    ]


def test_ne_signale_pas_un_jeu_deja_regle(local):
    assert steam_input.actifs(local, [DEJA_DESACTIVE]) == []


def test_desactive_et_rend_la_sauvegarde(local):
    sauvegarde = steam_input.desactiver(local, [ACTIF, ABSENT_DU_FICHIER])
    assert sauvegarde is not None and sauvegarde.exists()
    assert steam_input.actifs(local, [ACTIF, ABSENT_DU_FICHIER]) == []


def test_n_ecrit_rien_si_tout_est_deja_regle(local):
    """Sans cela, chaque synchronisation déposerait une sauvegarde de plus."""
    avant = local.read_text(encoding="utf-8")
    assert steam_input.desactiver(local, [DEJA_DESACTIVE]) is None
    assert local.read_text(encoding="utf-8") == avant


def test_ne_touche_a_rien_dautre(local):
    """Le fichier porte bien plus que des manettes : tout doit survivre.

    La valeur JSON échappée est le cas qui casse : un aller-retour maladroit
    en mangerait les antislashs, et Steam relirait un document tronqué."""
    avant = vdf.loads(local.read_text(encoding="utf-8"))["UserLocalConfigStore"]
    steam_input.desactiver(local, [ACTIF])
    apres = vdf.loads(local.read_text(encoding="utf-8"))["UserLocalConfigStore"]

    assert apres["system"] == avant["system"]
    assert apres["ControllerTypesUsed"] == avant["ControllerTypesUsed"]
    assert apres["apps"][str(SANS_LA_CLE)] == avant["apps"][str(SANS_LA_CLE)]
    assert apres["apps"][str(DEJA_DESACTIVE)]["SteamControllerRumbleIntensity"] == "320"


def test_conserve_les_reglages_voisins_du_jeu_modifie(local):
    """Désactiver Steam Input ne doit pas effacer la vibration du même jeu."""
    steam_input.desactiver(local, [DEJA_DESACTIVE, ACTIF])
    apps = vdf.loads(local.read_text(encoding="utf-8"))["UserLocalConfigStore"]["apps"]
    assert apps[str(DEJA_DESACTIVE)]["SteamControllerRumble"] == "-1"


def test_un_fichier_absent_est_une_erreur_nommee(tmp_path):
    """Ni un fichier vide ni un silence : le fichier existe dès qu'un compte
    s'est connecté, donc son absence est une anomalie qui mérite son message."""
    with pytest.raises(steam_input.LocalConfigError, match="localconfig.vdf"):
        steam_input.etats(tmp_path / "localconfig.vdf")


def test_un_fichier_illisible_est_une_erreur_nommee(tmp_path):
    casse = tmp_path / "localconfig.vdf"
    casse.write_text('"UserLocalConfigStore" { "apps"', encoding="utf-8")
    with pytest.raises(steam_input.LocalConfigError):
        steam_input.etats(casse)


def test_une_racine_inattendue_est_une_erreur_nommee(tmp_path):
    autre = tmp_path / "localconfig.vdf"
    autre.write_text('"AutreChose"\n{\n\t"apps"\n\t{\n\t}\n}\n', encoding="utf-8")
    with pytest.raises(steam_input.LocalConfigError, match="UserLocalConfigStore"):
        steam_input.etats(autre)
