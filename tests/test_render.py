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


# --- le troisième axe : le REMPLISSAGE -----------------------------------
#
# Trois axes, pas deux et demi. Les tests qui suivent portent tous sur la même
# confusion, celle que la dette D2 décrit : le remplissage n'est ni le mode
# (combien de pixels l'émulateur CALCULE) ni le ratio d'époque (la FORME de
# l'image), c'est la façon dont l'image produite est POSÉE sur l'écran.

def _mode(**kw) -> render.RenderMode:
    """Un mode de rendu qui pilote quelque chose, par défaut."""
    kw.setdefault("args", "-x")
    return render.RenderMode(**kw)


def test_le_remplissage_n_est_ni_un_mode_ni_un_ratio():
    """Confondre le remplissage avec le mode ferait croire à un quatrième
    mode ; le confondre avec le ratio ferait prendre les bandes noires
    VOULUES d'un 4:3 sur un 16:9 pour un défaut de remplissage."""
    assert render.REMPLISSAGES == (render.ENTIER, render.AJUSTE)
    assert not set(render.REMPLISSAGES) & set(render.MODES)


def test_aucune_valeur_de_remplissage_ne_deforme():
    """C'est l'invariant de l'axe, et la seule raison qu'il ait deux valeurs
    plutôt qu'une : `entier` et `ajuste` agrandissent tous les deux SANS
    toucher au ratio. L'étirement n'est pas une troisième valeur qu'on
    n'aurait pas retenue — il n'est pas sur cet axe."""
    for valeur in render.REMPLISSAGES:
        assert "etir" not in valeur and "stretch" not in valeur
    assert render.SANS_DEFORMATION == render.REMPLISSAGES


@pytest.mark.parametrize("mode,attendu", [
    (render.NATIVE, render.ENTIER),
    (render.FULL, render.AJUSTE),
])
def test_la_politique_donne_un_remplissage_par_mode(mode, attendu):
    """Le natif préserve la trame de la console : seul un multiple ENTIER
    l'agrandit sans la rééchantillonner. Le full n'a plus de trame à
    préserver — sa résolution interne est déjà montée à la session — et vise
    donc le plus grand agrandissement qui tienne."""
    assert render.remplissage_attendu(mode) == attendu


def test_auto_n_a_pas_de_remplissage_a_lui():
    """`auto` ne déclare rien : il choisit un mode et hérite du remplissage
    de celui qu'il retient. Lui en donner un serait un quatrième réglage."""
    with pytest.raises(render.RenderError, match="auto"):
        render.remplissage_attendu(render.AUTO)


def test_la_politique_s_explique_pour_chaque_mode():
    """Même règle que pour `auto` : un réglage qui s'applique en silence est
    un défaut. `retro status` cite ce motif."""
    for mode in render.MODES_DECLARES:
        assert render.motif_remplissage(mode).strip()


def test_un_mode_qui_declare_son_remplissage_le_rend():
    choix = render.resoudre_remplissage(render.NATIVE,
                                        _mode(fill=render.ENTIER))
    assert choix.remplissage == render.ENTIER
    assert choix.motif.strip()


def test_un_emulateur_qui_n_expose_aucun_remplissage_le_dit():
    """Dolphin 2606a : aucune clé « Integer » dans GraphicsSettings.cpp. Ce
    n'est pas une mesure qui manque, c'est une réponse."""
    choix = render.resoudre_remplissage(
        render.FULL, _mode(fill_absent="aucune clé Integer dans sa config"))
    assert choix.remplissage == render.NON_REGLABLE
    assert "Integer" in choix.motif


def test_un_mode_sans_le_moindre_argument_n_a_rien_a_remplir():
    """DuckStation : dix-sept arguments, aucun de rendu. Le mode ENTIER est
    déclaré vide avec sa note — il n'y a pas de troisième axe à y régler, et
    ce n'est pas non plus une mesure qui manque. Le dire sans toucher au
    profil : sa note dit déjà pourquoi."""
    choix = render.resoudre_remplissage(
        render.FULL,
        render.RenderMode(args="", note="rien en ligne de commande"))
    assert choix.remplissage == render.NON_REGLABLE
    assert "rien en ligne de commande" in choix.motif


