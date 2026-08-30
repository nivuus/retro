# La langue de la console — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un jeu multilingue démarre dans la langue de Steam, et changer la
langue dans Steam la change partout, sans commande à taper.

**Architecture:** un axe transverse sur le modèle exact de `render`. Un fichier
`langue.txt` sous la racine locale, relu à chaque jeu. `retro scan` dépose un
fragment de configuration par langue déclarée, et écrit dans le plan **une ligne
par langue de Steam**, replis déjà résolus par Python. Le lanceur lit une ligne
et fusionne le fragment désigné, par le chemin de fusion qui existe déjà.

**Tech Stack:** Python 3.13, `pytest`, TOML (`tomllib`), C# compilé par le
`csc.exe` de Windows. Aucune dépendance nouvelle — le paquet n'en prend pas.

**Spec:** `docs/superpowers/specs/2026-08-30-langue-design.md`

## Global Constraints

- **Français partout** — code, commentaires, messages, noms de tests. Le dépôt
  est en français ; l'anglais y serait une exception non motivée.
- **Aucune dépendance nouvelle.** Ni côté Python, ni côté C#.
- **Aucune valeur de configuration d'émulateur inventée.** Toute clé posée dans
  un `.toml` de profil doit avoir été RELEVÉE sur l'invité. Une valeur fausse
  est ignorée en silence par l'émulateur, donc indiscernable de l'absence. Ce
  plan ne pose **aucune** table de langues : il livre le mécanisme.
- **La langue canonique est le nom que Steam emploie** (`french`, `koreana`,
  `brazilian`, `latam`), jamais un code ISO.
- **Le lanceur ne décide rien.** Toute résolution — langue voulue, repli — est
  faite par Python et écrite dans le plan. Le lanceur lit une ligne.
- **Fichiers courts.** 200 lignes est la ligne de conduite du dépôt.
- **Tests d'abord**, à chaque tâche, et un commit par tâche.
- Lancer la suite avec `python -m pytest` depuis `packages/retro`.

---

### Task 1 : Relever où Steam dit sa langue — AUCUN CODE

**Cette tâche ne produit pas de code. Elle produit un fait mesuré.** Tout le
reste du plan en dépend, et le spec dit explicitement que ce point n'est pas
prouvé.

**Files:**
- Modify: `docs/dettes.md` (ajouter le relevé en fin de fichier)

**Interfaces:**
- Consumes: rien.
- Produces: le nom exact de la source de la langue de Steam, la casse de sa
  valeur, et la liste épinglée des noms de langue. Les tâches 2 et 7 les
  emploient.

- [ ] **Step 1: Relever la clé de registre sur l'invité Windows**

À jouer sur l'invité (`NIVUUS-WIN`), Steam ayant tourné au moins une fois :

```
reg query "HKCU\Software\Valve\Steam" /v Language
```

Noter : la clé existe ou non, le type (`REG_SZ` attendu), et **la valeur
exacte, casse comprise**.

- [ ] **Step 2: Vérifier qu'elle SUIT un changement de langue**

Changer la langue de Steam dans son interface, puis rejouer la même commande
**sans redémarrer Steam**, puis après l'avoir redémarré. Noter à quel moment la
valeur change. C'est ce qui décide si `status` doit avertir « redémarrez Steam
pour que la langue suive ».

- [ ] **Step 3: Épingler la liste des noms de langue**

Depuis la liste que Steam documente (« API language code » / « Steam language
name »), relever **les noms**, pas les codes. Les pièges connus, qui montrent
que cette liste n'est pas devinable : `koreana` (et non `korean`), `brazilian`
(et non `portuguese_br`), `latam`, `schinese`, `tchinese`.

Attendu : une trentaine de noms. Les recopier tels quels — c'est la liste qui
partira dans `langue.py` à la tâche 2.

- [ ] **Step 4: Consigner le relevé**

Ajouter en fin de `docs/dettes.md` une section datée, sur le modèle des
relevés existants : la commande jouée, la sortie obtenue, le comportement au
changement de langue, la liste épinglée, et la date.

**Si la clé n'existe pas :** ne pas improviser. Le spec prévoit la bascule sur
`localconfig.vdf`, mais elle est **par compte** et exige une règle de départage
écrite — cette règle **passe en revue**, elle ne se décide pas ici. Arrêter le
plan et remonter le constat.

- [ ] **Step 5: Commit**

```bash
git add docs/dettes.md
git commit -m "Relevé : où Steam dit sa langue, et sous quels noms"
```

---

### Task 2 : `retro/langue.py` — le module qui ne connaît aucun émulateur

**Files:**
- Create: `retro/langue.py`
- Test: `tests/test_langue.py`

**Interfaces:**
- Consumes: la liste de noms épinglée en tâche 1.
- Produces:
  - `AUTO: str = "auto"`
  - `LANGUES: tuple[str, ...]` — les noms de Steam
  - `VALEURS: tuple[str, ...]` — `(AUTO, *LANGUES)`, ce que la CLI accepte
  - `class LangueError(RuntimeError)`
  - `@dataclasses.dataclass(frozen=True) class Decision: langue: str; motif: str`
  - `resoudre(demandee: str, steam: str) -> Decision` — la langue que la
    CONSOLE veut. `Decision.langue` peut être `""` (Steam muet sous `auto`).
  - `appliquer(voulue: str, declarees: tuple[str, ...], repli: str) -> Decision`
    — ce que CET émulateur pose. `Decision.langue` vaut `""` si `declarees`
    est vide.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_langue.py` :

```python
"""La langue qui s'applique, et pourquoi — jamais l'une sans l'autre."""
import pytest

from retro import langue as langue_mod


def test_une_langue_explicite_se_rend_elle_meme():
    d = langue_mod.resoudre("japanese", steam="french")
    assert d.langue == "japanese"
    assert "à la main" in d.motif


def test_auto_prend_la_langue_de_steam():
    d = langue_mod.resoudre(langue_mod.AUTO, steam="french")
    assert d.langue == "french"
    assert "Steam" in d.motif and "french" in d.motif


def test_auto_sur_un_steam_muet_ne_pretend_pas_savoir():
    """Rendre « english » ici serait un choix silencieux sur une mesure
    absente : le propriétaire croirait Steam en anglais."""
    d = langue_mod.resoudre(langue_mod.AUTO, steam="")
    assert d.langue == ""
    assert "n'a rien dit" in d.motif


def test_auto_ignore_un_steam_qui_dit_n_importe_quoi():
    """Une valeur hors liste n'est pas une langue : la traiter comme telle
    ferait chercher un fragment qui n'existe pas."""
    d = langue_mod.resoudre(langue_mod.AUTO, steam="klingon")
    assert d.langue == ""


def test_une_valeur_inconnue_est_refusee_en_se_nommant():
    with pytest.raises(langue_mod.LangueError) as exc:
        langue_mod.resoudre("frensh", steam="")
    assert "frensh" in str(exc.value)


def test_une_langue_declaree_est_posee_telle_quelle():
    d = langue_mod.appliquer("french", ("english", "french"), "english")
    assert d.langue == "french"
    assert d.motif == ""


def test_une_langue_non_declaree_donne_le_repli_ET_LE_DIT():
    d = langue_mod.appliquer("dutch", ("english", "french"), "english")
    assert d.langue == "english"
    assert "dutch" in d.motif and "english" in d.motif


def test_une_langue_vide_donne_le_repli():
    """Steam muet : le repli s'applique, et le motif ne parle d'aucune
    langue absente — il n'y en avait pas."""
    d = langue_mod.appliquer("", ("english", "french"), "english")
    assert d.langue == "english"


def test_sans_table_declaree_rien_n_est_pose():
    """L'état qui compte : cet émulateur ne suit pas la langue DU TOUT, et
    c'est différent de la suivre mal."""
    d = langue_mod.appliquer("french", (), "")
    assert d.langue == ""
    assert "aucune table" in d.motif


def test_la_liste_porte_les_noms_de_steam_et_non_des_codes_iso():
    """`koreana` et `brazilian` sont les pièges : un code ISO ne trouverait
    jamais la valeur que Steam écrit."""
    assert "koreana" in langue_mod.LANGUES
    assert "brazilian" in langue_mod.LANGUES
    assert "korean" not in langue_mod.LANGUES
    assert "fr" not in langue_mod.LANGUES


