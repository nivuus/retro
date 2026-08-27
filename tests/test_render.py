"""Les trois modes de rendu : lequel s'applique, et avec quels arguments."""
import pytest

from retro import render


SOLIDE = render.Machine(gpu="RTX A2000", vram_mo=6144, coeurs=8,
                        largeur=1920, hauteur=1080)
MOYENNE = render.Machine(gpu="GTX 1650", vram_mo=4096, coeurs=6,
                         largeur=1920, hauteur=1080)
MODESTE = render.Machine(gpu="UHD 630", vram_mo=1024, coeurs=4,
                         largeur=1280, hauteur=720)


# --- classer une machine ------------------------------------------------

@pytest.mark.parametrize("machine,attendu", [
    (SOLIDE, render.SOLIDE),
    (MOYENNE, render.MOYENNE),
    (MODESTE, render.MODESTE),
])
def test_classement_des_machines(machine, attendu):
    assert render.classe_machine(machine) == attendu


def test_un_seul_critere_ne_suffit_pas_a_monter_de_classe():
    """Beaucoup de VRAM sur deux cœurs ne fait pas une machine solide : les
    deux seuils doivent tenir, sinon l'émulation lourde rame côté CPU sur une
    machine que le rapport aurait annoncée capable."""
    genereuse = render.Machine(vram_mo=16384, coeurs=2, largeur=1920, hauteur=1080)
    assert render.classe_machine(genereuse) == render.MODESTE


# --- choisir un mode ----------------------------------------------------

@pytest.mark.parametrize("mode", [render.NATIVE, render.FULL])
def test_un_mode_explicite_ne_s_arbitre_pas(mode):
    """Le propriétaire a choisi : rien à décider, quelle que soit la machine."""
    assert render.resoudre(mode, render.LOURD, MODESTE).mode == mode


@pytest.mark.parametrize("classe,machine", [
    ("solide", SOLIDE), ("moyenne", MOYENNE), ("modeste", MODESTE)])
@pytest.mark.parametrize("cout", render.COUTS)
def test_auto_rend_toujours_un_mode_declarable(classe, machine, cout):
    """`auto` n'est jamais lui-même le résultat : il choisit."""
    assert render.resoudre(render.AUTO, cout, machine).mode \
        in render.MODES_DECLARES


def test_auto_menage_les_systemes_lourds_sur_machine_moyenne():
    assert render.resoudre(render.AUTO, render.LOURD, MOYENNE).mode \
        == render.NATIVE
    assert render.resoudre(render.AUTO, render.LEGER, MOYENNE).mode \
        == render.FULL


def test_auto_pousse_tout_sur_une_machine_solide():
    for cout in render.COUTS:
        assert render.resoudre(render.AUTO, cout, SOLIDE).mode == render.FULL


def test_auto_explique_toujours_son_choix():
    """Sans motif, `auto` est une boîte noire : un jeu qui rame ressemble à du
    matériel insuffisant plutôt qu'à un arbitrage qu'on peut contredire."""
    d = render.resoudre(render.AUTO, render.LOURD, MOYENNE)
    assert "moyenne" in d.motif and "heavy" in d.motif
    assert str(MOYENNE.vram_mo) in d.motif


def test_une_machine_non_mesuree_n_est_pas_une_machine_modeste():
    """Zéro de VRAM sur zéro cœur n'est pas une petite machine : c'est une
    mesure qui n'a pas eu lieu. Les confondre ferait passer `auto` en natif
    partout, ce qui ressemble à de la prudence et n'en est pas."""
    d = render.resoudre(render.AUTO, render.LEGER, render.Machine())
    assert d.mode == render.NATIVE
    assert "non mesurée" in d.motif


def test_un_mode_inconnu_est_refuse():
    with pytest.raises(render.RenderError, match="mode de rendu inconnu"):
        render.resoudre("maximum", render.LEGER, SOLIDE)


