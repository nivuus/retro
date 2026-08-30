"""La langue qui s'applique, et pourquoi — jamais l'une sans l'autre."""
import pytest

from retro import langue as langue_mod


def test_une_langue_explicite_se_rend_elle_meme():
    d = langue_mod.resoudre("japanese", steam="french")
    assert d.langue == "japanese"
    assert "à la main" in d.motif


def test_auto_prend_la_langue_de_steam():
    d = langue_mod.resoudre(langue_mod.AUTO, steam="french")
    assert d.langue == "french"
    assert "Steam" in d.motif and "french" in d.motif


def test_auto_sur_un_steam_muet_ne_pretend_pas_savoir():
    """Rendre « english » ici serait un choix silencieux sur une mesure
    absente : le propriétaire croirait Steam en anglais."""
    d = langue_mod.resoudre(langue_mod.AUTO, steam="")
    assert d.langue == ""
    assert "n'a rien dit" in d.motif


def test_auto_ignore_un_steam_qui_dit_n_importe_quoi():
    """Une valeur hors liste n'est pas une langue : la traiter comme telle
    ferait chercher un fragment qui n'existe pas."""
    d = langue_mod.resoudre(langue_mod.AUTO, steam="klingon")
    assert d.langue == ""


def test_une_valeur_inconnue_est_refusee_en_se_nommant():
    with pytest.raises(langue_mod.LangueError) as exc:
        langue_mod.resoudre("frensh", steam="")
    assert "frensh" in str(exc.value)


def test_une_langue_declaree_est_posee_telle_quelle():
    d = langue_mod.appliquer("french", ("english", "french"), "english")
    assert d.langue == "french"
    assert d.motif == ""


def test_une_langue_non_declaree_donne_le_repli_ET_LE_DIT():
    d = langue_mod.appliquer("dutch", ("english", "french"), "english")
    assert d.langue == "english"
    assert "dutch" in d.motif and "english" in d.motif


def test_une_langue_vide_donne_le_repli():
    """Steam muet : le repli s'applique, et le motif ne parle d'aucune
    langue absente — il n'y en avait pas."""
    d = langue_mod.appliquer("", ("english", "french"), "english")
    assert d.langue == "english"


def test_sans_table_declaree_rien_n_est_pose():
    """L'état qui compte : cet émulateur ne suit pas la langue DU TOUT, et
    c'est différent de la suivre mal."""
    d = langue_mod.appliquer("french", (), "")
    assert d.langue == ""
    assert "aucune table" in d.motif


def test_la_liste_porte_les_noms_de_steam_et_non_des_codes_iso():
    """`koreana` et `brazilian` sont les pièges : un code ISO ne trouverait
    jamais la valeur que Steam écrit."""
    assert "koreana" in langue_mod.LANGUES
    assert "brazilian" in langue_mod.LANGUES
    assert "korean" not in langue_mod.LANGUES
    assert "fr" not in langue_mod.LANGUES


def test_auto_n_est_pas_une_langue():
    assert langue_mod.AUTO not in langue_mod.LANGUES
    assert langue_mod.AUTO in langue_mod.VALEURS
