"""Vérification des BIOS que les émulateurs exigent.

Aucun BIOS n'entre dans ce dépôt : les fixtures fabriquent des fichiers
quelconques et calculent leur empreinte à la volée.
"""
import hashlib
import pathlib

import pytest

from retro import bios, profiles

PROFIL = """
schema = 1
id = "retroarch"
exe = "retroarch.exe"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-f "{rom}"'
bios = [
  { file = "scph5501.bin", md5 = "{md5_a}", required = true },
  { file = "scph5502.bin", md5 = "{md5_b}", required = false },
]
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-f "{{rom}}"'
bios = []
"""


def empreinte(contenu: bytes) -> str:
    return hashlib.md5(contenu).hexdigest()


@pytest.fixture
def contexte(tmp_path):
    """Un profil dont les empreintes correspondent à de vrais fichiers."""
    a, b = b"contenu-a", b"contenu-b"
    p = tmp_path / "retroarch.toml"
    p.write_text(
        PROFIL.replace("{md5_a}", empreinte(a)).replace("{md5_b}", empreinte(b)),
        encoding="utf-8",
    )
    racine = tmp_path / "BIOS"
    racine.mkdir()
    return {"retroarch": profiles.load_profile(p)}, racine, a, b


def test_tout_present_est_ok(contexte):
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(a)
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok
    assert psx.missing_required == ()


def test_un_bios_requis_absent(contexte):
    profils, racine, a, b = contexte
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert not psx.ok
    assert psx.missing_required == ("scph5501.bin",)


def test_un_bios_optionnel_absent_ne_bloque_pas(contexte):
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(a)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok
    optionnel = next(f for f in psx.files if f.name == "scph5502.bin")
    assert optionnel.state == "absent"


def test_un_bios_present_mais_faux_est_signale_a_part(contexte):
    """« Corrompu » n'est pas « absent » : le propriétaire CROIT l'avoir mis.
    Lui dire qu'il manque l'enverrait chercher un fichier qui est déjà là."""
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(b"ce n'est pas le bon fichier")
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    requis = next(f for f in psx.files if f.name == "scph5501.bin")
    assert requis.state == "corrompu"
    assert not psx.ok
    assert psx.missing_required == ("scph5501.bin",)


def test_un_systeme_sans_bios_est_toujours_ok(contexte):
    profils, racine, _, _ = contexte
    snes = next(s for s in bios.check_bios(profils, racine) if s.system_id == "snes")
    assert snes.ok and snes.files == ()


def test_racine_absente_rend_tout_absent(contexte):
    """G:\\ non monté est une panne réelle sur cette machine : elle ne doit pas
    lever, elle doit se voir dans le rapport."""
    profils, racine, _, _ = contexte
    psx = next(s for s in bios.check_bios(profils, racine / "jamais")
               if s.system_id == "psx")
    assert not psx.ok
    assert all(f.state == "absent" for f in psx.files)


def test_l_empreinte_est_insensible_a_la_casse(contexte):
    """Les md5 publiés le sont tantôt en majuscules, tantôt en minuscules."""
    profils, racine, a, b = contexte
    for s in profils["retroarch"].systems:
        for f in s.bios:
            f["md5"] = f["md5"].upper()
    (racine / "scph5501.bin").write_bytes(a)
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok


def test_le_nom_de_fichier_est_insensible_a_la_casse(contexte, tmp_path):
    """Le propriétaire dépose ses fichiers depuis Windows, qui ne distingue pas
    la casse ; le scan tourne peut-être sur un système qui la distingue."""
    profils, racine, a, b = contexte
    (racine / "SCPH5501.BIN").write_bytes(a)
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok


def test_un_bios_illisible_ne_leve_pas(contexte):
    """La garantie centrale du module. Un fichier présent mais illisible —
    permissions refusées, partage qui répond sans servir — ne doit pas faire
    échouer le rapport ENTIER pour un seul fichier.

    En root les permissions ne bloquent rien : le test saute plutôt que de
    prétendre vérifier ce qu'il ne vérifie pas.
    """
    import os
    if os.geteuid() == 0:
        pytest.skip("root ignore les permissions : ce test ne prouverait rien")
    profils, racine, a, b = contexte
    illisible = racine / "scph5501.bin"
    illisible.write_bytes(a)
    illisible.chmod(0o000)
    try:
        psx = next(s for s in bios.check_bios(profils, racine)
                   if s.system_id == "psx")
        requis = next(f for f in psx.files if f.name == "scph5501.bin")
        assert requis.state == "corrompu"
    finally:
        illisible.chmod(0o644)


