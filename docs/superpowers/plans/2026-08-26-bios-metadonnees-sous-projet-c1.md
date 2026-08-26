# BIOS, métadonnées et rapport (sous-projet C1) — plan d'implémentation

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development`. Les étapes utilisent la syntaxe
> case à cocher (`- [ ]`).

**Objectif :** dire au propriétaire ce qui manque avant qu'il s'en aperçoive
manette en main, et enrichir sa bibliothèque des métadonnées que Steam sait
afficher.

**Architecture :** trois modules sans effet de bord au-delà d'un cache local,
plus une commande qui ne modifie rien. `retro status` est le seul endroit du
projet dont le but est d'être lu par un humain — tout le reste est conçu pour
tourner sans témoin.

**Pile technique :** Python 3.11+, `requests`, `pytest`.

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`

## Contraintes globales

- **Python 3.11 minimum.**
- **Aucun test ne touche le réseau.** L'accès HTTP est injecté, comme dans
  `retro/steam/artwork.py`.
- **Aucun test n'exige Steam ni Windows.**
- **Les chemins Windows sont des `str`**, jamais des `pathlib.Path` — sous
  Linux, `Path("D:\\Emulation")` est un chemin relatif. Les `Path` servent au
  disque local.
- **Aucune ROM, aucun BIOS, aucun binaire dans le dépôt**, y compris en
  fixture. Un BIOS ne peut pas être distribué : les fixtures fabriquent des
  fichiers quelconques et calculent leur empreinte à la volée.
- **Les empreintes de BIOS sont des `md5`**, pas des `sha1` : ce sont les
  seules publiquement citables, et calculer un SHA-1 aurait exigé de faire
  entrer un BIOS dans le dépôt.
- **Aucune erreur ne remonte des métadonnées.** Comme l'artwork, elles sont un
  ornement : une panne ne doit jamais empêcher un jeu de remonter dans Steam.
- **Un test qui passerait quelle que soit l'implémentation est un défaut.**
  Ce projet en a rencontré plusieurs ; vérifier qu'un test échoue avant sa
  correction fait partie de la tâche.

---

## Tâche 1 : la vérification des BIOS

Sans BIOS, un jeu PlayStation apparaît dans Steam, se lance, écran noir. Rien
n'explique pourquoi, et le propriétaire est sur son canapé sans clavier.

**Fichiers :**
- Créer : `retro/bios.py`
- Test : `tests/test_bios.py`

**Interfaces :**
- Consomme : `profiles.Profile`, `profiles.System`.
- Produit :
  - `BiosFile` — dataclass gelée : `name: str`, `expected_md5: str`,
    `required: bool`, `state: str` (`"ok"`, `"absent"`, `"corrompu"`).
  - `SystemBios` — dataclass gelée : `system_id: str`, `system_name: str`,
    `files: tuple[BiosFile, ...]`, et deux propriétés `ok: bool` et
    `missing_required: tuple[str, ...]`.
  - `check_bios(profils: dict, bios_root: pathlib.Path) -> list[SystemBios]`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/test_bios.py` :

```python
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
  {{ file = "scph5501.bin", md5 = "{md5_a}", required = true }},
  {{ file = "scph5502.bin", md5 = "{md5_b}", required = false }},
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
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/test_bios.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.bios'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/bios.py` :