def test_auto_n_est_pas_une_langue():
    assert langue_mod.AUTO not in langue_mod.LANGUES
    assert langue_mod.AUTO in langue_mod.VALEURS
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_langue.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'retro.langue'`

- [ ] **Step 3: Écrire `retro/langue.py`**

```python
"""Quelle langue s'applique, et pourquoi.

Ce module ne connaît AUCUN émulateur. Il dit quelle langue la console veut et
laquelle un émulateur donné peut poser ; ce que cette langue signifie dans un
fichier de réglages reste dans le TOML du profil, comme le reste.

LA LANGUE CANONIQUE EST LE NOM QUE STEAM EMPLOIE — « french », « koreana »,
« brazilian » — et non un code ISO. Steam étant la source par défaut, tout
autre choix imposerait une table de correspondance de plus, donc un endroit de
plus où une langue peut se perdre : une entrée manquante y rendrait « langue
inconnue » sur une langue que Steam sait très bien nommer, et le symptôme
serait un émulateur resté en anglais sans qu'aucune ligne ne dise pourquoi.

Il reste UNE traduction, irréductible : du nom Steam vers la valeur que
l'émulateur attend. Elle vit dans le profil, et nulle part ailleurs.

DEUX RÉSOLUTIONS, et elles ne se confondent pas :

`resoudre`  dit ce que la CONSOLE veut — le fichier `langue.txt`, ou Steam.
`appliquer` dit ce qu'UN ÉMULATEUR pose — la langue voulue si son profil la
            déclare, son repli sinon, rien du tout s'il n'a pas de table.

Les séparer est ce qui permet à `retro status` d'écrire « Steam dit dutch » ET
« PPSSPP ne le déclare pas, repli sur english » : une seule fonction rendrait
l'un des deux faits, et le rapport ne saurait pas dire lequel manque.

LE MOTIF N'EST PAS UN ORNEMENT. Comme pour le rendu, chaque résolution rend sa
raison, parce que le rapport doit pouvoir l'écrire. Une langue choisie en
silence donnerait un jeu en anglais que le propriétaire croirait non traduit.
"""
from __future__ import annotations

import dataclasses

AUTO = "auto"

# Les noms de langue de Steam, RELEVÉS et non devinés (voir le relevé daté
# dans docs/dettes.md). Ce ne sont pas des codes ISO, et la liste n'est pas
# déductible : « koreana » n'est pas « korean », « brazilian » n'est pas
# « portuguese_br », et « latam » ne ressemble à rien d'autre.
LANGUES = (
    "arabic", "bulgarian", "schinese", "tchinese", "czech", "danish",
    "dutch", "english", "finnish", "french", "german", "greek",
    "hungarian", "indonesian", "italian", "japanese", "koreana",
    "norwegian", "polish", "portuguese", "brazilian", "romanian",
    "russian", "spanish", "latam", "swedish", "thai", "turkish",
    "ukrainian", "vietnamese",
)

# Ce que la commande accepte. `auto` n'est PAS une langue : il n'a pas de
# fragment à lui, il désigne celle de Steam.
VALEURS = (AUTO, *LANGUES)


class LangueError(RuntimeError):
    """Une langue demandée n'existe pas chez Steam."""


@dataclasses.dataclass(frozen=True)
class Decision:
    """La langue retenue, et pourquoi. `langue` vide veut dire « rien à
    poser », et le motif dit toujours laquelle des deux raisons c'est."""
    langue: str
    motif: str


def resoudre(demandee: str, steam: str) -> Decision:
    """La langue que la CONSOLE veut, et pourquoi.

    Un `steam` hors liste vaut un `steam` vide : une valeur qu'aucun profil ne
    peut déclarer ferait chercher un fragment qui n'existe pas. Mieux vaut le
    repli, qui est déclaré, que l'échec au lancement d'un jeu.
    """
    if demandee not in VALEURS:
        raise LangueError(
            f"langue inconnue : « {demandee} ». Les langues sont celles de "
            f"Steam, par leur nom : {', '.join(LANGUES)} — ou « {AUTO} », qui "
            "suit celle de Steam."
        )
    if demandee != AUTO:
        return Decision(demandee, "posée à la main")
    if steam in LANGUES:
        return Decision(steam, f"« {AUTO} » : Steam dit « {steam} »")
    return Decision(
        "",
        f"« {AUTO} » : Steam n'a rien dit — jamais lancé, ou sa langue n'a "
        "pas pu être lue",
    )


def appliquer(voulue: str, declarees: tuple[str, ...], repli: str) -> Decision:
    """Ce que CET émulateur pose, et pourquoi.

    Sans table déclarée, il ne pose RIEN, et c'est un état à part entière :
    « cet émulateur ne suit pas la langue » n'est pas « il la suit mal ». Les
    confondre ferait chercher une mauvaise valeur là où il n'y en a aucune.
    """
    if not declarees:
        return Decision("", "aucune table de langues déclarée")
    if voulue and voulue in declarees:
        return Decision(voulue, "")
    if voulue:
        return Decision(
            repli, f"« {voulue} » n'est pas déclaré ici, repli sur « {repli} »")
    return Decision(repli, f"repli sur « {repli} »")
```

**Avant d'écrire :** remplacer `LANGUES` par la liste épinglée en tâche 1 si
elle diffère. La liste ci-dessus est celle que Steam documente ; elle doit être
**confirmée**, pas recopiée de confiance.

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `python -m pytest tests/test_langue.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add retro/langue.py tests/test_langue.py
git commit -m "La langue qui s'applique, et pourquoi — le module de résolution"
```

---

### Task 3 : `[bootstrap.langue]` dans les profils, et ses quatre refus

**Files:**
- Modify: `retro/profiles.py` — `Bootstrap` (~ligne 257), `_lire_bootstrap`
  (~ligne 753), `_valider_regimes` (~ligne 950)
- Test: `tests/test_profiles.py`

**Interfaces:**
- Consumes: `retro.langue.LANGUES`, `retro.langue.LangueError` (tâche 2).
- Produces: `Bootstrap.langues: tuple[tuple[str, str], ...]` — couples
  `(nom de langue, fragment)`, triés par nom ; et
  `Bootstrap.langue_repli: str`. Les tâches 4, 5 et 9 les lisent.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_profiles.py` :

