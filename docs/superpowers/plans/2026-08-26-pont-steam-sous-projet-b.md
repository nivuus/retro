# Pont Steam (sous-projet B) — plan d'implémentation

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour dérouler ce plan tâche par tâche. Les
> étapes utilisent la syntaxe case à cocher (`- [ ]`).

**Objectif :** faire apparaître des ROMs comme jeux non-Steam dans Steam Big
Picture, avec leurs cinq assets d'artwork et leurs tags, de façon idempotente et
sans jamais toucher aux entrées que le propriétaire a créées lui-même.

**Architecture :** une bibliothèque Python pure qui lit et réécrit
`shortcuts.vdf`. La réconciliation est une fonction sans effet de bord —
elle prend l'existant et le voulu, renvoie le résultat — ce qui la rend
intégralement testable sur fixtures, sans Steam et sans VM. Les effets de bord
(écriture disque, appels réseau) vivent dans des modules distincts et minces.

**Pile technique :** Python 3.11+, `vdf` 3.4 (MIT, ValvePython), `requests`,
`pytest`.

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`

## Contraintes globales

Ces règles s'appliquent à **toutes** les tâches.

- **Python 3.11 minimum.** La VM installe Python via l'étape `32-retro.ps1` ; ne
  pas utiliser de syntaxe postérieure à 3.11.
- **Aucun test ne touche le réseau.** Les réponses HTTP sont des fixtures.
  Un test qui exige le réseau est un test cassé.
- **Aucun test n'exige Steam ni Windows.** Toute la tâche B tourne sur Linux.
- **Le tag de propriété est exactement `Rétro`**, accent compris, défini une
  seule fois dans `retro/steam/entry.py` comme `OWNER_TAG`. Ne jamais le
  réécrire en dur ailleurs.
- **Une entrée nous appartient si et seulement si** son champ `tags` contient
  `OWNER_TAG` **et** son champ `exe` désigne un chemin sous la racine
  d'émulation. Les deux conditions, toujours.
- **Aucune ROM, aucun BIOS, aucun binaire d'émulateur dans le dépôt**, y compris
  dans les fixtures de test. Les fixtures ne contiennent que des chemins.
- **Les chemins Windows sont des chaînes, jamais des `pathlib.Path`** dès qu'ils
  entrent dans un VDF : `pathlib` sur Linux transformerait `D:\Emulation` en
  chemin relatif. Utiliser `pathlib.PureWindowsPath` pour toute comparaison de
  chemin Windows.
- **La casse des champs du VDF est celle que Steam écrit**, mesurée sur un
  `shortcuts.vdf` réel le 2026-08-26 : `appid`, `appname`, `exe`, `icon`,
  `sortas`, `tags` en **minuscules** ; `StartDir`, `LaunchOptions`, `IsHidden`,
  `AllowDesktopConfig`, `AllowOverlay`, `OpenVR`, `Devkit`, `DevkitGameID`,
  `DevkitOverrideAppID`, `LastPlayTime`, `ShortcutPath`, `FlatpakAppID` en
  CamelCase. Un champ dans la mauvaise casse est ignoré par Steam en silence.
- **Les arguments de lancement vont dans `LaunchOptions`, jamais dans `exe`.**
  L'identifiant dérive de `exe` : y mettre le chemin de la ROM le ferait changer
  à chaque déplacement de ROM, orphelinant tout l'artwork.
- **Les extensions d'artwork varient** (`.png`, `.jpg`, `.ico` pour le même
  rôle). Toute recherche ou purge se fait par PRÉFIXE, jamais sur une extension
  codée en dur.
- **Style de test :** `pytest` idiomatique (`def test_…`, `assert`). Le paquet
  `installer` utilise un style maison à base de listes `failures` ; `retro` est
  destiné à des contributeurs externes et suit la convention qu'ils attendent.

---

## Tâche 1 : socle du paquet et aller-retour VDF

Le premier livrable prouve la seule chose sans laquelle rien d'autre n'a de
sens : qu'on peut relire un `shortcuts.vdf` et le réécrire à l'identique. Un
aller-retour infidèle corromprait la bibliothèque Steam du propriétaire.

**Fichiers :**
- Créer : `pyproject.toml`
- Créer : `retro/__init__.py`
- Créer : `retro/steam/__init__.py`
- Créer : `retro/steam/vdf_io.py`
- Créer : `tests/conftest.py`
- Test : `tests/steam/test_vdf_io.py`

**Interfaces :**
- Consomme : rien.
- Produit :
  - `load_shortcuts(path: pathlib.Path) -> list[dict]` — les entrées dans
    l'ordre, l'index VDF étant purement positionnel.
  - `loads_shortcuts(blob: bytes) -> list[dict]`
  - `dumps_shortcuts(entries: list[dict]) -> bytes`

- [ ] **Étape 1 : initialiser le dépôt**

`packages/retro` n'est pas encore un dépôt git. Les étapes « commit » de tout ce
plan en dépendent.

```bash
cd /home/mallanic/Projects/Nivuus/packages/retro
git init
git add docs/
git commit -m "docs: conception de la console de retrogaming"
```

Si le paquet doit finalement vivre dans le dépôt `installer` plutôt qu'être
autonome, **arrêter ici et le signaler** : cela change l'emplacement de tous les
fichiers de ce plan.

- [ ] **Étape 2 : écrire `pyproject.toml`**

```toml
[project]
name = "retro"
version = "0.1.0"
description = "Fait remonter une bibliothèque de jeux rétro dans Steam"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "vdf>=3.4",
    "requests>=2.31",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
retro = "retro.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Étape 3 : créer les paquets vides**

```bash
mkdir -p retro/steam tests/steam tests/fixtures
touch retro/__init__.py retro/steam/__init__.py
touch tests/__init__.py tests/steam/__init__.py
```

- [ ] **Étape 4 : écrire le test qui échoue**

Fichier `tests/steam/test_vdf_io.py` :

```python
"""Aller-retour sur shortcuts.vdf.

Steam relit ce fichier au démarrage. Une écriture qui perd un champ, change un
type d'entier ou casse l'UTF-8 corrompt la bibliothèque du propriétaire sans
rien signaler : Steam affiche simplement moins de jeux qu'avant.
"""
import pytest

from retro.steam import vdf_io

ENTRY = {
    "appid": -1896004318,
    "appname": "Chrono Trigger",
    "exe": '"D:\\Emulation\\RetroArch\\retroarch.exe"',
    "StartDir": '"D:\\Emulation\\RetroArch\\"',
    "icon": "",
    "ShortcutPath": "",
    "LaunchOptions": '-L "cores\\snes9x_libretro.dll" -f "G:\\ROMs\\snes\\ct.sfc"',
    "IsHidden": 0,
    "AllowDesktopConfig": 1,
    "AllowOverlay": 1,
    "OpenVR": 0,
    "Devkit": 0,
    "DevkitGameID": "",
    "DevkitOverrideAppID": 0,
    "LastPlayTime": 0,
    "tags": {"0": "Rétro", "1": "Super Nintendo"},
}


def test_aller_retour_preserve_tout():
    blob = vdf_io.dumps_shortcuts([ENTRY])
    assert vdf_io.loads_shortcuts(blob) == [ENTRY]


def test_appid_negatif_reste_negatif():
    """Le champ appid est un int32 signé. Un aller-retour qui le rendrait non
    signé produirait un identifiant que Steam n'associe à aucun artwork."""
    blob = vdf_io.dumps_shortcuts([ENTRY])
    assert vdf_io.loads_shortcuts(blob)[0]["appid"] == -1896004318


def test_utf8_survit():
    """Les titres rétro sont pleins d'accents et de caractères japonais."""
    entry = dict(ENTRY, appname="Pokémon Édition Rouge 赤")
    blob = vdf_io.dumps_shortcuts([entry])
    assert vdf_io.loads_shortcuts(blob)[0]["appname"] == "Pokémon Édition Rouge 赤"


def test_ordre_preserve():
    a = dict(ENTRY, appname="A")
    b = dict(ENTRY, appname="B")
    c = dict(ENTRY, appname="C")
    noms = [e["appname"] for e in vdf_io.loads_shortcuts(vdf_io.dumps_shortcuts([a, b, c]))]
    assert noms == ["A", "B", "C"]


def test_fichier_vide_donne_liste_vide(tmp_path):
    """Steam écrit un shortcuts.vdf ne contenant que la racine quand le
    propriétaire n'a aucun jeu non-Steam. Ce n'est pas une erreur."""
    p = tmp_path / "shortcuts.vdf"
    p.write_bytes(vdf_io.dumps_shortcuts([]))
    assert vdf_io.load_shortcuts(p) == []


def test_fichier_absent_donne_liste_vide(tmp_path):
    """Steam ne crée shortcuts.vdf qu'au premier raccourci ajouté."""
    assert vdf_io.load_shortcuts(tmp_path / "jamais-ecrit.vdf") == []


def test_blob_corrompu_leve_une_erreur_claire(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    p.write_bytes(b"ceci n'est pas du VDF binaire")
    with pytest.raises(vdf_io.ShortcutsError):
        vdf_io.load_shortcuts(p)
```

- [ ] **Étape 5 : vérifier que le test échoue**

```bash
python3 -m pytest tests/steam/test_vdf_io.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.steam.vdf_io'`.

- [ ] **Étape 6 : implémenter**

Fichier `retro/steam/vdf_io.py` :

```python
"""Lecture et écriture de shortcuts.vdf.

Le fichier est un VDF binaire dont la racine est une clé "shortcuts" contenant
un mapping d'index décimaux vers les entrées. Ces index sont purement
positionnels — Steam les renumérote lui-même — donc cette couche les gomme et
expose une liste.
"""
from __future__ import annotations

import pathlib

import vdf

ROOT_KEY = "shortcuts"


class ShortcutsError(RuntimeError):
    """shortcuts.vdf est illisible ou n'a pas la forme attendue."""


def loads_shortcuts(blob: bytes) -> list[dict]:
    try:
        parsed = vdf.binary_loads(blob)
    except Exception as exc:  # la bibliothèque lève des types variés
        raise ShortcutsError(f"VDF binaire illisible : {exc}") from exc
    if ROOT_KEY not in parsed:
        raise ShortcutsError(
            f"racine '{ROOT_KEY}' absente ; clés trouvées : {sorted(parsed)}"
        )
    shortcuts = parsed[ROOT_KEY]
    # Trier numériquement : "10" doit suivre "9", pas "1".
    return [shortcuts[k] for k in sorted(shortcuts, key=int)]


def dumps_shortcuts(entries: list[dict]) -> bytes:
    body = {str(i): entry for i, entry in enumerate(entries)}
    return vdf.binary_dumps({ROOT_KEY: body})


def load_shortcuts(path: pathlib.Path) -> list[dict]:
    """Un fichier absent vaut zéro raccourci : Steam ne le crée qu'au premier."""
    if not path.exists():
        return []
    return loads_shortcuts(path.read_bytes())
```