```python
"""Les BIOS que les émulateurs exigent, et ce qui manque.

Sans BIOS, un jeu PlayStation apparaît dans Steam, se lance, écran noir. Rien
n'explique pourquoi, et le propriétaire est sur son canapé sans clavier : ce
module existe pour que « rien ne se passe » devienne une phrase lisible.

Trois états, pas deux. « Corrompu » n'est pas « absent » : le propriétaire
croit avoir déposé le fichier, et lui dire qu'il manque l'enverrait chercher ce
qui est déjà là.
"""
from __future__ import annotations

import dataclasses
import hashlib
import pathlib


@dataclasses.dataclass(frozen=True)
class BiosFile:
    name: str
    expected_md5: str
    required: bool
    state: str  # "ok" | "absent" | "corrompu"


@dataclasses.dataclass(frozen=True)
class SystemBios:
    system_id: str
    system_name: str
    files: tuple[BiosFile, ...]

    @property
    def ok(self) -> bool:
        return not self.missing_required

    @property
    def missing_required(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.files
                     if f.required and f.state != "ok")


def _trouver(racine: pathlib.Path, nom: str) -> pathlib.Path | None:
    """Le fichier, quelle que soit la casse de son nom.

    Le propriétaire dépose ses BIOS depuis Windows, qui ne distingue pas la
    casse ; ce code tourne peut-être sur un système qui la distingue.
    """
    try:
        direct = racine / nom
        if direct.is_file():
            return direct
        if not racine.is_dir():
            return None
        cible = nom.lower()
        for f in racine.iterdir():
            if f.is_file() and f.name.lower() == cible:
                return f
    except OSError:
        # Un dossier illisible est indiscernable d'un dossier absent du point de
        # vue du propriétaire : dans les deux cas, ses BIOS ne servent à rien.
        return None
    return None


def check_bios(profils: dict, bios_root: pathlib.Path) -> list[SystemBios]:
    """L'état des BIOS, système par système. Ne lève jamais : une racine
    absente — un partage non monté — est un résultat, pas une erreur."""
    resultat = []
    for pid in sorted(profils):
        for systeme in profils[pid].systems:
            fichiers = []
            for declare in systeme.bios:
                nom = declare["file"]
                attendu = declare["md5"].lower()
                chemin = _trouver(bios_root, nom)
                if chemin is None:
                    etat = "absent"
                else:
                    try:
                        obtenu = hashlib.md5(chemin.read_bytes()).hexdigest()
                    except OSError:
                        # Présent mais illisible — permissions refusées, partage
                        # qui répond sans servir. « Corrompu » est exactement ce
                        # que c'est pour le propriétaire : le fichier est là et
                        # ne sert à rien. Lever ici ferait échouer le rapport
                        # entier pour un seul fichier.
                        etat = "corrompu"
                    else:
                        etat = "ok" if obtenu == attendu else "corrompu"
                fichiers.append(BiosFile(
                    name=nom, expected_md5=attendu,
                    required=bool(declare.get("required", True)), state=etat,
                ))
            resultat.append(SystemBios(
                system_id=systeme.id, system_name=systeme.name,
                files=tuple(fichiers),
            ))
    return resultat
```

- [ ] **Étape 4 : vérifier que les tests passent**

```bash
python3 -m pytest tests/test_bios.py -v
```

Attendu : 9 passed.

- [ ] **Étape 5 : commit**

```bash
git add retro/bios.py tests/test_bios.py
git commit -m "feat(bios): verification des BIOS requis, avec l'etat corrompu distinct"
```

---

## Tâche 2 : les métadonnées

**Fichiers :**
- Créer : `retro/metadata.py`
- Créer : `tests/fixtures/screenscraper-jeu.json`
- Test : `tests/test_metadata.py`

**Interfaces :**
- Consomme : `entry.RomEntry`.
- Produit :
  - `Metadata` — dataclass gelée : `title: str`, `year: str`, `genre: str`,
    `players: str`, `publisher: str`, `synopsis: str`.
  - `MetadataClient(api_key, cache_dir, fetch_json=…)`
  - `MetadataClient.tags_for(rom_filename, system_id) -> tuple[str, ...]`
  - `enrich(entries, client, dimensions=("decennie", "genre")) -> list[RomEntry]`

- [ ] **Étape 1 : créer la fixture**

Fichier `tests/fixtures/screenscraper-jeu.json` — la forme réduite de ce que
rend l'API, avec seulement les champs lus :

```json
{
  "response": {
    "jeu": {
      "noms": [{"region": "wor", "text": "Chrono Trigger"}],
      "dates": [{"region": "wor", "text": "1995-03-11"}],
      "genres": [{"noms": [{"langue": "fr", "text": "RPG"}]}],
      "joueurs": {"text": "1"},
      "editeur": {"text": "Square"},
      "synopsis": [{"langue": "fr", "text": "Un jeu de rôle."}]
    }
  }
}
```

- [ ] **Étape 2 : écrire le test qui échoue**

