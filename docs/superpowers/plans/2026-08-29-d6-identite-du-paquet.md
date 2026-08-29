# Identité du paquet (dette D6) — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — `superpowers:subagent-driven-development`
> ou `superpowers:executing-plans`. Les étapes sont des cases à cocher.

**Objectif :** qu'une roue construite ici porte une version qui BOUGE, que la
console dise laquelle elle exécute, et que l'hôte REFUSE de synchroniser quand
les deux ne sont pas la même.

**Dette :** `docs/dettes.md`, section « D6 — La console tourne sur un paquet
périmé, et absolument rien ne le dit ».

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`

---

## Pourquoi celle-ci avant les autres

D6 n'est pas une dette parmi neuf : **c'est un multiplicateur de coût sur les
huit autres.** Un correctif écrit ici, testé ici, commité ici peut rester sans
le moindre effet sur la machine — et l'erreur qu'on obtient alors décrit le
symptôme d'origine, exactement comme si le correctif était faux. On rouvre
l'enquête sur un profil qui est déjà juste, on « re-corrige » du code qui n'a
jamais tourné, et rien dans aucun rapport ne dit que le paquet installé date.

Tant que D6 tient, chaque heure passée sur D1, D3, D7 ou n'importe quelle autre
peut être annulée en silence par une installation qui n'a pas suivi.

---

## Ce qui est MESURÉ, ce qui est SUPPOSÉ

**Mesuré ici, le 2026-08-29 :**

- `pip install --no-index --find-links <roues> --upgrade retro` sur une version
  **identique** ne réinstalle rien. Sortie littérale, dans un venv neuf, à
  partir de `dist/retro-0.1.0-py3-none-any.whl` :
  `Requirement already satisfied: retro in ./v/lib/python3.13/site-packages (0.1.0)`.
  C'est la ligne exacte que `32-retro.ps1` exécute (`installer`,
  `console/guest/provision/32-retro.ps1`). **Conséquence, et elle précise
  l'énoncé de la dette : le défaut n'est pas seulement qu'on ne peut pas
  comparer les versions — c'est que l'installation elle-même ne se fait
  JAMAIS tant que la version ne bouge pas.** Reprovisionner la console
  n'aurait rien changé. Une version qui bouge n'est donc pas seulement le
  moyen de diagnostiquer D6 : c'est le seul moyen de la réparer.
- Le témoin durable vit sur la console en `D:\state\retro.status`. Il est écrit
  par `Write-RetroStatus` (`installer`,
  `console/guest/provision/assets/retro-status.ps1`), qui inscrit son propre
  contrat en tête du fichier produit, et **réécrit** par l'hôte
  (`installer`, `console/guest/retro_sync.py`, `format_witness`). Ses clés,
  dans cet ordre : `run=`, `status=`, `when=`, `emulation_root=`, puis
  `report:` et le rapport brut.
- La roue livrée à la console est construite sur l'HÔTE par
  `installer`, `console/guest/fetch_payload.py::build_retro_wheels`, avec
  `pip wheel --no-deps` sur `packages/retro`, et déposée dans
  `<workdir>/payload/retro/wheels/`. Le workdir par défaut est
  `/var/lib/nivuus/guest` (`console/guest_steps.py::DEFAULT_GUEST_WORKDIR`), et
  `drivers_dir` y vaut `<workdir>/payload`. **La référence que l'hôte peut
  opposer à la console existe donc déjà sur son disque :
  `/var/lib/nivuus/guest/payload/retro/wheels/retro-*.whl`.**
- La charge utile ne survit PAS sur la console : elle voyage sur l'ISO de
  réponses, que `guest-ready-watch.py` détache une fois le provisionnement
  fini. L'invité ne peut donc pas se comparer tout seul — **c'est bien l'hôte
  qui doit constater**, ce que dit déjà la dette.
- `.git` de ce dépôt : `HEAD` contient `ref: refs/heads/main`, et
  `refs/heads/main` est une référence libre.

**Supposé, à confirmer par les étapes de mesure des tâches 1 et 6 :**

- que `pip wheel <dossier>` construit *dans l'arbre* (donc que `.git` est
  visible pendant la construction). C'est le comportement documenté de pip
  depuis 21.3 ; le plan n'en dépend pas — l'horodatage, lui, ne demande aucun
  dépôt, et c'est lui qui porte la garantie.
- que le partage `G:` de la console correspond à `/media/data/Console` sur
  l'hôte (lu dans la spec, jamais mesuré ici) ;
- l'état exact du paquet actuellement installé sur la console. La roue a été
  reconstruite et réinstallée à la main le 2026-08-29 ; **rien ne le repose**,
  et aucune étape de ce plan ne suppose que cette réinstallation tienne encore.

---

## Contraintes globales

- **Python 3.11 minimum.** Aucun test ne touche le réseau, aucun n'exige
  Windows.
- **Un test qui passe quelle que soit l'implémentation est un défaut.** Chaque
  tâche dit contre quoi le test doit d'abord échouer, et avec quel message.
- **Aucune dépendance nouvelle.** `setuptools-scm` est explicitement écarté
  (voir tâche 1).
- Vérifie les mutations avec `PYTHONDONTWRITEBYTECODE=1`.
- Les tâches 4 et 5 vivent dans le **dépôt voisin `nivuus/installer`**. Elles
  sont décrites ici parce que la moitié utile de D6 s'y joue ; elles ne se
  commitent pas dans `packages/retro`.
- **La console Windows n'est pas accessible depuis la session qui écrit ce
  plan.** Tout ce qui exige la machine est la tâche 6, et rien d'autre.

---

## Tâche 1 : une version qui bouge, gravée à la construction

**La question tranchée, et sa raison.** L'identité est calculée **à la
construction de la roue**, jamais à l'exécution. À l'exécution il faudrait
`git` — que la console n'a pas — et un dépôt — que la console n'a pas non
plus : `C:\Python\Lib\site-packages\retro` est un arbre de fichiers, rien
d'autre. Une identité calculée à l'exécution y rendrait « inconnue » sur la
seule machine où la question se pose. Gravée dans la roue, elle survit à une
installation sans dépôt parce qu'elle voyage DANS le paquet.

**Et elle est calculée par le backend de construction du paquet, pas par
l'appelant.** Le geste qui a produit la panne du 2026-08-29 est une roue
reconstruite À LA MAIN ; si la gravure vivait dans `fetch_payload.py`, cette
roue-là n'aurait porté aucune identité. Un mécanisme qu'on peut oublier est
exactement le mécanisme qui a manqué.

Trois écartés, avec leur raison :

- **relever `version = "0.1.0"` à la main** : c'est la discipline qui a déjà
  échoué — neuf profils d'un côté, dix de l'autre, le même numéro des deux ;
- **`setuptools-scm`** : une dépendance de construction de plus, qui exige un
  dépôt git à la construction et échoue sur un arbre exporté ;
- **une empreinte de contenu seule** (`0.1.0+<sha du contenu>`) : les segments
  locaux PEP 440 se comparent alphabétiquement, donc deux constructions
  successives peuvent se classer à l'envers et `pip --upgrade` refuserait de
  « rétrograder ». L'horodatage passe donc EN PREMIER dans le segment local :
  numérique, il se compare numériquement, et la version croît toujours.

**L'horodatage n'est pas l'heure courante** : c'est la mtime la plus récente
des fichiers embarqués. Raison mesurable : pip appelle chaque hook PEP 517
dans un **processus séparé** (`prepare_metadata_for_build_wheel` puis
`build_wheel`), donc une horloge lue deux fois donnerait deux versions
différentes et pip refuserait la roue pour incohérence de métadonnée. Une
fonction déterministe de l'arbre donne la même valeur aux deux appels.

**Fichiers :**
- Créer : `outils/identite_build.py`, `retro/identite.py`,
  `tests/test_identite.py`
- Modifier : `pyproject.toml`, `.gitignore`
- Généré, jamais versionné : `retro/_identite.py`

**Ce qu'il faut obtenir :**

`outils/identite_build.py` — un backend PEP 517 en arbre qui grave puis
délègue à `setuptools.build_meta` :

```python
"""Backend de construction : grave l'identité de la roue avant de déléguer.

Il existe parce qu'une identité qu'on peut oublier de calculer est exactement
celle qui manquait le 2026-08-29 : la roue avait été reconstruite à la main.
Ici, toute construction la porte — `pip wheel`, `python -m build`, un pip
install éditable, ou la main.
"""
from __future__ import annotations

