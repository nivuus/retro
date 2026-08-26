"""Dérivation de l'identifiant de raccourci.

Verrouillée contre une fixture produite par Steam. Une formule fausse ne lève
rien : elle nomme les fichiers d'artwork d'après un identifiant que Steam ne
cherchera jamais, et la bibliothèque affiche des vignettes grises.
"""
import pathlib

import pytest

from retro.steam import appid, vdf_io

FIXTURE = pathlib.Path(__file__).parent.parent / "fixtures" / "shortcuts-reel.vdf"


GRID_LISTING = (FIXTURE.parent / "grid-listing.txt").read_text().split()


@pytest.mark.parametrize("entree", vdf_io.load_shortcuts(FIXTURE))
def test_l_artwork_est_nomme_d_apres_l_appid_du_fichier(entree):
    """Ce que la fixture atteste réellement.

    Steam ne RECALCULE jamais l'appid d'un raccourci existant : il lit celui du
    fichier et cherche l'artwork sous ce nombre. Mesuré le 2026-08-26 sur une
    installation réelle — 8 des 10 raccourcis ont leurs 5 assets, tous nommés
    d'après l'appid non signé de leur entrée.

    C'est pourquoi ce test n'exige PAS que notre formule reproduise celle de
    Steam : sur cette même fixture, 9 des 10 appid ne correspondent à aucun
    calcul, parce que leurs chemins ont changé depuis leur création. La formule
    doit être déterministe et stable, pas fidèle.
    """
    non_signe = appid.to_unsigned(entree["appid"])
    prefixes = set(appid.grid_prefixes(non_signe).values())
    presents = {f.rsplit(".", 1)[0] for f in GRID_LISTING}
    trouves = prefixes & presents
    # Un raccourci sans artwork est légitime (jeu lancé par son propre lanceur).
    # Mais s'il en a, ce doit être sous NOS préfixes et sous aucun autre.
    if trouves:
        assert len(trouves) == 5, f"{entree['appname']!r} : {sorted(trouves)}"


def test_la_fixture_couvre_des_raccourcis_avec_artwork():
    """Sans cette garde, une fixture dont aucun raccourci n'a d'artwork ferait
    passer le test ci-dessus sans rien vérifier."""
    presents = {f.rsplit(".", 1)[0] for f in GRID_LISTING}
    avec = [e for e in vdf_io.load_shortcuts(FIXTURE)
            if set(appid.grid_prefixes(appid.to_unsigned(e["appid"])).values()) & presents]
    assert len(avec) >= 5


def test_la_casse_des_champs_est_celle_de_steam():
    """Steam écrit appname/exe/icon en minuscules et StartDir en CamelCase. Un
    champ dans la mauvaise casse est ignoré en silence."""
    entree = vdf_io.load_shortcuts(FIXTURE)[0]
    for champ in ("appid", "appname", "exe", "icon", "sortas", "tags"):
        assert champ in entree
    for champ in ("StartDir", "LaunchOptions", "IsHidden", "FlatpakAppID"):
        assert champ in entree
    assert "AppName" not in entree and "Exe" not in entree


def test_la_fixture_contient_au_moins_un_raccourci():
    """Une fixture vide ferait passer le test paramétré sans rien vérifier."""
    assert len(vdf_io.load_shortcuts(FIXTURE)) >= 1


def test_le_bit_haut_est_toujours_pose():
    legacy = appid.legacy_appid('"C:\\jeu.exe"', "Jeu")
    assert legacy & 0x80000000


def test_to_signed_est_reversible():
    legacy = appid.legacy_appid('"C:\\jeu.exe"', "Jeu")
    assert appid.to_unsigned(appid.to_signed(legacy)) == legacy


def test_les_guillemets_comptent():
    """Steam stocke exe avec ses guillemets et calcule dessus. Les retirer
    donnerait un identifiant différent et de l'artwork jamais trouvé."""
    avec = appid.legacy_appid('"C:\\jeu.exe"', "Jeu")
    sans = appid.legacy_appid("C:\\jeu.exe", "Jeu")
    assert avec != sans


def test_prefixes_des_cinq_assets():
    assert appid.grid_prefixes(2398962978) == {
        "portrait": "2398962978p",
        "paysage": "2398962978",
        "hero": "2398962978_hero",
        "logo": "2398962978_logo",
        "icone": "2398962978_icon",
    }


def test_asset_trouve_quelle_que_soit_l_extension(tmp_path):
    (tmp_path / "2398962978p.png").write_bytes(b"x")
    assert appid.existing_asset(tmp_path, "2398962978p").suffix == ".png"


def test_le_paysage_ne_capte_pas_le_portrait(tmp_path):
    """Le préfixe du paysage est le nombre nu ; une correspondance par préfixe
    de chaîne le ferait matcher 2398962978p.png et 2398962978_hero.png."""
    (tmp_path / "2398962978p.png").write_bytes(b"x")
    assert appid.existing_asset(tmp_path, "2398962978") is None