Fichier `tests/test_metadata.py` :

```python
"""Métadonnées : ce que Steam sait afficher, et rien de plus.

shortcuts.vdf n'a aucun champ de description, de date ou d'éditeur. Toute la
richesse passe par les tags — d'où l'extraction de la décennie, du genre et du
nombre de joueurs, qui deviennent des catégories filtrables à la manette.

Aucun test ne touche le réseau.
"""
import json
import pathlib

import pytest

from retro import metadata
from retro.steam import entry

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
JEU = json.loads((FIXTURES / "screenscraper-jeu.json").read_text(encoding="utf-8"))


def faux_reseau(reponse=None, erreur=None):
    appels = []

    def fetch_json(url, params):
        appels.append((url, params))
        if erreur:
            raise erreur
        return reponse if reponse is not None else JEU

    return fetch_json, appels


def rom(titre="Chrono Trigger"):
    return entry.RomEntry(
        title=titre, rom_path=f"G:\\ROMs\\snes\\{titre}.sfc",
        system_name="Super Nintendo",
        emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
        launch_template='-f "{rom}"', start_dir="D:\\Emulation\\RetroArch",
    )


def test_sans_cle_aucun_appel(tmp_path):
    """Dégradation gracieuse : pas de clé, pas de métadonnées, pas d'erreur."""
    fj, appels = faux_reseau()
    c = metadata.MetadataClient(api_key=None, cache_dir=tmp_path, fetch_json=fj)
    assert c.tags_for("Chrono Trigger.sfc", "snes") == ()
    assert appels == []


def test_les_tags_sont_extraits(tmp_path):
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    tags = c.tags_for("Chrono Trigger.sfc", "snes")
    assert "1990s" in tags
    assert "RPG" in tags


def test_le_cache_evite_un_second_appel(tmp_path):
    """Trois mille ROMs et une API à quota : le cache n'est pas un confort."""
    fj, appels = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    c.tags_for("Chrono Trigger.sfc", "snes")
    c.tags_for("Chrono Trigger.sfc", "snes")
    assert len(appels) == 1


def test_le_cache_survit_a_un_nouveau_client(tmp_path):
    fj, appels = faux_reseau()
    metadata.MetadataClient(api_key="cle", cache_dir=tmp_path,
                            fetch_json=fj).tags_for("Chrono Trigger.sfc", "snes")
    metadata.MetadataClient(api_key="cle", cache_dir=tmp_path,
                            fetch_json=fj).tags_for("Chrono Trigger.sfc", "snes")
    assert len(appels) == 1


def test_une_panne_reseau_ne_leve_pas(tmp_path):
    """Les métadonnées sont un ornement : une panne ne doit jamais empêcher un
    jeu de remonter dans Steam."""
    fj, _ = faux_reseau(erreur=OSError("réseau injoignable"))
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    assert c.tags_for("Chrono Trigger.sfc", "snes") == ()


def test_un_jeu_inconnu_ne_leve_pas(tmp_path):
    fj, _ = faux_reseau(reponse={"response": {}})
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    assert c.tags_for("Inconnu 9999.sfc", "snes") == ()


def test_une_reponse_partielle_rend_ce_qu_elle_peut(tmp_path):
    """L'API rend des fiches très inégales : l'absence d'un champ ne doit pas
    faire perdre les autres."""
    fj, _ = faux_reseau(reponse={"response": {"jeu": {
        "genres": [{"noms": [{"langue": "fr", "text": "Plateforme"}]}]}}})
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    assert c.tags_for("X.sfc", "snes") == ("Plateforme",)


def test_la_cle_ne_fuit_pas_dans_le_cache(tmp_path):
    """Le cache vit sur le volume de jeux, que d'autres outils lisent."""
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="secret-de-l-api", cache_dir=tmp_path,
                                fetch_json=fj)
    c.tags_for("Chrono Trigger.sfc", "snes")
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert "secret-de-l-api" not in f.read_text(encoding="utf-8")


# --- enrichissement d'un inventaire ---

def test_enrich_remplit_les_extra_tags(tmp_path):
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    enrichies = metadata.enrich([rom()], c)
    assert "RPG" in enrichies[0].extra_tags


def test_enrich_ne_touche_pas_aux_autres_champs(tmp_path):
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    avant = rom()
    apres = metadata.enrich([avant], c)[0]
    for champ in ("title", "rom_path", "system_name", "emulator_exe",
                  "launch_template", "start_dir"):
        assert getattr(apres, champ) == getattr(avant, champ)


def test_enrich_sans_cle_rend_l_inventaire_intact(tmp_path):
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key=None, cache_dir=tmp_path, fetch_json=fj)
    assert metadata.enrich([rom()], c) == [rom()]


def test_les_dimensions_sont_configurables(tmp_path):
    """Trois mille jeux et huit tags chacun rendent Big Picture illisible."""
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    seul_genre = metadata.enrich([rom()], c, dimensions=("genre",))[0]
    assert seul_genre.extra_tags == ("RPG",)
```