```python
# --- la langue : une table par entrée d'amorçage --------------------------

PROFIL_LANGUE = PROFIL + """
[[bootstrap]]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose
; à chaque lancement, ce qu'il a posé une fois, et ce qui vous appartient.
[Main]
Theme = dark
'''
[bootstrap.langue]
repli = "english"
english = '''
[Main]
Language = en
'''
french = '''
[Main]
Language = fr
'''
"""


def test_une_table_de_langues_est_lue_triee(tmp_path):
    profil = _ecrire(tmp_path, PROFIL_LANGUE)
    amorcage = profil.bootstraps[0]
    assert [nom for nom, _ in amorcage.langues] == ["english", "french"]
    assert "Language = fr" in dict(amorcage.langues)["french"]
    assert amorcage.langue_repli == "english"


def test_une_entree_sans_table_de_langues_n_en_porte_aucune(tmp_path):
    profil = _ecrire(tmp_path, PROFIL_IMPOSE)
    assert profil.bootstraps[0].langues == ()
    assert profil.bootstraps[0].langue_repli == ""


def test_une_langue_qui_n_est_pas_un_nom_de_steam_est_refusee(tmp_path):
    """« frensh » ne serait jamais demandé par personne : le fragment serait
    déposé et jamais lu, sans un mot."""
    texte = PROFIL_LANGUE.replace("french = '''", "frensh = '''")
    with pytest.raises(profiles.ProfileError) as exc:
        _ecrire(tmp_path, texte)
    assert "frensh" in str(exc.value)


def test_un_repli_non_declare_est_refuse(tmp_path):
    """La ligne de repli du plan pointerait vers un fragment inexistant, et
    le lanceur crierait devant la télévision, pas ici."""
    texte = PROFIL_LANGUE.replace('repli = "english"', 'repli = "japanese"')
    with pytest.raises(profiles.ProfileError) as exc:
        _ecrire(tmp_path, texte)
    assert "japanese" in str(exc.value)


def test_un_repli_manquant_est_refuse(tmp_path):
    texte = PROFIL_LANGUE.replace('repli = "english"\n', "")
    with pytest.raises(profiles.ProfileError) as exc:
        _ecrire(tmp_path, texte)
    assert "repli" in str(exc.value)


def test_deux_langues_qui_ne_posent_pas_les_memes_cles_sont_refusees(tmp_path):
    """LE PLUS VICIEUX DES QUATRE. La fusion n'écrit que les clés qu'un
    fragment apporte : passer de « french » à « japanese » laisserait
    « Language » en place, l'émulateur lirait deux réglages, et la langue
    refuserait de changer sans que rien n'ait échoué."""
    texte = PROFIL_LANGUE.replace(
        "french = '''\n[Main]\nLanguage = fr\n'''",
        "french = '''\n[Main]\nLangue = fr\n'''")
    with pytest.raises(profiles.ProfileError) as exc:
        _ecrire(tmp_path, texte)
    message = str(exc.value)
    assert "Langue" in message and "Language" in message


def test_un_en_tete_muet_est_refuse_meme_sans_cles_imposees(tmp_path):
    """Les clés de langue SONT des clés imposées. Un profil qui n'a que
    celles-là doit prévenir son propriétaire comme les autres."""
    texte = PROFIL_LANGUE.replace(
        "; Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose\n"
        "; à chaque lancement, ce qu'il a posé une fois, et ce qui vous appartient.",
        "; Écrit par « retro ».")
    with pytest.raises(profiles.ProfileError) as exc:
        _ecrire(tmp_path, texte)
    assert "TROIS catégories" in str(exc.value)


def test_une_cle_de_langue_aussi_dans_content_est_refusee(tmp_path):
    """Le réglage serait décidé à deux endroits, et l'imposé gagnerait
    toujours : la préférence posée ne tiendrait jamais."""
    texte = PROFIL_LANGUE.replace("Theme = dark", "Language = en")
    with pytest.raises(profiles.ProfileError) as exc:
        _ecrire(tmp_path, texte)
    assert "DEUX régimes" in str(exc.value)
```

**Note pour l'implémenteur :** `_ecrire`, `PROFIL` et `PROFIL_IMPOSE` existent
déjà dans ce fichier de tests. Les réemployer, ne pas en créer d'autres.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_profiles.py -k langue -v`
Expected: FAIL — `AttributeError: 'Bootstrap' object has no attribute 'langues'`

- [ ] **Step 3: Étendre `Bootstrap`**

Dans `retro/profiles.py`, à la suite de `enforced: str = ""` :

```python
    # LA LANGUE, par entrée et non par profil. RetroArch le démontre : sa
    # langue d'interface vit dans retroarch.cfg, la langue système que les
    # JEUX lisent est une option de cœur, dans melonDS.opt. Deux fichiers,
    # deux entrées, deux tables. Une table au niveau du profil aurait forcé à
    # choisir un des deux fichiers, et l'autre axe serait resté muet.
    #
    # Les couples (nom de langue Steam, fragment), triés par nom. Un tuple et
    # non un dict : ce dataclass est gelé, et l'ordre doit être stable — le
    # plan écrit une ligne par langue, et un ordre qui bouge ferait différer
    # deux plans identiques.
    #
    # CES CLÉS SONT DES CLÉS IMPOSÉES : elles passent par la fusion, reposées
    # à chaque lancement, et sont donc soumises aux mêmes gardes que
    # `enforced` — c'est ce que `_valider_regimes` reçoit désormais.
    langues: tuple[tuple[str, str], ...] = ()
    # La langue posée quand celle de la console n'est pas déclarée ci-dessus.
    # Vide si et seulement si `langues` est vide.
    langue_repli: str = ""
```

- [ ] **Step 4: Lire et valider la table dans `_lire_bootstrap`**

Ajouter `from retro import langue as langue_mod` en tête de `profiles.py`, puis
une fonction de lecture juste avant `_lire_bootstrap` :

```python
def _lire_langues(path: pathlib.Path, target: str,
                  brut) -> tuple[tuple[tuple[str, str], ...], str]:
    """La table de langues d'UNE entrée : les couples triés, et le repli.

    Les quatre refus portent chacun sur une faute muette. Aucune ne fait
    échouer quoi que ce soit au moment où elle est commise — elles se
    découvrent devant une télévision, sur un jeu qui n'est pas traduit.
    """
    if not brut:
        return (), ""
    repli = brut.get("repli", "")
    fragments = {nom: texte for nom, texte in brut.items() if nom != "repli"}

    inconnues = sorted(n for n in fragments if n not in langue_mod.LANGUES)
    if inconnues:
        raise ProfileError(
            f"{path} [bootstrap.langue] : {', '.join(inconnues)} — ce ne sont "
            "pas des noms de langue de Steam. La langue canonique est le NOM "
            "que Steam emploie (« french », « koreana », « brazilian »), pas "
            "un code ISO : un nom que Steam n'écrit jamais ne serait demandé "
            "par personne, et son fragment serait déposé sans jamais être lu."
        )
    if not fragments:
        raise ProfileError(
            f"{path} [bootstrap.langue] : la table ne déclare aucune langue. "
            "Un bloc vide se lit comme « cet émulateur suit la langue », "
            "alors qu'il n'en pose aucune."
        )
    if repli not in fragments:
        raise ProfileError(
            f"{path} [bootstrap.langue] : 'repli' vaut {repli!r}, qui n'est "
            f"pas déclaré ici. Les langues déclarées sont "
            f"{', '.join(sorted(fragments))}. La ligne de repli du plan "
            "pointerait vers un fragment inexistant, et le lanceur "
            "échouerait au lancement d'un jeu — devant la télévision, loin "
            "d'ici."
        )
    # LES MÊMES CLÉS DANS TOUTES LES LANGUES. La fusion n'écrit que les clés
    # qu'un fragment apporte : une langue qui en poserait une autre laisserait
    # celle de la précédente en place. L'émulateur lirait deux réglages,
    # l'ancien gagnerait, et la langue refuserait de changer sans que rien
    # n'ait échoué.
    attendues = None
    for nom in sorted(fragments):
        cles = frozenset(cles_de(target, fragments[nom]))
        if attendues is None:
            attendues, temoin = cles, nom
            continue
        if cles != attendues:
            ecart = sorted(c for _, c in cles.symmetric_difference(attendues))
            raise ProfileError(
                f"{path} [bootstrap.langue] : « {nom} » et « {temoin} » ne "
                f"posent pas les mêmes clés — {', '.join(ecart)}. Toutes les "
                "langues d'une entrée doivent poser EXACTEMENT les mêmes "
                "clés : la fusion n'écrit que ce qu'un fragment apporte, donc "
                "passer d'une langue à l'autre laisserait la clé de la "
                "précédente en place, et la langue refuserait de changer sans "
                "qu'aucune erreur ne le dise."
            )
    return tuple(sorted(fragments.items())), repli
```

Puis, dans `_lire_bootstrap`, juste avant l'appel à `_valider_regimes` :

```python
    langues, repli = _lire_langues(path, target, brut.get("langue"))
    # LES CLÉS DE LANGUE SONT DES CLÉS IMPOSÉES : elles passent par la même
    # fusion, à chaque lancement. Les soumettre aux mêmes gardes que
    # `enforced` — le chevauchement avec 'content', et l'en-tête qui doit
    # distinguer les trois catégories — sinon un profil qui n'imposerait QUE
    # des langues promettrait à son propriétaire un régime qu'il n'applique
    # pas.
    impose_total = "\n".join(
        [enforced, *(texte for _, texte in langues)])
    if langues:
        # Même raison qu'au-dessus pour `enforced` : une extension inconnue
        # doit faire échouer qui écrit le profil, pas le propriétaire.
        dialecte(target)
    _valider_regimes(path, target, content, impose_total)
    return Bootstrap(target=target, content=content,
                     enforced=enforced.strip(),
                     langues=langues, langue_repli=repli)
```

