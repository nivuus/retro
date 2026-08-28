# Amorçage des émulateurs — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE —
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans`. Les étapes se cochent (`- [ ]`).

**Objectif :** un émulateur que `retro install` vient de poser lance un jeu, et
non son assistant de première configuration.

**Architecture :** le profil déclare un bloc `[bootstrap]` (une cible en chemin
Windows, un contenu) ; `retro scan` dépose le contenu dans
`_launcher\systems\` et trois lignes dans chaque plan du profil ; le lanceur
pose le fichier **si et seulement si la cible est absente**, puis inscrit ce
qu'il a posé dans un témoin que `retro status` sait lire. Aucune décision n'est
prise en C# : le lanceur exécute une consigne calculée en Python.

**Pile :** Python 3.11 (stdlib seule, `tomllib`), pytest, C# compilé par le
`csc.exe` du .NET Framework.

**Spec :** `docs/superpowers/specs/2026-08-28-amorcage-emulateurs-design.md`

## Contraintes globales

- **Python 3.11 minimum.** Aucun test ne touche le réseau, aucun n'exige
  Windows.
- **Les chemins Windows sont des `str`**, jamais des `pathlib.Path`. Utiliser
  `pathlib.PureWindowsPath` pour toute comparaison ou extraction de suffixe.
- **Le lanceur ne décide rien.** Toute politique est calculée en Python, testée,
  et écrite dans le plan.
- **Rien n'écrase une configuration d'émulateur sans sauvegarde préalable ni
  sans en-tête disant qui l'a écrite.**
- **Une clé absente du plan est une faute du plan**, jamais une valeur vide :
  `Valeur()` lève. Les lignes `bootstrap_*` sont donc TOUJOURS écrites, vides
  quand le profil n'a pas de bloc.
- **Aucune valeur qui n'a pas été relevée sur la machine n'entre dans un
  gabarit.** Une clé inventée est ignorée en silence par l'émulateur.
- **Aucun binaire dans le dépôt.** Le lanceur est livré en source.
- **Un test qui passerait quelle que soit l'implémentation est un défaut.**
- Les messages, docstrings et commentaires sont en français ; les clés TOML et
  les identifiants de code sont en anglais, comme le reste du dépôt.

---

## Structure des fichiers

| Fichier | Responsabilité | Tâches |
|---|---|---|
| `retro/profiles.py` | lit et valide le bloc `[bootstrap]` ; expose `Bootstrap` et `Profile.bootstrap` | 1 |
| `retro/launcher.py` | nomme le fichier d'amorçage, l'écrit, le purge, pose les trois lignes du plan, écrit l'ordre de ré-amorçage, relit le témoin | 2, 3, 5 |
| `retro/cli.py` | `retro launcher --reamorcer <profil>` ; passe le témoin à `build_report` | 3, 5 |
| `retro/status.py` | l'état d'amorçage de chaque profil dans le rapport | 5 |
| `retro/data/launcher/retro-launch.cs` | pose le fichier sur la machine, sauvegarde, journal, témoin, ordre consommé | 4 |
| `retro/data/profiles/duckstation.toml` | le premier bloc `[bootstrap]` rempli, mesuré | 6 |
| les huit autres `retro/data/profiles/*.toml` | un bloc mesuré par émulateur | 7 |

---

### Task 1: Le bloc `[bootstrap]` d'un profil

**Files:**
- Modify: `retro/profiles.py`
- Test: `tests/test_profiles.py`

**Interfaces:**
- Consumes: rien.
- Produces: `profiles.Bootstrap(target: str, content: str)` — dataclass gelée ;
  `profiles.Profile.bootstrap: Bootstrap | None` ;
  `profiles.MARQUE_BOOTSTRAP: str` ; `profiles.ProfileError` (existe déjà).

- [ ] **Étape 1 : écrire les tests qui échouent**

Ajouter à la fin de `tests/test_profiles.py` :

```python
# --- le bloc [bootstrap] ------------------------------------------------

# `content` est déclaré avec les guillemets simples triples de TOML : la
# chaîne LITTÉRALE, qui n'interprète aucun échappement. C'est le format à
# employer dans les profils livrés — un fichier de configuration Windows est
# plein d'antislashs, et une chaîne TOML de base les mangerait.
BOOTSTRAP_VALIDE = """
schema = 1
id = "duckstation"
exe = 'duckstation-qt.exe'
[bootstrap]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[Main]
SetupWizardIncomplete = false
'''
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{rom}"'
"""


def ecrire(tmp_path, texte, nom="duckstation.toml"):
    p = tmp_path / nom
    p.write_text(texte, encoding="utf-8")
    return p


def test_le_bloc_bootstrap_est_lu(tmp_path):
    """Le contenu vit dans le profil, jamais dans le code : c'est lui que le
    lanceur posera tel quel."""
    profil = profiles.load_profile(ecrire(tmp_path, BOOTSTRAP_VALIDE))
    assert profil.bootstrap is not None
    assert profil.bootstrap.target == (
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini")
    assert "SetupWizardIncomplete = false" in profil.bootstrap.content


def test_un_profil_sans_bootstrap_reste_valide(tmp_path):
    """Un émulateur qui démarre nu n'a pas de bloc, et son profil doit
    continuer de se charger."""
    sans = BOOTSTRAP_VALIDE[:BOOTSTRAP_VALIDE.index("[bootstrap]")] + \
        BOOTSTRAP_VALIDE[BOOTSTRAP_VALIDE.index("[[system]]"):]
    assert profiles.load_profile(ecrire(tmp_path, sans)).bootstrap is None


def test_une_cible_sans_contenu_est_refusee(tmp_path):
    """La moitié d'un amorçage n'amorce rien, et se lirait pourtant comme un
    profil complet."""
    texte = BOOTSTRAP_VALIDE.replace(
        BOOTSTRAP_VALIDE[BOOTSTRAP_VALIDE.index("content ="):
                         BOOTSTRAP_VALIDE.index("[[system]]")], "")
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, texte))
    assert "content" in str(e.value) and "duckstation.toml" in str(e.value)


def test_un_contenu_sans_cible_est_refuse(tmp_path):
    """Un contenu sans cible n'a nulle part où aller."""
    texte = BOOTSTRAP_VALIDE.replace(
        "target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'\n", "")
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, texte))
    assert "target" in str(e.value)


def test_une_cible_relative_est_refusee(tmp_path):
    """Un chemin relatif s'écrirait dans le dossier de travail de l'émulateur,
    qui n'est pas celui de sa configuration — et le fichier posé ne serait lu
    par personne."""
    texte = BOOTSTRAP_VALIDE.replace(
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini",
        "settings.ini")
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, texte))
    assert "absolu" in str(e.value)


def test_un_contenu_sans_marque_est_refuse(tmp_path):
    """Une configuration écrite par un outil et qui ne le dit pas est un piège
    pour le prochain lecteur — et pour le propriétaire qui la modifierait."""
    texte = BOOTSTRAP_VALIDE.replace(
        "; Écrit par « retro » au premier lancement, parce que ce fichier "
        "était absent.\n", "")
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, texte))
    assert profiles.MARQUE_BOOTSTRAP in str(e.value)
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_profiles.py -k bootstrap -v`
Expected: FAIL — `AttributeError: module 'retro.profiles' has no attribute 'MARQUE_BOOTSTRAP'`

- [ ] **Étape 3 : implémenter**

Dans `retro/profiles.py`, après la classe `System` :

```python
# La phrase qu'un fichier d'amorçage porte en tête, dans la syntaxe de
# commentaire de son propre format. Elle est EXIGÉE : une configuration écrite
# par un outil et qui ne le dit pas est un piège pour le prochain lecteur, qui
# la prendrait pour la sienne et chercherait longtemps pourquoi ses réglages
# « reviennent ». C'est la même exigence que l'en-tête des plans de lancement.
MARQUE_BOOTSTRAP = "Écrit par « retro »"


@dataclasses.dataclass(frozen=True)
class Bootstrap:
    """La configuration qu'un émulateur neuf reçoit, et où elle va.

    `target` est un chemin WINDOWS, variables d'environnement comprises : la
    configuration d'un émulateur vit dans le profil de l'utilisateur Windows,
    que la machine qui pilote `retro` n'atteint pas. Le lanceur, lui, y est.
    """
    target: str
    content: str
```

Ajouter le champ à `Profile` (après `steam_input`) :

```python
    # Facultatif : un émulateur qui démarre nu n'a rien à recevoir. Le profil
    # doit alors DIRE pourquoi il n'a pas de bloc — sans quoi rien ne
    # distingue « cet émulateur se débrouille » d'un bloc oublié.
    bootstrap: Bootstrap | None = None
```

Ajouter la fonction de lecture, avant `load_profile` :

```python
def _lire_bootstrap(path: pathlib.Path, brut) -> Bootstrap | None:
    """Le bloc [bootstrap], validé, ou None s'il n'y en a pas.

    Les trois refus ci-dessous portent chacun sur une faute MUETTE : un bloc
    à moitié écrit, un chemin qui vise un dossier au hasard, un fichier qui
    ne dit pas d'où il vient. Aucune ne fait échouer quoi que ce soit au
    moment où elle est commise — elles se découvrent devant une télévision,
    sur un jeu qui n'a pas démarré.
    """
    if not brut:
        return None
    target = brut.get("target", "")
    content = brut.get("content", "")
    for nom, valeur in (("target", target), ("content", content)):
        if not isinstance(valeur, str) or not valeur.strip():
            raise ProfileError(
                f"{path} [bootstrap] : champ '{nom}' manquant ou vide. La "
                "moitié d'un amorçage n'amorce rien, et se lit pourtant comme "
                "un profil complet."
            )
    if not (target.startswith("%")
            or pathlib.PureWindowsPath(target).is_absolute()):
        raise ProfileError(
            f"{path} [bootstrap] : 'target' doit être un chemin Windows "
            f"absolu ou commencer par une variable d'environnement — reçu "
            f"{target!r}. Un chemin relatif s'écrirait dans le dossier de "
            "travail de l'émulateur, et le fichier posé ne serait lu par "
            "personne."
        )
    if MARQUE_BOOTSTRAP not in content:
        raise ProfileError(
            f"{path} [bootstrap] : 'content' ne porte pas « "
            f"{MARQUE_BOOTSTRAP} » en commentaire. Un fichier de "
            "configuration écrit par un outil doit dire qui l'a écrit : sans "
            "cela, le propriétaire le prend pour le sien."
        )
    return Bootstrap(target=target, content=content)
```

Et dans le `return Profile(...)` de `load_profile` :

```python
        steam_input=entree.get("steam_input", "required"),
        bootstrap=_lire_bootstrap(path, data.get("bootstrap")),
    )
```

- [ ] **Étape 4 : lancer les tests, vérifier qu'ils passent**

Run: `python -m pytest tests/test_profiles.py -v`
Expected: PASS, y compris les tests préexistants.

- [ ] **Étape 5 : commit**

```bash
git add retro/profiles.py tests/test_profiles.py
git commit -m "feat(profils): un profil peut declarer la configuration d'un emulateur neuf"
```

---

### Task 2: Le plan porte l'amorçage

**Files:**
- Modify: `retro/launcher.py`
- Test: `tests/test_launcher.py`

**Interfaces:**
- Consumes: `profiles.Bootstrap`, `profiles.Profile.bootstrap` (tâche 1).
- Produces: `launcher.BOOTSTRAP: str = "bootstrap"` ;
  `launcher.SI_ABSENT: str = "si-absent"` ;
  `launcher.bootstrap_name(profile_id: str, target: str) -> str` ;
  `plan_systeme(profile_id, systeme, emulator_exe, workdir, plan_dir="",
  bootstrap=None) -> str` — le paramètre `bootstrap` est ajouté **en dernier**,
  avec `None` par défaut, pour ne casser aucun appelant existant.

- [ ] **Étape 1 : écrire les tests qui échouent**

Ajouter à `tests/test_launcher.py`. Le `PROFIL` du fichier n'a pas de bloc :
en déclarer un second à côté, pour tester les deux cas.

```python
# La chaîne Python est délimitée par des guillemets doubles triples, et le
# `content` du TOML par des guillemets SIMPLES triples : la chaîne littérale
# de TOML, qui n'interprète aucun échappement. C'est ce qu'il faut pour un
# fichier de configuration Windows, plein d'antislashs.
PROFIL_AMORCE = PROFIL + """
[bootstrap]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[Main]
SetupWizardIncomplete = false
'''
"""


@pytest.fixture
def profils_amorces(tmp_path):
    p = tmp_path / "duckstation-amorce.toml"
    p.write_text(PROFIL_AMORCE, encoding="utf-8")
    return {"duckstation": profiles.load_profile(p)}


def test_le_plan_porte_les_trois_lignes_d_amorcage(profils_amorces):
    """Le lanceur ne reconstruit ni le chemin de la source ni la stratégie :
    les deux sont décidées ici."""
    systeme = profils_amorces["duckstation"].systems[0]
    texte = launcher.plan_systeme(
        "duckstation", systeme, "D:\\Emulation\\DS\\duckstation-qt.exe",
        "D:\\Emulation\\DS", "D:\\Emulation\\_launcher\\systems",
        bootstrap=profils_amorces["duckstation"].bootstrap)
    l = lignes(texte)
    assert l["bootstrap_target"] == (
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini")
    assert l["bootstrap_source"] == (
        "D:\\Emulation\\_launcher\\systems\\duckstation.bootstrap.ini")
    assert l["bootstrap_when"] == launcher.SI_ABSENT


def test_un_profil_sans_amorcage_porte_les_lignes_vides(profils):
    """Vides, jamais absentes : le lanceur traite une clé manquante comme une
    faute du plan, et c'est une propriété qu'on garde."""
    l = lignes(plan(profils))
    assert l["bootstrap_target"] == ""
    assert l["bootstrap_source"] == ""
    assert l["bootstrap_when"] == ""


def test_le_nom_du_fichier_suit_l_extension_de_la_cible():
    """Un émulateur dont la configuration est un .toml ne reçoit pas un .ini :
    le nom du fichier déposé porte l'extension de sa cible."""
    assert launcher.bootstrap_name(
        "duckstation", "%USERPROFILE%\\Documents\\DuckStation\\settings.ini"
    ) == "duckstation.bootstrap.ini"
    assert launcher.bootstrap_name(
        "xemu", "%APPDATA%\\xemu\\xemu.toml") == "xemu.bootstrap.toml"


def test_le_fichier_d_amorcage_est_ecrit(tmp_path, profils_amorces):
    """Le contenu du profil arrive tel quel à côté des plans, là où le lanceur
    ira le chercher."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    depose = (tmp_path / launcher.DIR / launcher.PLAN
              / "duckstation.bootstrap.ini")
    assert "SetupWizardIncomplete = false" in depose.read_text(encoding="utf-8")


def test_un_amorcage_perime_est_retire(tmp_path, profils_amorces):
    """Un amorçage resté là après qu'un profil a disparu réécrirait la
    configuration d'un émulateur que plus rien ne décrit."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    dossier = tmp_path / launcher.DIR / launcher.PLAN
    (dossier / "ancien.bootstrap.toml").write_text("x", encoding="utf-8")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    assert not (dossier / "ancien.bootstrap.toml").exists()
    assert (dossier / "duckstation.bootstrap.ini").exists()
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_launcher.py -k amorc -v`
Expected: FAIL — `AttributeError: module 'retro.launcher' has no attribute 'bootstrap_name'`

- [ ] **Étape 3 : implémenter**

Dans `retro/launcher.py`, à côté des constantes existantes :

```python
BOOTSTRAP = "bootstrap"
# La seule stratégie d'écriture pour l'instant, et le champ existe déjà pour
# qu'il y en ait une seconde : les configurations d'entrée du sous-projet E
# écrivent dans les MÊMES fichiers, réécrites à chaque lancement avec les
# manettes mesurées. Deux mécanismes distincts pour « un fichier de
# configuration que retro pose sur la machine » divergeraient au premier
# changement.
SI_ABSENT = "si-absent"


def bootstrap_name(profile_id: str, target: str) -> str:
    """Le nom du fichier d'amorçage déposé à côté des plans.

    L'extension est celle de la CIBLE : un `.toml` déposé sous un nom en
    `.ini` se lirait comme un fichier d'un autre format, et le premier
    lecteur du dossier n'aurait aucun moyen de savoir ce qu'il regarde.
    """
    suffixe = pathlib.PureWindowsPath(target).suffix or ".txt"
    return f"{profile_id}.{BOOTSTRAP}{suffixe}"
```

Dans `plan_systeme`, ajouter le paramètre et les trois lignes. La signature
devient :

```python
def plan_systeme(profile_id: str, systeme, emulator_exe: str,
                 workdir: str, plan_dir: str = "", bootstrap=None) -> str:
```

et, juste avant la boucle `for classe in render_mod.CLASSES:` :

```python
    # L'amorçage, s'il y en a un. Les trois lignes sont TOUJOURS écrites :
    # `Valeur()` traite une clé absente comme une faute du plan, et c'est
    # cette propriété qui a déjà attrapé des plans écrits par une version
    # antérieure. Vides, elles disent « cet émulateur n'a rien à recevoir ».
    source = (f"{plan_dir}\\{bootstrap_name(profile_id, bootstrap.target)}"
              if bootstrap else "")
    lignes += [
        f"bootstrap_target={bootstrap.target if bootstrap else ''}",
        f"bootstrap_source={source}",
        f"bootstrap_when={SI_ABSENT if bootstrap else ''}",
    ]
```

Dans `ecrire_plan`, passer le bloc et déposer le fichier. Remplacer l'appel à
`plan_systeme` par :

```python
            (dossier / f"{cle}.ini").write_text(
                plan_systeme(pid, systeme, exe, workdir, plan_dir,
                             bootstrap=profil.bootstrap),
                encoding="utf-8")
```

et, après la boucle sur les systèmes du profil (au même niveau que
`for systeme in profil.systems:`) :

```python
        # Un seul fichier par PROFIL : la configuration d'un émulateur ne
        # change pas selon la console qu'il émule.
        if profil.bootstrap:
            nom = bootstrap_name(pid, profil.bootstrap.target)
            (dossier / nom).write_text(profil.bootstrap.content,
                                       encoding="utf-8")
            fichiers.add(nom)
```

Enfin, la purge. Elle ne connaît aujourd'hui que `*.ini` et `*.cfg`, et
laisserait un `.toml` ou un `.yml` d'amorçage périmé. Ce dossier n'appartient
qu'à `retro` — son en-tête le dit à chaque fichier — donc tout ce qui n'est
plus attendu s'en va :

```python
    # Tout fichier que ce passage n'a pas écrit s'en va : ce dossier
    # appartient entièrement à « retro scan », et un amorçage d'un format
    # qu'on n'aurait pas pensé à énumérer réécrirait la configuration d'un
    # émulateur à chaque lancement, avec le contenu d'un autre âge.
    for perime in sorted(p for p in dossier.iterdir() if p.is_file()):
        if perime.name not in fichiers:
            perime.unlink()
```

- [ ] **Étape 4 : lancer toute la suite**

Run: `python -m pytest tests/ -q`
Expected: PASS — la purge élargie touche `test_un_plan_perime_est_retire` et
`test_un_fichier_de_reglages_perime_est_retire`, qui doivent continuer de
passer.

- [ ] **Étape 5 : commit**

```bash
git add retro/launcher.py tests/test_launcher.py
git commit -m "feat(plan): le plan de lancement porte la configuration a poser"
```

---

### Task 3: L'ordre de ré-amorçage

**Files:**
- Modify: `retro/launcher.py`, `retro/cli.py`
- Test: `tests/test_launcher.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `launcher.BOOTSTRAP`, `launcher.local_dir`, `launcher.PLAN` (tâche 2).
- Produces: `launcher.REAMORCER: str = "reamorcer.txt"` ;
  `launcher.AmorcageError(RuntimeError)` ;
  `launcher.profils_amorcables(emulation_root_local) -> list[str]` ;
  `launcher.ordonner_reamorcage(emulation_root_local, profile_id) -> pathlib.Path` ;
  option CLI `retro launcher --reamorcer PROFIL`.

- [ ] **Étape 1 : écrire les tests qui échouent**

Dans `tests/test_launcher.py` :

```python
def test_l_ordre_de_reamorcage_est_ecrit(tmp_path, profils_amorces):
    """« retro » n'atteint pas C:\\Users : forcer n'est pas une écriture, c'est
    un ordre que le lanceur exécutera là où il est."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    fichier = launcher.ordonner_reamorcage(tmp_path, "duckstation")
    assert fichier.read_text(encoding="utf-8").split() == ["duckstation"]


def test_un_ordre_ne_s_ecrit_pas_deux_fois(tmp_path, profils_amorces):
    """Deux ordres pour le même profil feraient deux sauvegardes et une
    réécriture de plus, sans rien apporter."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    launcher.ordonner_reamorcage(tmp_path, "duckstation")
    fichier = launcher.ordonner_reamorcage(tmp_path, "duckstation")
    assert fichier.read_text(encoding="utf-8").split() == ["duckstation"]


def test_reamorcer_un_profil_inconnu_est_refuse(tmp_path, profils_amorces):
    """Un ordre qui nomme un profil sans amorçage ne serait jamais consommé :
    il resterait dans le fichier, et le propriétaire attendrait un effet qui
    ne vient pas."""
    launcher.ecrire_plan(tmp_path, "D:\\Emulation", profils_amorces,
                         {"duckstation": "DS"})
    with pytest.raises(launcher.AmorcageError) as e:
        launcher.ordonner_reamorcage(tmp_path, "pcsx2")
    assert "duckstation" in str(e.value)
```

Dans `tests/test_cli.py`, en suivant le style des tests de commandes déjà
présents dans ce fichier :

```python
def test_launcher_reamorcer(tmp_path, capsys):
    """Le geste est disponible depuis la ligne de commande, et il nomme le
    fichier écrit — sans quoi rien ne dit que l'ordre est parti."""
    from retro import launcher, profiles
    profil = tmp_path / "duckstation.toml"
    profil.write_text(PROFIL_AMORCE_CLI, encoding="utf-8")
    launcher.ecrire_plan(tmp_path, "D:\\Emulation",
                         {"duckstation": profiles.load_profile(profil)},
                         {"duckstation": "DS"})
    code = cli.main(["launcher", "--emulation-root-local", str(tmp_path),
                     "--reamorcer", "duckstation"])
    assert code == 0
    assert "duckstation" in capsys.readouterr().out


def test_launcher_reamorcer_un_inconnu_echoue(tmp_path, capsys):
    """Un profil mal orthographié doit s'entendre dire, pas se taire."""
    code = cli.main(["launcher", "--emulation-root-local", str(tmp_path),
                     "--reamorcer", "duckstaton"])
    assert code == 2
    assert "duckstaton" in capsys.readouterr().err
```

avec, en tête de `tests/test_cli.py`, le profil que ce test écrit :

```python
PROFIL_AMORCE_CLI = """
schema = 1
id = "duckstation"
exe = 'duckstation-qt.exe'
[bootstrap]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[Main]
SetupWizardIncomplete = false
'''
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{rom}"'
"""
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_launcher.py -k reamorc tests/test_cli.py -k reamorcer -v`
Expected: FAIL — `AttributeError: module 'retro.launcher' has no attribute 'ordonner_reamorcage'`

- [ ] **Étape 3 : implémenter**

Dans `retro/launcher.py` :

```python
REAMORCER = "reamorcer.txt"


class AmorcageError(RuntimeError):
    """L'ordre n'a pas été écrit, et le propriétaire sait pourquoi."""


def profils_amorcables(emulation_root_local) -> list[str]:
    """Les profils dont un amorçage est DÉPOSÉ, lus sur le disque.

    Lire le dossier plutôt que recharger les profils : c'est l'état réel de
    la console qui décide, et un profil dont l'amorçage n'a pas encore été
    déposé par « retro scan » ne peut pas être ré-amorcé — l'ordre serait
    donné pour un fichier que le lanceur ne trouverait pas.
    """
    dossier = local_dir(emulation_root_local) / PLAN
    try:
        noms = [p.name for p in dossier.iterdir() if p.is_file()]
    except OSError:
        return []
    marque = f".{BOOTSTRAP}"
    return sorted({n[:n.index(marque)] for n in noms if marque in n})


def ordonner_reamorcage(emulation_root_local, profile_id: str) -> pathlib.Path:
    """Demande au lanceur de reposer l'amorçage de ce profil, une fois.

    L'ordre, et pas l'écriture : la configuration d'un émulateur vit dans le
    profil de l'utilisateur Windows, que la machine qui pilote n'atteint pas.
    Le lanceur sauvegardera l'existant avant de le remplacer, puis consommera
    la ligne — un ordre ne vaut qu'un passage.
    """
    connus = profils_amorcables(emulation_root_local)
    if profile_id not in connus:
        raise AmorcageError(
            f"« {profile_id} » n'a pas d'amorçage déposé. "
            + (f"Profils amorçables : {', '.join(connus)}." if connus else
               "Aucun profil n'en a : lancer « retro scan » d'abord.")
        )
    dossier = local_dir(emulation_root_local)
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / REAMORCER
    try:
        deja = fichier.read_text(encoding="utf-8").split()
    except OSError:
        deja = []
    if profile_id not in deja:
        deja.append(profile_id)
    fichier.write_text("\n".join(deja) + "\n", encoding="utf-8")
    return fichier
```

Dans `retro/cli.py`, au début de `_cmd_launcher`, avant le dépôt de la source :

```python
    racine = pathlib.Path(args.emulation_root_local)
    # Le ré-amorçage est un geste à part : il ne redépose pas la source du
    # lanceur, et il ne dépend pas de sa compilation.
    if args.reamorcer:
        try:
            fichier = launcher_mod.ordonner_reamorcage(racine, args.reamorcer)
        except (launcher_mod.AmorcageError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"ré-amorçage demandé pour « {args.reamorcer} » : {fichier}\n"
              "Il sera posé au prochain lancement d'un jeu de cet émulateur, "
              "après sauvegarde de sa configuration actuelle.")
        return 0
```

et dans `_build_parser`, sur le sous-parseur `lan` :

```python
    lan.add_argument("--reamorcer", metavar="PROFIL", default=None,
                     help="reposer la configuration de cet émulateur au "
                          "prochain lancement, en sauvegardant l'actuelle. "
                          "Sans cette option, une configuration existante "
                          "n'est jamais touchée.")
```

- [ ] **Étape 4 : lancer toute la suite**

Run: `python -m pytest tests/ -q`
Expected: PASS

- [ ] **Étape 5 : commit**

```bash
git add retro/launcher.py retro/cli.py tests/test_launcher.py tests/test_cli.py
git commit -m "feat(cli): reposer la configuration d'un emulateur deja configure"
```

---

### Task 4: Le lanceur pose la configuration

**Files:**
- Modify: `retro/data/launcher/retro-launch.cs`
- Test: aucun test automatisé (le dépôt n'a pas de cadre de test C#). La
  vérification est manuelle, sur la machine, et **écrite** — étape 5.

**Interfaces:**
- Consumes: les lignes `bootstrap_target`, `bootstrap_source`,
  `bootstrap_when` du plan (tâche 2) ; le fichier `_launcher\reamorcer.txt`
  (tâche 3).
- Produces: `_launcher\bootstrap.txt` — une ligne par profil amorcé,
  `profil<TAB>AAAA-MM-JJ HH:MM:SS<TAB>cible`, lu par la tâche 5.

- [ ] **Étape 1 : ajouter les constantes et les quatre fonctions**

Dans `retro-launch.cs`, après `static string journal;` :

```csharp
    const string SI_ABSENT = "si-absent";
```

Après la méthode `Noter` :

```csharp
    // L'amorçage : poser la configuration d'un émulateur qui n'en a jamais eu.
    //
    // Mesuré le 2026-08-28 : sans son settings.ini, DuckStation tient
    // SetupWizardIncomplete pour vrai et ouvre son assistant AVANT d'honorer
    // sa ligne de commande. Aucun de ses dix-sept arguments ne le saute, et
    // comme personne ne termine un assistant depuis un canapé, rien n'est
    // jamais ecrit : le lancement suivant recommence a l'identique.
    //
    // Ce qui est pose, et quand, est decide par « retro scan » : cette
    // methode lit trois lignes du plan et n'en invente aucune.
    static void Amorcer(Dictionary<string, string> p, string profil)
    {
        string cible = Valeur(p, "bootstrap_target");
        if (cible.Length == 0) return;   // cet emulateur n'a rien a recevoir

        string quand = Valeur(p, "bootstrap_when");
        if (quand != SI_ABSENT)
            throw new Exception(
                "Le plan demande une strategie d'amorcage inconnue : « " + quand
                + " ». Ce lanceur ne connait que « " + SI_ABSENT + " ».\n\n"
                + "Recompiler le lanceur (compiler.cmd), ou relancer "
                + "« retro scan ».");

        cible = Environment.ExpandEnvironmentVariables(cible);
        bool force = OrdreDeReamorcage(profil);
        if (File.Exists(cible) && !force) return;

        string source = Valeur(p, "bootstrap_source");
        if (!File.Exists(source))
            throw new Exception(
                "Le fichier de configuration a poser est introuvable :\n\n"
                + source + "\n\nRelancer « retro scan » depuis l'hote.");

        string parent = Path.GetDirectoryName(cible);
        if (parent.Length > 0 && !Directory.Exists(parent))
            Directory.CreateDirectory(parent);

        // Rien n'ecrase une configuration sans sauvegarde : la convention est
        // celle de shortcuts.vdf.bak-*, deja en usage cote synchronisation.
        if (File.Exists(cible))
        {
            string sauvegarde = cible + ".bak-"
                + DateTime.Now.ToString("yyyyMMdd-HHmmss");
            File.Copy(cible, sauvegarde, false);
            Noter("amorcage : " + cible + " sauvegarde en " + sauvegarde);
        }

        File.Copy(source, cible, true);
        Noter("amorcage : " + profil + " -> " + cible
              + (force ? " (ordre de reamorcage)" : ""));
        InscrireTemoin(profil, cible);
        if (force) ConsommerOrdre(profil);
    }

    // Le propriétaire a-t-il demande de reposer la configuration de ce profil ?
    static bool OrdreDeReamorcage(string profil)
    {
        string fichier = Path.Combine(dossier, "reamorcer.txt");
        if (!File.Exists(fichier)) return false;
        foreach (string ligne in File.ReadAllLines(fichier, Encoding.UTF8))
            if (ligne.Trim() == profil) return true;
        return false;
    }

    // Un ordre ne vaut qu'un passage : le laisser ferait une sauvegarde et une
    // reecriture a chaque lancement, et le propriétaire ne pourrait plus jamais
    // regler son emulateur lui-meme.
    static void ConsommerOrdre(string profil)
    {
        string fichier = Path.Combine(dossier, "reamorcer.txt");
        var restants = new List<string>();
        foreach (string ligne in File.ReadAllLines(fichier, Encoding.UTF8))
            if (ligne.Trim().Length > 0 && ligne.Trim() != profil)
                restants.Add(ligne.Trim());
        if (restants.Count == 0) File.Delete(fichier);
        else File.WriteAllLines(fichier, restants, new UTF8Encoding(false));
    }

    // Le temoin : « retro status » tourne sur l'hote, qui n'atteint ni
    // C:\Users ni %APPDATA%. Il ne peut donc pas CONSTATER qu'un emulateur est
    // amorce — seulement lire ce que le lanceur a ecrit la ou l'hote regarde.
    // C'est une trace, jamais une source de verite : Amorcer() consulte la
    // cible, jamais ce fichier.
    static void InscrireTemoin(string profil, string cible)
    {
        try
        {
            string fichier = Path.Combine(dossier, "bootstrap.txt");
            var lignes = new List<string>();
            if (File.Exists(fichier))
                foreach (string l in File.ReadAllLines(fichier, Encoding.UTF8))
                    if (l.Length > 0 && !l.StartsWith(profil + "\t"))
                        lignes.Add(l);
            lignes.Add(profil + "\t"
                + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "\t" + cible);
            lignes.Sort();
            File.WriteAllLines(fichier, lignes, new UTF8Encoding(false));
        }
        catch (Exception e)
        {
            // Un temoin illisible ne doit pas priver le propriétaire de son jeu :
            // la configuration, elle, est posee.
            Noter("temoin d'amorcage non ecrit : " + e.Message);
        }
    }
```

- [ ] **Étape 2 : appeler l'amorçage avant le lancement**

Dans `Lancer()`, la clé du plan est `<profil>.<systeme>` : le profil est ce qui
précède le premier point. Ajouter **après** le bloc `if (expliquer) { … return
0; }` et **avant** `IntPtr job = CreerJob();` :

```csharp
        // Avant de lancer : poser la configuration si l'emulateur n'en a
        // aucune. Un echec n'empeche PAS le jeu de demarrer — il ouvrira son
        // assistant, mais le propriétaire aura lu pourquoi. Abandonner ici
        // rendrait la main a Steam, ce qui ressemble exactement a un jeu
        // qu'on vient de quitter.
        try
        {
            Amorcer(p, cle.Split('.')[0]);
        }
        catch (Exception e)
        {
            Noter("ECHEC de l'amorcage : " + e.Message);
            MessageBoxW(IntPtr.Zero,
                e.Message + "\n\nLe jeu va tout de meme demarrer : "
                + "l'emulateur ouvrira peut-etre son assistant de "
                + "configuration.",
                "Console retro — configuration non posee", 0x30);
        }
```

Dans le rapport `--explain`, avant `Console.Out.Write(rapport.ToString());`,
ajouter deux lignes — `--explain` rend compte **sans effet de bord**, et doit
donc dire ce qu'il aurait fait :

```csharp
            string cibleAmorcage = Valeur(p, "bootstrap_target");
            rapport.AppendLine("amorcage_cible=" + cibleAmorcage);
            rapport.AppendLine("amorcage_a_poser="
                + (cibleAmorcage.Length == 0 ? "rien"
                   : (File.Exists(Environment.ExpandEnvironmentVariables(
                          cibleAmorcage)) ? "non (la cible existe)" : "oui")));
```

- [ ] **Étape 3 : compiler sur la machine**

```bash
winvm 'D:\Emulation\_launcher\compiler.cmd'
```
Expected: la compilation réussit, `retro-launch.exe` est réécrit. Une erreur de
compilation nomme sa ligne : la corriger avant d'aller plus loin.

- [ ] **Étape 4 : vérifier par `--explain`, qui ne lance rien**

```bash
winvm 'D:\Emulation\_launcher\retro-launch.exe --explain duckstation.psx "G:\Games\Sony\Playstation\Crash Team Racing-PSX-PAL.cue"'
winvm 'type D:\Emulation\_launcher\explain.txt'
```
Expected: `amorcage_cible=%USERPROFILE%\Documents\DuckStation\settings.ini` et
`amorcage_a_poser=` avec la réponse conforme à l'état du disque. **Aucun**
fichier ne doit avoir été posé — le vérifier :
```bash
winvm --ps 'Get-ChildItem "$env:USERPROFILE\Documents\DuckStation\settings.ini" | Select-Object Length,LastWriteTime'
```

- [ ] **Étape 5 : la vérification de bout en bout, et son procès-verbal**

Elle ne peut se faire qu'après la tâche 6, qui remplit le bloc de DuckStation.
Y revenir alors, et **écrire le relevé** dans le rapport de fin : commande
lancée, contenu de `journal.txt` et de `bootstrap.txt`, état du jeu à l'écran.

- [ ] **Étape 6 : commit**

```bash
git add retro/data/launcher/retro-launch.cs
git commit -m "feat(lanceur): poser la configuration d'un emulateur qui n'en a aucune"
```

---

### Task 5: Le rapport dit ce qui est amorcé

**Files:**
- Modify: `retro/launcher.py`, `retro/status.py`, `retro/cli.py`
- Test: `tests/test_launcher.py`, `tests/test_status.py`

**Interfaces:**
- Consumes: le témoin `_launcher\bootstrap.txt` (tâche 4) ;
  `profiles.Profile.bootstrap` (tâche 1).
- Produces: `launcher.TEMOIN_BOOTSTRAP: str = "bootstrap.txt"` ;
  `launcher.lire_amorcages(emulation_root_local) -> dict[str, tuple[str, str]]`
  (profil → (date, cible)) ; `status.Amorcage(profile_id, declare, date,
  target)` ; `status.etat_amorcage(profils, amorcages) -> list[Amorcage]` ;
  `build_report(..., amorcages=...)` et `Report.amorcages`.

- [ ] **Étape 1 : écrire les tests qui échouent**

Dans `tests/test_launcher.py` :

```python
def test_le_temoin_d_amorcage_est_relu(tmp_path):
    """Le lanceur écrit ce qu'il a posé ; l'hôte, qui n'atteint pas C:\\Users,
    n'a que ça pour le savoir."""
    dossier = tmp_path / launcher.DIR
    dossier.mkdir(parents=True)
    (dossier / launcher.TEMOIN_BOOTSTRAP).write_text(
        "duckstation\t2026-08-28 10:27:26\tC:\\Users\\A\\settings.ini\n",
        encoding="utf-8")
    assert launcher.lire_amorcages(tmp_path) == {
        "duckstation": ("2026-08-28 10:27:26", "C:\\Users\\A\\settings.ini")}


def test_un_temoin_absent_ne_fait_pas_echouer(tmp_path):
    """Aucun jeu n'a encore été lancé : c'est un état normal, pas une panne."""
    assert launcher.lire_amorcages(tmp_path) == {}
```

Dans `tests/test_status.py` :

```python
def test_le_rapport_dit_ce_qui_est_amorce(profils_amorces_status):
    """« amorcé le … » : le propriétaire doit pouvoir vérifier qu'une
    configuration a bien été posée sans ouvrir l'émulateur."""
    etats = status.etat_amorcage(
        profils_amorces_status,
        {"duckstation": ("2026-08-28 10:27:26", "C:\\Users\\A\\settings.ini")})
    assert [(e.profile_id, e.declare, e.date) for e in etats] == [
        ("duckstation", True, "2026-08-28 10:27:26")]


def test_le_rapport_dit_ce_qui_n_est_pas_encore_amorce(profils_amorces_status):
    """Aucun jeu de cet émulateur n'a encore été lancé. Ce n'est pas un
    problème — c'est un état à dire, pas à taire."""
    etats = status.etat_amorcage(profils_amorces_status, {})
    assert etats[0].declare and etats[0].date == ""


def test_un_profil_sans_bloc_est_nomme(profils_sans_amorcage_status):
    """« cet émulateur se débrouille » et « le bloc a été oublié » ne se
    distinguent que si le rapport nomme les profils sans amorçage."""
    etats = status.etat_amorcage(profils_sans_amorcage_status, {})
    assert etats[0].declare is False


def test_la_section_amorcage_figure_dans_le_texte(profils_amorces_status):
    """Un état que le rapport calcule sans l'imprimer ne sert à personne."""
    rapport = status.build_report(
        install_dirs={"duckstation": "DS"},
        emulation_root=pathlib.Path("D:\\Emulation"),
        systems=[], bios_status=[], bios_root=pathlib.Path("G:\\bios"),
        profils=profils_amorces_status,
        amorcages={"duckstation": ("2026-08-28 10:27:26",
                                   "C:\\Users\\A\\settings.ini")},
    )
    texte = status.format_report(rapport)
    assert "Amorçage" in texte and "2026-08-28 10:27:26" in texte
```

Les deux fixtures, en tête de `tests/test_status.py`. Elles chargent de vrais
profils plutôt que des doubles : `etat_amorcage` lit `Profile.bootstrap`, et un
double qui porterait cet attribut passerait quelle que soit l'implémentation de
la tâche 1.

```python
PROFIL_STATUS_AMORCE = """
schema = 1
id = "duckstation"
exe = 'duckstation-qt.exe'
[bootstrap]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[Main]
SetupWizardIncomplete = false
'''
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{rom}"'
"""


@pytest.fixture
def profils_amorces_status(tmp_path):
    from retro import profiles
    p = tmp_path / "duckstation.toml"
    p.write_text(PROFIL_STATUS_AMORCE, encoding="utf-8")
    return {"duckstation": profiles.load_profile(p)}


@pytest.fixture
def profils_sans_amorcage_status(tmp_path):
    from retro import profiles
    texte = (PROFIL_STATUS_AMORCE[:PROFIL_STATUS_AMORCE.index("[bootstrap]")]
             + PROFIL_STATUS_AMORCE[PROFIL_STATUS_AMORCE.index("[[system]]"):])
    p = tmp_path / "duckstation.toml"
    p.write_text(texte, encoding="utf-8")
    return {"duckstation": profiles.load_profile(p)}
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_status.py -k amorc tests/test_launcher.py -k temoin -v`
Expected: FAIL — `AttributeError: module 'retro.status' has no attribute 'etat_amorcage'`

- [ ] **Étape 3 : implémenter**

Dans `retro/launcher.py` :

```python
TEMOIN_BOOTSTRAP = "bootstrap.txt"


def lire_amorcages(emulation_root_local) -> dict[str, tuple[str, str]]:
    """Ce que le lanceur a posé : profil → (date, cible).

    Une TRACE, pas une source de vérité : c'est la cible sur le disque de la
    console qui décide, et le lanceur ne consulte jamais ce fichier pour
    savoir s'il doit écrire. Un témoin effacé fait donc dire au rapport « pas
    encore amorcé » d'un émulateur qui l'est — sans que rien ne soit réécrit.
    """
    fichier = local_dir(emulation_root_local) / TEMOIN_BOOTSTRAP
    try:
        texte = fichier.read_text(encoding="utf-8")
    except OSError:
        return {}
    amorces = {}
    for ligne in texte.splitlines():
        parts = ligne.split("\t")
        if len(parts) == 3 and parts[0].strip():
            amorces[parts[0].strip()] = (parts[1].strip(), parts[2].strip())
    return amorces
```

Dans `retro/status.py`, à côté de `SystemRender` :

```python
@dataclasses.dataclass(frozen=True)
class Amorcage:
    """Ce qu'un émulateur a reçu comme configuration, ou n'a pas reçu.

    Trois états, et ils appellent trois lectures différentes : configuration
    posée (avec sa date), profil qui en déclare une mais dont aucun jeu n'a
    encore été lancé, et profil qui n'en déclare aucune. Le dernier n'est une
    anomalie que s'il n'est pas dit : « cet émulateur démarre nu » et « le
    bloc a été oublié » se ressemblent exactement, vus du canapé.
    """
    profile_id: str
    declare: bool
    date: str = ""
    target: str = ""


def etat_amorcage(profils: dict,
                  amorcages: dict[str, tuple[str, str]]) -> list[Amorcage]:
    etats = []
    for pid in sorted(profils):
        declare = getattr(profils[pid], "bootstrap", None) is not None
        date, cible = amorcages.get(pid, ("", ""))
        etats.append(Amorcage(profile_id=pid, declare=declare,
                              date=date if declare else "",
                              target=cible if declare else ""))
    return etats
```

Ajouter à `Report` :

```python
    amorcages: list[Amorcage] = dataclasses.field(default_factory=list)
```

Dans `build_report`, ajouter le paramètre
`amorcages: dict[str, tuple[str, str]] | None = None` et, dans le `return
Report(...)` :

```python
        amorcages=etat_amorcage(profils, amorcages or {}) if profils else [],
```

Dans `format_report`, une section après celle du rendu, dans le style des
sections existantes du fichier :

```python
    if rapport.amorcages:
        lignes.append("")
        lignes.append("Amorçage")
        for a in rapport.amorcages:
            if not a.declare:
                lignes.append(f"  · {a.profile_id} : aucune configuration à "
                              "poser (voir son profil)")
            elif a.date:
                lignes.append(f"  · {a.profile_id} : amorcé le {a.date} "
                              f"({a.target})")
            else:
                lignes.append(f"  · {a.profile_id} : pas encore amorcé — sa "
                              "configuration sera posée au premier lancement "
                              "d'un de ses jeux")
```

Dans `retro/cli.py`, `_cmd_status`, ajouter à l'appel de `build_report` :

```python
            # Le témoin que le lanceur écrit : `status` ne peut pas
            # constater l'état d'un fichier qui vit dans le profil de
            # l'utilisateur Windows. Même racine que `lire_mode` ci-dessus,
            # et même limite : sur la machine, les deux chemins se
            # confondent.
            amorcages=launcher_mod.lire_amorcages(
                pathlib.Path(args.emulation_root)),
```

- [ ] **Étape 4 : lancer toute la suite**

Run: `python -m pytest tests/ -q`
Expected: PASS

- [ ] **Étape 5 : commit**

```bash
git add retro/launcher.py retro/status.py retro/cli.py tests/test_launcher.py tests/test_status.py
git commit -m "feat(status): nommer les emulateurs dont la configuration n'a jamais ete posee"
```

---

### Task 6: DuckStation, mesuré et rempli

**Files:**
- Modify: `retro/data/profiles/duckstation.toml`
- Modify: `README.md` (la section « Ce que ça fait », une phrase sur l'amorçage)
- Test: `tests/test_profiles.py` — le profil livré se charge et déclare un
  amorçage.

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: le premier bloc `[bootstrap]` livré.

**Aucune clé ne s'écrit sans avoir été relevée sur la machine.** Les chaînes
`SetupWizardIncomplete`, `StartFullscreen`, `ConfirmPowerOff`,
`HideCursorInFullscreen`, `InhibitScreensaver`, `PauseOnFocusLoss`,
`SaveStateOnExit`, les sections `Main`, `BIOS`, `Folders` et les clés
`PathNTSCU` / `PathPAL` / `PathNTSCJ` ont été **repérées dans l'exécutable
livré** le 2026-08-28 — c'est un point de départ pour la mesure, pas une
autorisation de les écrire.

- [ ] **Étape 1 : faire écrire à DuckStation son propre fichier**

Sur la machine, dans la **session interactive** — lancé par WinRM, donc en
session 0, il ne voit ni écran ni manette :

```bash
winvm --ps 'schtasks /create /tn retro-duckstation /tr "D:\Emulation\DuckStation\duckstation-qt-x64-ReleaseLTCG.exe" /sc once /st 00:00 /it /f; schtasks /run /tn retro-duckstation'
```

Régler dans son interface : plein écran au démarrage, pas de confirmation à
l'arrêt, curseur masqué, veille inhibée, pas de pause à la perte du focus, et
le dossier de BIOS sur `G:\retro\bios`. Puis le **fermer proprement**, pour
qu'il persiste lui-même son fichier.

- [ ] **Étape 2 : relever le fichier**

```bash
cat "/media/win-d/../win-c/Users/Administrator/Documents/DuckStation/settings.ini" 2>/dev/null \
  || winvm --ps 'Get-Content "$env:USERPROFILE\Documents\DuckStation\settings.ini"'
```
Expected: le fichier complet. Noter les clés qui correspondent aux réglages
faits — ce sont les seules qui entrent dans le gabarit, avec la valeur que
DuckStation a écrite, à l'octet près.

- [ ] **Étape 3 : écrire le bloc dans le profil**

Dans `retro/data/profiles/duckstation.toml`, après le bloc `[exit]`, avec un
commentaire par clé disant ce qu'elle fait et d'où elle vient. Le squelette —
les valeurs sont celles de l'étape 2, et la ligne `SetupWizardIncomplete` est
la seule dont la mesure est déjà faite :

```toml
[bootstrap]
# Une installation neuve n'a pas de settings.ini, et DuckStation tient alors
# Main/SetupWizardIncomplete pour vrai : il ouvre son assistant AVANT
# d'honorer sa ligne de commande. Mesuré le 2026-08-28 sur la machine — cinq
# lancements de Crash Team Racing, ligne de commande correcte à chaque fois,
# aucun fichier de données créé. Le même lancement, ce fichier posé, démarre
# le jeu : playtime.dat porte SCES-02105.
#
# Ce fichier n'est posé que s'il est ABSENT. Une installation configurée
# appartient au propriétaire ; « retro launcher --reamorcer duckstation »
# est le seul chemin qui l'écrase, et il sauvegarde d'abord.
target = '%USERPROFILE%\Documents\DuckStation\settings.ini'
content = """
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
; Vos modifications sont conservées : ce fichier ne sera pas réécrit.
[Main]
SetupWizardIncomplete = false
"""
```

- [ ] **Étape 4 : le test du profil livré**

Dans `tests/test_profiles.py` :

```python
def test_le_profil_duckstation_livre_declare_un_amorcage():
    """C'est le défaut mesuré le 2026-08-28 : sans ce bloc, lancer un jeu
    PlayStation ouvre l'assistant de DuckStation."""
    livres = pathlib.Path(profiles.__file__).parent / "data" / "profiles"
    profil = profiles.load_profile(livres / "duckstation.toml")
    assert profil.bootstrap is not None
    assert "SetupWizardIncomplete" in profil.bootstrap.content
```

- [ ] **Étape 5 : dérouler la chaîne complète**

```bash
python -m pytest tests/ -q
```
puis, sur la machine — `retro scan` avec les options du README, et :

```bash
winvm --ps 'Move-Item "$env:USERPROFILE\Documents\DuckStation\settings.ini" "$env:USERPROFILE\settings.ini.avant-retro" -Force'
```

Lancer Crash Team Racing **depuis Steam, sur la console**. Attendu : le jeu
démarre sans assistant. Puis :

```bash
winvm 'type D:\Emulation\_launcher\journal.txt | more +9999'
winvm 'type D:\Emulation\_launcher\bootstrap.txt'
```
Expected: une ligne `amorcage : duckstation -> C:\Users\…\settings.ini` au
journal, et une ligne dans le témoin. Reporter ces sorties dans le rapport de
fin : c'est la vérification manuelle de la tâche 4.

- [ ] **Étape 6 : commit**

```bash
git add retro/data/profiles/duckstation.toml tests/test_profiles.py README.md
git commit -m "feat(duckstation): l'assistant ne s'ouvre plus a la place du jeu"
```

---

### Task 7: Les huit autres émulateurs, un par un

**Files:**
- Modify: `retro/data/profiles/pcsx2.toml`, `retroarch.toml`, `dolphin.toml`,
  `cemu.toml`, `ppsspp.toml`, `rpcs3.toml`, `flycast.toml`, `xemu.toml`
- Test: `tests/test_profiles.py`

**Interfaces:**
- Consumes: tout ce qui précède. Aucun code n'est modifié ici : le mécanisme
  est fini, seuls les gabarits s'ajoutent.
- Produces: un bloc `[bootstrap]` mesuré, ou un commentaire disant pourquoi il
  n'y en a pas.

**Ordre :** PCSX2 d'abord — il a le même assistant obligatoire et sera le
prochain à s'ouvrir à la place d'un jeu.

**Pour CHAQUE émulateur, dans l'ordre, un commit par émulateur :**

- [ ] **Étape 1 : établir s'il ouvre un assistant**

Le lancer dans la session interactive sur une installation neuve
(`schtasks /create … /IT` puis `/run`, comme en tâche 6), avec la ligne de
commande de son profil et une ROM réelle. Deux réponses possibles, et les deux
sont un résultat :

- il démarre le jeu → **pas de bloc `[bootstrap]`**. Écrire dans le profil
  qu'il démarre nu, avec la date de la mesure. Un bloc absent sans explication
  ne se distingue pas d'un bloc oublié.
- il ouvre autre chose que le jeu → continuer.

- [ ] **Étape 2 : trouver où il écrit**

```bash
winvm --ps 'Get-ChildItem "$env:USERPROFILE\Documents","$env:APPDATA","$env:LOCALAPPDATA","D:\Emulation\<installation>" -Recurse -Depth 3 -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-10) } | Select-Object FullName,LastWriteTime'
```
Expected: le fichier qu'il vient d'écrire. C'est la `target` — **relevée**, pas
celle du tableau de la spec, qui n'est qu'un point de départ.

**Si le fichier vit sous le dossier d'installation** (`D:\Emulation\<émulateur>`)
: `acquire.acquire` supprime ce dossier à chaque montée de version. Chercher si
l'émulateur expose un dossier de données ailleurs. Si non, l'écrire dans le
profil : l'amorçage se rejouera après chaque mise à jour, ce que le lanceur
fait naturellement puisque la cible aura disparu avec le dossier.

- [ ] **Étape 3 : régler, fermer, relever**

Régler dans son interface ce que l'amorçage doit porter — ne pas ouvrir
d'assistant, plein écran, pas de confirmation à l'arrêt, curseur masqué, veille
inhibée, et **le chemin des BIOS** si ses systèmes en déclarent. Fermer
proprement. Lire le fichier qu'il a persisté, et n'en garder que les clés
réglées.

**Le chemin des BIOS n'est pas du confort :** `retro status --bios` vérifie
`G:\retro\bios` pendant que l'émulateur cherche ailleurs. Sans ce réglage, le
rapport annonce « BIOS présent » sur un émulateur qui n'en voit aucun.

- [ ] **Étape 4 : écrire le bloc, avec un commentaire par clé**

Dans le profil, en tête de commentaire : la date de la mesure, la révision de
l'émulateur mesurée, et ce qui a été fait dans son interface. La marque
`Écrit par « retro »` va dans le `content`, **dans la syntaxe de commentaire du
format de ce fichier** — `;` pour un INI, `#` pour un TOML ou un YAML, `<!-- -->`
pour un XML. `profiles.MARQUE_BOOTSTRAP` refuse le contenu qui ne la porte pas.

- [ ] **Étape 5 : vérifier de bout en bout**

`python -m pytest tests/ -q`, puis `retro scan`, puis la cible déplacée, puis
un jeu de cet émulateur lancé **depuis Steam sur la console**. Le jeu démarre,
`journal.txt` et `bootstrap.txt` le disent. Reporter le relevé.

- [ ] **Étape 6 : commit**

```bash
git add retro/data/profiles/<emulateur>.toml
git commit -m "feat(<emulateur>): la configuration est posee au premier lancement"
```

---

## Vérification finale

- [ ] Suite complète, arbre frais : `python -m pytest tests/ -q -W error`
- [ ] Aucun test ne touche le réseau, aucun n'exige Windows
- [ ] Aucune clé écrite qui n'ait été relevée sur la machine
- [ ] Chaque profil livré porte un bloc `[bootstrap]` **ou** une phrase disant
      pourquoi il n'en a pas
- [ ] Sur la console, session Moonlight ouverte : un jeu par émulateur couvert
      démarre sans assistant, sur une configuration effacée au préalable
- [ ] `retro status` nomme l'état d'amorçage de chaque profil
- [ ] `retro launcher --reamorcer duckstation` suivi d'un lancement : la
      configuration est sauvegardée puis reposée, et l'ordre ne se rejoue pas
      au lancement suivant
- [ ] Le README dit ce que l'amorçage fait et ce qu'il ne fait pas