- [ ] **Étape 3 : vérifier que le test échoue**

```bash
python3 -m pytest tests/test_metadata.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.metadata'`.

- [ ] **Étape 4 : implémenter**

Fichier `retro/metadata.py` :

```python
"""Ce que Steam sait afficher d'un jeu non-Steam : des tags, et rien d'autre.

`shortcuts.vdf` n'a aucun champ de description, de date de sortie ou
d'éditeur — c'est une limite du format, pas un oubli. Toute la richesse passe
donc par les tags, qui deviennent des catégories filtrables à la manette dans
Big Picture.

Aucune erreur ne remonte de ce module. Les métadonnées sont un ornement : une
panne de l'API ne doit jamais empêcher un jeu de remonter dans Steam.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import re

BASE = "https://api.screenscraper.fr/api2/jeuInfos.php"
DIMENSIONS = ("decennie", "genre", "joueurs")


@dataclasses.dataclass(frozen=True)
class Metadata:
    title: str = ""
    year: str = ""
    genre: str = ""
    players: str = ""
    publisher: str = ""
    synopsis: str = ""


def _premier(liste, *cles):
    """Le premier texte d'une liste de traductions, quelle que soit la forme.

    L'API rend des fiches très inégales : listes vides, champs absents,
    langues variables. L'absence d'un champ ne doit pas faire perdre les autres.
    """
    if not isinstance(liste, list):
        liste = [liste] if liste else []
    for element in liste:
        if isinstance(element, dict):
            for cle in cles:
                if element.get(cle):
                    return str(element[cle])
    return ""


def _lire(jeu: dict) -> Metadata:
    genres = jeu.get("genres") or []
    genre = ""
    if genres and isinstance(genres[0], dict):
        genre = _premier(genres[0].get("noms"), "text")
    date = _premier(jeu.get("dates"), "text")
    return Metadata(
        title=_premier(jeu.get("noms"), "text"),
        year=date[:4] if date[:4].isdigit() else "",
        genre=genre,
        players=str((jeu.get("joueurs") or {}).get("text", "")),
        publisher=str((jeu.get("editeur") or {}).get("text", "")),
        synopsis=_premier(jeu.get("synopsis"), "text"),
    )


def _fetch_json(url: str, params: dict) -> dict:
    import requests
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


class MetadataClient:
    def __init__(self, api_key: str | None, cache_dir: pathlib.Path,
                 fetch_json=_fetch_json):
        self.api_key = api_key
        self.cache_dir = cache_dir
        self._fetch_json = fetch_json

    def _chemin_cache(self, rom_filename: str, system_id: str) -> pathlib.Path:
        cle = hashlib.sha256(f"{system_id}/{rom_filename}".encode()).hexdigest()[:32]
        return self.cache_dir / f"{cle}.json"

    def metadata_for(self, rom_filename: str, system_id: str) -> Metadata:
        if not self.api_key:
            return Metadata()  # dégradation gracieuse, pas une erreur
        cache = self._chemin_cache(rom_filename, system_id)
        if cache.is_file():
            try:
                return Metadata(**json.loads(cache.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001 - un cache illisible se refait
                pass
        try:
            brut = self._fetch_json(BASE, {
                "devid": "", "softname": "retro", "output": "json",
                "ssid": "", "sspassword": "", "romnom": rom_filename,
                "systemeid": system_id, "devpassword": self.api_key,
            })
            jeu = (brut.get("response") or {}).get("jeu")
            if not jeu:
                return Metadata()
            meta = _lire(jeu)
        except Exception:  # noqa: BLE001 - volontairement large, voir docstring
            return Metadata()
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # La clé d'API ne fait PAS partie de ce qu'on écrit : le cache vit
            # sur le volume de jeux, que d'autres outils lisent.
            cache.write_text(json.dumps(dataclasses.asdict(meta),
                                        ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001 - un cache non écrit n'est pas fatal
            pass
        return meta

    def tags_for(self, rom_filename: str, system_id: str,
                 dimensions=DIMENSIONS) -> tuple[str, ...]:
        m = self.metadata_for(rom_filename, system_id)
        tags = []
        if "decennie" in dimensions and m.year:
            tags.append(f"{m.year[:3]}0s")
        if "genre" in dimensions and m.genre:
            tags.append(m.genre)
        if "joueurs" in dimensions and m.players:
            tags.append(f"{m.players} joueur" + ("s" if m.players != "1" else ""))
        return tuple(tags)


def enrich(entries: list, client: MetadataClient,
           dimensions=("decennie", "genre")) -> list:
    """Rend un inventaire dont les extra_tags sont remplis.

    Les entrées sont RECONSTRUITES, jamais modifiées : RomEntry est gelée, et
    un inventaire à moitié enrichi serait plus difficile à diagnostiquer qu'un
    inventaire non enrichi.
    """
    sortie = []
    for e in entries:
        nom = e.rom_path.rsplit("\\", 1)[-1]
        tags = client.tags_for(nom, _systeme_de(e), dimensions=dimensions)
        sortie.append(dataclasses.replace(e, extra_tags=tuple(tags)))
    return sortie


def _systeme_de(entry_obj) -> str:
    """L'identifiant de système que l'API attend, dérivé du chemin de la ROM.

    Le dossier porte l'identifiant du profil (« snes », « psx »), qui est
    exactement ce que le scan a utilisé pour ranger la ROM.
    """
    morceaux = entry_obj.rom_path.split("\\")
    return morceaux[-2] if len(morceaux) >= 2 else ""
```