- [ ] **Étape 7 : vérifier que les tests passent**

```bash
pip install -e '.[dev]'
python3 -m pytest tests/steam/test_vdf_io.py -v
```

Attendu : 7 passed.

- [ ] **Étape 8 : commit**

```bash
git add pyproject.toml retro/ tests/
git commit -m "feat(steam): aller-retour fidèle sur shortcuts.vdf"
```

---

## Tâche 2 : dérivation de l'identifiant

L'identifiant dérivé de `(exe, appname)` nomme les fichiers d'artwork. Une
dérivation fausse ne lève aucune erreur — elle produit des vignettes muettes
que rien ne signale. Cette tâche est donc la seule du plan qui **exige une
fixture produite par Steam lui-même**.

**Fichiers :**
- Créer : `retro/steam/appid.py`
- Créer : `tests/fixtures/shortcuts-reel.vdf`
- Créer : `tests/fixtures/README.md`
- Test : `tests/steam/test_appid.py`

**Interfaces :**
- Consomme : `vdf_io.load_shortcuts` (tâche 1).
- Produit :
  - `legacy_appid(exe: str, app_name: str) -> int` — non signé sur 32 bits, c'est
    lui qui nomme les fichiers d'artwork.
  - `to_signed(legacy: int) -> int` — la forme stockée dans le champ `appid`.
  - `grid_prefixes(legacy: int) -> dict[str, str]` — préfixes SANS extension,
    clés `portrait`, `paysage`, `hero`, `logo`, `icone`.
  - `existing_asset(grid_dir: pathlib.Path, prefix: str) -> pathlib.Path | None`
    — le fichier présent pour ce préfixe, quelle que soit son extension.

- [ ] **Étape 1 : vérifier la fixture (déjà présente)**

`tests/fixtures/shortcuts-reel.vdf` et `tests/fixtures/grid-listing.txt` ont été
extraits d'une installation Steam réelle le 2026-08-26, puis neutralisés : plus
aucun chemin personnel, aucun identifiant de compte, aucun titre d'origine. Les
titres de remplacement conservent ce que le test doit couvrir — accents,
apostrophe typographique U+2019, deux-points.

```bash
python3 -c "
import vdf
d = vdf.binary_loads(open('tests/fixtures/shortcuts-reel.vdf','rb').read())
print(len(d['shortcuts']), 'raccourcis')
print(sorted(d['shortcuts']['0'].keys()))"
```

Attendu : 10 raccourcis, et des clés `appname`/`exe`/`icon` en minuscules.

<details><summary>Si la fixture devait être régénérée</summary>

Sur n'importe quelle machine où Steam est installé **et qui possède au moins un
jeu non-Steam** (« Ajouter un jeu » → « Ajouter un jeu non-Steam »), fermer
Steam entièrement, puis copier :

- Windows : `<Steam>\userdata\<compte>\config\shortcuts.vdf`
- Linux : `~/.steam/steam/userdata/<compte>/config/shortcuts.vdf`

vers `tests/fixtures/shortcuts-reel.vdf`.