import hashlib
import pathlib
import time

from setuptools import build_meta as _setuptools

BASE = "0.1.0"
GENERE = pathlib.Path("retro") / "_identite.py"
# Ce qui part dans la roue, et rien d'autre : les tests et la documentation
# changent sans que le code installé change, et une version qui bougerait pour
# eux ferait réinstaller la console pour rien.
SOURCES = ("retro", "pyproject.toml")
# `_identite.py` est exclu des DEUX calculs, sans quoi graver changerait la
# valeur qu'on vient de graver et deux appels ne s'accorderaient jamais.
IGNORES = ("__pycache__", "_identite.py")


def fichiers(racine: pathlib.Path) -> list[pathlib.Path]:
    trouves = []
    for nom in SOURCES:
        chemin = racine / nom
        if chemin.is_file():
            trouves.append(chemin)
            continue
        for f in chemin.rglob("*"):
            if f.is_file() and not any(p in IGNORES for p in f.parts):
                trouves.append(f)
    return sorted(trouves)


def horodatage(racine: pathlib.Path) -> str:
    """La mtime la plus récente des fichiers embarqués, en UTC.

    Pas l'heure courante : pip appelle chaque hook PEP 517 dans un processus
    séparé, et deux lectures d'horloge donneraient deux versions que pip
    rejetterait pour incohérence de métadonnée.
    """
    recente = max((f.stat().st_mtime for f in fichiers(racine)), default=0.0)
    return time.strftime("%Y%m%d%H%M%S", time.gmtime(int(recente)))