def test_un_remplissage_jamais_mesure_n_est_pas_un_emulateur_sans_reglage():
    """Les confondre ferait rouvrir l'enquête à chaque passage, ou pire,
    attendre un effet qui ne viendra jamais. Même distinction que « bloc
    absent » contre « mode déclaré vide »."""
    choix = render.resoudre_remplissage(render.NATIVE, _mode())
    assert choix.remplissage == render.NON_MESURE
    assert "mesur" in choix.motif


@pytest.mark.parametrize("mode_declare", [
    render.RenderMode(args="-x"),
    render.RenderMode(args="-x", fill=render.ENTIER),
    render.RenderMode(args="-x", fill_absent="rien à régler"),
    render.RenderMode(args="", note="rien en ligne de commande"),
])
def test_le_remplissage_explique_toujours_sa_valeur(mode_declare):
    choix = render.resoudre_remplissage(render.NATIVE, mode_declare)
    assert choix.motif.strip()


# --- le remplissage IMPOSÉ PAR L'AMORÇAGE -------------------------------
#
# Le chaînon qui manquait au modèle : un émulateur dont les deux modes ne
# passent rien — DuckStation — rendait NON_REGLABLE, et le rapport disait
# « rien à régler » sur un émulateur dont la console règle pourtant le
# cadrage. Le réglage n'est pas dans `args` : il est dans le fragment
# `enforced`, posé avant que le mode ne soit résolu.

def test_un_remplissage_impose_par_l_amorcage_se_declare_sur_un_mode_vide():
    """Le cas que le modèle ne savait pas décrire. Un mode qui ne passe rien
    a QUAND MÊME un remplissage si l'amorçage le pose dans le fichier de
    réglages de l'émulateur."""
    choix = render.resoudre_remplissage(
        render.FULL,
        render.RenderMode(args="", note="rien en ligne de commande"),
        fill_enforced=render.ENTIER,
        fill_enforced_where="[Display] Scaling = X — relevé le 2026-01-01",
    )
    assert choix.remplissage == render.ENTIER


def test_le_motif_d_un_remplissage_impose_dit_ou_il_est_pose():
    """Trois choses que le propriétaire ne peut pas deviner : que le réglage
    vient de l'amorçage, OÙ il est posé, et qu'il vaut la même chose dans les
    deux modes parce que cet émulateur ne règle rien en ligne de commande."""
    choix = render.resoudre_remplissage(
        render.NATIVE,
        render.RenderMode(args="", note="rien en ligne de commande"),
        fill_enforced=render.ENTIER,
        fill_enforced_where="[Display] Scaling = X — relevé le 2026-01-01",
    )
    assert "[Display] Scaling" in choix.motif
    assert "amorçage" in choix.motif
    assert "deux modes" in choix.motif.lower()


def test_un_remplissage_impose_vaut_la_meme_chose_dans_les_deux_modes():
    """LA CONTRAINTE A CHANGÉ, PAS LE VERDICT — retourné le 2026-09-05 (D14).

    Cette docstring disait « le fragment est posé avant que le mode ne soit
    résolu », et c'était FAUX : `Amorcer()` est appelé depuis `Lancer()`, une
    fois le mode connu. Ce champ-ci reste néanmoins à valeur unique, parce
    qu'il est ce que le profil AFFIRME — « cet émulateur pose la même chose
    dans les deux modes » — et non ce que le mécanisme impose. La politique
    reste donc hors de sa portée, et le rapport ne doit pas faire croire
    qu'elle s'applique. Un remplissage imposé PAR MODE, lui, y est soumis :
    voir les tests de D14 en fin de fichier."""
    vide = render.RenderMode(args="", note="rien en ligne de commande")
    ou = "[Display] Scaling = X — relevé le 2026-01-01"
    deux = {render.resoudre_remplissage(m, vide, fill_enforced=render.ENTIER,
                                        fill_enforced_where=ou).remplissage
            for m in render.MODES_DECLARES}
    assert deux == {render.ENTIER}