- [ ] **Étape 5 : vérifier que les tests passent**

```bash
python3 -m pytest tests/test_metadata.py -v
```

Attendu : 12 passed.

- [ ] **Étape 6 : commit**

```bash
git add retro/metadata.py tests/test_metadata.py tests/fixtures/screenscraper-jeu.json
git commit -m "feat(metadata): tags derives des metadonnees, avec cache et degradation gracieuse"
```

---

## Tâche 3 : la commande `retro status`

Le seul endroit du projet dont le but est d'être lu par un humain.

**Fichiers :**
- Créer : `retro/status.py`
- Modifier : `retro/cli.py`
- Test : `tests/test_status.py`

**Interfaces :**
- Consomme : `manifest`, `profiles`, `bios`, `scan`, `acquire.TEMOIN`.
- Produit :
  - `Report` — dataclass gelée : `emulators: list[tuple[str, str]]`,
    `systems: list[tuple[str, int]]`, `bios: list[SystemBios]`,
    `problems: list[str]`.
  - `build_report(...) -> Report`
  - `format_report(report) -> str`
  - sous-commande `retro status`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/test_status.py` :

```python
"""Le rapport lisible. Ne modifie jamais rien."""
import pathlib

import pytest

from retro import bios, status


def test_un_emulateur_installe_est_signale_avec_sa_version(tmp_path):
    emu = tmp_path / "RetroArch"
    emu.mkdir()
    (emu / ".retro-version").write_text("1.22.2\n", encoding="utf-8")
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[], bios_status=[])
    assert ("retroarch", "1.22.2") in r.emulators


def test_un_emulateur_absent_est_un_probleme(tmp_path):
    r = status.build_report(
        install_dirs={"retroarch": "RetroArch"}, emulation_root=tmp_path,
        systems=[], bios_status=[])
    assert ("retroarch", "absent") in r.emulators
    assert any("retroarch" in p for p in r.problems)