def empreinte(racine: pathlib.Path) -> str:
    """Ce que la roue contient, en huit caractères. Diagnostic seul : deux
    constructions d'un contenu identique se reconnaissent d'un coup d'œil."""
    h = hashlib.sha256()
    for f in fichiers(racine):
        h.update(f.relative_to(racine).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:8]


def revision(racine: pathlib.Path) -> str:
    """Le SHA court, LU DANS .git, sans le binaire git.

    Un CONFORT, jamais la garantie : un arbre modifié sans commit garde le
    même SHA, et c'est l'horodatage qui fait bouger la version. Lu à la main
    parce que la construction peut tourner là où git n'est pas installé, et
    parce qu'un arbre de travail lié (git worktree) porte un `.git` FICHIER —
    c'est le cas de l'agent qui exécutera ce plan.
    """
    try:
        point = racine / ".git"
        if point.is_file():
            texte = point.read_text(encoding="utf-8").strip()
            if not texte.startswith("gitdir:"):
                return ""
            point = pathlib.Path(texte.split(":", 1)[1].strip())
            if not point.is_absolute():
                point = (racine / point).resolve()
        if not point.is_dir():
            return ""
        tete = (point / "HEAD").read_text(encoding="utf-8").strip()
        if not tete.startswith("ref:"):
            return tete[:7]
        ref = tete.split(":", 1)[1].strip()
        bases = [point]
        commun = point / "commondir"
        if commun.is_file():
            bases.append((point / commun.read_text(encoding="utf-8").strip()).resolve())
        for base in bases:
            libre = base / ref
            if libre.is_file():
                return libre.read_text(encoding="utf-8").strip()[:7]
            paquet = base / "packed-refs"
            if paquet.is_file():
                for ligne in paquet.read_text(encoding="utf-8").splitlines():
                    if ligne.startswith(("#", "^")):
                        continue
                    sha, _, nom = ligne.partition(" ")
                    if nom.strip() == ref:
                        return sha[:7]
    except OSError:
        return ""
    return ""


def version(racine: pathlib.Path) -> str:
    """« 0.1.0+20260829143512.a1b2c3d4.g9f8e7d6 ».

    L'horodatage EN PREMIER : les segments locaux PEP 440 se comparent
    segment par segment, un segment numérique numériquement. Mis ailleurs, une
    construction plus récente pourrait se classer AVANT une plus ancienne et
    `pip --upgrade` refuserait de l'installer.
    """
    parties = [horodatage(racine), empreinte(racine)]
    sha = revision(racine)
    if sha:
        parties.append("g" + sha)
    return f"{BASE}+{'.'.join(parties)}"