def test_une_mesure_d_absence_l_emporte_sur_un_remplissage_impose():
    """L'ordre des cas. `fill_absent` est une MESURE — « il n'y a rien à
    régler sur cet axe » — et elle l'emporte sur une déclaration. L'inverse
    ferait annoncer un remplissage sur un émulateur dont on a constaté qu'il
    n'en a pas."""
    choix = render.resoudre_remplissage(
        render.FULL,
        render.RenderMode(args="", note="rien en ligne de commande",
                          fill_absent="aucune clé de cet axe"),
        fill_enforced=render.ENTIER,
        fill_enforced_where="[Display] Scaling = X — relevé le 2026-01-01",
    )
    assert choix.remplissage == render.NON_REGLABLE
    assert "aucune clé de cet axe" in choix.motif


# --- le remplissage imposé PAR MODE — dette D14 --------------------------
#
# Le fait qui a rendu ceci possible, et il a été MESURÉ dans le lanceur plutôt
# que supposé : `Amorcer()` est appelé DEPUIS `Lancer()`, à la ligne 1487,
# quand le mode effectif est résolu à la ligne 1257. Le fragment imposé est
# donc posé APRÈS que le mode est connu, et non avant — ce que ce module a
# longtemps affirmé, et qui était faux.
#
# Un remplissage imposé par mode est donc soumis à la POLITIQUE, comme un
# `fill` : c'est la garde qui mord ici, et non une exemption de plus.

def test_un_mode_peut_porter_son_propre_remplissage_impose():
    """PCSX2 : rien en ligne de commande, mais un fragment imposé PAR MODE.
    Le mode natif impose la mise à l'échelle entière dans PCSX2.ini."""
    choix = render.resoudre_remplissage(
        render.NATIVE,
        render.RenderMode(
            args="", note="rien en ligne de commande",
            fill_enforced=render.ENTIER,
            fill_enforced_where="[EmuCore/GS] IntegerScaling = true — relevé"),
    )
    assert choix.remplissage == render.ENTIER


def test_le_remplissage_impose_par_mode_suit_la_politique_mode_par_mode():
    """Les DEUX modes, et ils ne disent pas la même chose. C'est très
    exactement ce que le champ par profil ne savait pas exprimer."""
    natif = render.resoudre_remplissage(
        render.NATIVE,
        render.RenderMode(args="", note="rien",
                          fill_enforced=render.ENTIER,
                          fill_enforced_where="[A] B = true — relevé"))
    plein = render.resoudre_remplissage(
        render.FULL,
        render.RenderMode(args="", note="rien",
                          fill_enforced=render.AJUSTE,
                          fill_enforced_where="[A] B = false — relevé"))
    assert (natif.remplissage, plein.remplissage) == (render.ENTIER,
                                                      render.AJUSTE)


def test_le_motif_d_un_remplissage_impose_par_mode_dit_ou_ET_cite_la_politique():
    """Deux choses à la fois, et aucune ne remplace l'autre : OÙ la clé est
    posée — c'est ce que la console reprend au propriétaire dans SON fichier —
    et POURQUOI cette valeur-là, qui est la politique du mode."""
    choix = render.resoudre_remplissage(
        render.NATIVE,
        render.RenderMode(args="", note="rien",
                          fill_enforced=render.ENTIER,
                          fill_enforced_where="[EmuCore/GS] IntegerScaling"))
    assert "[EmuCore/GS] IntegerScaling" in choix.motif
    assert "amorçage" in choix.motif
    assert render.motif_remplissage(render.NATIVE) in choix.motif


def test_une_mesure_d_absence_l_emporte_sur_un_remplissage_impose_par_mode():
    """Le même ordre que pour le champ par profil : `fill_absent` est une
    MESURE, et elle l'emporte sur toute déclaration."""
    choix = render.resoudre_remplissage(
        render.FULL,
        render.RenderMode(args="", note="rien",
                          fill_absent="aucune clé de cet axe",
                          fill_enforced=render.AJUSTE,
                          fill_enforced_where="[A] B"))
    assert choix.remplissage == render.NON_REGLABLE