**Retirer** l'ancien appel `_valider_regimes(path, target, content, enforced)`
et l'ancien `return Bootstrap(...)` qu'il précédait : deux appels feraient
crier deux fois sur la même faute.

- [ ] **Step 5: Lancer toute la suite**

Run: `python -m pytest -q`
Expected: PASS. Les tests existants de `_valider_regimes` doivent passer sans
retouche — `impose_total` vaut exactement `enforced` quand aucune langue n'est
déclarée.

- [ ] **Step 6: Commit**

```bash
git add retro/profiles.py tests/test_profiles.py
git commit -m "Les profils déclarent une table de langues, et quatre refus la gardent"
```

---

### Task 4 : Les fragments de langue déposés par `retro scan`

**Files:**
- Modify: `retro/launcher.py` — près de `enforced_name` (~ligne 124) et
  `fragments_attendus` (~ligne 149)
- Test: `tests/test_launcher.py`

**Interfaces:**
- Consumes: `Bootstrap.langues` (tâche 3).
- Produces: `launcher.langue_name(profile_id: str, index: int, langue: str,
  target: str) -> str`. La tâche 5 l'emploie pour écrire les lignes du plan,
  la tâche 9 pour le contrôle de conformité.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/test_launcher.py` :

```python
# --- les fragments de langue ----------------------------------------------

def test_le_nom_d_un_fragment_de_langue_porte_le_rang_ET_la_langue():
    """Sans le rang, les deux cibles d'un même profil se disputeraient un
    nom ; sans la langue, les fragments s'écraseraient entre eux."""
    assert launcher.langue_name(
        "retroarch", 2, "french", r"{install_dir}\config\melonDS\melonDS.opt"
    ) == "retroarch.langue.2.french.opt"


def test_un_fragment_de_langue_est_attendu_par_langue_declaree():
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n",
        langues=(("english", "[Main]\nLanguage = en\n"),
                 ("french", "[Main]\nLanguage = fr\n")),
        langue_repli="english",
    )
    noms = dict(launcher.fragments_attendus("duckstation", 1, amorcage))
    assert "duckstation.langue.1.english.ini" in noms
    assert "duckstation.langue.1.french.ini" in noms
    assert noms["duckstation.langue.1.french.ini"] == "[Main]\nLanguage = fr\n"


def test_un_fragment_de_langue_se_termine_par_un_saut_de_ligne():
    """Le contrôle de conformité compare à l'octet près : sans ce saut, il
    crierait au loup sur un fragment tout neuf."""
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n",
        langues=(("english", "[Main]\nLanguage = en"),),
        langue_repli="english",
    )
    noms = dict(launcher.fragments_attendus("duckstation", 1, amorcage))
    assert noms["duckstation.langue.1.english.ini"].endswith("\n")


def test_une_entree_sans_langues_n_attend_aucun_fragment_de_langue():
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n",
    )
    noms = [n for n, _ in launcher.fragments_attendus("duckstation", 1, amorcage)]
    assert not [n for n in noms if ".langue." in n]
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_launcher.py -k langue -v`
Expected: FAIL — `AttributeError: module 'retro.launcher' has no attribute 'langue_name'`

- [ ] **Step 3: Écrire `langue_name` et étendre `fragments_attendus`**

Dans `retro/launcher.py`, à la suite de `IMPOSE = "impose"` :

```python
LANGUE = "langue"
```

Puis, après `bootstrap_name` :

```python
def langue_name(profile_id: str, index: int, langue: str, target: str) -> str:
    """Le nom du fragment d'UNE langue, déposé à côté des plans.

    Le rang ET la langue, pour deux raisons distinctes : sans le rang, les
    deux cibles d'un même profil se disputeraient un nom de fichier — c'est ce
    qui a fait indicer `enforced_name` ; sans la langue, les fragments
    s'écraseraient l'un l'autre et la console poserait la dernière langue
    écrite, quelle que soit celle demandée.

    L'extension vient de la cible BRUTE, comme partout ailleurs : c'est elle
    qui dit le format, et la substitution ne la change pas.
    """
    return f"{profile_id}.{LANGUE}.{index}.{langue}{_suffixe(target)}"
```

Puis, dans `fragments_attendus`, avant le `return` :

```python
    # Un fichier par langue déclarée. Le lanceur en choisira UN, désigné par
    # le plan ; les autres restent sur le disque, prêts pour le jour où la
    # langue de Steam changera — c'est ce qui rend le changement de langue
    # gratuit, sans resynchronisation.
    for nom, texte in amorcage.langues:
        # Le saut de ligne final, pour la raison exacte du fragment imposé :
        # le contrôle compare à l'octet près.
        fragments.append((langue_name(profile_id, index, nom, amorcage.target),
                          texte.strip() + "\n"))
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `python -m pytest tests/test_launcher.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retro/launcher.py tests/test_launcher.py
git commit -m "Un fragment de configuration par langue déclarée, déposé par le scan"
```

---

### Task 5 : Les lignes du plan — Python résout, le lanceur lira

**Files:**
- Modify: `retro/launcher.py` — `plan_systeme` (~ligne 217, dans la boucle
  `for rang, amorcage in enumerate(bootstraps, 1)`)
- Test: `tests/test_launcher.py`

**Interfaces:**
- Consumes: `langue_name` (tâche 4), `langue.appliquer` et `langue.LANGUES`
  (tâche 2), `Bootstrap.langues` / `.langue_repli` (tâche 3).
- Produces: les clés de plan `bootstrap_langue.<rang>.<langue>` (une par nom de
  `langue.LANGUES`) et `bootstrap_langue.<rang>.defaut`. La tâche 7 les lit
  côté C#.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def _plan_avec_langues():
    """Un plan écrit pour une entrée qui déclare english et french."""
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n",
        langues=(("english", "[Main]\nLanguage = en\n"),
                 ("french", "[Main]\nLanguage = fr\n")),
        langue_repli="english",
    )
    systeme = profiles.System(id="psx", name="PlayStation", launch="{rom}")
    texte = launcher.plan_systeme(
        "duckstation", systeme, "E:\\D\\duck.exe", "E:\\D",
        plan_dir="E:\\_launcher\\systems", bootstraps=(amorcage,))
    return dict(l.split("=", 1) for l in texte.splitlines()
                if "=" in l and not l.startswith("#"))


def test_le_plan_porte_une_ligne_par_langue_de_steam():
    """TOUTES les langues, pas seulement celles que le profil déclare : le
    lanceur doit trouver une ligne quoi que Steam dise, sinon `Valeur()`
    lèverait sur une langue parfaitement légitime."""
    l = _plan_avec_langues()
    for nom in langue_mod.LANGUES:
        assert f"bootstrap_langue.1.{nom}" in l


def test_une_langue_declaree_pointe_vers_son_propre_fragment():
    l = _plan_avec_langues()
    assert l["bootstrap_langue.1.french"] == (
        "E:\\_launcher\\systems\\duckstation.langue.1.french.ini")


def test_une_langue_non_declaree_pointe_vers_LE_REPLI_deja_resolu():
    """C'est tout le principe : Python résout, le lanceur lit une ligne. Un
    lanceur qui calculerait le repli pourrait en choisir un autre que celui
    que `retro status` annonce, et les deux ne se contrediraient jamais à
    voix haute."""
    l = _plan_avec_langues()
    assert l["bootstrap_langue.1.dutch"] == (
        "E:\\_launcher\\systems\\duckstation.langue.1.english.ini")


def test_le_plan_porte_un_defaut_pour_un_steam_muet():
    """Le seul cas que Python ne peut pas pré-résoudre. Une clé absente
    resterait une faute du plan, et `Valeur()` lèverait devant la
    télévision."""
    l = _plan_avec_langues()
    assert l["bootstrap_langue.1.defaut"] == (
        "E:\\_launcher\\systems\\duckstation.langue.1.english.ini")


