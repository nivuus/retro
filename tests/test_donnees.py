"""Les données livrées avec le paquet.

Ce test est la seule chose qui empêche une faute de frappe dans un TOML de
n'être découverte que sur la console du propriétaire.
"""
import pathlib

from retro import manifest, profiles

RACINE = pathlib.Path(__file__).parent.parent
CORE = RACINE / "manifests" / "core.toml"
PROFILS = RACINE / "profiles"

# Aucun test ne référence de nom d'émulateur au statut contesté : le dépôt est
# public et sa politique l'exclut. Cette liste est le garde-fou automatique.
INTERDITS = ("ryujinx", "yuzu", "citron", "sudachi", "switch", "ryubing")


def test_le_manifeste_noyau_se_charge():
    m = manifest.load_manifest(CORE)
    assert m, "le manifeste noyau est vide"


def test_les_profils_se_chargent():
    p = profiles.load_profiles(PROFILS)
    assert p


def test_chaque_emulateur_a_son_profil():
    """Un émulateur sans profil s'installe et ne lance jamais rien."""
    m = manifest.load_manifest(CORE)
    p = profiles.load_profiles(PROFILS)
    orphelins = [e.key for e in m.values() if e.profile not in p]
    assert orphelins == [], f"émulateurs sans profil : {orphelins}"


def test_chaque_profil_a_son_emulateur():
    """Un profil sans émulateur déclare des systèmes que rien ne peut lancer."""
    m = manifest.load_manifest(CORE)
    utilises = {e.profile for e in m.values()}
    p = profiles.load_profiles(PROFILS)
    orphelins = sorted(set(p) - utilises)
    assert orphelins == [], f"profils sans émulateur au manifeste : {orphelins}"


def test_les_empreintes_ont_la_bonne_forme():
    """Un sha256 tronqué ou remplacé par un espace réservé ne protège de rien."""
    for e in manifest.load_manifest(CORE).values():
        assert len(e.sha256) == 64, f"{e.key} : sha256 de {len(e.sha256)} caractères"
        assert all(c in "0123456789abcdef" for c in e.sha256.lower()), e.key


def test_les_url_sont_en_https():
    for e in manifest.load_manifest(CORE).values():
        assert e.url.startswith("https://"), f"{e.key} : {e.url}"


def test_aucun_emulateur_au_statut_conteste():
    """Le dépôt est public. Cette politique est écrite dans la spec ; ce test
    est ce qui l'applique, plutôt que la vigilance d'un relecteur."""
    textes = [CORE.read_text(encoding="utf-8").lower()]
    textes += [f.read_text(encoding="utf-8").lower() for f in PROFILS.glob("*.toml")]
    for t in textes:
        for interdit in INTERDITS:
            assert interdit not in t, f"référence interdite : {interdit}"


def test_les_identifiants_de_systeme_sont_uniques_entre_profils():
    """Deux profils qui revendiquent le même système rendraient le scan
    dépendant de l'ordre de chargement."""
    vus = {}
    for pid, p in profiles.load_profiles(PROFILS).items():
        for s in p.systems:
            assert s.id not in vus, f"{s.id} revendiqué par {vus.get(s.id)} et {pid}"
            vus[s.id] = pid