def test_les_bios_manquants_sont_des_problemes():
    manquant = bios.SystemBios(
        system_id="psx", system_name="PlayStation",
        files=(bios.BiosFile("scph5501.bin", "abc", True, "absent"),))
    r = status.build_report(install_dirs={}, emulation_root=pathlib.Path("."),
                            systems=[], bios_status=[manquant])
    assert any("scph5501.bin" in p for p in r.problems)


def test_un_bios_corrompu_se_distingue_d_un_bios_absent():
    """Le propriétaire CROIT l'avoir déposé : le message doit le lui dire."""
    corrompu = bios.SystemBios(
        system_id="psx", system_name="PlayStation",
        files=(bios.BiosFile("scph5501.bin", "abc", True, "corrompu"),))
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[], bios_status=[corrompu]))
    assert "corrompu" in texte.lower()
    assert "scph5501.bin" in texte


def test_le_rapport_compte_les_jeux_par_systeme():
    r = status.build_report(install_dirs={}, emulation_root=pathlib.Path("."),
                            systems=[("Super Nintendo", 142)], bios_status=[])
    assert ("Super Nintendo", 142) in r.systems
    assert "142" in status.format_report(r)


def test_sans_probleme_le_rapport_le_dit():
    texte = status.format_report(status.build_report(
        install_dirs={}, emulation_root=pathlib.Path("."),
        systems=[("Super Nintendo", 1)], bios_status=[]))
    assert "aucun" in texte.lower()


def test_le_rapport_ne_modifie_rien(tmp_path):
    """`status` est consultatif : rien de ce qu'il touche ne doit changer."""
    avant = sorted(p.name for p in tmp_path.rglob("*"))
    status.build_report(install_dirs={"x": "X"}, emulation_root=tmp_path,
                        systems=[], bios_status=[])
    assert sorted(p.name for p in tmp_path.rglob("*")) == avant
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/test_status.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.status'`.

- [ ] **Étape 3 : implémenter `retro/status.py`**

Le module assemble un `Report` et le rend lisible. Les règles qui comptent :

- un émulateur dont le dossier ne porte pas de `.retro-version` est `"absent"`,
  et c'est un problème ;
- un BIOS requis dont l'état n'est pas `"ok"` est un problème, et le message
  **distingue** « absent » de « corrompu » — le propriétaire croit avoir déposé
  le second ;
- quand `problems` est vide, le rapport le dit explicitement plutôt que de
  laisser une section vide, qu'on lit comme une panne d'affichage ;
- `build_report` ne crée, ne modifie et ne supprime rien.

Format attendu de `format_report`, à respecter parce que c'est ce que
l'hôte relaiera :

```
Émulateurs
  retroarch     1.22.2
  dolphin       absent

Systèmes
  Super Nintendo      142 jeux
  PlayStation          38 jeux

BIOS
  PlayStation     MANQUANT : scph5501.bin
  Saturn          CORROMPU : sega_101.bin (le fichier est là mais ne
                  correspond pas — il a peut-être été renommé)

Problèmes (2)
  - dolphin n'est pas installé
  - PlayStation : BIOS scph5501.bin absent
```

- [ ] **Étape 4 : ajouter la sous-commande dans `retro/cli.py`**

`retro status` prend les mêmes options que `scan` (`--manifest`,
`--user-manifest`, `--profiles`, `--emulation-root`, `--roms`) plus `--bios`.
Elle **ne modifie rien** et rend 0 même quand des problèmes sont signalés :
c'est une consultation, pas une validation. Tout échec attendu produit un
message et un code non nul, jamais une trace.

- [ ] **Étape 5 : vérifier que les tests passent**

```bash
python3 -m pytest -v
```

- [ ] **Étape 6 : commit**

```bash
git add retro/status.py retro/cli.py tests/test_status.py
git commit -m "feat(cli): commande retro status"
```

---

## Tâche 4 : le champ `icon` des raccourcis

Reporté du sous-projet B pour une raison qui n'a plus lieu d'être : le champ
porte un chemin Windows absolu, que les tests d'alors ne pouvaient pas
construire. La racine Steam est désormais un paramètre.