def test_un_cout_inconnu_est_refuse():
    """Une faute de frappe sur `cost` ferait décider `auto` sur une case
    absente de la table : mieux vaut le dire que rendre KeyError."""
    with pytest.raises(render.RenderError, match="coût d'émulation inconnu"):
        render.resoudre(render.AUTO, "leger", SOLIDE)


# --- l'échelle interne --------------------------------------------------

@pytest.mark.parametrize("session,natif,maxi,attendu", [
    (1080, 240, 8, 4),      # PlayStation sur un écran 1080p
    (2160, 240, 8, 8),      # 4K : 9x tiendrait, la borne dit 8
    (720, 1080, 8, 1),      # session plus basse que l'original : jamais 0
    (1080, 480, 4, 2),
])
def test_calcul_de_l_echelle(session, natif, maxi, attendu):
    assert render.echelle(session, natif, maxi) == attendu


def test_une_hauteur_native_absurde_est_refusee():
    with pytest.raises(render.RenderError):
        render.echelle(1080, 0, 8)


# --- composer la ligne d'arguments --------------------------------------

def rendu(native_args="", full_args="", crt="", crt_absent="x",
          native_height=0, max_scale=0):
    return render.Render(
        native=render.RenderMode(args=native_args, crt=crt,
                                 crt_absent=crt_absent),
        full=render.RenderMode(args=full_args),
        native_height=native_height, max_scale=max_scale)


def test_substitution_de_la_resolution_de_session():
    r = rendu(full_args="--resolution={width}x{height}")
    assert render.composer(r, render.FULL, SOLIDE) == "--resolution=1920x1080"


def test_la_meme_entree_suit_la_session():
    """Deux clients Apollo, deux résolutions, une seule entrée Steam : c'est
    tout l'intérêt de composer au lancement plutôt qu'à la synchronisation."""
    r = rendu(full_args="--resolution={width}x{height}")
    tv = render.Machine(vram_mo=6144, coeurs=8, largeur=3840, hauteur=2160)
    assert render.composer(r, render.FULL, tv) == "--resolution=3840x2160"
    assert render.composer(r, render.FULL, SOLIDE) == "--resolution=1920x1080"


def test_substitution_de_l_echelle():
    r = rendu(full_args="-scale={scale}", native_height=240, max_scale=8)
    assert render.composer(r, render.FULL, SOLIDE) == "-scale=4"


def test_le_crt_accompagne_le_mode_natif():
    r = rendu(native_args="-scale=1", crt="-shader=crt", crt_absent="")
    assert render.composer(r, render.NATIVE, SOLIDE) == "-scale=1 -shader=crt"


def test_le_crt_ne_suit_pas_le_mode_full():
    """Un shader CRT en mode full annulerait le mode full."""
    r = rendu(native_args="-scale=1", full_args="-scale=4",
              crt="-shader=crt", crt_absent="")
    assert render.composer(r, render.FULL, SOLIDE) == "-scale=4"


def test_un_mode_qui_ne_pilote_rien_rend_une_chaine_vide():
    """Certains émulateurs n'exposent aucun réglage en ligne de commande.
    C'est une réponse, pas une panne — et le profil l'a déclaré par une note."""
    assert render.composer(rendu(), render.NATIVE, SOLIDE) == ""


def test_composer_refuse_de_substituer_une_resolution_non_mesuree():
    """« --resolution=0x0 » ferait refuser l'émulateur, ou pire, démarrerait
    dans une taille absurde. Zéro n'est pas une mesure."""
    r = rendu(full_args="--resolution={width}x{height}")
    with pytest.raises(render.RenderError, match="n'a pas été mesurée"):
        render.composer(r, render.FULL, render.Machine(vram_mo=1, coeurs=1))


def test_composer_refuse_auto():
    """`auto` a été résolu AVANT d'arriver ici : le laisser passer
    signifierait qu'un arbitrage a été sauté."""
    with pytest.raises(render.RenderError, match="n'est pas un mode déclarable"):
        render.composer(rendu(), render.AUTO, SOLIDE)