def test_une_entree_sans_table_n_ecrit_aucune_ligne_de_langue():
    """Sur le modèle de `bootstrap_count=0` : écrire trente lignes vides
    ferait boucler le lanceur sur du rien."""
    amorcage = profiles.Bootstrap(
        target=r"%USERPROFILE%\Documents\DuckStation\settings.ini",
        content="; Écrit par « retro »\n")
    systeme = profiles.System(id="psx", name="PlayStation", launch="{rom}")
    texte = launcher.plan_systeme(
        "duckstation", systeme, "E:\\D\\duck.exe", "E:\\D",
        plan_dir="E:\\_launcher\\systems", bootstraps=(amorcage,))
    assert "bootstrap_langue." not in texte
```

**Note :** ajouter `from retro import langue as langue_mod` en tête de
`tests/test_launcher.py`. Si la construction de `profiles.System` ci-dessus ne
correspond pas aux champs obligatoires du dépôt, réemployer le constructeur que
les tests voisins de ce fichier utilisent déjà — ne pas en inventer un.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_launcher.py -k langue -v`
Expected: FAIL — `KeyError: 'bootstrap_langue.1.french'`

- [ ] **Step 3: Écrire les lignes dans `plan_systeme`**

Dans la boucle `for rang, amorcage in enumerate(bootstraps, 1)`, après la
ligne `f"bootstrap_enforced.{rang}={impose}"` :

```python
        # LA LANGUE : une ligne par langue de Steam, replis DÉJÀ RÉSOLUS.
        #
        # C'est la transposition exacte des lignes `auto_<classe>` du rendu, et
        # pour la même raison : le lanceur classe ce qu'il mesure et lit la
        # réponse, il ne rejoue aucune décision, donc il ne peut pas en prendre
        # une autre. Un lanceur qui calculerait le repli pourrait en choisir un
        # que `retro status` n'annonce pas — et deux juges qui se contredisent
        # ne se contredisent jamais à voix haute.
        #
        # TOUTES les langues, y compris celles que ce profil ne déclare pas :
        # le lanceur doit trouver une ligne quoi que Steam dise, sinon
        # `Valeur()` lèverait sur une langue parfaitement légitime.
        #
        # `defaut` couvre le seul cas que Python ne peut pas pré-résoudre :
        # Steam muet — jamais lancé, valeur absente, lecture impossible.
        if amorcage.langues:
            declarees = tuple(nom for nom, _ in amorcage.langues)
            for voulue in (*langue_mod.LANGUES, ""):
                posee = langue_mod.appliquer(
                    voulue, declarees, amorcage.langue_repli).langue
                cle = voulue or "defaut"
                lignes.append(
                    f"bootstrap_langue.{rang}.{cle}={plan_dir}\\"
                    f"{langue_name(profile_id, rang, posee, amorcage.target)}")
```

Ajouter `from retro import langue as langue_mod` en tête de `retro/launcher.py`.

- [ ] **Step 4: Lancer toute la suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retro/launcher.py tests/test_launcher.py
git commit -m "Le plan porte une ligne par langue, replis déjà résolus"
```

---

### Task 6 : `langue.txt`, voisin de `mode.txt`

**Files:**
- Modify: `retro/launcher.py` — près de `MODE` (~ligne 45), `lire_mode` et
  `ecrire_mode` (~lignes 511-538)
- Test: `tests/test_launcher.py`

**Interfaces:**
- Consumes: `langue.VALEURS`, `langue.AUTO`, `langue.LangueError` (tâche 2).
- Produces: `launcher.LANGUE_FICHIER = "langue.txt"`,
  `launcher.lire_langue(emulation_root_local) -> str`,
  `launcher.ecrire_langue(emulation_root_local, langue: str) -> pathlib.Path`.
  Les tâches 8 et 9 les emploient.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_sans_fichier_la_langue_vaut_auto(tmp_path):
    """Le défaut est de suivre Steam : c'est ce que le propriétaire a
    choisi, et un défaut figé ferait mentir la commande qui l'affiche."""
    assert launcher.lire_langue(tmp_path) == langue_mod.AUTO


def test_une_langue_posee_se_relit(tmp_path):
    launcher.ecrire_langue(tmp_path, "japanese")
    assert launcher.lire_langue(tmp_path) == "japanese"


def test_un_fichier_illisible_retombe_sur_auto(tmp_path):
    """Un fichier abîmé ne doit pas empêcher un jeu de se lancer : `auto`
    est le comportement par défaut, pas un aveu."""
    dossier = launcher.local_dir(tmp_path)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / launcher.LANGUE_FICHIER).write_text("n'importe quoi\n",
                                                   encoding="utf-8")
    assert launcher.lire_langue(tmp_path) == langue_mod.AUTO


def test_une_langue_inconnue_est_refusee_a_l_ecriture(tmp_path):
    """Refusée à l'écriture, pas ignorée à la lecture : une coquille posée
    en silence ferait croire à un réglage appliqué."""
    with pytest.raises(langue_mod.LangueError):
        launcher.ecrire_langue(tmp_path, "frensh")


def test_auto_s_ecrit_comme_les_autres(tmp_path):
    launcher.ecrire_langue(tmp_path, "french")
    launcher.ecrire_langue(tmp_path, langue_mod.AUTO)
    assert launcher.lire_langue(tmp_path) == langue_mod.AUTO
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_launcher.py -k langue -v`
Expected: FAIL — `AttributeError: module 'retro.launcher' has no attribute 'lire_langue'`

- [ ] **Step 3: Écrire les deux fonctions**

À la suite de `MODE = "mode.txt"` :

```python
LANGUE_FICHIER = "langue.txt"
```

Puis, après `ecrire_mode` :