Inspecter la fixture avant de la committer et **remplacer tout chemin
personnel** (nom d'utilisateur, dossiers privés) par des chemins neutres — le
dépôt est public :

```bash
python3 -c "
import vdf, pprint
d = vdf.binary_loads(open('tests/fixtures/shortcuts-reel.vdf','rb').read())
pprint.pprint(d)"
```

Ne jamais fabriquer une fixture synthétique : elle validerait le code contre
lui-même et ne prouverait rien.

</details>

Écrire `tests/fixtures/README.md` :

```markdown
# Fixtures

`shortcuts-reel.vdf` a été produit par Steam, pas par ce dépôt. C'est la seule
chose qui atteste la dérivation d'identifiant dans `retro/steam/appid.py` : une
fixture régénérée par notre propre code validerait la formule contre elle-même.

Les chemins qu'il contient ont été neutralisés à la main. Il ne contient aucune
ROM, aucun binaire, aucune donnée personnelle.

Pour en produire une autre : fermer Steam, copier
`userdata/<compte>/config/shortcuts.vdf`, neutraliser les chemins.
```

- [ ] **Étape 2 : écrire le test qui échoue**

Fichier `tests/steam/test_appid.py` :

```python
"""Dérivation de l'identifiant de raccourci.

Verrouillée contre une fixture produite par Steam. Une formule fausse ne lève
rien : elle nomme les fichiers d'artwork d'après un identifiant que Steam ne
cherchera jamais, et la bibliothèque affiche des vignettes grises.
"""
import pathlib

import pytest

from retro.steam import appid, vdf_io

FIXTURE = pathlib.Path(__file__).parent.parent / "fixtures" / "shortcuts-reel.vdf"


GRID_LISTING = (FIXTURE.parent / "grid-listing.txt").read_text().split()


@pytest.mark.parametrize("entree", vdf_io.load_shortcuts(FIXTURE))
def test_l_artwork_est_nomme_d_apres_l_appid_du_fichier(entree):
    """Ce que la fixture atteste réellement.

    Steam ne RECALCULE jamais l'appid d'un raccourci existant : il lit celui du
    fichier et cherche l'artwork sous ce nombre. Mesuré le 2026-08-26 sur une
    installation réelle — 8 des 10 raccourcis ont leurs 5 assets, tous nommés
    d'après l'appid non signé de leur entrée.

    C'est pourquoi ce test n'exige PAS que notre formule reproduise celle de
    Steam : sur cette même fixture, 9 des 10 appid ne correspondent à aucun
    calcul, parce que leurs chemins ont changé depuis leur création. La formule
    doit être déterministe et stable, pas fidèle.
    """
    non_signe = appid.to_unsigned(entree["appid"])
    prefixes = set(appid.grid_prefixes(non_signe).values())
    presents = {f.rsplit(".", 1)[0] for f in GRID_LISTING}
    trouves = prefixes & presents
    # Un raccourci sans artwork est légitime (jeu lancé par son propre lanceur).
    # Mais s'il en a, ce doit être sous NOS préfixes et sous aucun autre.
    if trouves:
        assert len(trouves) == 5, f"{entree['appname']!r} : {sorted(trouves)}"


def test_la_fixture_couvre_des_raccourcis_avec_artwork():
    """Sans cette garde, une fixture dont aucun raccourci n'a d'artwork ferait
    passer le test ci-dessus sans rien vérifier."""
    presents = {f.rsplit(".", 1)[0] for f in GRID_LISTING}
    avec = [e for e in vdf_io.load_shortcuts(FIXTURE)
            if set(appid.grid_prefixes(appid.to_unsigned(e["appid"])).values()) & presents]
    assert len(avec) >= 5


def test_la_casse_des_champs_est_celle_de_steam():
    """Steam écrit appname/exe/icon en minuscules et StartDir en CamelCase. Un
    champ dans la mauvaise casse est ignoré en silence."""
    entree = vdf_io.load_shortcuts(FIXTURE)[0]
    for champ in ("appid", "appname", "exe", "icon", "sortas", "tags"):
        assert champ in entree
    for champ in ("StartDir", "LaunchOptions", "IsHidden", "FlatpakAppID"):
        assert champ in entree
    assert "AppName" not in entree and "Exe" not in entree


def test_la_fixture_contient_au_moins_un_raccourci():
    """Une fixture vide ferait passer le test paramétré sans rien vérifier."""
    assert len(vdf_io.load_shortcuts(FIXTURE)) >= 1


def test_le_bit_haut_est_toujours_pose():
    legacy = appid.legacy_appid('"C:\\jeu.exe"', "Jeu")
    assert legacy & 0x80000000


def test_to_signed_est_reversible():
    legacy = appid.legacy_appid('"C:\\jeu.exe"', "Jeu")
    assert appid.to_unsigned(appid.to_signed(legacy)) == legacy


def test_les_guillemets_comptent():
    """Steam stocke exe avec ses guillemets et calcule dessus. Les retirer
    donnerait un identifiant différent et de l'artwork jamais trouvé."""
    avec = appid.legacy_appid('"C:\\jeu.exe"', "Jeu")
    sans = appid.legacy_appid("C:\\jeu.exe", "Jeu")
    assert avec != sans


def test_prefixes_des_cinq_assets():
    assert appid.grid_prefixes(2398962978) == {
        "portrait": "2398962978p",
        "paysage": "2398962978",
        "hero": "2398962978_hero",
        "logo": "2398962978_logo",
        "icone": "2398962978_icon",
    }


def test_asset_trouve_quelle_que_soit_l_extension(tmp_path):
    (tmp_path / "2398962978p.png").write_bytes(b"x")
    assert appid.existing_asset(tmp_path, "2398962978p").suffix == ".png"


def test_le_paysage_ne_capte_pas_le_portrait(tmp_path):
    """Le préfixe du paysage est le nombre nu ; une correspondance par préfixe
    de chaîne le ferait matcher 2398962978p.png et 2398962978_hero.png."""
    (tmp_path / "2398962978p.png").write_bytes(b"x")
    assert appid.existing_asset(tmp_path, "2398962978") is None
```

- [ ] **Étape 3 : vérifier que le test échoue**

```bash
python3 -m pytest tests/steam/test_appid.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.steam.appid'`.

- [ ] **Étape 4 : implémenter**

Fichier `retro/steam/appid.py` :

```python
"""Identifiant d'un raccourci non-Steam.

Steam le dérive du couple (exe, appname). Il sert à deux choses : le champ
`appid` du VDF, en entier signé, et le nom des fichiers d'artwork, en non signé.
Confondre les deux formes donne de l'artwork que Steam ne trouve jamais.
"""
from __future__ import annotations

import zlib

_HIGH_BIT = 0x80000000
_2POW32 = 0x100000000


def legacy_appid(exe: str, app_name: str) -> int:
    """Forme non signée sur 32 bits. C'est elle qui nomme l'artwork.

    `exe` doit être la chaîne EXACTE du champ exe, guillemets inclus : Steam
    calcule sur ce qu'il a stocké, pas sur un chemin nettoyé.
    """
    return zlib.crc32((exe + app_name).encode("utf-8")) | _HIGH_BIT


def to_signed(legacy: int) -> int:
    """Forme stockée dans le champ `appid`, qui est un int32 signé."""
    return legacy - _2POW32 if legacy >= 0x80000000 else legacy


def to_unsigned(signed: int) -> int:
    return signed + _2POW32 if signed < 0 else signed


def grid_prefixes(legacy: int) -> dict[str, str]:
    """Les CINQ assets du dossier grid\\, en PRÉFIXES sans extension.

    Mesuré sur une installation réelle le 2026-08-26 : `.png`, `.jpg` et `.ico`
    coexistent pour le même rôle — 18 jeux, 5 assets chacun, extensions
    mélangées. Coder une extension en dur ferait retélécharger un asset déjà
    présent sous une autre, à chaque synchronisation, indéfiniment.
    """
    return {
        "portrait": f"{legacy}p",
        "paysage": f"{legacy}",
        "hero": f"{legacy}_hero",
        "logo": f"{legacy}_logo",
        "icone": f"{legacy}_icon",
    }


def existing_asset(grid_dir, prefix: str):
    """Le fichier présent pour ce préfixe, quelle que soit son extension.

    `paysage` a pour préfixe le nombre nu, donc `2398p` et `2398_hero`
    commenceraient aussi par lui : la correspondance porte sur le STEM entier,
    jamais sur un préfixe de chaîne.
    """
    if not grid_dir.is_dir():
        return None
    for f in grid_dir.iterdir():
        if f.stem == prefix:
            return f
    return None
```

- [ ] **Étape 5 : vérifier que les tests passent**

```bash
python3 -m pytest tests/steam/test_appid.py -v
```

Attendu : tous verts, dont un cas paramétré par raccourci de la fixture.

**Si `test_la_formule_reproduit_l_appid_de_steam` échoue, ne pas ajuster le test
pour qu'il passe.** C'est le seul test du plan qui atteste un comportement
externe. Consigner les couples `(exe, appname, appid)` observés et chercher la
formule qui les explique tous.

- [ ] **Étape 6 : commit**

```bash
git add retro/steam/appid.py tests/steam/test_appid.py tests/fixtures/
git commit -m "feat(steam): dérivation de l'identifiant, verrouillée sur fixture Steam"
```

---

## Tâche 3 : découverte des comptes

`userdata/` contient un dossier par compte connecté. Zéro compte et plusieurs
comptes sont deux situations réelles qui, non traitées, se manifestent par une
exception opaque au pire moment.

**Fichiers :**
- Créer : `retro/steam/accounts.py`
- Test : `tests/steam/test_accounts.py`

**Interfaces :**
- Consomme : rien.
- Produit :
  - `SteamAccount` — dataclass gelée à DEUX champs stockés : `account_id: str`,
    `config_dir: pathlib.Path` ; plus `shortcuts_path` et `grid_dir` en
    `@property` dérivées de `config_dir`. Les stocker séparément rendrait
    constructible un compte dont l'artwork et les raccourcis vivent à deux
    endroits différents — un état incohérent que rien ne signalerait.
  - `discover_accounts(steam_root: pathlib.Path) -> list[SteamAccount]`
  - `NoSteamAccountError`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/steam/test_accounts.py` :

```python
"""Découverte des comptes Steam locaux."""
import pytest

from retro.steam import accounts


def _faire_compte(racine, account_id):
    d = racine / "userdata" / account_id / "config"
    d.mkdir(parents=True)
    return d


def test_un_seul_compte(tmp_path):
    _faire_compte(tmp_path, "123456789")
    trouves = accounts.discover_accounts(tmp_path)
    assert [c.account_id for c in trouves] == ["123456789"]


def test_plusieurs_comptes_sont_tous_rendus(tmp_path):
    """On ne devine pas lequel est le bon : on les synchronise tous."""
    _faire_compte(tmp_path, "111")
    _faire_compte(tmp_path, "222")
    assert sorted(c.account_id for c in accounts.discover_accounts(tmp_path)) == ["111", "222"]


def test_aucun_compte_leve_une_erreur_explicite(tmp_path):
    (tmp_path / "userdata").mkdir()
    with pytest.raises(accounts.NoSteamAccountError) as exc:
        accounts.discover_accounts(tmp_path)
    assert "connect" in str(exc.value).lower()


def test_userdata_absent_leve_la_meme_erreur(tmp_path):
    with pytest.raises(accounts.NoSteamAccountError):
        accounts.discover_accounts(tmp_path)


def test_dossier_anonymous_ignore(tmp_path):
    """Steam crée userdata/0 pour la session anonyme : ce n'est pas un compte."""
    _faire_compte(tmp_path, "0")
    _faire_compte(tmp_path, "123456789")
    assert [c.account_id for c in accounts.discover_accounts(tmp_path)] == ["123456789"]


def test_entree_non_numerique_ignoree(tmp_path):
    (tmp_path / "userdata" / "ac_backup" / "config").mkdir(parents=True)
    _faire_compte(tmp_path, "123456789")
    assert [c.account_id for c in accounts.discover_accounts(tmp_path)] == ["123456789"]


def test_chemins_derives(tmp_path):
    _faire_compte(tmp_path, "123456789")
    compte = accounts.discover_accounts(tmp_path)[0]
    assert compte.shortcuts_path.name == "shortcuts.vdf"
    assert compte.grid_dir.name == "grid"
    assert compte.grid_dir.parent == compte.config_dir
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/steam/test_accounts.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.steam.accounts'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/steam/accounts.py` :

```python
"""Comptes Steam locaux.

Chaque compte connecté a son propre shortcuts.vdf et son propre dossier
d'artwork. On les synchronise tous : deviner lequel est « le bon » serait un
pari, et se tromper laisserait une bibliothèque muette sans rien signaler.
"""
from __future__ import annotations

import dataclasses
import pathlib


class NoSteamAccountError(RuntimeError):
    """Aucun compte Steam local : personne ne s'est jamais connecté."""


@dataclasses.dataclass(frozen=True)
class SteamAccount:
    account_id: str
    config_dir: pathlib.Path

    @property
    def shortcuts_path(self) -> pathlib.Path:
        return self.config_dir / "shortcuts.vdf"

    @property
    def grid_dir(self) -> pathlib.Path:
        return self.config_dir / "grid"


def discover_accounts(steam_root: pathlib.Path) -> list[SteamAccount]:
    userdata = steam_root / "userdata"
    comptes = []
    if userdata.is_dir():
        for entree in sorted(userdata.iterdir()):
            # "0" est la session anonyme de Steam, pas un compte.
            if not entree.is_dir() or not entree.name.isdigit() or entree.name == "0":
                continue
            config = entree / "config"
            if config.is_dir():
                comptes.append(SteamAccount(account_id=entree.name, config_dir=config))
    if not comptes:
        raise NoSteamAccountError(
            f"aucun compte Steam sous {userdata} : ouvrir Steam et se connecter "
            "au moins une fois avant de synchroniser la bibliothèque"
        )
    return comptes
```

- [ ] **Étape 4 : vérifier que les tests passent**

```bash
python3 -m pytest tests/steam/test_accounts.py -v
```

Attendu : 7 passed.

- [ ] **Étape 5 : commit**

```bash
git add retro/steam/accounts.py tests/steam/test_accounts.py
git commit -m "feat(steam): découverte des comptes userdata"
```

---

## Tâche 4 : construction d'une entrée et test de propriété

Le test de propriété est la garantie qui protège les jeux du propriétaire. Il
est écrit avant la réconciliation qui s'en sert, et testé séparément, parce
qu'un faux positif ici supprime des données qui ne nous appartiennent pas.

**Fichiers :**
- Créer : `retro/steam/entry.py`
- Test : `tests/steam/test_entry.py`

**Interfaces :**
- Consomme : `appid.legacy_appid`, `appid.to_signed` (tâche 2).
- Produit :
  - `OWNER_TAG: str` — vaut `"Rétro"`.
  - `RomEntry` — dataclass gelée : `title: str`, `rom_path: str`,
    `system_name: str`, `emulator_exe: str`, `launch_template: str`,
    `start_dir: str`, `extra_tags: tuple[str, ...] = ()`.
    Tous les chemins sont des **chaînes Windows**, jamais des `Path`.
  - `build_shortcut(entry: RomEntry) -> dict`
  - `is_owned(shortcut: dict, emulation_root: str) -> bool`
  - `quote(path: str) -> str`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/steam/test_entry.py` :

```python
"""Construction d'un raccourci et test de propriété."""
from retro.steam import appid, entry

EMU_ROOT = "D:\\Emulation"

ROM = entry.RomEntry(
    title="Chrono Trigger",
    rom_path="G:\\ROMs\\snes\\Chrono Trigger.sfc",
    system_name="Super Nintendo",
    emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
    launch_template='-L "cores\\snes9x_libretro.dll" -f "{rom}"',
    start_dir="D:\\Emulation\\RetroArch",
    extra_tags=("1995", "RPG"),
)


def test_les_champs_obligatoires_sont_presents():
    s = entry.build_shortcut(ROM)
    attendus = {
        "appid", "appname", "exe", "StartDir", "icon", "ShortcutPath",
        "LaunchOptions", "IsHidden", "AllowDesktopConfig", "AllowOverlay",
        "OpenVR", "Devkit", "DevkitGameID", "DevkitOverrideAppID",
        "LastPlayTime", "tags", "FlatpakAppID", "sortas",
    }
    assert attendus <= set(s)


def test_le_chemin_de_rom_est_substitue():
    s = entry.build_shortcut(ROM)
    assert "G:\\ROMs\\snes\\Chrono Trigger.sfc" in s["LaunchOptions"]
    assert "{rom}" not in s["LaunchOptions"]


def test_les_chemins_sont_entre_guillemets():
    """Sans guillemets, un chemin contenant une espace casse au lancement."""
    s = entry.build_shortcut(ROM)
    assert s["exe"].startswith('"') and s["exe"].endswith('"')
    assert s["StartDir"].startswith('"')


def test_le_tag_de_propriete_vient_en_premier():
    s = entry.build_shortcut(ROM)
    assert s["tags"]["0"] == entry.OWNER_TAG


def test_les_tags_contiennent_systeme_et_extras():
    s = entry.build_shortcut(ROM)
    valeurs = set(s["tags"].values())
    assert {"Rétro", "Super Nintendo", "1995", "RPG"} == valeurs


def test_les_tags_sont_indexes_consecutivement():
    s = entry.build_shortcut(ROM)
    assert sorted(s["tags"], key=int) == ["0", "1", "2", "3"]


def test_l_appid_correspond_a_la_derivation():
    s = entry.build_shortcut(ROM)
    attendu = appid.to_signed(appid.legacy_appid(s["exe"], s["appname"]))
    assert s["appid"] == attendu


def test_construction_deterministe():
    """Deux constructions de la même ROM doivent être identiques, sinon chaque
    synchronisation réécrirait le fichier pour rien."""
    assert entry.build_shortcut(ROM) == entry.build_shortcut(ROM)


# --- propriété ---

def test_notre_entree_est_reconnue():
    assert entry.is_owned(entry.build_shortcut(ROM), EMU_ROOT)


def test_jeu_du_proprietaire_sans_tag_est_etranger():
    """Un jeu ajouté à la main, même sous D:\\Emulation, ne nous appartient pas."""
    s = entry.build_shortcut(ROM)
    s["tags"] = {"0": "Favoris"}
    assert not entry.is_owned(s, EMU_ROOT)


def test_tag_present_mais_hors_arborescence_est_etranger():
    """Le propriétaire a le droit de taguer un de ses jeux « Rétro »."""
    s = entry.build_shortcut(ROM)
    s["exe"] = '"C:\\Program Files\\SonJeu\\jeu.exe"'
    assert not entry.is_owned(s, EMU_ROOT)


def test_propriete_insensible_a_la_casse_du_chemin():
    """Windows ne distingue pas d:\\emulation de D:\\Emulation."""
    s = entry.build_shortcut(ROM)
    s["exe"] = '"d:\\emulation\\RetroArch\\retroarch.exe"'
    assert entry.is_owned(s, EMU_ROOT)


def test_prefixe_trompeur_rejete():
    """D:\\EmulationAutre n'est pas sous D:\\Emulation, malgré le préfixe commun."""
    s = entry.build_shortcut(ROM)
    s["exe"] = '"D:\\EmulationAutre\\truc.exe"'
    assert not entry.is_owned(s, EMU_ROOT)


def test_entree_sans_champ_tags_est_etrangere():
    """Un shortcuts.vdf écrit par un outil tiers peut omettre le champ."""
    s = entry.build_shortcut(ROM)
    del s["tags"]
    assert not entry.is_owned(s, EMU_ROOT)


def test_entree_sans_champ_exe_est_etrangere():
    s = entry.build_shortcut(ROM)
    del s["exe"]
    assert not entry.is_owned(s, EMU_ROOT)


def test_exe_portant_ses_arguments_est_reconnu():
    """Les raccourcis existants du propriétaire mettent les arguments DANS exe."""
    s = entry.build_shortcut(ROM)
    s["exe"] = '"D:\\Emulation\\RetroArch\\retroarch.exe" -L core.dll "G:\\ROMs\\x.sfc"'
    assert entry.is_owned(s, EMU_ROOT)


def test_exe_sans_guillemets_avec_arguments():
    s = entry.build_shortcut(ROM)
    s["exe"] = "D:\\Emulation\\RetroArch\\retroarch.exe -f"
    assert entry.is_owned(s, EMU_ROOT)


def test_les_champs_recents_de_steam_sont_ecrits():
    s = entry.build_shortcut(ROM)
    assert s["FlatpakAppID"] == "" and s["sortas"] == ""
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/steam/test_entry.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.steam.entry'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/steam/entry.py` :

```python
"""Un raccourci Steam construit depuis une ROM, et le test de propriété.

Le test de propriété est la seule chose qui empêche la réconciliation de
supprimer les jeux non-Steam que le propriétaire a ajoutés lui-même. Il exige
DEUX conditions, jamais une seule : le tag nous marque, le chemin nous confirme.
Le tag seul serait ambigu — « Rétro » est un tag que quelqu'un peut légitimement
poser sur son propre jeu.
"""
from __future__ import annotations

import dataclasses
import pathlib

from retro.steam import appid as appid_mod

OWNER_TAG = "Rétro"


@dataclasses.dataclass(frozen=True)
class RomEntry:
    """Tous les chemins sont des chaînes Windows.

    Surtout pas des pathlib.Path : sur Linux, où tournent les tests,
    Path("D:\\Emulation") est un chemin RELATIF nommé « D:\\Emulation », et
    toute comparaison qu'on en tirerait serait fausse.
    """
    title: str
    rom_path: str
    system_name: str
    emulator_exe: str
    launch_template: str
    start_dir: str
    extra_tags: tuple[str, ...] = ()


def quote(path: str) -> str:
    """Steam stocke les chemins entre guillemets, et calcule l'identifiant sur
    la forme guillemetée. Ne jamais les retirer avant de dériver."""
    return path if path.startswith('"') else f'"{path}"'


def build_shortcut(entry: RomEntry) -> dict:
    exe = quote(entry.emulator_exe)
    tags = [OWNER_TAG, entry.system_name, *entry.extra_tags]
    legacy = appid_mod.legacy_appid(exe, entry.title)
    return {
        "appid": appid_mod.to_signed(legacy),
        "appname": entry.title,
        "exe": exe,
        "StartDir": quote(entry.start_dir),
        "icon": "",
        "ShortcutPath": "",
        "LaunchOptions": entry.launch_template.replace("{rom}", entry.rom_path),
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": "",
        "DevkitOverrideAppID": 0,
        # Steam récent écrit ces deux champs : mesurés présents sur les 10
        # raccourcis de la fixture. Les omettre laisse Steam les recréer, mais
        # produit une différence de fichier à chaque synchronisation.
        "FlatpakAppID": "",
        "sortas": "",
        "LastPlayTime": 0,
        "tags": {str(i): t for i, t in enumerate(tags)},
    }


def exe_path(exe_field: str) -> str:
    """Le chemin de l'exécutable, dépouillé des arguments qui le suivent.

    Nous écrivons les arguments dans LaunchOptions, mais les raccourcis
    existants du propriétaire — mesurés sur une installation réelle — les
    portent DANS le champ exe. Un test de propriété qui ne le prévoit pas
    juge ces entrées d'après une chaîne qui n'est pas un chemin.
    """
    exe_field = exe_field.strip()
    if exe_field.startswith('"'):
        fin = exe_field.find('"', 1)
        if fin != -1:
            return exe_field[1:fin]
    return exe_field.split(" ", 1)[0]


def is_owned(shortcut: dict, emulation_root: str) -> bool:
    """Vrai seulement si les DEUX conditions tiennent."""
    tags = shortcut.get("tags")
    if not isinstance(tags, dict) or OWNER_TAG not in tags.values():
        return False
    exe = shortcut.get("exe")
    if not exe:
        return False
    # PureWindowsPath compare segment par segment et sans casse : « D:\EmulationAutre »
    # n'est donc pas sous « D:\Emulation », alors qu'une comparaison de préfixe
    # de chaîne l'aurait accepté à tort.
    chemin = pathlib.PureWindowsPath(exe_path(exe))
    racine = pathlib.PureWindowsPath(emulation_root.strip('"'))
    return racine in chemin.parents
```

- [ ] **Étape 4 : vérifier que les tests passent**

```bash
python3 -m pytest tests/steam/test_entry.py -v
```

Attendu : 15 passed.

- [ ] **Étape 5 : commit**

```bash
git add retro/steam/entry.py tests/steam/test_entry.py
git commit -m "feat(steam): construction d'entrée et test de propriété à double condition"
```

---

## Tâche 5 : réconciliation

Le cœur du sous-projet, et une fonction pure : elle prend l'existant et le
voulu, elle renvoie le résultat, elle ne touche à rien. Toute la logique
délicate se teste donc sans disque, sans Steam et sans réseau.

**Fichiers :**
- Créer : `retro/steam/reconcile.py`
- Test : `tests/steam/test_reconcile.py`

**Interfaces :**
- Consomme : `entry.RomEntry`, `entry.build_shortcut`, `entry.is_owned`
  (tâche 4) ; `appid.to_unsigned` (tâche 2).
- Produit :
  - `ReconcileResult` — dataclass gelée : `entries: list[dict]`,
    `created: list[str]`, `removed: list[str]`, `kept: list[str]`,
    `orphaned_appids: list[int]` (identifiants **non signés**, pour l'artwork
    à supprimer).
  - `reconcile(existing: list[dict], wanted: list[RomEntry], emulation_root: str) -> ReconcileResult`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/steam/test_reconcile.py` :

```python
"""Réconciliation entre la bibliothèque Steam et les ROMs présentes."""
import dataclasses

from retro.steam import entry, reconcile

EMU_ROOT = "D:\\Emulation"


def rom(titre, systeme="Super Nintendo", fichier=None):
    return entry.RomEntry(
        title=titre,
        rom_path=fichier or f"G:\\ROMs\\snes\\{titre}.sfc",
        system_name=systeme,
        emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
        launch_template='-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        start_dir="D:\\Emulation\\RetroArch",
    )


def etranger(nom):
    """Un jeu non-Steam ajouté à la main par le propriétaire."""
    return {
        "appid": 42,
        "appname": nom,
        "exe": '"C:\\Program Files\\SonJeu\\jeu.exe"',
        "StartDir": '"C:\\Program Files\\SonJeu"',
        "icon": "", "ShortcutPath": "", "LaunchOptions": "",
        "IsHidden": 0, "AllowDesktopConfig": 1, "AllowOverlay": 1,
        "OpenVR": 0, "Devkit": 0, "DevkitGameID": "",
        "DevkitOverrideAppID": 0, "LastPlayTime": 0,
        "tags": {"0": "Favoris"},
    }


def noms(entrees):
    return sorted(e["appname"] for e in entrees)


def test_creation_depuis_une_bibliotheque_vide():
    r = reconcile.reconcile([], [rom("Chrono Trigger")], EMU_ROOT)
    assert r.created == ["Chrono Trigger"]
    assert noms(r.entries) == ["Chrono Trigger"]


def test_rom_disparue_supprime_l_entree():
    existant = [entry.build_shortcut(rom("Chrono Trigger"))]
    r = reconcile.reconcile(existant, [], EMU_ROOT)
    assert r.removed == ["Chrono Trigger"]
    assert r.entries == []


def test_entree_etrangere_jamais_touchee():
    """La garantie centrale : les jeux du propriétaire survivent à tout."""
    existant = [etranger("Mon jeu à moi")]
    r = reconcile.reconcile(existant, [], EMU_ROOT)
    assert r.removed == []
    assert noms(r.entries) == ["Mon jeu à moi"]


def test_etranger_conserve_pendant_qu_on_cree_et_supprime():
    existant = [etranger("Mon jeu à moi"), entry.build_shortcut(rom("Ancien"))]
    r = reconcile.reconcile(existant, [rom("Nouveau")], EMU_ROOT)
    assert noms(r.entries) == ["Mon jeu à moi", "Nouveau"]
    assert r.created == ["Nouveau"]
    assert r.removed == ["Ancien"]


def test_idempotence():
    """Deuxième passage : rien à créer, rien à supprimer, fichier inchangé."""
    r1 = reconcile.reconcile([], [rom("Chrono Trigger")], EMU_ROOT)
    r2 = reconcile.reconcile(r1.entries, [rom("Chrono Trigger")], EMU_ROOT)
    assert r2.created == [] and r2.removed == []
    assert r2.entries == r1.entries


def test_tags_mis_a_jour_sur_entree_conservee():
    """Les métadonnées s'enrichissent avec le temps ; l'entrée doit suivre."""
    r1 = reconcile.reconcile([], [rom("Chrono Trigger")], EMU_ROOT)
    enrichie = dataclasses.replace(rom("Chrono Trigger"), extra_tags=("1995", "RPG"))
    r2 = reconcile.reconcile(r1.entries, [enrichie], EMU_ROOT)
    assert "RPG" in r2.entries[0]["tags"].values()
    assert r2.created == [] and r2.removed == []
    assert r2.kept == ["Chrono Trigger"]


def test_les_etrangers_gardent_leur_place_en_tete():
    """Steam renumérote, mais on ne réordonne pas gratuitement la bibliothèque."""
    existant = [etranger("A"), entry.build_shortcut(rom("B")), etranger("C")]
    r = reconcile.reconcile(existant, [rom("B")], EMU_ROOT)
    assert [e["appname"] for e in r.entries] == ["A", "B", "C"]


def test_appid_orphelin_signale_en_non_signe():
    """L'artwork est nommé d'après l'identifiant NON signé. Rendre le signé
    ferait chercher des fichiers qui n'existent pas, et l'artwork resterait."""
    existant = [entry.build_shortcut(rom("Chrono Trigger"))]
    r = reconcile.reconcile(existant, [], EMU_ROOT)
    assert r.orphaned_appids == [2398962978]


def test_renommer_un_jeu_orpheline_l_ancien_appid():
    """Le titre entre dans l'identifiant : le renommer en crée un autre."""
    r1 = reconcile.reconcile([], [rom("Chrono Trigger")], EMU_ROOT)
    ancien = reconcile.reconcile(r1.entries, [], EMU_ROOT).orphaned_appids
    r2 = reconcile.reconcile(r1.entries, [rom("Chrono Trigger (FR)")], EMU_ROOT)
    assert r2.orphaned_appids == ancien
    assert r2.created == ["Chrono Trigger (FR)"]


def test_doublons_dans_le_voulu_ne_creent_qu_une_entree():
    """Deux ROMs de même titre — régions différentes — ne peuvent pas coexister :
    leur identifiant serait identique et Steam n'en garderait qu'une."""
    r = reconcile.reconcile([], [rom("Sonic"), rom("Sonic")], EMU_ROOT)
    assert len(r.entries) == 1


def test_bibliotheque_vide_des_deux_cotes():
    r = reconcile.reconcile([], [], EMU_ROOT)
    assert r.entries == [] and r.created == [] and r.removed == []
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/steam/test_reconcile.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.steam.reconcile'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/steam/reconcile.py` :

```python
"""Réconciliation entre ce que Steam affiche et ce que le disque contient.

Fonction pure, sans effet de bord : elle prend l'existant et le voulu, elle
renvoie le résultat. Toute la logique délicate se teste ainsi sans Steam, sans
disque et sans réseau — et c'est précisément la logique qu'on n'a pas le droit
de rater, puisqu'elle SUPPRIME des entrées.

L'ordre des entrées conservées est préservé. Steam les renumérote de toute
façon, mais réordonner gratuitement la bibliothèque du propriétaire fabriquerait
une différence visible là où rien n'a changé.
"""
from __future__ import annotations

import dataclasses

from retro.steam import appid as appid_mod
from retro.steam import entry as entry_mod


@dataclasses.dataclass(frozen=True)
class ReconcileResult:
    entries: list[dict]
    created: list[str]
    removed: list[str]
    kept: list[str]
    orphaned_appids: list[int]  # NON signés : ce sont eux qui nomment l'artwork


def reconcile(
    existing: list[dict],
    wanted: list[entry_mod.RomEntry],
    emulation_root: str,
) -> ReconcileResult:
    # Les entrées voulues, indexées par identifiant. Un doublon de titre écrase :
    # deux ROMs de même titre produiraient le même identifiant et Steam n'en
    # garderait qu'une de toute façon.
    voulu: dict[int, dict] = {}
    for rom in wanted:
        raccourci = entry_mod.build_shortcut(rom)
        voulu[raccourci["appid"]] = raccourci

    sortie: list[dict] = []
    created: list[str] = []
    removed: list[str] = []
    kept: list[str] = []
    orphelins: list[int] = []
    vus: set[int] = set()

    for existante in existing:
        if not entry_mod.is_owned(existante, emulation_root):
            sortie.append(existante)          # jamais touchée
            continue
        cle = existante.get("appid")
        if cle in voulu:
            sortie.append(voulu[cle])         # remplacée : tags rafraîchis
            kept.append(voulu[cle]["appname"])
            vus.add(cle)
        else:
            removed.append(existante.get("appname", "?"))
            orphelins.append(appid_mod.to_unsigned(cle))

    for cle, raccourci in voulu.items():
        if cle not in vus:
            sortie.append(raccourci)
            created.append(raccourci["appname"])

    return ReconcileResult(
        entries=sortie,
        created=created,
        removed=removed,
        kept=kept,
        orphaned_appids=orphelins,
    )
```

- [ ] **Étape 4 : vérifier que les tests passent**

```bash
python3 -m pytest tests/steam/test_reconcile.py -v
```

Attendu : 11 passed.

- [ ] **Étape 5 : commit**

```bash
git add retro/steam/reconcile.py tests/steam/test_reconcile.py
git commit -m "feat(steam): réconciliation idempotente préservant les entrées étrangères"
```

---

## Tâche 6 : écriture atomique et garde Steam

Steam réécrit `shortcuts.vdf` à sa fermeture. Écrire pendant qu'il tourne perd
le travail sans rien signaler — c'est un échec qui ressemble à une réussite,
exactement ce que le dépôt s'interdit.

**Fichiers :**
- Créer : `retro/steam/writer.py`
- Test : `tests/steam/test_writer.py`

**Interfaces :**
- Consomme : `vdf_io.dumps_shortcuts`, `vdf_io.load_shortcuts` (tâche 1).
- Produit :
  - `SteamRunningError`
  - `steam_is_running(processes: list[str] | None = None) -> bool`
  - `assert_steam_not_running() -> None`
  - `write_shortcuts(path: pathlib.Path, entries: list[dict]) -> pathlib.Path | None`
    — renvoie le chemin du `.bak` créé, ou `None` s'il n'y avait rien à sauver.

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/steam/test_writer.py` :

```python
"""Écriture de shortcuts.vdf : atomicité, sauvegarde, garde Steam."""
import os
import pathlib
import types

import pytest

from retro.steam import vdf_io, writer

ENTREE = {
    "appid": -1, "appname": "Jeu", "exe": '"D:\\x.exe"', "StartDir": '"D:\\"',
    "icon": "", "ShortcutPath": "", "LaunchOptions": "", "IsHidden": 0,
    "AllowDesktopConfig": 1, "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0,
    "DevkitGameID": "", "DevkitOverrideAppID": 0, "LastPlayTime": 0,
    "tags": {"0": "Rétro"},
}


def test_ecrit_un_fichier_relisible(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    writer.write_shortcuts(p, [ENTREE])
    assert vdf_io.load_shortcuts(p) == [ENTREE]


def test_sauvegarde_l_ancien_fichier(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    ancien = dict(ENTREE, appname="Ancien")
    p.write_bytes(vdf_io.dumps_shortcuts([ancien]))
    bak = writer.write_shortcuts(p, [ENTREE])
    assert bak is not None and bak.exists()
    assert vdf_io.load_shortcuts(bak) == [ancien]


def test_pas_de_sauvegarde_si_rien_a_sauver(tmp_path):
    assert writer.write_shortcuts(tmp_path / "shortcuts.vdf", [ENTREE]) is None


def test_aucun_fichier_temporaire_ne_subsiste(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    writer.write_shortcuts(p, [ENTREE])
    assert [f.name for f in tmp_path.iterdir()] == ["shortcuts.vdf"]


def test_l_ancien_fichier_survit_a_un_echec(tmp_path, monkeypatch):
    """Écriture atomique : si le rendu échoue, l'ancien fichier est intact."""
    p = tmp_path / "shortcuts.vdf"
    p.write_bytes(vdf_io.dumps_shortcuts([ENTREE]))
    original = p.read_bytes()

    def explose(_entries):
        raise RuntimeError("rendu impossible")

    monkeypatch.setattr(writer.vdf_io, "dumps_shortcuts", explose)
    with pytest.raises(RuntimeError):
        writer.write_shortcuts(p, [ENTREE])
    assert p.read_bytes() == original


def test_steam_detecte_comme_actif():
    assert writer.steam_is_running(["explorer.exe", "steam.exe"])


def test_steam_detecte_comme_inactif():
    assert not writer.steam_is_running(["explorer.exe", "retroarch.exe"])


def test_steamwebhelper_ne_compte_pas():
    """steamwebhelper survit brièvement à la fermeture de Steam. Le prendre
    pour Steam bloquerait toute synchronisation sans raison."""
    assert not writer.steam_is_running(["steamwebhelper.exe"])


def test_detection_insensible_a_la_casse():
    assert writer.steam_is_running(["STEAM.EXE"])


def test_l_ecriture_passe_par_un_fichier_temporaire(tmp_path, monkeypatch):
    """L'atomicité elle-même, pas seulement l'ordre des opérations.

    Le test d'échec ci-dessus simule la panne dans dumps_shortcuts, donc avant
    tout contact avec le disque : mesuré, il reste vert même si l'on remplace
    temp+os.replace par une écriture directe. Il atteste « rendre avant
    d'écrire », pas « écrire ailleurs puis basculer ». Celui-ci pin le motif.
    """
    p = tmp_path / "shortcuts.vdf"
    ecrits, bascules = [], []
    vrai_write = pathlib.Path.write_bytes
    monkeypatch.setattr(pathlib.Path, "write_bytes",
                        lambda self, d: (ecrits.append(self.name), vrai_write(self, d))[1])
    vrai_replace = os.replace
    monkeypatch.setattr(os, "replace",
                        lambda a, b: (bascules.append((str(a), str(b))), vrai_replace(a, b))[1])
    writer.write_shortcuts(p, [ENTREE])
    assert "shortcuts.vdf" not in ecrits, f"écriture directe sur la cible : {ecrits}"
    assert len(bascules) == 1 and bascules[0][1].endswith("shortcuts.vdf")


def test_le_parsing_de_tasklist_extrait_les_noms(monkeypatch):
    """La branche Windows, testée sans Windows.

    Son mode de panne va dans le mauvais sens : un découpage cassé rend une
    liste vide, donc steam_is_running renvoie False pendant que Steam tourne et
    la garde devient silencieusement inactive.
    """
    sortie = '"steam.exe","4028","Console","1","89 340 K"\n"explorer.exe","912","Console","1","42 000 K"\n'
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(writer.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(stdout=sortie))
    assert writer._running_processes() == ["steam.exe", "explorer.exe"]
    assert writer.steam_is_running()


def test_la_garde_leve_une_erreur_explicite(monkeypatch):
    monkeypatch.setattr(writer, "_running_processes", lambda: ["steam.exe"])
    with pytest.raises(writer.SteamRunningError) as exc:
        writer.assert_steam_not_running()
    assert "steam" in str(exc.value).lower()
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/steam/test_writer.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.steam.writer'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/steam/writer.py` :

```python
"""Écriture de shortcuts.vdf.

Deux protections, et les deux sont là parce que leur absence produit un échec
MUET : Steam réécrit le fichier à sa fermeture, donc écrire pendant qu'il tourne
perd le travail sans rien dire ; et une écriture interrompue en place laisserait
une bibliothèque tronquée que Steam accepterait sans broncher.
"""
from __future__ import annotations

import datetime
import os
import pathlib
import subprocess

from retro.steam import vdf_io

# steamwebhelper.exe survit quelques secondes à la fermeture de Steam. Le
# compter pour Steam bloquerait la synchronisation sans raison, donc la
# correspondance est exacte, pas un préfixe.
STEAM_PROCESS_NAMES = {"steam.exe", "steam"}


class SteamRunningError(RuntimeError):
    """Steam tourne : écrire maintenant serait écrasé à sa fermeture."""


def _running_processes() -> list[str]:
    """Sous Windows uniquement. Ailleurs, la liste est vide : les tests et le
    développement sous Linux n'ont pas de Steam à surveiller."""
    if os.name != "nt":
        return []
    sortie = subprocess.run(
        ["tasklist", "/fo", "csv", "/nh"],
        capture_output=True, text=True, check=False,
    ).stdout
    return [ligne.split('","')[0].strip('"') for ligne in sortie.splitlines() if ligne]


def steam_is_running(processes: list[str] | None = None) -> bool:
    noms = _running_processes() if processes is None else processes
    return any(n.lower() in STEAM_PROCESS_NAMES for n in noms)


def assert_steam_not_running() -> None:
    if steam_is_running():
        raise SteamRunningError(
            "Steam est en cours d'exécution : il réécrirait shortcuts.vdf à sa "
            "fermeture et la synchronisation serait perdue. Fermer Steam d'abord."
        )


def write_shortcuts(path: pathlib.Path, entries: list[dict]) -> pathlib.Path | None:
    """Écriture atomique. Renvoie le chemin de la sauvegarde, ou None."""
    # Rendre AVANT de toucher au disque : un rendu qui échoue ne doit pas
    # laisser un fichier à moitié écrit ni une sauvegarde orpheline.
    blob = vdf_io.dumps_shortcuts(entries)

    sauvegarde = None
    if path.exists():
        horodatage = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        sauvegarde = path.with_suffix(f".vdf.bak-{horodatage}")
        sauvegarde.write_bytes(path.read_bytes())

    temporaire = path.with_suffix(".vdf.tmp")
    temporaire.write_bytes(blob)
    os.replace(temporaire, path)  # atomique sur Windows comme sur POSIX
    return sauvegarde
```

- [ ] **Étape 4 : vérifier que les tests passent**

```bash
python3 -m pytest tests/steam/test_writer.py -v
```

Attendu : 10 passed.

Si `test_sauvegarde_l_ancien_fichier` échoue sur le nom du fichier, noter que
`Path("shortcuts.vdf").with_suffix(".vdf.bak-…")` remplace le suffixe existant :
le résultat est `shortcuts.vdf.bak-…`, ce qui est voulu.

- [ ] **Étape 5 : commit**

```bash
git add retro/steam/writer.py tests/steam/test_writer.py
git commit -m "feat(steam): écriture atomique avec sauvegarde et garde Steam"
```

---

## Tâche 7 : artwork SteamGridDB

Les cinq assets sont ce qui sépare une bibliothèque crédible d'une bibliothèque
visiblement bricolée. Mais leur absence ne doit jamais empêcher un jeu de
remonter dans Steam.

**Fichiers :**
- Créer : `retro/steam/artwork.py`
- Créer : `tests/fixtures/sgdb-search.json`
- Créer : `tests/fixtures/sgdb-grids.json`
- Test : `tests/steam/test_artwork.py`

**Interfaces :**
- Consomme : `appid.grid_prefixes`, `appid.existing_asset` (tâche 2).
- Produit :
  - `ArtworkClient(api_key: str | None, fetch_json=…, fetch_bytes=…)` — les deux
    fonctions d'accès réseau sont injectées, ce qui rend la classe testable sans
    réseau.
  - `ArtworkClient.fetch_for(title: str, legacy_appid: int, grid_dir: pathlib.Path) -> list[str]`
    — renvoie les noms des fichiers écrits.
  - `prune_orphans(grid_dir: pathlib.Path, orphaned: list[int]) -> list[str]`

- [ ] **Étape 1 : créer les fixtures**

Fichier `tests/fixtures/sgdb-search.json` :

```json
{"success": true, "data": [{"id": 1234, "name": "Chrono Trigger"}]}
```

Fichier `tests/fixtures/sgdb-grids.json` :

```json
{"success": true, "data": [{"id": 1, "url": "https://exemple.invalid/portrait.jpg"}]}
```

Le domaine `.invalid` est réservé par la RFC 2606 : aucun test ne peut y accéder
par accident, même si l'injection venait à être contournée.

- [ ] **Étape 2 : écrire le test qui échoue**

Fichier `tests/steam/test_artwork.py` :

```python
"""Récupération de l'artwork. Aucun test ne touche le réseau."""
import json
import pathlib

from retro.steam import artwork

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"
RECHERCHE = json.loads((FIXTURES / "sgdb-search.json").read_text())
GRILLES = json.loads((FIXTURES / "sgdb-grids.json").read_text())


def faux_reseau(reponses=None):
    appels = []

    def fetch_json(url, headers):
        appels.append(url)
        if "search" in url:
            return RECHERCHE
        return (reponses or {}).get(url, GRILLES)

    def fetch_bytes(url):
        appels.append(url)
        return b"\xff\xd8\xff-image-factice"

    return fetch_json, fetch_bytes, appels


def test_sans_cle_ne_telecharge_rien(tmp_path):
    """Dégradation gracieuse : pas de clé, pas d'artwork, pas d'erreur."""
    fj, fb, appels = faux_reseau()
    client = artwork.ArtworkClient(api_key=None, fetch_json=fj, fetch_bytes=fb)
    assert client.fetch_for("Chrono Trigger", 2398962978, tmp_path) == []
    assert appels == []


def test_ecrit_les_assets_sous_les_bons_noms(tmp_path):
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    ecrits = client.fetch_for("Chrono Trigger", 2398962978, tmp_path)
    assert "2398962978p.jpg" in ecrits
    assert (tmp_path / "2398962978p.jpg").read_bytes().startswith(b"\xff\xd8\xff")


def test_les_cinq_assets_sont_demandes(tmp_path):
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    assert len(client.fetch_for("Chrono Trigger", 2398962978, tmp_path)) == 5


def test_asset_present_sous_une_autre_extension_non_retelecharge(tmp_path):
    """Le piège que la mesure a révélé : coder .jpg en dur ferait retélécharger
    à chaque synchronisation un portrait déjà présent en .png."""
    (tmp_path / "2398962978p.png").write_bytes(b"deja-la")
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    assert "2398962978p.jpg" not in client.fetch_for("Chrono Trigger", 2398962978, tmp_path)
    assert (tmp_path / "2398962978p.png").read_bytes() == b"deja-la"


def test_un_asset_deja_present_n_est_pas_retelecharge(tmp_path):
    """Chaque asset se décide INDIVIDUELLEMENT.

    Un portrait déjà présent ne doit ni être écrasé, ni empêcher la
    récupération des quatre autres. Sauter globalement dès qu'un seul asset
    existe laisserait à jamais incomplète toute bibliothèque dont une
    synchronisation s'est interrompue en cours de boucle.

    N'assertionne PAS « aucun appel ne contient telle URL » : le faux réseau
    rend la même URL pour tous les endpoints, et le client la redemande
    légitimement pour les assets manquants — l'assertion serait insatisfiable
    quel que soit le code.
    """
    (tmp_path / "2398962978p.jpg").write_bytes(b"deja-la")
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    ecrits = client.fetch_for("Chrono Trigger", 2398962978, tmp_path)
    assert (tmp_path / "2398962978p.jpg").read_bytes() == b"deja-la"
    assert not any(n.startswith("2398962978p.") for n in ecrits)
    assert len(ecrits) == 4, f"les quatre autres assets doivent être récupérés : {ecrits}"


def test_jeu_introuvable_ne_leve_pas(tmp_path):
    def fetch_json(url, headers):
        return {"success": True, "data": []}
    client = artwork.ArtworkClient(
        api_key="cle", fetch_json=fetch_json, fetch_bytes=lambda u: b"")
    assert client.fetch_for("Jeu Inconnu 9999", 123, tmp_path) == []


def test_erreur_reseau_ne_leve_pas(tmp_path):
    """L'artwork est un ornement. Une panne SteamGridDB ne doit pas faire
    échouer une synchronisation par ailleurs valide."""
    def fetch_json(url, headers):
        raise OSError("réseau injoignable")
    client = artwork.ArtworkClient(
        api_key="cle", fetch_json=fetch_json, fetch_bytes=lambda u: b"")
    assert client.fetch_for("Chrono Trigger", 2398962978, tmp_path) == []


def test_dossier_grid_cree_si_absent(tmp_path):
    cible = tmp_path / "grid"
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    client.fetch_for("Chrono Trigger", 2398962978, cible)
    assert cible.is_dir()


def test_la_cle_part_dans_l_en_tete(tmp_path):
    vus = []

    def fetch_json(url, headers):
        vus.append(headers)
        return {"success": True, "data": []}

    client = artwork.ArtworkClient(
        api_key="secret", fetch_json=fetch_json, fetch_bytes=lambda u: b"")
    client.fetch_for("X", 1, tmp_path)
    assert vus[0]["Authorization"] == "Bearer secret"


def test_purge_des_orphelins(tmp_path):
    for nom in ["111p.jpg", "111_hero.png", "111_icon.ico", "222p.jpg"]:
        (tmp_path / nom).write_bytes(b"x")
    supprimes = artwork.prune_orphans(tmp_path, [111])
    assert sorted(supprimes) == ["111_hero.png", "111_icon.ico", "111p.jpg"]
    assert (tmp_path / "222p.jpg").exists()


def test_la_purge_ne_deborde_pas_sur_un_appid_voisin(tmp_path):
    """111 préfixe la chaîne 1112 : une purge par préfixe de chaîne détruirait
    l'artwork d'un jeu parfaitement valide."""
    (tmp_path / "1112p.jpg").write_bytes(b"x")
    (tmp_path / "111p.jpg").write_bytes(b"x")
    assert artwork.prune_orphans(tmp_path, [111]) == ["111p.jpg"]
    assert (tmp_path / "1112p.jpg").exists()


def test_purge_sans_orphelin_ne_touche_a_rien(tmp_path):
    (tmp_path / "222p.jpg").write_bytes(b"x")
    assert artwork.prune_orphans(tmp_path, []) == []
    assert (tmp_path / "222p.jpg").exists()


def test_purge_sur_dossier_absent(tmp_path):
    assert artwork.prune_orphans(tmp_path / "jamais", [111]) == []
```

- [ ] **Étape 3 : vérifier que le test échoue**

```bash
python3 -m pytest tests/steam/test_artwork.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.steam.artwork'`.

- [ ] **Étape 4 : implémenter**

Fichier `retro/steam/artwork.py` :

```python
"""Artwork de bibliothèque, depuis SteamGridDB.

L'accès réseau est INJECTÉ plutôt qu'appelé directement : c'est ce qui permet
aux tests de couvrir la logique — quels assets, quels noms, quoi ne pas
retélécharger — sans jamais toucher au réseau.

Aucune erreur ne remonte de ce module. L'artwork est un ornement : une panne
SteamGridDB ne doit pas faire échouer une synchronisation qui, par ailleurs,
fait très bien remonter les jeux.
"""
from __future__ import annotations

import pathlib

import requests

from retro.steam import appid as appid_mod

BASE = "https://www.steamgriddb.com/api/v2"

# Le type d'asset SteamGridDB pour chaque nom de fichier attendu par Steam.
ASSETS = (
    ("portrait", "grids", {"dimensions": "600x900"}),
    ("paysage", "grids", {"dimensions": "920x430"}),
    ("hero", "heroes", {}),
    ("logo", "logos", {}),
    ("icone", "icons", {}),
)



def _fetch_json(url: str, headers: dict) -> dict:
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def _fetch_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


class ArtworkClient:
    def __init__(self, api_key: str | None, fetch_json=_fetch_json, fetch_bytes=_fetch_bytes):
        self.api_key = api_key
        self._fetch_json = fetch_json
        self._fetch_bytes = fetch_bytes

    def fetch_for(self, title: str, legacy_appid: int, grid_dir: pathlib.Path) -> list[str]:
        if not self.api_key:
            return []  # dégradation gracieuse, pas une erreur
        prefixes = appid_mod.grid_prefixes(legacy_appid)
        manquants = {k: pre for k, pre in prefixes.items()
                     if appid_mod.existing_asset(grid_dir, pre) is None}
        if not manquants:
            return []
        entetes = {"Authorization": f"Bearer {self.api_key}"}
        try:
            recherche = self._fetch_json(f"{BASE}/search/autocomplete/{title}", entetes)
            resultats = recherche.get("data") or []
            if not resultats:
                return []
            jeu_id = resultats[0]["id"]
            grid_dir.mkdir(parents=True, exist_ok=True)
            ecrits = []
            for cle, endpoint, params in ASSETS:
                if cle not in manquants:
                    continue
                suffixe = "".join(f"?{k}={v}" for k, v in params.items())
                reponse = self._fetch_json(f"{BASE}/{endpoint}/game/{jeu_id}{suffixe}", entetes)
                candidats = reponse.get("data") or []
                if not candidats:
                    continue
                url = candidats[0]["url"]
                # L'extension suit la source : Steam accepte .png, .jpg et .ico
                # indifféremment, et la conserver évite de retélécharger à chaque
                # passage un asset déjà présent sous un autre suffixe.
                ext = pathlib.PurePosixPath(url).suffix or ".png"
                nom = f"{manquants[cle]}{ext}"
                (grid_dir / nom).write_bytes(self._fetch_bytes(url))
                ecrits.append(nom)
            return ecrits
        except Exception:  # noqa: BLE001 - volontairement large, voir docstring
            return []


def prune_orphans(grid_dir: pathlib.Path, orphaned: list[int]) -> list[str]:
    """Supprime l'artwork des identifiants abandonnés.

    Renommer un jeu change son identifiant : sans cette purge, chaque
    renommage laisserait quatre fichiers que plus rien ne référence.
    """
    if not orphaned or not grid_dir.is_dir():
        return []
    # Comparaison sur le STEM entier, jamais sur un préfixe de chaîne :
    # l'appid 111 préfixe aussi 1112p.png, qui appartient à un autre jeu.
    condamnes = {pre for a in orphaned for pre in appid_mod.grid_prefixes(a).values()}
    supprimes = []
    for fichier in grid_dir.iterdir():
        if fichier.stem in condamnes:
            fichier.unlink()
            supprimes.append(fichier.name)
    return supprimes
```

- [ ] **Étape 5 : vérifier que les tests passent**

```bash
python3 -m pytest tests/steam/test_artwork.py -v
```

Attendu : 10 passed.

- [ ] **Étape 6 : commit**

```bash
git add retro/steam/artwork.py tests/steam/test_artwork.py tests/fixtures/
git commit -m "feat(steam): artwork SteamGridDB avec dégradation gracieuse"
```

---

## Tâche 8 : commande `retro sync`

Assemble les sept tâches précédentes en une commande utilisable, et produit le
rapport que l'hôte relaiera au propriétaire.

**Fichiers :**
- Créer : `retro/steam/sync.py`
- Créer : `retro/cli.py`
- Test : `tests/steam/test_sync.py`
- Test : `tests/test_cli.py`

**Interfaces :**
- Consomme : tout ce qui précède.
- Produit :
  - `SyncReport` — dataclass gelée : `account_id: str`, `created: list[str]`,
    `removed: list[str]`, `kept: list[str]`, `artwork_written: int`,
    `artwork_pruned: int`, `backup: pathlib.Path | None`.
  - `sync_account(account, wanted, emulation_root, artwork_client) -> SyncReport`
  - `format_report(reports: list[SyncReport]) -> str`
  - `main(argv: list[str] | None = None) -> int`

**Note :** l'inventaire des ROMs (`wanted`) est produit par le sous-projet A.
Cette tâche le reçoit en paramètre et ne le fabrique jamais elle-même — c'est
ce qui garde les deux sous-projets indépendants. La commande `retro sync` du
sous-projet B lit un inventaire JSON ; le sous-projet C la branchera sur le
scanner réel.

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/steam/test_sync.py` :

```python
"""Synchronisation d'un compte, de bout en bout, sans Steam ni réseau."""
import pathlib

from retro.steam import accounts, artwork, entry, sync, vdf_io


class ArtworkMuet(artwork.ArtworkClient):
    def __init__(self):
        super().__init__(api_key=None)


class ArtworkTemoin(artwork.ArtworkClient):
    """Observe l'état du monde au moment où l'artwork est demandé.

    ArtworkMuet ne peut rien attester : il rend [] sans regarder ni le disque ni
    l'entrée. Mesuré — avec lui seul, inverser l'ordre artwork/écriture ou
    retirer le filtre de propriété laisse toute la suite verte.
    """

    def __init__(self, shortcuts_path):
        super().__init__(api_key=None)
        self.shortcuts_path = shortcuts_path
        self.appels = []

    def fetch_for(self, title, legacy_appid, grid_dir):
        self.appels.append((title, self.shortcuts_path.exists()))
        return []


def faire_compte(tmp_path):
    config = tmp_path / "userdata" / "123" / "config"
    config.mkdir(parents=True)
    return accounts.SteamAccount(account_id="123", config_dir=config)


def etranger(nom):
    """Un jeu non-Steam que le propriétaire a ajouté lui-même."""
    return {
        "appid": 42, "appname": nom, "exe": '"C:\\Jeux\\perso.exe"',
        "StartDir": '"C:\\Jeux"', "icon": "", "ShortcutPath": "",
        "LaunchOptions": "", "IsHidden": 0, "AllowDesktopConfig": 1,
        "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0, "DevkitGameID": "",
        "DevkitOverrideAppID": 0, "FlatpakAppID": "", "sortas": "",
        "LastPlayTime": 0, "tags": {"0": "Favoris"},
    }


def rom(titre):
    return entry.RomEntry(
        title=titre,
        rom_path=f"G:\\ROMs\\snes\\{titre}.sfc",
        system_name="Super Nintendo",
        emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
        launch_template='-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        start_dir="D:\\Emulation\\RetroArch",
    )


def test_synchronisation_depuis_zero(tmp_path):
    compte = faire_compte(tmp_path)
    rapport = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    assert rapport.created == ["Chrono Trigger"]
    assert [e["appname"] for e in vdf_io.load_shortcuts(compte.shortcuts_path)] == ["Chrono Trigger"]


def test_deuxieme_passage_ne_change_rien(tmp_path):
    compte = faire_compte(tmp_path)
    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    avant = compte.shortcuts_path.read_bytes()
    r2 = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    assert r2.created == [] and r2.removed == []
    assert compte.shortcuts_path.read_bytes() == avant


def test_l_artwork_est_recupere_avant_l_ecriture(tmp_path):
    """Un jeu sans vignette vaut mieux qu'une vignette sans jeu : une panne
    d'artwork ne doit pas empêcher les raccourcis d'être écrits. Le témoin
    observe que shortcuts.vdf n'existe pas encore quand l'artwork est demandé."""
    compte = faire_compte(tmp_path)
    client = ArtworkTemoin(compte.shortcuts_path)
    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", client)
    assert client.appels, "l'artwork n'a jamais été demandé"
    assert all(not existait for _, existait in client.appels), (
        "shortcuts.vdf existait déjà : l'écriture a précédé l'artwork"
    )


def test_l_artwork_n_est_demande_que_pour_nos_entrees(tmp_path):
    """Chercher de l'artwork pour les jeux du propriétaire écraserait le sien."""
    compte = faire_compte(tmp_path)
    compte.shortcuts_path.write_bytes(vdf_io.dumps_shortcuts([etranger("Mon jeu à moi")]))
    client = ArtworkTemoin(compte.shortcuts_path)
    sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", client)
    assert [t for t, _ in client.appels] == ["Chrono Trigger"]


def test_le_rapport_est_lisible(tmp_path):
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [rom("Chrono Trigger")], "D:\\Emulation", ArtworkMuet())
    texte = sync.format_report([r])
    assert "Chrono Trigger" in texte and "123" in texte


def test_rapport_vide_le_dit(tmp_path):
    compte = faire_compte(tmp_path)
    r = sync.sync_account(compte, [], "D:\\Emulation", ArtworkMuet())
    assert "aucun" in sync.format_report([r]).lower()
```

Fichier `tests/test_cli.py` :

```python
"""Interface en ligne de commande."""
import json

from retro import cli


def test_sync_sans_inventaire_echoue_proprement(tmp_path, capsys):
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--inventory", str(tmp_path / "absent.json")])
    assert code != 0
    assert "absent.json" in capsys.readouterr().err


def test_sync_sans_compte_steam_echoue_proprement(tmp_path, capsys):
    inventaire = tmp_path / "inv.json"
    inventaire.write_text("[]")
    (tmp_path / "userdata").mkdir()
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--inventory", str(inventaire)])
    assert code != 0
    assert "connect" in capsys.readouterr().err.lower()


def test_inventaire_malforme_ne_leve_pas_de_trace(tmp_path, capsys):
    """Une console sans clavier ni écran ne doit jamais rendre de trace Python."""
    (tmp_path / "userdata" / "123" / "config").mkdir(parents=True)
    mauvais = tmp_path / "inv.json"
    mauvais.write_text("{ceci n'est pas du JSON")
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--inventory", str(mauvais)])
    assert code != 0
    assert "Traceback" not in capsys.readouterr().err


def test_sync_complet(tmp_path, capsys):
    (tmp_path / "userdata" / "123" / "config").mkdir(parents=True)
    inventaire = tmp_path / "inv.json"
    inventaire.write_text(json.dumps([{
        "title": "Chrono Trigger",
        "rom_path": "G:\\ROMs\\snes\\ct.sfc",
        "system_name": "Super Nintendo",
        "emulator_exe": "D:\\Emulation\\RetroArch\\retroarch.exe",
        "launch_template": '-L "cores\\snes9x_libretro.dll" -f "{rom}"',
        "start_dir": "D:\\Emulation\\RetroArch",
        "extra_tags": ["1995"],
    }]))
    code = cli.main(["sync", "--steam-root", str(tmp_path),
                     "--inventory", str(inventaire)])
    assert code == 0
    assert "Chrono Trigger" in capsys.readouterr().out
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/steam/test_sync.py tests/test_cli.py -v
```

Attendu : `ModuleNotFoundError` sur `retro.steam.sync` puis `retro.cli`.

- [ ] **Étape 3 : implémenter `sync.py`**

Fichier `retro/steam/sync.py` :

```python
"""Synchronisation d'un compte Steam."""
from __future__ import annotations

import dataclasses
import pathlib

from retro.steam import appid as appid_mod
from retro.steam import accounts, artwork, entry, reconcile, vdf_io, writer


@dataclasses.dataclass(frozen=True)
class SyncReport:
    account_id: str
    created: list[str]
    removed: list[str]
    kept: list[str]
    artwork_written: int
    artwork_pruned: int
    backup: pathlib.Path | None


def sync_account(
    account: accounts.SteamAccount,
    wanted: list[entry.RomEntry],
    emulation_root: str,
    artwork_client,
) -> SyncReport:
    existant = vdf_io.load_shortcuts(account.shortcuts_path)
    resultat = reconcile.reconcile(existant, wanted, emulation_root)

    # L'artwork AVANT l'écriture : un jeu sans vignette vaut mieux qu'une
    # vignette sans jeu, et une panne réseau ne doit pas empêcher l'écriture.
    ecrits = 0
    for raccourci in resultat.entries:
        if not entry.is_owned(raccourci, emulation_root):
            continue
        legacy = appid_mod.to_unsigned(raccourci["appid"])
        ecrits += len(artwork_client.fetch_for(raccourci["appname"], legacy, account.grid_dir))

    purges = len(artwork.prune_orphans(account.grid_dir, resultat.orphaned_appids))

    sauvegarde = writer.write_shortcuts(account.shortcuts_path, resultat.entries)
    return SyncReport(
        account_id=account.account_id,
        created=resultat.created,
        removed=resultat.removed,
        kept=resultat.kept,
        artwork_written=ecrits,
        artwork_pruned=purges,
        backup=sauvegarde,
    )


def format_report(reports: list[SyncReport]) -> str:
    lignes = []
    for r in reports:
        lignes.append(f"Compte {r.account_id}")
        if not r.created and not r.removed:
            lignes.append(f"  aucun changement ({len(r.kept)} jeux déjà à jour)")
        for titre in r.created:
            lignes.append(f"  + {titre}")
        for titre in r.removed:
            lignes.append(f"  - {titre}")
        lignes.append(
            f"  artwork : {r.artwork_written} récupéré(s), {r.artwork_pruned} purgé(s)"
        )
        if r.backup:
            lignes.append(f"  sauvegarde : {r.backup.name}")
    return "\n".join(lignes)
```

- [ ] **Étape 4 : implémenter `cli.py`**

Fichier `retro/cli.py` :

```python
"""Ligne de commande de retro."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from retro.steam import accounts, artwork, entry, sync

DEFAULT_STEAM_ROOT = "D:\\Steam"
DEFAULT_EMULATION_ROOT = "D:\\Emulation"


def _load_inventory(path: pathlib.Path) -> list[entry.RomEntry]:
    donnees = json.loads(path.read_text(encoding="utf-8"))
    return [
        entry.RomEntry(
            title=d["title"],
            rom_path=d["rom_path"],
            system_name=d["system_name"],
            emulator_exe=d["emulator_exe"],
            launch_template=d["launch_template"],
            start_dir=d["start_dir"],
            extra_tags=tuple(d.get("extra_tags", ())),
        )
        for d in donnees
    ]


def _cmd_sync(args) -> int:
    inventaire_path = pathlib.Path(args.inventory)
    if not inventaire_path.exists():
        print(f"inventaire introuvable : {inventaire_path}", file=sys.stderr)
        return 2
    try:
        writer_guard()
        comptes = accounts.discover_accounts(pathlib.Path(args.steam_root))
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 3

    voulu = _load_inventory(inventaire_path)
    client = artwork.ArtworkClient(api_key=args.steamgriddb_key)
    rapports = [
        sync.sync_account(c, voulu, args.emulation_root, client) for c in comptes
    ]
    print(sync.format_report(rapports))
    return 0


def writer_guard() -> None:
    """Isolée pour rester monkeypatchable dans les tests."""
    from retro.steam import writer
    writer.assert_steam_not_running()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retro")
    sous = parser.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("sync", help="fait remonter les ROMs dans Steam")
    p.add_argument("--steam-root", default=DEFAULT_STEAM_ROOT)
    p.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    p.add_argument("--inventory", required=True,
                   help="inventaire JSON produit par le scanner (sous-projet A)")
    p.add_argument("--steamgriddb-key", default=None)
    p.set_defaults(func=_cmd_sync)

    args = parser.parse_args(argv)
    return args.func(args)
```

- [ ] **Étape 5 : vérifier que les tests passent**

```bash
python3 -m pytest -v
```

Attendu : toute la suite verte, tâches 1 à 8.

- [ ] **Étape 6 : commit**

```bash
git add retro/steam/sync.py retro/cli.py tests/
git commit -m "feat(cli): commande retro sync"
```

---

## Vérification finale

- [ ] **Suite complète**

```bash
python3 -m pytest -v
```

- [ ] **Aucun test ne touche le réseau**

```bash
grep -rn "requests\.\|urlopen\|http://\|https://" tests/ | grep -v ".invalid"
```

Attendu : aucune ligne. Toute occurrence est un test à corriger.

- [ ] **Le tag de propriété n'est écrit qu'une fois**

```bash
grep -rn "Rétro" retro/ | grep -v "OWNER_TAG ="
```

Attendu : aucune ligne hors de la définition dans `entry.py`.

- [ ] **Aucune ROM ni binaire dans le dépôt**

```bash
find . -name "*.sfc" -o -name "*.nes" -o -name "*.iso" -o -name "*.exe" | grep -v "\.git"
```

Attendu : aucune ligne.

## Ce que ce sous-projet ne fait pas

- **Le scan des ROMs** — sous-projet A. `retro sync` reçoit un inventaire JSON.
- **L'installation des émulateurs** — sous-projet A.
- **Les métadonnées ScreenScraper** — sous-projet C ; les `extra_tags` arrivent
  déjà remplis dans l'inventaire.
- **La sentinelle `steam.hold` et l'arrêt de Steam** — sous-projet C, côté hôte
  et PowerShell. Ici, `retro sync` se contente de **refuser** si Steam tourne.
- **La vérification ViGEmBus** — sous-projet C, dans `installer`.
- **Le cinquième asset, l'icône** — sous-projet C. Les quatre fichiers de
  `grid\` couvrent toutes les vues de Big Picture ; l'icône n'apparaît que dans
  des listes compactes. Elle est reportée pour une raison technique et non par
  oubli : le champ `icon` porte un **chemin Windows absolu**, que des tests
  tournant sous Linux ne peuvent pas construire honnêtement. Le sous-projet C,
  qui s'exécute sur la VM, dispose du vrai chemin. `build_shortcut` laisse donc
  le champ vide, et le renseigner plus tard ne change pas l'identifiant — celui-ci
  ne dépend que de `exe` et `appname`.