def graver(racine: pathlib.Path) -> str:
    v = version(racine)
    (racine / GENERE).write_text(
        '"""Écrit à la construction par outils/identite_build.py.\n\n'
        'NE PAS ÉDITER, NE PAS VERSIONNER : sa valeur décrit UNE roue.\n'
        '"""\n'
        f'VERSION = "{v}"\n', encoding="utf-8")
    return v


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    graver(pathlib.Path.cwd())
    return _setuptools.build_wheel(wheel_directory, config_settings,
                                   metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    graver(pathlib.Path.cwd())
    return _setuptools.build_sdist(sdist_directory, config_settings)


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    graver(pathlib.Path.cwd())
    return _setuptools.prepare_metadata_for_build_wheel(
        metadata_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    graver(pathlib.Path.cwd())
    return _setuptools.build_editable(wheel_directory, config_settings,
                                      metadata_directory)


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    graver(pathlib.Path.cwd())
    return _setuptools.prepare_metadata_for_build_editable(
        metadata_directory, config_settings)


get_requires_for_build_wheel = _setuptools.get_requires_for_build_wheel
get_requires_for_build_sdist = _setuptools.get_requires_for_build_sdist
get_requires_for_build_editable = _setuptools.get_requires_for_build_editable
```

`retro/identite.py` — ce que le paquet INSTALLÉ sait de lui-même :

```python
"""Quelle construction du paquet tourne réellement ici.

Le paquet ne peut pas répondre en interrogeant un dépôt : sur la console il
n'y en a pas, et git n'y est pas installé. La réponse est donc GRAVÉE dans la
roue à la construction (outils/identite_build.py) et simplement relue ici.

Un arbre source jamais construit le dit, plutôt que d'inventer : c'est le cas
normal de l'hôte, qui lance ce paquet depuis son dépôt.
"""
from __future__ import annotations

import importlib

BASE = "0.1.0"
SOURCE = f"{BASE}+source"


def _lire(importer=importlib.import_module) -> str:
    try:
        return importer("retro._identite").VERSION
    except ImportError:
        return SOURCE


VERSION = _lire()


def lisible(version: str = "") -> str:
    """La version, dite à quelqu'un qui la lit depuis son canapé."""
    v = version or VERSION
    _, _, local = v.partition("+")
    if not local or local == "source":
        return f"{v} — arbre source, jamais construit en roue"
    morceaux = local.split(".")
    h = morceaux[0]
    quand = (f"{h[0:4]}-{h[4:6]}-{h[6:8]} à {h[8:10]}:{h[10:12]} UTC"
             if len(h) == 14 and h.isdigit() else h)
    rev = next((m[1:] for m in morceaux[1:] if m.startswith("g")), "")
    return (f"{v} — construit le {quand}, "
            + (f"révision {rev}" if rev else "révision inconnue"))
```

`pyproject.toml` :

```toml
[project]
name = "retro"
dynamic = ["version"]
# ... le reste inchangé, la ligne `version = "0.1.0"` est RETIRÉE

[build-system]
requires = ["setuptools>=68"]
build-backend = "identite_build"
backend-path = ["outils"]

[tool.setuptools.dynamic]
version = { attr = "retro.identite.VERSION" }
```

`.gitignore` : ajouter `retro/_identite.py`, avec le commentaire qui dit
pourquoi (« gravé à la construction, décrit UNE roue »).

**Étapes :**

- [ ] **1.** Écrire `tests/test_identite.py` (contenu ci-dessous), le lancer,
      constater l'échec : `ModuleNotFoundError: No module named 'identite_build'`.
- [ ] **2.** Écrire `outils/identite_build.py` et `retro/identite.py`, relancer
      jusqu'au vert.
- [ ] **3.** Modifier `pyproject.toml` et `.gitignore`.
- [ ] **4.** **Mesure** — construire une roue réelle, hors dépôt, sans réseau :
      ```bash
      python -m pip wheel --no-index --no-deps --no-build-isolation \
          -w /tmp/roues .
      python - <<'PY'
      import glob, zipfile, re
      w = glob.glob("/tmp/roues/retro-*.whl")[0]
      print("fichier :", w)
      z = zipfile.ZipFile(w)
      m = [n for n in z.namelist() if n.endswith(".dist-info/METADATA")][0]
      print([l for l in z.read(m).decode().splitlines() if l.startswith("Version:")])
      print([n for n in z.namelist() if n.endswith("_identite.py")])
      PY
      ```
      **Attendu :** la version porte un segment local
      `+<14 chiffres>.<8 hexa>[.g<7 hexa>]`, `_identite.py` est DANS la roue,
      et la version de la métadonnée est celle du module. Noter la version
      obtenue dans le rapport de tâche : elle sert de repère à la tâche 6.
- [ ] **5.** Commit.

**Les tests, et ce contre quoi ils doivent d'abord échouer :**

```python
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
```

Le dernier test exige `pip` et `setuptools` dans l'environnement, et **il doit
échouer sans eux plutôt que se sauter** : le backend fait partie du contrat du
paquet. Aucun de ces tests ne touche le réseau (`--no-index`,
`--no-build-isolation`).

---

## Tâche 2 : `retro identite`

**Fichiers :**
- Modifier : `retro/cli.py`
- Test : `tests/test_cli.py`

**Ce qu'il faut obtenir :**

- une sous-commande `identite` qui écrit **exactement une ligne** sur la sortie
  standard : la version, rien d'autre, et rend 0. Une seule ligne parce que
  c'est l'hôte qui la lira à travers WinRM ; une deuxième ligne « pour le
  confort » est un piège d'analyse qu'on paierait une fois, tard ;
- aucune option, aucun argument requis : elle doit pouvoir se lancer sur une
  machine où rien n'est monté, rien n'est installé, rien n'est configuré.

```python
def _cmd_identite(args) -> int:
    """Quelle construction du paquet tourne ICI.

    Une ligne, la version seule : c'est l'hôte qui la lit, à travers WinRM,
    pour la comparer à la roue qu'il a livrée. La prose est dans `status`.
    """
    print(identite.VERSION)
    return 0
```

**Une conséquence à écrire dans le code**, parce qu'elle sera vraie le jour de
la mise en service : sur la console d'aujourd'hui, `retro identite` n'existe
pas et argparse rend 2. **Ce n'est pas une panne, c'est le premier constat** —
un paquet antérieur à l'identité. La tâche 4 le traite comme un écart.

**Étapes :**

- [ ] **1.** Écrire le test, constater l'échec (argparse : `invalid choice: 'identite'`).
      ```python
      def test_identite_rend_une_seule_ligne(capsys):
          from retro import identite as identite_mod
          assert cli.main(["identite"]) == 0
          lignes = capsys.readouterr().out.splitlines()
          assert lignes == [identite_mod.VERSION]
      ```
- [ ] **2.** Ajouter le sous-analyseur et `_cmd_identite`, relancer.
- [ ] **3.** Commit.

---

## Tâche 3 : l'identité dans ce qui se lit

**Fichiers :**
- Modifier : `retro/status.py`, `retro/cli.py`
- Test : `tests/test_status.py`, `tests/test_cli.py`

**Ce qu'il faut obtenir :**

- `Report` porte un champ `paquet: str = ""` ; `build_report` prend
  `paquet: str = ""` ; `format_report` rend une section **inconditionnelle**
  `Paquet`, comme BIOS, Rendu, Amorçage et Manettes — une section qui
  disparaît se lit comme une panne d'affichage, et c'est déjà la règle du
  fichier. Son contenu est `identite.lisible(report.paquet)`, et son repli
  (`_section(..., vide=...)`) dit « identité inconnue : ce rapport ne peut pas
  dire quelle construction l'a produit » ;
- `_cmd_status` passe `paquet=identite.VERSION` ;
- **une identité `+source` n'est PAS un problème** et ne va donc pas dans la
  section « Problèmes ». Lancer le paquet depuis son arbre source est le cas
  normal de l'hôte ; en faire une accusation apprendrait au lecteur à ignorer
  la section. Le rapport le CONSTATE, il ne le reproche pas. `status` n'a
  d'ailleurs aucune référence à opposer : il ne peut pas savoir quelle
  identité *devrait* être là — c'est le travail de la tâche 4 ;
- `_cmd_scan` écrit `paquet : <version>` en **première** ligne de sa sortie.
  Première, parce que c'est la commande dont deux exécutions ont rendu deux
  résultats différents le 2026-08-29 : quiconque compare deux scans doit voir
  d'un coup d'œil qu'ils ne viennent pas du même paquet.

**Ce qui n'est PAS fait, et pourquoi :** le format de l'inventaire JSON n'est
pas touché. Y ajouter l'identité obligerait à en faire un objet là où c'est une
liste, donc à changer `_load_inventory` — le seul fichier sur lequel `scan` et
`sync` s'accordent. Une chaîne de diagnostic ne vaut pas ce risque, et la ligne
imprimée plus le témoin de la tâche 4 portent déjà l'information.

**Étapes :**

- [ ] **1.** Écrire les tests, constater les échecs.
      ```python
      def test_le_rapport_nomme_le_paquet():
          texte = status.format_report(status.build_report(
              install_dirs={}, emulation_root=pathlib.Path("."), systems=[],
              bios_status=[], bios_root=pathlib.Path("/BIOS"),
              paquet="0.1.0+20260829143512.a1b2c3d4.g9f8e7d6"))
          assert "Paquet" in texte
          assert "20260829143512" in texte
          assert "2026-08-29" in texte and "9f8e7d6" in texte

      def test_la_section_paquet_est_inconditionnelle():
          texte = status.format_report(status.build_report(
              install_dirs={}, emulation_root=pathlib.Path("."), systems=[],
              bios_status=[], bios_root=pathlib.Path("/BIOS")))
          assert "Paquet" in texte

      def test_un_arbre_source_n_est_pas_un_probleme():
          r = status.build_report(
              install_dirs={}, emulation_root=pathlib.Path("."), systems=[],
              bios_status=[], bios_root=pathlib.Path("/BIOS"),
              paquet="0.1.0+source")
          assert not any("paquet" in p.what.lower() for p in r.problems)
      ```
      et, pour `scan` (`tests/test_cli.py`, sur le modèle des scans déjà testés
      là-bas) : la première ligne de la sortie commence par `paquet : `.
- [ ] **2.** Implémenter, relancer.
- [ ] **3.** Suite complète (`python -m pytest -W error`), commit.

---

## Tâche 4 : le témoin porte l'identité, et l'hôte REFUSE l'écart

> **Dépôt voisin `nivuus/installer`.** Rien de cette tâche ne se commite dans
> `packages/retro`.

**La question tranchée, et sa raison. L'hôte REFUSE, il ne se contente pas de
signaler.** Les deux coûtent, et voici lequel on paie :

- *signaler* coûte une ligne de plus dans un rapport, et rien d'autre. C'est
  précisément la situation d'aujourd'hui poussée d'un cran : l'information
  existe, personne ne la lit, la bibliothèque Steam se remplit quand même
  d'entrées produites par le mauvais code — des systèmes absents, des chemins
  d'exécutables tirés d'un manifeste périmé — et c'est le propriétaire qui le
  découvre depuis son canapé. **D6 existe parce que rien n'a arrêté personne.**
  Un message qu'on peut ignorer reproduit le défaut à un cran de distance.
- *refuser* coûte une console qui ne se synchronise plus tant que le paquet
  n'est pas remis à jour. C'est un coût réel, et c'est celui qu'on accepte :
  `retro_sync.py` refuse déjà pour six motifs, sa règle écrite est « fermé par
  défaut — un témoin qu'on ne sait pas lire ne prouve rien, et une
  bibliothèque d'entrées mortes est pire qu'une bibliothèque absente ». Une
  identité en écart tombe exactement dans cette phrase. Et la tâche 5 donne au
  refus un remède d'une commande, ce qui est la condition pour que refuser
  reste tenable.

**Absence de référence n'est PAS un écart.** Si l'hôte ne trouve aucune roue à
opposer, il le DIT et laisse passer : refuser là punirait une machine dont on
ne sait rien, et ce n'est pas la même faute.

**Fichiers (dans `nivuus/installer`) :**
- Modifier : `console/guest/provision/assets/retro-status.ps1`,
  `console/guest/provision/32-retro.ps1`, `console/guest/retro_sync.py`
- Test : `console/tests/test_windows_guest_retro_sync.py`,
  `console/tests/test_windows_guest_provision.py`

**Ce qu'il faut obtenir :**

1. **Le témoin gagne une clé `package=`**, entre `emulation_root=` et
   `report:`. Les DEUX écrivains doivent s'accorder sur cet ordre :
   `Write-RetroStatus` (PowerShell) et `format_witness` (Python). Le contrat en
   tête du fichier produit (`$RetroStatusHeader`) gagne les lignes qui
   l'expliquent — c'est là que vit le contrat, pas dans une prose ailleurs :
   ```
   # package= identifie la CONSTRUCTION du paquet retro installee sur cette
   # console. Deux roues peuvent porter le meme 0.1.0 et ne pas contenir le
   # meme code : seule cette valeur les distingue. « inconnue » veut dire que
   # le paquet installe est anterieur a « retro identite ».
   ```
2. **`32-retro.ps1`** garde une variable `$RetroPackage = 'inconnue'`, la met à
   jour juste après le `pip install` réussi
   (`& $retroExe identite`, exit 0 → la première ligne ; sinon `'inconnue'`) et
   la passe à chaque `Write-RetroStatus`. Le `Write-RetroStatus 'started'` du
   début écrit forcément `inconnue` : à ce moment-là Python n'est pas encore
   installé, et prétendre autre chose serait un mensonge daté.
3. **`retro_sync.py`** gagne quatre choses pures, donc testables sans Windows :

```python
# console/guest_steps.py::DEFAULT_GUEST_WORKDIR + fetch_payload.py :
# drivers_dir = <workdir>/payload, puis retro/wheels.
WHEELHOUSE = Path("/var/lib/nivuus/guest/payload/retro/wheels")


def identite_roue(wheelhouse: Path) -> str | None:
    """La version de la roue que l'hôte a livrée, ou None s'il n'en a aucune.

    Lue dans la METADATA de la roue, pas dans son nom de fichier : le nom
    échappe le « + » du segment local en « _ », et reconstituer une version à
    l'envers est le genre de devinette qui se trompe en silence.
    """
    try:
        roues = sorted(wheelhouse.glob("retro-*.whl"))
    except OSError:
        return None
    if len(roues) != 1:
        return None          # zéro : pas de référence. Plusieurs : ambiguïté.
    with zipfile.ZipFile(roues[0]) as z:
        nom = next((n for n in z.namelist()
                    if n.endswith(".dist-info/METADATA")), None)
        if nom is None:
            return None
        for ligne in z.read(nom).decode("utf-8", "replace").splitlines():
            if ligne.startswith("Version: "):
                return ligne.split(": ", 1)[1].strip()
    return None


def identite_invitee(guest) -> str | None:
    """Ce que la console dit exécuter, ou None si elle ne sait pas le dire.

    Un code non nul n'est PAS une panne à remonter : sur un paquet antérieur à
    D6 la sous-commande n'existe pas, argparse rend 2, et c'est justement le
    constat qu'on cherche.
    """
    code, rapport = guest.retro(["identite"])
    if code != 0:
        return None
    lignes = [l.strip() for l in rapport.splitlines() if l.strip()]
    return lignes[0] if lignes else None


def ecart_identite(invitee: str | None, attendue: str | None) -> str | None:
    """Le motif de refus, ou None quand il n'y a rien à reprocher."""
    if attendue is None:
        return None          # pas de référence : ce n'est pas un écart.
    if invitee is None:
        return ("la console ne sait pas dire quelle construction du paquet "
                "elle exécute (« retro identite » n'y existe pas) : son paquet "
                f"est ANTÉRIEUR à celui que cet hôte a livré ({attendue}). "
                "Tout ce qu'un correctif récent a changé y est absent, et le "
                "scan produirait un inventaire par du code périmé. Réinstaller "
                "le paquet : relancer ce script avec --reinstaller-le-paquet.")
    if invitee != attendue:
        return (f"la console exécute le paquet {invitee} alors que cet hôte a "
                f"livré {attendue} : ce n'est pas le même code. Un inventaire "
                "produit là-bas ne décrit pas ce que ce dépôt contient, et "
                "l'écart ne se verrait nulle part ailleurs — les deux roues "
                "peuvent porter le même 0.1.0. Réinstaller le paquet : "
                "relancer ce script avec --reinstaller-le-paquet.")
    return None
```

4. Le branchement dans `synchronise`, **juste après** la garde
   `guest.exists(cfg.retro_exe)` et **avant** le premier téléchargement : le
   script se dit à lui-même, pour les sessions de streaming, qu'« un refus qui
   arrive après dix minutes d'installation est un refus qui arrive trop tard ».
   La même phrase vaut ici. Nouveau code de sortie **8**, et la ligne de codes
   de la docstring du module est complétée. Quand `identite_roue` rend `None`,
   un avertissement sur `stderr` nomme `--wheelhouse` et dit qu'aucun écart ne
   peut être constaté — se taire ferait croire à une vérification qui n'a pas
   eu lieu. La valeur lue est passée à `refresh_witness`, qui l'écrit dans
   `package=`.
5. Nouvelle option `--wheelhouse` (défaut `WHEELHOUSE`).

**Étapes :**

- [ ] **1.** Écrire les tests dans `console/tests/test_windows_guest_retro_sync.py` :
      une roue factice construite à la volée avec `zipfile` (une seule entrée
      `retro-<v>.dist-info/METADATA` contenant `Version: …`) pour
      `identite_roue` ; les quatre cas de `ecart_identite` (pas de référence,
      invitée absente, écart, égalité) ; un faux `Guest` dont `retro()` rend
      `(2, "usage: retro ...")` pour `identite_invitee`. Épingler aussi, dans
      `test_windows_guest_provision.py`, que `32-retro.ps1` appelle
      `identite` et que `retro-status.ps1` écrit `package=` — sur le modèle des
      épinglages déjà présents dans ces fichiers.
- [ ] **2.** Les constater rouges.
- [ ] **3.** Implémenter les trois fichiers, relancer :
      `cd installer/console && make test`.
- [ ] **4.** Commit **dans `nivuus/installer`**.

---

## Tâche 5 : le remède, en une commande

> **Dépôt voisin `nivuus/installer`.**

Un refus sans remède transforme D6 en console inutilisable : aujourd'hui, la
seule façon de remettre le paquet à jour est de reconstruire la charge utile,
l'ISO de réponses, et de reprovisionner — pour remplacer 100 ko de Python. Ce
n'est pas un remède, c'est une menace.

**Fichiers (dans `nivuus/installer`) :**
- Modifier : `console/guest/retro_sync.py`
- Test : `console/tests/test_windows_guest_retro_sync.py`

**Ce qu'il faut obtenir :**

- une option `--reinstaller-le-paquet` qui, avant toute la séquence :
  1. copie le contenu de `--wheelhouse` (hôte) vers le **partage déjà monté**
     `--partage-roues` (défaut `/media/data/Console/retro/wheels`, que la
     console voit en `G:\retro\wheels`) — le partage `Console` → `G:` existe
     depuis le provisionnement, et le manifeste du propriétaire y vit déjà en
     `G:\retro\emulators.toml` ; c'est le seul canal capable de porter une
     roue, `Guest.write_text` encodant tout en base64 DANS une ligne de
     commande bornée à 32 767 caractères ;
  2. lance dans l'invité
     `pip install --no-index --find-links G:\retro\wheels --upgrade retro` ;
  3. relit `retro identite` et **refuse (8) si l'écart persiste** : une
     réinstallation qu'on croit faite est exactement le défaut d'origine ;
- **jamais automatique.** Remplacer le paquet est un geste ; le faire en
  passant, à chaque synchronisation, mettrait une console de salon à la merci
  de l'état de l'arbre de l'hôte.

**Ce qui rend ce remède possible et ne l'était pas :** la tâche 1. Avec deux
roues numérotées `0.1.0`, le `pip install --upgrade` ci-dessus est un no-op —
mesuré, ligne pour ligne, en tête de ce plan.

**Étapes :**

- [ ] **1.** Test : un faux `Guest` et un faux partage sous `tmp_path` ; la roue
      est copiée, la commande pip est bien celle attendue, et une identité
      restée en écart après la réinstallation rend 8.
- [ ] **2.** Le constater rouge, implémenter, relancer `make test`.
- [ ] **3.** Commit **dans `nivuus/installer`**.

---

## Tâche 6 : mesure sur la console

**La console Windows n'est pas accessible depuis la session qui a écrit ce
plan. Cette tâche est la seule qui l'exige, et elle ne se simule pas.**

Prérequis : les tâches 1 à 5 commitées, l'hôte porte une charge utile dont la
roue a été reconstruite (`python3 console/guest/fetch_payload.py --retro
--drivers-dir /var/lib/nivuus/guest/payload`), la console est allumée et
personne ne joue.

- [ ] **1. Ce que la console exécute AUJOURD'HUI**, avant tout geste :
      ```bash
      cd installer/console/guest
      python3 winrm_exec.py cmd "C:\Python\Scripts\retro.exe identite"
      python3 winrm_exec.py cmd "type D:\state\retro.status"
      python3 winrm_exec.py cmd "dir /b C:\Python\Lib\site-packages\retro\data\profiles"
      ```
      **Attendu, et c'est l'hypothèse à vérifier :** la première commande
      échoue (le paquet est antérieur à `identite`), le témoin n'a pas de clé
      `package=`, et la liste des profils est celle de la roue réinstallée à la
      main le 2026-08-29. **Consigner les trois sorties** : c'est l'état de
      départ, et il n'est reposé nulle part.
- [ ] **2. Le refus** — lancer la synchronisation sans rien réparer :
      ```bash
      python3 console/guest/retro_sync.py
      ```
      **Attendu :** code 8, message nommant la version livrée par l'hôte, et
      **rien d'écrit** : ni Steam arrêté, ni sentinelle posée, ni inventaire.
      Vérifier ce dernier point (`dir C:\nivuus\state\retro-inventory.json`,
      horodatage inchangé) — un refus qui aurait déjà agi ne serait pas un
      refus.
- [ ] **3. Le remède** :
      ```bash
      python3 console/guest/retro_sync.py --reinstaller-le-paquet
      ```
      **Attendu :** pip rapporte une installation RÉELLE (« Successfully
      installed retro-0.1.0+… »), pas un « Requirement already satisfied » —
      c'est l'assertion centrale de tout ce plan, et la seule qui ne peut se
      mesurer que là. Puis la séquence habituelle va jusqu'au bout.
- [ ] **4. Ce que le témoin dit ensuite** :
      ```bash
      python3 winrm_exec.py cmd "type D:\state\retro.status"
      ```
      **Attendu :** `package=` porte la même version que
      `identite_roue(/var/lib/nivuus/guest/payload/retro/wheels)` sur l'hôte.
- [ ] **5. Le rapport** :
      ```bash
      python3 winrm_exec.py cmd "C:\Python\Scripts\retro.exe status --roms G:\ROMs --bios G:\BIOS"
      ```
      **Attendu :** une section `Paquet` portant la date de construction et la
      révision.
- [ ] **6. Le second passage** : relancer `retro_sync.py` sans option. Aucun
      écart, aucun refus. Si le second passage refusait, l'identité ne
      survivrait pas à sa propre écriture — le défaut le plus probable de tout
      ce mécanisme.
- [ ] **7.** Consigner les six résultats dans le rapport de tâche, en
      distinguant ce qui a été VU de ce qui a été déduit.

---

## Vérification finale

- [ ] Suite complète de `packages/retro`, arbre frais, sous `-W error`,
      `PYTHONDONTWRITEBYTECODE=1`
- [ ] `cd installer/console && make test` au vert
- [ ] Aucun test ne touche le réseau ; aucun n'exige Windows
- [ ] `git status` ne montre pas `retro/_identite.py` (il est ignoré)
- [ ] `pip install -e .` fonctionne encore depuis un arbre nu — c'est ainsi que
      l'hôte lance ce paquet
- [ ] La tâche 6 est faite, ses six sorties consignées
- [ ] `docs/dettes.md` n'a pas été touché par ce plan : **la clôture de D6 s'y
      écrit après la tâche 6, dans un geste à part, et par quelqu'un qui a les
      mesures sous les yeux**

---

## Ce que ce plan ne fait pas

- **Il ne relève pas `0.1.0`.** La version publique du paquet reste ce qu'elle
  est ; seul le segment local bouge. Décider d'un `0.2.0` est une question de
  publication, pas d'identité.
- **Il ne détecte pas un arbre modifié sans commit.** Le SHA gravé est celui
  du dernier commit ; l'horodatage, lui, bouge. Une roue peut donc annoncer une
  révision dont son contenu diffère — l'empreinte de contenu (`.a1b2c3d4`) est
  là pour ça, mais rien ne dit « modifié ».
- **Il ne vérifie pas l'identité des ÉMULATEURS.** Le témoin `.retro-version`
  par émulateur existe déjà et n'est pas touché ; le paquet et les émulateurs
  sont deux périmés distincts.
- **Il ne fait pas de `retro status` un juge.** `status` dit quelle
  construction l'a produit ; il n'a aucune référence à opposer et ne prétend
  pas en avoir. Le seul endroit qui REFUSE est `retro_sync.py`, côté hôte.
- **Il ne réinstalle rien tout seul.** `--reinstaller-le-paquet` est explicite,
  et le reste, quand l'écart persiste, c'est un refus.
- **Il ne change pas le format de l'inventaire JSON**, ni le contrat de
  `retro sync`.
- **Il ne touche pas au provisionnement complet.** Reconstruire l'ISO de
  réponses reste le chemin normal ; la tâche 5 n'est qu'une réparation à chaud.
- **Il ne clôt aucune autre dette.** Il rend seulement possible de savoir que
  les autres correctifs sont bien arrivés sur la machine.