def test_une_racine_illisible_ne_leve_pas(contexte):
    import os
    if os.geteuid() == 0:
        pytest.skip("root ignore les permissions : ce test ne prouverait rien")
    profils, racine, _, _ = contexte
    racine.chmod(0o000)
    try:
        psx = next(s for s in bios.check_bios(profils, racine)
                   if s.system_id == "psx")
        assert all(f.state == "absent" for f in psx.files)
    finally:
        racine.chmod(0o755)


def test_une_racine_qui_est_un_fichier_ne_leve_pas(contexte, tmp_path):
    """Cas réel : le propriétaire crée un fichier au lieu d'un dossier."""
    profils, _, _, _ = contexte
    faux = tmp_path / "BIOS-fichier"
    faux.write_text("pas un dossier", encoding="utf-8")
    psx = next(s for s in bios.check_bios(profils, faux) if s.system_id == "psx")
    assert all(f.state == "absent" for f in psx.files)


def test_un_dossier_portant_le_nom_d_un_bios_ne_compte_pas(contexte):
    profils, racine, _, b = contexte
    (racine / "scph5501.bin").mkdir()
    (racine / "scph5502.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    requis = next(f for f in psx.files if f.name == "scph5501.bin")
    assert requis.state == "absent"


def test_tous_les_systemes_sont_rendus(contexte):
    profils, racine, _, _ = contexte
    assert {s.system_id for s in bios.check_bios(profils, racine)} == {"psx", "snes"}


# --- Groupes : « un parmi ceux-ci suffit » --------------------------------

PROFIL_GROUPE = """
schema = 1
id = "retroarch"
exe = "retroarch.exe"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-f "{rom}"'
bios = [
  { file = "scph5500.bin", md5 = "{md5_a}", required = true, group = "region", region = "Japon" },
  { file = "scph5501.bin", md5 = "{md5_b}", required = true, group = "region", region = "Amerique du Nord" },
  { file = "scph5502.bin", md5 = "{md5_c}", required = true, group = "region", region = "Europe" },
]
"""


@pytest.fixture
def contexte_groupe(tmp_path):
    a, b, c = b"jp", b"us", b"eu"
    p = tmp_path / "retroarch.toml"
    p.write_text(
        PROFIL_GROUPE.replace("{md5_a}", empreinte(a))
                     .replace("{md5_b}", empreinte(b))
                     .replace("{md5_c}", empreinte(c)),
        encoding="utf-8",
    )
    racine = tmp_path / "BIOS"
    racine.mkdir()
    return {"retroarch": profiles.load_profile(p)}, racine, a, b, c


def test_un_seul_bios_du_groupe_suffit(contexte_groupe):
    """Le cœur du défaut : quelqu'un qui dépose scph5501.bin — le bon — lisait
    « MANQUANT : scph5500.bin » et « MANQUANT : scph5502.bin », et partait
    chercher deux fichiers dont il n'a pas besoin."""
    profils, racine, a, b, c = contexte_groupe
    (racine / "scph5501.bin").write_bytes(b)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok
    assert psx.missing_required == ()


def test_aucun_bios_du_groupe_est_un_seul_manque(contexte_groupe):
    """Le vrai cas « aucun BIOS PlayStation » ne doit pas être masqué."""
    profils, racine, *_ = contexte_groupe
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert not psx.ok
    assert psx.missing_required == ("scph5500.bin", "scph5501.bin", "scph5502.bin")
    besoins = [n for n in psx.needs if not n.satisfied]
    assert len(besoins) == 1, "trois manques distincts au lieu d'un seul besoin"
    assert besoins[0].group == "region"


def test_un_membre_corrompu_ne_masque_pas_un_membre_valide(contexte_groupe):
    profils, racine, a, b, c = contexte_groupe
    (racine / "scph5500.bin").write_bytes(b"ce n'est pas le bon fichier")
    (racine / "scph5502.bin").write_bytes(c)
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert psx.ok


def test_les_besoins_hors_groupe_restent_individuels(contexte):
    """Un BIOS sans groupe reste un besoin à lui seul."""
    profils, racine, a, b = contexte
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert [n.group for n in psx.needs] == [None, None]
    assert [tuple(f.name for f in n.files) for n in psx.needs] == [
        ("scph5501.bin",), ("scph5502.bin",)]


def test_la_region_est_portee_jusqu_au_resultat(contexte_groupe):
    """La clé `region` du profil n'était lue par personne : elle sert
    maintenant à nommer, dans le rapport, lequel des trois déposer."""
    profils, racine, *_ = contexte_groupe
    psx = next(s for s in bios.check_bios(profils, racine) if s.system_id == "psx")
    assert [f.region for f in psx.files] == ["Japon", "Amerique du Nord", "Europe"]


# --- obtenir ce qui manque -------------------------------------------------
#
# Toujours aucun BIOS dans ce dépôt : la « source » de ces tests est une
# fonction qui rend des octets fabriqués, et l'empreinte attendue est celle
# que le profil déclare.

class Source:
    """Une source de BIOS en mémoire, qui compte ce qu'on lui demande."""

    def __init__(self, contenus, base="https://exemple.invalid/BIOS"):
        self.contenus = contenus
        self.base = base
        self.demandes = []

    def url_for(self, nom):
        return f"{self.base}/{nom}"

    def fetch(self, url):
        nom = url.rsplit("/", 1)[1]
        self.demandes.append(nom)
        if nom not in self.contenus:
            raise RuntimeError(f"404 {url}")
        return self.contenus[nom]


def test_un_bios_verifie_est_ecrit(contexte):
    profils, racine, a, b = contexte
    src = Source({"scph5501.bin": a, "scph5502.bin": b})
    res = bios.fetch_bios(profils, racine, src, fetch=src.fetch)
    assert [r.state for r in res] == [bios.OBTENU, bios.OBTENU]
    assert (racine / "scph5501.bin").read_bytes() == a


def test_une_empreinte_inattendue_n_ecrit_rien(contexte):
    """L'ORDRE COMPTE : vérifier PUIS écrire. Écrire d'abord, quitte à effacer
    ensuite, laisserait après une coupure un fichier du mauvais contenu dans
    le dossier des BIOS — qu'un émulateur aurait pu charger entre temps.

    Et un BIOS faux ne se distingue pas d'un BIOS absent avant d'être en jeu :
    l'émulateur démarre, au lieu de planter."""
    profils, racine, a, b = contexte
    src = Source({"scph5501.bin": b"autre chose", "scph5502.bin": b})
    res = bios.fetch_bios(profils, racine, src, fetch=src.fetch)
    refus = next(r for r in res if r.name == "scph5501.bin")
    assert refus.state == bios.REFUSE
    assert not (racine / "scph5501.bin").exists()
    assert not list(racine.glob("*.partiel"))


def test_une_panne_de_transport_n_est_pas_un_refus(contexte):
    """Les deux n'appellent pas le même geste : l'une se réessaie, l'autre
    veut qu'on regarde la source."""
    profils, racine, a, b = contexte
    src = Source({"scph5502.bin": b})
    res = bios.fetch_bios(profils, racine, src, fetch=src.fetch)
    assert next(r for r in res
                if r.name == "scph5501.bin").state == bios.INJOIGNABLE


def test_un_besoin_deja_satisfait_ne_demande_rien(contexte):
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(a)
    (racine / "scph5502.bin").write_bytes(b)
    src = Source({"scph5501.bin": a, "scph5502.bin": b})
    assert bios.fetch_bios(profils, racine, src, fetch=src.fetch) == []
    assert src.demandes == []


def test_un_fichier_corrompu_est_redemande_et_le_dit(contexte):
    """Ce n'est pas un réglage du propriétaire : c'est un fichier qui ne sert
    à rien. Le remplacer est la seule réparation — mais le rapport le dit,
    plutôt que de le faire en silence."""
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(b"pas le bon")
    src = Source({"scph5501.bin": a, "scph5502.bin": b})
    res = bios.fetch_bios(profils, racine, src, fetch=src.fetch)
    repare = next(r for r in res if r.name == "scph5501.bin")
    assert repare.state == bios.OBTENU
    assert "corrompu" in repare.detail
    assert (racine / "scph5501.bin").read_bytes() == a


def test_sans_source_rien_n_est_demande(contexte):
    profils, racine, a, b = contexte
    assert bios.fetch_bios(profils, racine, None, fetch=None) == []


# --- porter les BIOS là où l'émulateur regarde -----------------------------

PROFIL_AVEC_DOSSIER = PROFIL.replace(
    'exe = "retroarch.exe"',
    'exe = "retroarch.exe"\nbios_dir = \'RetroArch-Win64\\system\'')


@pytest.fixture
def contexte_porte(tmp_path):
    a, b = b"contenu-a", b"contenu-b"
    p = tmp_path / "retroarch.toml"
    p.write_text(PROFIL_AVEC_DOSSIER.replace("{md5_a}", empreinte(a))
                 .replace("{md5_b}", empreinte(b)), encoding="utf-8")
    racine = tmp_path / "BIOS"
    racine.mkdir()
    return ({"retroarch": profiles.load_profile(p)}, racine,
            tmp_path / "Emulation", a, b)


def test_un_bios_verifie_est_porte_chez_l_emulateur(contexte_porte):
    """Le dossier du propriétaire n'est pas celui où l'émulateur regarde.
    Tant que rien ne les reliait, le rapport pouvait annoncer « présent,
    empreinte vérifiée » sur un émulateur qui ne voyait aucun BIOS."""
    profils, racine, emu, a, b = contexte_porte
    (racine / "scph5501.bin").write_bytes(a)
    res = bios.place_bios(profils, racine, emu, {"retroarch": "RetroArch"})
    porte = next(r for r in res if r.name == "scph5501.bin")
    assert porte.state == bios.PORTE
    cible = emu / "RetroArch" / "RetroArch-Win64" / "system" / "scph5501.bin"
    assert cible.read_bytes() == a


def test_un_bios_corrompu_n_est_jamais_porte(contexte_porte):
    """Le copier le rendrait indiscernable d'un bon aux yeux de l'émulateur,
    pendant que le rapport continuerait de le dire corrompu — deux vérités
    contradictoires sur la même machine."""
    profils, racine, emu, a, b = contexte_porte
    (racine / "scph5501.bin").write_bytes(b"pas le bon")
    res = bios.place_bios(profils, racine, emu, {"retroarch": "RetroArch"})
    assert [r for r in res if r.state == bios.PORTE] == []
    assert not (emu / "RetroArch" / "RetroArch-Win64" / "system"
                / "scph5501.bin").exists()


def test_un_profil_sans_dossier_est_nomme_et_non_devine(contexte):
    """« Personne n'a mesuré où il regarde » n'est pas « il n'en a pas
    besoin ». Un dossier inventé déposerait les fichiers à côté, sans autre
    symptôme qu'un écran noir."""
    profils, racine, a, b = contexte
    (racine / "scph5501.bin").write_bytes(a)
    res = bios.place_bios(profils, racine, racine.parent / "E",
                          {"retroarch": "RetroArch"})
    assert [r.state for r in res] == [bios.SANS_DOSSIER]
    assert not (racine.parent / "E").exists()


def test_un_bios_va_dans_le_sous_dossier_que_l_emulateur_declare(tmp_path):
    """FBNeo declare « fbneo/neogeo.zip » dans son propre .info : le
    sous-dossier fait partie de ce que l'emulateur dit, pas d'une supposition.
    Depose a la racine, le fichier serait hors de sa portee — le symptome
    exact d'un BIOS jamais telecharge."""
    a = b"contenu-a"
    p = tmp_path / "retroarch.toml"
    p.write_text(PROFIL_AVEC_DOSSIER.replace("{md5_a}", empreinte(a))
                 .replace("{md5_b}", empreinte(b"contenu-b"))
                 .replace('{ file = "scph5501.bin", md5 = "' + empreinte(a)
                          + '", required = true }',
                          '{ file = "scph5501.bin", md5 = "' + empreinte(a)
                          + '", required = true, dir = "fbneo" }'),
                 encoding="utf-8")
    profils = {"retroarch": profiles.load_profile(p)}
    racine = tmp_path / "BIOS"
    racine.mkdir()
    (racine / "scph5501.bin").write_bytes(a)
    emu = tmp_path / "Emulation"
    bios.place_bios(profils, racine, emu, {"retroarch": "RetroArch"})
    cible = (emu / "RetroArch" / "RetroArch-Win64" / "system" / "fbneo"
             / "scph5501.bin")
    assert cible.read_bytes() == a
    # ... et le dossier du proprietaire, lui, range a plat : la verification
    # cherche par NOM, jamais par chemin.
    assert (racine / "scph5501.bin").is_file()