```python
def lire_langue(emulation_root_local) -> str:
    """La langue choisie par le propriétaire, ou `auto` à défaut.

    Dans un fichier, PAS dans les options de lancement de Steam, et pour la
    raison exacte qui y a mis le mode de rendu : l'identifiant d'un raccourci
    dérive de ses options. Écrire la langue là ferait changer d'identifiant à
    toute la bibliothèque à chaque changement de langue, et tout l'artwork
    serait à retélécharger pour un réglage.
    """
    fichier = local_dir(emulation_root_local) / LANGUE_FICHIER
    try:
        valeur = fichier.read_text(encoding="utf-8").strip()
    except OSError:
        return langue_mod.AUTO
    return valeur if valeur in langue_mod.VALEURS else langue_mod.AUTO


def ecrire_langue(emulation_root_local, langue: str) -> pathlib.Path:
    """Pose la langue. Le lanceur la relit à chaque jeu : rien à
    resynchroniser, aucune entrée Steam touchée, aucune vignette à reprendre.

    Refusée ICI si elle est inconnue, et non ignorée à la lecture : une
    coquille posée en silence ferait croire à un réglage appliqué.
    """
    if langue not in langue_mod.VALEURS:
        raise langue_mod.LangueError(
            f"langue inconnue : « {langue} ». Les langues sont celles de "
            f"Steam, par leur nom, ou « {langue_mod.AUTO} »."
        )
    dossier = local_dir(emulation_root_local)
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / LANGUE_FICHIER
    fichier.write_text(langue + "\n", encoding="utf-8")
    return fichier
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `python -m pytest tests/test_launcher.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retro/launcher.py tests/test_launcher.py
git commit -m "langue.txt, relu à chaque jeu — voisin de mode.txt"
```

---

### Task 7 : Le lanceur C# — lire Steam, fusionner, laisser un témoin

**Files:**
- Modify: `retro/data/launcher/retro-launch.cs` — près de `ModeChoisi`
  (~ligne 1472) et dans `AmorcerUne` (~ligne 386)
- Test: `tests/test_launcher.py`

**Interfaces:**
- Consumes: les clés `bootstrap_langue.<rang>.<langue>` et
  `bootstrap_langue.<rang>.defaut` (tâche 5), `langue.txt` (tâche 6).
- Produces: le témoin `langue-vue.txt` sous la racine locale, trois lignes
  `steam=`, `langue=`, `motif=`. La tâche 9 le lit.

**Rappel du contexte, qui change la façon de tester :** il n'existe **aucun
compilateur C# sur l'hôte** — ni `csc`, ni `mcs`, ni `mono`, ni `dotnet` (voir
D7 dans `docs/dettes.md`). Ce `.cs` ne peut donc être validé que par des tests
Python qui **lisent la source** et exigent qu'elle porte ce qu'il faut. C'est
le motif qu'emploient déjà `test_le_lanceur_substitue_l_identifiant_du_jeu` et
ses voisins ; le reprendre à l'identique.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# --- la langue, côté lanceur : la source, faute de compilateur ------------

def _source_du_lanceur() -> str:
    """La SOURCE, faute de compilateur C# sur cette machine — c'est le motif
    qu'emploient déjà les tests voisins de ce fichier."""
    return (launcher.SOURCES / launcher.SOURCE).read_text(encoding="utf-8-sig")


def test_le_lanceur_lit_le_fichier_de_langue():
    src = _source_du_lanceur()
    assert launcher.LANGUE_FICHIER in src, (
        "le lanceur ne lit pas langue.txt : la commande « retro langue » "
        "poserait un fichier que personne ne lit")


def test_le_lanceur_lit_la_langue_de_steam_dans_le_registre():
    """Le relevé de la tâche 1 dit où. Si ce test doit changer, c'est que
    le relevé a dit autre chose — et alors le SPEC change aussi."""
    src = _source_du_lanceur()
    assert "Software\\\\Valve\\\\Steam" in src or "Software\\Valve\\Steam" in src
    assert "\"Language\"" in src


def test_le_lanceur_cherche_la_ligne_de_langue_du_plan():
    src = _source_du_lanceur()
    assert "bootstrap_langue." in src, (
        "sans cette clé, le lanceur ne trouverait aucun fragment de langue "
        "et n'en poserait aucun, en silence")


def test_le_lanceur_retombe_sur_defaut_quand_steam_est_muet():
    src = _source_du_lanceur()
    assert "\"defaut\"" in src, (
        "un Steam muet ferait chercher « bootstrap_langue.1. » sans langue, "
        "et Valeur() lèverait devant la télévision")


def test_le_lanceur_ne_porte_AUCUN_nom_de_langue_en_dur():
    """Le repli est résolu par Python et écrit dans le plan. Un nom de langue
    codé dans le lanceur serait forcément une décision qu'il prend seul — un
    « si la langue est inconnue, mettre english » —, et il pourrait alors
    poser autre chose que ce que `retro status` annonce. Deux juges qui se
    contredisent ne se contredisent jamais à voix haute."""
    src = _source_du_lanceur().lower()
    en_dur = [nom for nom in langue_mod.LANGUES if '"' + nom + '"' in src]
    assert not en_dur, (
        f"le lanceur porte {en_dur} en dur : la résolution doit rester côté "
        "Python, qui écrit une ligne de plan par langue")


def test_le_lanceur_ecrit_le_temoin_de_langue():
    """`retro status` tourne AUSSI sur l'hôte, qui n'atteint pas le registre
    de l'invité. Sans témoin, le rapport ne pourrait rien dire de la langue
    de Steam — ou dirait autre chose selon la machine qui l'exécute."""
    src = _source_du_lanceur()
    assert launcher.TEMOIN_LANGUE in src


def test_la_langue_est_fusionnee_APRES_les_cles_imposees():
    """L'ordre est fixé pour que deux exécutions rendent le même fichier à
    l'octet près, et pour que le journal se lise."""
    src = _source_du_lanceur()
    impose = src.index("bootstrap_enforced.")
    langue = src.index("bootstrap_langue.")
    assert impose < langue
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_launcher.py -k "langue and lanceur" -v`
Expected: FAIL — les chaînes ne sont pas dans la source.

- [ ] **Step 3: Ajouter la constante du témoin côté Python**

Dans `retro/launcher.py`, à la suite de `LANGUE_FICHIER` :

```python
# Ce que le lanceur a VU chez Steam, écrit à chaque jeu. `retro status`
# tourne aussi sur l'hôte, qui n'atteint pas le registre de l'invité : sans ce
# témoin, le rapport rendrait la langue de Steam sur Windows et autre chose
# ailleurs — deux rapports contradictoires sur la même console.
TEMOIN_LANGUE = "langue-vue.txt"
```

- [ ] **Step 4: Écrire le C#**

Dans `retro/data/launcher/retro-launch.cs`, à côté de `ModeChoisi()` :

```csharp
    // La langue que la console veut. Meme forme que ModeChoisi() : un fichier
    // relu a chaque jeu, et un defaut qui ne pretend rien.
    static string LangueChoisie()
    {
        try
        {
            string m = File.ReadAllText(Path.Combine(dossier, "langue.txt"),
                                        Encoding.UTF8).Trim();
            if (m.Length > 0) return m;
        }
        catch (Exception) { }
        return "auto";
    }

    // Ce que STEAM dit, brut. Chaine vide si on n'a rien pu lire — jamais une
    // langue supposee : « english » invente ici serait indiscernable d'un
    // Steam reellement en anglais, et le proprietaire chercherait au mauvais
    // endroit.
    //
    // LE REGISTRE ET NON localconfig.vdf : ce dernier est PAR COMPTE, et la
    // console synchronise tous les comptes locaux. Deux comptes peuvent donc
    // porter deux langues, et il n'existe aucune regle honnete pour les
    // departager. Le registre porte la valeur du client qui tourne : une
    // seule, celle que le proprietaire voit a l'ecran.
    static string LangueDeSteam()
    {
        try
        {
            using (RegistryKey k = Registry.CurrentUser.OpenSubKey(
                       @"Software\Valve\Steam"))
            {
                if (k == null) return "";
                object v = k.GetValue("Language");
                return v == null ? "" : v.ToString().Trim().ToLowerInvariant();
            }
        }
        catch (Exception) { return ""; }
    }

    // La langue effective, et le fragment qui la porte pour CETTE entree.
    // Rend "" s'il n'y a pas de ligne de langue dans le plan : cette entree
    // ne declare aucune table, et il n'y a rien a poser.
    //
    // AUCUN REPLI N'EST CALCULE ICI. Le plan porte une ligne par langue, replis
    // deja resolus par Python : on lit une ligne, on ne decide pas. Un lanceur
    // qui deciderait pourrait choisir autre chose que ce que « retro status »
    // annonce, et les deux ne se contrediraient jamais a voix haute.
    static string FragmentDeLangue(Dictionary<string, string> p, int n,
                                   string langue)
    {
        string cle = "bootstrap_langue." + n.ToString(CultureInfo.InvariantCulture)
                   + "." + (langue.Length == 0 ? "defaut" : langue);
        string chemin;
        return p.TryGetValue(cle, out chemin) ? chemin : "";
    }
```

Ajouter `using Microsoft.Win32;` en tête du fichier — c'est dans `mscorlib`,
donc aucune référence supplémentaire à passer à `csc.exe`.

Dans `AmorcerUne`, **après** le bloc qui fusionne `bootstrap_enforced` :

```csharp
        // LA LANGUE, fusionnee APRES les cles imposees. L'ordre est sans effet
        // sur le resultat — les deux fragments ne partagent aucune cle, une
        // garde du profil le refuse — mais il est fixe pour que le journal se
        // lise et que deux executions rendent le meme fichier a l'octet pres.
        string voulue = LangueChoisie();
        if (voulue == "auto") voulue = LangueDeSteam();
        string fragmentLangue = FragmentDeLangue(p, n, voulue);
        if (fragmentLangue.Length > 0)
        {
            // Le meme chemin de fusion que les cles imposees : marques,
            // sauvegarde horodatee, et aucune reecriture si la cible porte
            // deja ces valeurs.
            quelqueChosePose |= FusionnerDepuis(cible, fragmentLangue);
            Noter("langue : " + profil + " -> " + cible + " (" + voulue + ")");
        }
```

**Note pour l'implémenteur :** `FusionnerDepuis` est un nom de commodité. La
fusion des clés imposées existe déjà dans `AmorcerUne` (lecture de la cible,
`Fusionner(...)`, comparaison `SansMarques`, `EcrireAtomique`). **Extraire ce
bloc en une méthode et l'appeler deux fois** — une fois pour l'imposé, une fois
pour la langue. Ne pas le recopier : deux copies divergeraient, et la seconde
poserait la langue sans sauvegarde le jour où la première en gagnerait une.

