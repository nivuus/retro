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


# La substitution et le calcul de l'échelle ne sont plus testés ici : ils ne
# sont plus ICI. Ils vivaient en double — une fois en Python, appelée par ces
# seuls tests, une fois en C# dans le lanceur, seule exécutée. Le lanceur se
# vérifie par « retro-launch.exe --explain » ; le vérifier depuis pytest
# demanderait un Windows, et un second exemplaire de la logique testé à la
# place du vrai ne prouve rien.