**Fichiers :**
- Modifier : `retro/steam/entry.py`
- Modifier : `retro/steam/sync.py`
- Test : `tests/steam/test_entry.py`, `tests/steam/test_sync.py`

**Interfaces :**
- `build_shortcut(entry, icon_path: str = "") -> dict` — le champ `icon` reçoit
  `icon_path`.
- `sync_account(..., grid_dir_windows: str | None = None)` — quand il est
  fourni, l'icône récupérée est référencée par son chemin Windows.

- [ ] **Étape 1 : écrire les tests qui échouent**

Dans `tests/steam/test_entry.py` :

```python
def test_l_icone_est_renseignee_quand_elle_est_fournie():
    """Mesuré sur une installation réelle : le champ icon porte un chemin
    absolu vers le fichier déposé dans grid\\."""
    s = entry.build_shortcut(ROM, icon_path="D:\\Steam\\...\\grid\\123_icon.png")
    assert s["icon"] == "D:\\Steam\\...\\grid\\123_icon.png"


def test_sans_icone_le_champ_reste_vide():
    assert entry.build_shortcut(ROM)["icon"] == ""


def test_l_icone_ne_change_pas_l_identifiant():
    """L'identifiant dérive de (exe, appname) : renseigner l'icône plus tard ne
    doit pas orpheliner l'artwork déjà déposé."""
    sans = entry.build_shortcut(ROM)
    avec = entry.build_shortcut(ROM, icon_path="D:\\x\\123_icon.png")
    assert sans["appid"] == avec["appid"]
```

Dans `tests/steam/test_sync.py`, un test vérifiant que `sync_account` renseigne
le champ `icon` des entrées dont l'icône existe, quand `grid_dir_windows` est
fourni, et le laisse vide sinon.

- [ ] **Étape 2 : vérifier que les tests échouent**

- [ ] **Étape 3 : implémenter**

`build_shortcut` prend `icon_path` en paramètre nommé, par défaut `""`.
`sync_account` prend `grid_dir_windows` en paramètre nommé, par défaut `None` ;
quand il est fourni et qu'un fichier d'icône existe pour l'identifiant, le
raccourci le référence.

**Ne change pas l'ordre des opérations** : l'artwork est toujours récupéré
avant l'écriture de `shortcuts.vdf`, et le champ `icon` est renseigné dans le
même passage. Un test du sous-projet B garantit cet ordre — il doit rester vert.

- [ ] **Étape 4 : vérifier que toute la suite passe**

```bash
python3 -m pytest -v
```

- [ ] **Étape 5 : commit**

```bash
git add retro/steam/entry.py retro/steam/sync.py tests/steam/
git commit -m "feat(steam): renseigner le champ icon des raccourcis"
```

---

## Vérification finale

- [ ] **Suite complète, arbre frais, sous `-W error`**

```bash
find . -name __pycache__ -type d -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null
python3 -W error -m compileall -q retro tests && echo PROPRE
python3 -W error -m pytest -q
```

- [ ] **Aucun test ne touche le réseau**

```bash
grep -rn "requests\.\|urlopen\|http://\|https://" tests/ | grep -vE "exemple.invalid|screenscraper.fr"
```

- [ ] **Aucun BIOS, aucune ROM, aucun binaire**

```bash
find . \( -name "*.bin" -o -name "*.sfc" -o -name "*.iso" -o -name "*.exe" \) -not -path "./.git/*"
```

- [ ] **Le garde-fou juridique passe toujours**

```bash
python3 -m pytest tests/test_donnees.py -v
```

## Ce que ce sous-projet ne fait pas

- **L'étape PowerShell, la sentinelle `steam.hold`, la vérification ViGEmBus,
  le dépôt de `7zr.exe`** — ils vivent dans `packages/installer`, un dépôt
  distinct. C'est le lot C2.
- **Les configurations Steam Input** — même lot, et le point à mesurer en
  premier là-bas : rien ne prouve hors ligne qu'une configuration déposée dans
  `userdata\<compte>\config\controller_configs\` soit reprise telle quelle.
- **Les huit profils standalone** — sous-projet D.
