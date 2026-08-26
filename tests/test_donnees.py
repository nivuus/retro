"""Les données livrées avec le paquet.

Ce test est la seule chose qui empêche une faute de frappe dans un TOML de
n'être découverte que sur la console du propriétaire.
"""
import fnmatch
import importlib.resources
import pathlib
import tomllib

from retro import cli, manifest, profiles

RACINE = pathlib.Path(__file__).parent.parent

# Les données vivent DANS le paquet, et ce test les atteint comme le code les
# atteint : par importlib.resources. Les localiser depuis la racine du dépôt
# laissait passer le défaut qui rendait « retro scan » inutilisable sur un
# wheel installé — les fichiers étaient bien versionnés, simplement pas là où
# le paquet installé allait les chercher.
DONNEES = pathlib.Path(str(importlib.resources.files("retro"))) / "data"
CORE = DONNEES / "manifests" / "core.toml"
PROFILS = DONNEES / "profiles"

# Aucun test ne référence de nom d'émulateur au statut contesté : le dépôt est
# public et sa politique l'exclut. Cette liste est le garde-fou automatique.
INTERDITS = ("ryujinx", "yuzu", "citron", "sudachi", "switch", "ryubing")


def test_le_manifeste_noyau_se_charge():
    m = manifest.load_manifest(CORE)
    assert m, "le manifeste noyau est vide"


def test_les_profils_se_chargent():
    p = profiles.load_profiles(PROFILS)
    assert p


def test_les_donnees_vivent_dans_le_paquet():
    """Un wheel installé ne voit que ce qui est DANS le paquet.

    Mesuré : avec les données à la racine du dépôt et data-files, un wheel
    installé dans un venv neuf faisait pointer DEFAULT_MANIFEST sur
    site-packages/manifests/core.toml, qui n'existe pas — « retro scan » et
    « retro install » étaient inutilisables. Le mode éditable, où __file__
    reste dans le dépôt, masquait entièrement le défaut.
    """
    paquet = pathlib.Path(str(importlib.resources.files("retro")))
    assert CORE.is_file(), f"manifeste noyau absent du paquet : {CORE}"
    assert sorted(f.name for f in PROFILS.glob("*.toml")), "aucun profil livré"
    # Et le code doit les chercher là, pas ailleurs.
    assert cli.DEFAULT_MANIFEST == CORE
    assert cli.DEFAULT_PROFILES == PROFILS
    assert paquet in cli.DEFAULT_MANIFEST.parents, (
        f"{cli.DEFAULT_MANIFEST} est hors du paquet {paquet}"
    )


def test_chaque_fichier_de_donnees_est_emporte_par_le_wheel():
    """Vivre dans l'arbre ne suffit pas : sans package-data, setuptools laisse
    les .toml derrière lui et l'installation retombe sur le défaut d'origine.
    """
    conf = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    motifs = conf["tool"]["setuptools"]["package-data"]["retro"]
    paquet = RACINE / "retro"
    oublies = [
        str(f.relative_to(paquet))
        for f in sorted((paquet / "data").rglob("*")) if f.is_file()
        if not any(fnmatch.fnmatch(str(f.relative_to(paquet)), m) for m in motifs)
    ]
    assert oublies == [], f"données hors de package-data : {oublies}"


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
    """Un sha256 tronqué ou remplacé par un espace réservé ne protège de rien.

    Les archives supplémentaires sont vérifiées de la même façon : celle qui
    porte les cores de RetroArch pèse plus que l'archive principale, et une
    empreinte fantaisiste y serait tout aussi aveugle.
    """
    for e in manifest.load_manifest(CORE).values():
        for quoi, sha in [(e.key, e.sha256)] + [
            (f"{e.key} parts[{i}]", p.sha256) for i, p in enumerate(e.parts)
        ]:
            assert len(sha) == 64, f"{quoi} : sha256 de {len(sha)} caractères"
            assert all(c in "0123456789abcdef" for c in sha.lower()), quoi


def test_les_url_sont_en_https():
    for e in manifest.load_manifest(CORE).values():
        assert e.url.startswith("https://"), f"{e.key} : {e.url}"
        for i, p in enumerate(e.parts):
            assert p.url.startswith("https://"), f"{e.key} parts[{i}] : {p.url}"


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
