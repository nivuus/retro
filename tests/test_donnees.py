"""Les données livrées avec le paquet.

Ce test est la seule chose qui empêche une faute de frappe dans un TOML de
n'être découverte que sur la console du propriétaire.
"""
import fnmatch
import importlib.resources
import pathlib
import re
import subprocess
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

# Aucun fichier versionné ne référence de nom d'émulateur au statut contesté :
# le dépôt est public et sa politique l'exclut. Cette liste est le garde-fou
# automatique. Les forks du projet fermé en 2024 y figurent aussi : le nom
# change, le statut non.
INTERDITS = ("ryujinx", "yuzu", "citron", "sudachi", "switch", "ryubing",
             "suyu", "torzu", "uzuy", "eden", "kefir", "strato", "skyline")

# Les documents qui ÉNONCENT la politique doivent pouvoir nommer ce qu'ils
# excluent : sans cela, la raison de l'exclusion n'est écrite nulle part. Ce
# sont les seules exemptions, nominatives, et gelées par
# test_le_garde_fou_ne_se_raccourcit_pas : en ajouter une se voit en revue,
# contrairement à retirer discrètement un nom d'INTERDITS.
EXEMPTES = frozenset({
    "tests/test_donnees.py",
    "docs/superpowers/specs/2026-08-26-retro-console-design.md",
    "docs/superpowers/plans/2026-08-26-emulateurs-sous-projet-a.md",
})

# Un gabarit launch est une ligne de commande Windows : des jetons séparés par
# des espaces, ceux qui portent un chemin étant guillemetés.
_JETON = re.compile(r'"([^"]*)"|(\S+)')


def _jetons(gabarit: str) -> list[str]:
    return [guillemete or nu for guillemete, nu in _JETON.findall(gabarit)]


def _est_sous(chemin: pathlib.PureWindowsPath,
              dossier: pathlib.PureWindowsPath) -> bool:
    return chemin.parts[:len(dossier.parts)] == dossier.parts


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


def test_les_gabarits_launch_suivent_la_structure_de_l_archive():
    """Les chemins d'un gabarit sont relatifs au dossier d'installation.

    Rien ne les reliait à l'archive : retirer le préfixe « RetroArch-Win64\\ »
    des neuf gabarits, ou viser un core qui n'en est pas un, laissait les tests
    de données verts — et le raccourci Steam échouait en silence sur la
    console. La règle est déduite du profil lui-même (le dossier racine de son
    exe), donc elle vaut pour tout profil futur, RetroArch ou non ; un profil
    sans « -L », comme Dolphin, n'a simplement rien à vérifier de ce côté.

    Ce que ce test NE prouve pas : que le core existe dans l'archive. Le
    vérifier exigerait de télécharger 200 Mo, et aucun test d'ici ne touche au
    réseau.
    """
    for pid, p in profiles.load_profiles(PROFILS).items():
        dossier = pathlib.PureWindowsPath(p.exe).parent
        for s in p.systems:
            jetons = _jetons(s.launch)
            for j in jetons:
                if "\\" not in j:
                    continue
                assert _est_sous(pathlib.PureWindowsPath(j), dossier), (
                    f"{pid}/{s.id} : « {j} » ne part pas de « {dossier} », le "
                    f"dossier racine de exe = « {p.exe} »"
                )
            for i, j in enumerate(jetons):
                if j != "-L":
                    continue
                assert i + 1 < len(jetons), f"{pid}/{s.id} : -L sans argument"
                core = pathlib.PureWindowsPath(jetons[i + 1])
                assert _est_sous(core, dossier / "cores"), (
                    f"{pid}/{s.id} : le core « {jetons[i + 1]} » n'est pas dans "
                    f"« {dossier / 'cores'} »"
                )
                assert core.name.endswith("_libretro.dll"), (
                    f"{pid}/{s.id} : « {core.name} » n'est pas un core libretro"
                )


def test_le_garde_fou_ne_se_raccourcit_pas():
    """Sans cette assertion, retirer un nom d'INTERDITS — ou ajouter une
    exemption — suffisait à faire taire le garde-fou sans qu'aucun test ne le
    remarque. La liste est donc gelée : la modifier est un acte explicite."""
    assert set(INTERDITS) == {
        "ryujinx", "yuzu", "citron", "sudachi", "switch", "ryubing",
        "suyu", "torzu", "uzuy", "eden", "kefir", "strato", "skyline",
    }
    assert EXEMPTES == {
        "tests/test_donnees.py",
        "docs/superpowers/specs/2026-08-26-retro-console-design.md",
        "docs/superpowers/plans/2026-08-26-emulateurs-sous-projet-a.md",
    }


def test_aucun_emulateur_au_statut_conteste():
    """Le dépôt est public. Cette politique est écrite dans la spec ; ce test
    est ce qui l'applique, plutôt que la vigilance d'un relecteur.

    La portée est TOUT le versionné : le README, retro/*.py et docs/ sont
    aussi publics que manifests/ et profiles/, et n'étaient vus par rien.
    """
    # La portée est déduite de git, pas d'une liste tenue à la main : un
    # fichier ajouté au dépôt entre d'office dans le champ du garde-fou.
    try:
        sortie = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE,
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        # Échec franc plutôt que skip : un garde-fou qu'on ne remarque pas
        # avoir cessé de tourner ne garde rien.
        raise AssertionError(
            "ce test énumère les fichiers versionnés et exige donc une copie "
            f"de travail git : {exc}"
        ) from exc
    fichiers = [f for f in sortie.split("\0") if f]
    assert len(fichiers) > 20, "git ls-files n'a rien rendu : ce test ne prouve rien"

    trouves = []
    for rel in fichiers:
        chemin = RACINE / rel
        if rel in EXEMPTES or not chemin.is_file():
            continue
        # La fixture .vdf est binaire ; ce qui s'y décode en texte est
        # précisément ce qu'il faut inspecter, le reste est ignoré.
        texte = chemin.read_bytes().decode("utf-8", errors="ignore").lower()
        trouves += [f"{rel} : {mot}" for mot in INTERDITS if mot in texte]
    assert trouves == [], f"références interdites : {trouves}"


def test_les_identifiants_de_systeme_sont_uniques_entre_profils():
    """Deux profils qui revendiquent le même système rendraient le scan
    dépendant de l'ordre de chargement."""
    vus = {}
    for pid, p in profiles.load_profiles(PROFILS).items():
        for s in p.systems:
            assert s.id not in vus, f"{s.id} revendiqué par {vus.get(s.id)} et {pid}"
            vus[s.id] = pid