Enfin, le témoin, écrit une fois par lancement (pas par entrée) :

```csharp
    // Ce qu'on a vu chez Steam, pour que « retro status » puisse le dire
    // depuis l'hote — qui n'atteint pas ce registre. Trois lignes, ecrasees a
    // chaque jeu : c'est un temoin, pas un journal.
    static void EcrireTemoinLangue(string steam, string effective, string motif)
    {
        try
        {
            File.WriteAllText(
                Path.Combine(dossier, "langue-vue.txt"),
                "steam=" + steam + "\n"
                + "langue=" + effective + "\n"
                + "motif=" + motif + "\n",
                new UTF8Encoding(false));
        }
        catch (Exception) { }   // un temoin manquant ne doit jamais empecher un jeu
    }
```

L'appeler depuis le point où le lancement est déjà décidé, avec la langue lue
et la valeur brute de Steam.

- [ ] **Step 5: Lancer toute la suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add retro/launcher.py retro/data/launcher/retro-launch.cs tests/test_launcher.py
git commit -m "Le lanceur lit la langue de Steam, fusionne son fragment, laisse un témoin"
```

---

### Task 8 : La commande `retro langue`

**Files:**
- Modify: `retro/cli.py` — près de `_cmd_render` (~ligne 790) et du parseur
  `render` (~ligne 900)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `launcher.lire_langue` / `ecrire_langue` (tâche 6),
  `langue.VALEURS` (tâche 2).
- Produces: la sous-commande `langue`, options `--emulation-root-local`
  (requise) et `--langue`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
def test_langue_sans_option_affiche_auto(tmp_path, capsys):
    assert cli.main(["langue", "--emulation-root-local", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "auto"


def test_langue_pose_la_valeur_et_la_confirme(tmp_path, capsys):
    (tmp_path / launcher.DIR).mkdir(parents=True)
    (tmp_path / launcher.DIR / launcher.EXE).write_bytes(b"MZ")
    assert cli.main(["langue", "--emulation-root-local", str(tmp_path),
                     "--langue", "french"]) == 0
    assert launcher.lire_langue(tmp_path) == "french"
    assert "french" in capsys.readouterr().out


def test_langue_posee_sans_lanceur_avertit_et_rend_1(tmp_path, capsys):
    """La langue est bien posée, mais personne ne la lira. Le taire ferait
    croire au propriétaire que son choix s'applique."""
    code = cli.main(["langue", "--emulation-root-local", str(tmp_path),
                     "--langue", "french"])
    assert code == 1
    assert "retro launcher" in capsys.readouterr().err


def test_une_langue_inconnue_est_refusee_par_la_commande(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["langue", "--emulation-root-local", str(tmp_path),
                  "--langue", "frensh"])
```

**Note :** aligner ces tests sur la façon dont les tests voisins de
`tests/test_cli.py` appellent `cli.main` et lisent la sortie — le motif exact
de `_cmd_render` est le bon modèle.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_cli.py -k langue -v`
Expected: FAIL — `SystemExit: 2`, argparse ne connaît pas la sous-commande.

- [ ] **Step 3: Écrire la commande**

Après `_cmd_render` :

```python
def _cmd_langue(args) -> int:
    """Lit ou pose la langue de la console.

    Même forme que le mode de rendu, et même propriété : la langue vit dans un
    fichier que le lanceur relit à CHAQUE jeu. En changer ne touche aucune
    option de raccourci, donc aucun identifiant Steam, donc aucune vignette.
    Rien à resynchroniser.

    Ce qui EXIGE un « retro scan », en revanche, c'est l'ajout d'une table de
    langues à un profil : les fragments sont déposés par le scan.
    """
    racine = pathlib.Path(args.emulation_root_local)
    if args.langue is None:
        print(launcher_mod.lire_langue(racine))
        return 0
    try:
        fichier = launcher_mod.ecrire_langue(racine, args.langue)
    except (langue_mod.LangueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"langue : {args.langue} ({fichier})")
    if not launcher_mod.est_installe(racine):
        print("le lanceur n'est pas installé : cette langue ne sera lue par "
              "personne tant qu'il ne l'est pas (« retro launcher »).",
              file=sys.stderr)
        return 1
    return 0
```

À côté du parseur `render` :

```python
    lng = sous.add_parser(
        "langue",
        help="lire ou poser la langue de la console (auto suit celle de Steam)")
    lng.add_argument("--emulation-root-local", required=True)
    lng.add_argument("--langue", choices=langue_mod.VALEURS, default=None,
                     help="sans --langue, affiche la langue courante")
    lng.set_defaults(func=_cmd_langue)
```

Ajouter `from retro import langue as langue_mod` en tête de `retro/cli.py`.

- [ ] **Step 4: Lancer toute la suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retro/cli.py tests/test_cli.py
git commit -m "« retro langue » : lire ou poser la langue de la console"
```

---

### Task 9 : La section « Langue » de `retro status`

**Files:**
- Modify: `retro/status.py` — dataclasses en tête, près de `etat_rendu`
  (~ligne 709), `build_report` (~ligne 935), `_lignes_rendu` (~ligne 1117)
- Modify: `retro/launcher.py` — lecture du témoin
- Modify: `retro/cli.py` — passer la langue et le témoin à `build_report`
- Test: `tests/test_status.py`

**Interfaces:**
- Consumes: `Bootstrap.langues` / `.langue_repli` (tâche 3),
  `langue.resoudre` / `appliquer` (tâche 2), `launcher.TEMOIN_LANGUE`
  (tâche 7).
- Produces: `launcher.lire_temoin_langue(emulation_root_local) -> dict[str, str] | None`,
  `status.ProfilLangue`, `status.etat_langues(profils, voulue) -> list[ProfilLangue]`,
  et les paramètres `langue=` / `langue_temoin=` de `build_report`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# --- la section Langue -----------------------------------------------------

def test_un_temoin_absent_ne_fait_supposer_aucune_langue(tmp_path):
    """Le seul état sous lequel l'absence n'accuse personne : aucun jeu n'a
    encore été lancé depuis que ce mécanisme existe."""
    assert launcher.lire_temoin_langue(tmp_path) is None


def test_le_temoin_se_relit(tmp_path):
    dossier = launcher.local_dir(tmp_path)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / launcher.TEMOIN_LANGUE).write_text(
        "steam=french\nlangue=french\nmotif=« auto » : Steam dit « french »\n",
        encoding="utf-8")
    temoin = launcher.lire_temoin_langue(tmp_path)
    assert temoin["steam"] == "french"
    assert temoin["langue"] == "french"


def test_un_profil_sans_table_est_NOMME_et_non_tu(profils_avec_langues):
    """L'état qui compte. Sans lui, un émulateur qui ne suit pas la langue
    serait indiscernable d'un émulateur qui la suit mal — et les deux se
    lisent à l'écran de la même façon : un jeu en anglais."""
    etats = status.etat_langues(profils_avec_langues, voulue="french")
    muets = [e for e in etats if not e.declared]
    assert muets, "aucun profil muet n'a été nommé"


def test_un_repli_est_nomme_avec_sa_raison(profils_avec_langues):
    etats = status.etat_langues(profils_avec_langues, voulue="dutch")
    replis = [e for e in etats if e.declared and e.motif]
    assert replis
    assert "dutch" in replis[0].motif and "english" in replis[0].motif


def test_le_rapport_ecrit_la_valeur_brute_de_steam():
    """Même quand elle ne sert pas : la langue est posée à la main, Steam dit
    autre chose, et le rapport doit porter les DEUX. C'est ce qui rend le
    relevé du registre vérifiable depuis le canapé — sans quoi il n'existe
    aucun moyen de savoir si le lanceur lit vraiment quelque chose."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        langue="japanese",
        langue_temoin={"steam": "french", "langue": "japanese",
                       "motif": "posée à la main"}))
    assert "japanese" in texte
    assert "french" in texte, (
        "le rapport tait ce que Steam disait : rien ne permet alors de "
        "vérifier que le lanceur lit sa langue")


def test_sans_temoin_le_rapport_ne_suppose_aucune_langue_de_steam():
    """Le seul état sous lequel une absence n'accuse personne : aucun jeu
    n'a encore été lancé. Le confondre avec « Steam n'a rien dit » enverrait
    chercher une panne là où il n'y a qu'une console qui n'a pas joué."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        langue="auto", langue_temoin=None))
    assert "aucun jeu" in texte.lower()


