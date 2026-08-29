"""L'identité gravée : elle doit BOUGER, et se lire sans dépôt."""
import os
import pathlib
import subprocess
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "outils"))
import identite_build  # noqa: E402

from retro import identite  # noqa: E402


def _arbre(racine, contenu="x = 1\n"):
    (racine / "retro").mkdir()
    (racine / "retro" / "__init__.py").write_text("")
    (racine / "retro" / "scan.py").write_text(contenu)
    (racine / "pyproject.toml").write_text("[project]\nname='retro'\n")
    return racine


def test_deux_appels_sur_le_meme_arbre_rendent_la_meme_version(tmp_path):
    """pip appelle chaque hook PEP 517 dans un processus séparé : deux valeurs
    différentes feraient rejeter la roue pour incohérence de métadonnée."""
    a = _arbre(tmp_path)
    assert identite_build.version(a) == identite_build.version(a)


def test_la_version_croit_quand_une_source_change(tmp_path):
    a = _arbre(tmp_path)
    avant = identite_build.version(a)
    fichier = a / "retro" / "scan.py"
    fichier.write_text("x = 2\n")
    os.utime(fichier, (1_800_000_000, 1_800_000_000))
    apres = identite_build.version(a)
    assert apres != avant
    # L'ordre PEP 440 doit tenir : l'horodatage passe en premier, numérique.
    assert apres.split("+")[1].split(".")[0] > avant.split("+")[1].split(".")[0]


def test_graver_ne_change_pas_la_version_qu_il_grave(tmp_path):
    a = _arbre(tmp_path)
    premiere = identite_build.graver(a)
    assert identite_build.graver(a) == premiere
    assert premiere in (a / "retro" / "_identite.py").read_text()


def test_sans_depot_la_version_reste_valide(tmp_path):
    a = _arbre(tmp_path)
    v = identite_build.version(a)
    assert identite_build.revision(a) == ""
    assert ".g" not in v.split("+")[1]
    assert len(v.split("+")[1].split(".")[0]) == 14


def test_la_revision_se_lit_dans_un_arbre_de_travail_lie(tmp_path):
    """`.git` y est un FICHIER, et les refs vivent dans le dépôt principal.
    C'est la forme qu'aura l'arbre de l'agent qui exécute ce plan."""
    principal = tmp_path / "principal" / ".git"
    (principal / "refs" / "heads").mkdir(parents=True)
    (principal / "refs" / "heads" / "main").write_text("a" * 40 + "\n")
    lie = tmp_path / "lie"
    lie.mkdir()
    interne = tmp_path / "principal" / ".git" / "worktrees" / "lie"
    interne.mkdir(parents=True)
    (interne / "HEAD").write_text("ref: refs/heads/main\n")
    (interne / "commondir").write_text("../..\n")
    (lie / ".git").write_text(f"gitdir: {interne}\n")
    assert identite_build.revision(lie) == "a" * 7


def test_la_revision_se_lit_dans_packed_refs(tmp_path):
    depot = tmp_path / ".git"
    depot.mkdir()
    (depot / "HEAD").write_text("ref: refs/heads/main\n")
    (depot / "packed-refs").write_text(
        "# pack-refs with: peeled\n" + "b" * 40 + " refs/heads/main\n")
    assert identite_build.revision(tmp_path) == "b" * 7


def test_un_arbre_jamais_construit_le_dit():
    def absent(_nom):
        raise ImportError("pas de gravure")
    assert identite._lire(importer=absent) == identite.SOURCE
    assert "jamais construit" in identite.lisible(identite.SOURCE)


def test_la_version_gravee_est_celle_de_la_metadonnee_de_la_roue(tmp_path):
    """La seule assertion qui traverse vraiment la construction : un backend
    qui ne s'exécuterait pas laisserait tout le reste vert."""
    import shutil
    racine = pathlib.Path(__file__).resolve().parents[1]
    copie = tmp_path / "src"
    copie.mkdir()
    for nom in ("retro", "outils"):
        shutil.copytree(racine / nom, copie / nom)
    shutil.copy2(racine / "pyproject.toml", copie / "pyproject.toml")
    (copie / "retro" / "_identite.py").unlink(missing_ok=True)
    attendue = identite_build.version(copie)
    sortie = tmp_path / "roues"
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps",
         "--no-build-isolation", "-w", str(sortie), str(copie)],
        check=True, capture_output=True)
    roue = next(sortie.glob("retro-*.whl"))
    z = zipfile.ZipFile(roue)
    meta = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
    versions = [l.split(": ", 1)[1] for l in z.read(meta).decode().splitlines()
                if l.startswith("Version: ")]
    assert versions == [attendue]
    assert any(n.endswith("retro/_identite.py") for n in z.namelist())


def _copie_du_depot(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    """Une copie de l'arbre, SANS le module gravé — l'état d'un dépôt frais."""
    import shutil
    racine = pathlib.Path(__file__).resolve().parents[1]
    copie = tmp_path / "src"
    copie.mkdir()
    for nom in ("retro", "outils"):
        shutil.copytree(racine / nom, copie / nom)
    shutil.copy2(racine / "pyproject.toml", copie / "pyproject.toml")
    (copie / "retro" / "_identite.py").unlink(missing_ok=True)
    return copie


def _appeler_hook(copie, nom):
    """Appelle un hook PEP 517 dans un processus à part, comme pip le fait."""
    outils = str(pathlib.Path(__file__).resolve().parents[1] / "outils")
    r = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, {outils!r});"
         f"import identite_build; identite_build.{nom}()"],
        cwd=copie, capture_output=True, text=True)
    assert r.returncode == 0, f"{nom} a échoué :\n{r.stderr[-1500:]}"


def test_le_tout_premier_hook_grave_lui_aussi(tmp_path):
    """`get_requires_for_build_wheel` est le PREMIER hook que pip appelle, et
    setuptools y lit déjà la version dynamique.

    Les trois `get_requires_*` étaient réexportés tels quels : sous isolation
    de construction — c'est-à-dire sur le chemin de PRODUCTION, celui que
    `fetch_payload.py` emprunte — la construction mourait en
    `ModuleNotFoundError: retro._identite`, alors que `--no-build-isolation`
    passait. Mesuré le 2026-08-29 en fabriquant le wheelhouse de la console.
    """
    copie = _copie_du_depot(tmp_path)
    _appeler_hook(copie, "get_requires_for_build_wheel")
    assert (copie / "retro" / "_identite.py").is_file(), (
        "le premier hook n'a pas gravé l'identité : setuptools lira une "
        "version dynamique dont le module n'existe pas")


def test_les_trois_get_requires_gravent(tmp_path):
    """La même omission sur l'un des trois suffirait : sdist et editable
    passent par leur propre hook, et l'oubli ne se verrait qu'à l'usage."""
    for hook in ("get_requires_for_build_wheel", "get_requires_for_build_sdist",
                 "get_requires_for_build_editable"):
        copie = _copie_du_depot(tmp_path / hook)
        _appeler_hook(copie, hook)
        assert (copie / "retro" / "_identite.py").is_file(), hook