def test_le_rapport_dit_que_ces_cles_sont_reposees_a_chaque_lancement():
    """La contrepartie de la décision 4 du spec. Le propriétaire qui change
    sa langue dans DuckStation et la voit revenir doit lire POURQUOI, et le
    rapport est le seul endroit où il peut le lire."""
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[], bios_root=pathlib.Path("/BIOS"),
        langue="french", langue_temoin={"steam": "french"}))
    assert "chaque lancement" in texte
```

**Note pour l'implémenteur :** `profils_avec_langues` est une fixture à créer
dans ce fichier, sur le modèle des fixtures de profils qui y existent déjà :
un profil dont l'entrée d'amorçage déclare `english` et `french` avec
`repli = "english"`, et un profil dont l'entrée n'a aucune table. Les appels à
`status.build_report` ci-dessus suivent le motif exact des tests voisins
(`install_dirs`, `emulation_root`, `systems`, `bios_status`, `bios_root`
obligatoires) ; ne pas en inventer un autre.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `python -m pytest tests/test_status.py -k langue -v`
Expected: FAIL — `AttributeError: module 'retro.status' has no attribute 'etat_langues'`

- [ ] **Step 3: Lire le témoin, côté `launcher.py`**

```python
def lire_temoin_langue(emulation_root_local) -> dict[str, str] | None:
    """Ce que le lanceur a vu chez Steam au dernier jeu, ou None.

    `None` veut dire « aucun jeu n'a été lancé depuis que ce mécanisme
    existe », et c'est le seul état sous lequel une absence n'accuse
    personne. Le confondre avec « Steam n'a rien dit » ferait chercher une
    panne là où il n'y a qu'une console qui n'a pas encore joué.
    """
    fichier = local_dir(emulation_root_local) / TEMOIN_LANGUE
    try:
        texte = fichier.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return dict(l.split("=", 1) for l in texte.splitlines() if "=" in l)
```

- [ ] **Step 4: Écrire `ProfilLangue` et `etat_langues`**

Dans `retro/status.py`, avec les autres dataclasses :

```python
@dataclasses.dataclass(frozen=True)
class ProfilLangue:
    """Ce qu'UN émulateur fait de la langue de la console.

    Trois états, et le troisième est celui qui compte : `declared=False` dit
    « cet émulateur ne suit pas la langue DU TOUT », ce qui n'est pas « il la
    suit mal ». Les confondre ferait chercher une mauvaise valeur là où il n'y
    en a aucune.
    """
    profile_id: str
    cible: str
    declared: bool
    langue: str = ""
    motif: str = ""
```

```python
def etat_langues(profils: dict, voulue: str) -> list[ProfilLangue]:
    """Ce que chaque entrée d'amorçage pose comme langue, et pourquoi.

    Par ENTRÉE et non par profil : RetroArch en a deux, sa langue d'interface
    et celle que les jeux lisent, et un rapport par profil en cacherait une.
    """
    etats = []
    for pid in sorted(profils):
        for amorcage in profils[pid].bootstraps:
            declarees = tuple(nom for nom, _ in amorcage.langues)
            decision = langue_mod.appliquer(
                voulue, declarees, amorcage.langue_repli)
            etats.append(ProfilLangue(
                profile_id=pid, cible=amorcage.target,
                declared=bool(declarees),
                langue=decision.langue,
                motif=decision.motif if declarees else "",
            ))
    return etats
```

- [ ] **Step 5: Câbler dans `build_report` et le rendu**

Ajouter à `build_report` les paramètres `langue: str = ""` et
`langue_temoin: dict | None = None`, les porter sur `Report`, et écrire
`_lignes_langue(report)` sur le modèle exact de `_lignes_rendu` :

- la langue effective et son motif, depuis `langue_mod.resoudre(langue,
  steam=temoin.get("steam", ""))` ;
- **la valeur brute du témoin, même inutilisée** — et « aucun jeu lancé
  depuis » quand `langue_temoin is None` ;
- une ligne par `ProfilLangue` : la langue posée, le repli et sa raison, ou
  « aucune table déclarée » ;
- **une ligne de rappel** disant que ces clés sont reposées à chaque
  lancement, sans quoi la contrepartie de la décision 4 n'est écrite nulle
  part.

L'insérer dans le corps du rapport via `_section("Langue", lignes, "…")`, et
passer depuis `retro/cli.py` `langue=launcher_mod.lire_langue(racine)` et
`langue_temoin=launcher_mod.lire_temoin_langue(racine)` là où `render_mode`
est déjà passé.

- [ ] **Step 6: Lancer toute la suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add retro/status.py retro/launcher.py retro/cli.py tests/test_status.py
git commit -m "retro status dit la langue, sa source, et ce que chaque émulateur en fait"
```

---

### Task 10 : Le README, et ce que le mécanisme ne fait pas encore

**Files:**
- Modify: `README.md`
- Modify: `docs/dettes.md`

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: rien de logiciel.

- [ ] **Step 1: Décrire `retro langue` dans la liste des commandes**

Dans la liste à puces des commandes du `README.md`, après `retro render`, sur
le même ton : ce qu'elle fait, que `auto` suit Steam, que changer de langue ne
retélécharge aucune vignette, et que ces clés sont **reposées à chaque
lancement** — la promesse « un émulateur que vous avez réglé vous appartient »
gagne ici une exception, et un README qui la tairait serait le pire endroit
où la taire.

- [ ] **Step 2: Écrire ce qui n'est PAS fait**

Ajouter, dans la même veine que « Le classement automatique en catégories […]
est **prévu et pas encore actif** » :

> Le mécanisme est en place et testé, mais **aucun profil ne déclare encore de
> table de langues** : `retro status` dit « aucune table déclarée » pour les
> dix, ce qui est l'état réel de la console. Les clés se relèvent sur
> l'émulateur, une par une — une valeur de langue fausse est ignorée en
> silence, donc indiscernable de l'absence.

- [ ] **Step 3: Ouvrir la dette des tables manquantes**

Ajouter une dette dans `docs/dettes.md`, sur le modèle des existantes :
le mécanisme livré, les **6 profils** qui ont déjà un `[[bootstrap]]` et
attendent leur table (DuckStation, PCSX2, Dolphin ×2, RetroArch ×2, RPCS3,
Vita3K), les **4 qui n'en ont aucun** et pour qui il faut d'abord établir où
vit le fichier de réglages (`cemu`, `flycast`, `ppsspp`, `xemu`), et le fait
que la double fusion et la lecture du registre **restent à mesurer sur la
console** — aucun compilateur C# n'existe sur l'hôte.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/dettes.md
git commit -m "La langue au README, et la dette des tables qui restent à relever"
```

---

## Ce que ce plan ne fait PAS

- **Il ne pose aucune table de langues.** C'est délibéré, et c'est la
  contrainte globale la plus dure : aucune clé d'émulateur n'est écrite sans
  avoir été relevée. Un mécanisme livré sans table est utile et honnête —
  `status` dira « aucune table déclarée » pour les dix profils, ce qui est
  l'état réel de la console.
- **Il ne crée aucun `[[bootstrap]]`** pour `cemu`, `flycast`, `ppsspp` et
  `xemu`. Chez eux, il faut d'abord établir où vit le fichier de réglages.
- **Il n'écrit jamais dans les réglages de Steam.** `retro` lit la langue de
  Steam, il ne la pose pas.
- **Il ne prouve pas le C#.** Aucun compilateur n'existe sur l'hôte : la
  boucle réelle, la lecture du registre et la double fusion se mesurent sur la
  console, après `retro launcher` et `compiler.cmd`.

**Ordre obligatoire sur la machine, après cette série :** `retro launcher`,
puis `compiler.cmd`, **puis** `retro scan`. Un lanceur d'avant échoue
bruyamment sur un plan d'après — c'est la conséquence que D7 a déjà portée, et
elle vaut ici à l'identique.
