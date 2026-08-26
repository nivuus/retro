# Émulateurs et bibliothèque (sous-projet A) — plan d'implémentation

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` pour dérouler ce plan tâche par
> tâche. Les étapes utilisent la syntaxe case à cocher (`- [ ]`).

**Objectif :** installer les émulateurs sur le volume persistant depuis un
manifeste à empreintes épinglées, puis scanner les ROMs du propriétaire pour
produire l'inventaire que `retro sync` consomme.

**Architecture :** un manifeste déclaratif décrit quoi télécharger et où ; un
profil déclaratif par émulateur décrit comment le lancer. Tout ce qui est
propre à un émulateur vit dans son fichier TOML, jamais dans le code — c'est
ce qui permettra au sous-projet D d'en ajouter dix sans rouvrir un module.

**Pile technique :** Python 3.11+, `tomllib` (natif), `requests`, `py7zr`,
`pytest`.

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`

## Contraintes globales

- **Python 3.11 minimum.** `tomllib` est en lecture seule : aucun code n'écrit
  de TOML.
- **Aucun test ne touche le réseau.** Les téléchargements sont injectés.
- **Aucun test n'exige Windows.** Tout tourne sous Linux.
- **Les chemins Windows sont des `str`**, jamais des `pathlib.Path` — sous
  Linux, `Path("D:\\Emulation")` est un chemin relatif. Utiliser
  `pathlib.PureWindowsPath` pour toute comparaison. Les chemins du système de
  fichiers local (destination d'extraction, dossier scanné) sont, eux, de vrais
  `Path`.
- **Aucune ROM, aucun BIOS, aucun binaire d'émulateur dans le dépôt**, y compris
  dans les fixtures. Les fixtures ne contiennent que des noms et des chemins.
- **Le manifeste versionné ne référence aucun émulateur au statut contesté.**
  Le dépôt est public. Le manifeste utilisateur, hors dépôt, n'a pas cette
  limite — c'est tout son objet.
- **Style de test :** `pytest` idiomatique.
- **Un test qui passerait quelle que soit l'implémentation est un défaut.**
  Quatre findings du sous-projet B étaient de cette nature : vérifier qu'un test
  échoue avant la correction fait partie de la tâche, pas du confort.

---

## Tâche 1 : le manifeste

**Fichiers :**
- Créer : `retro/manifest.py`
- Test : `tests/test_manifest.py`

**Interfaces :**
- Consomme : rien.
- Produit :
  - `Emulator` — dataclass gelée : `key: str`, `name: str`, `version: str`,
    `url: str`, `sha256: str`, `archive: str`, `install_dir: str`,
    `profile: str`.
  - `load_manifest(core: pathlib.Path, user: pathlib.Path | None = None) -> dict[str, Emulator]`
  - `ManifestError`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/test_manifest.py` :

```python
"""Le manifeste : quoi télécharger, sous quelle empreinte.

La surcharge utilisateur est le mécanisme qui permet au dépôt public de ne
référencer aucun émulateur au statut contesté sans pour autant brider le
propriétaire sur sa propre machine.
"""
import pathlib

import pytest

from retro import manifest

NOYAU = """
schema = 1

[emulator.retroarch]
name = "RetroArch"
version = "1.19.1"
url = "https://exemple.invalid/RetroArch.7z"
sha256 = "aa"
archive = "7z"
install_dir = "RetroArch"
profile = "retroarch"
"""


def ecrire(tmp_path, nom, contenu):
    p = tmp_path / nom
    p.write_text(contenu, encoding="utf-8")
    return p


def test_charge_le_noyau(tmp_path):
    m = manifest.load_manifest(ecrire(tmp_path, "core.toml", NOYAU))
    assert set(m) == {"retroarch"}
    assert m["retroarch"].name == "RetroArch"
    assert m["retroarch"].install_dir == "RetroArch"


def test_la_cle_est_reportee_dans_l_objet(tmp_path):
    """acquire() a besoin de la clé pour nommer ses journaux et son témoin."""
    m = manifest.load_manifest(ecrire(tmp_path, "core.toml", NOYAU))
    assert m["retroarch"].key == "retroarch"


def test_le_manifeste_utilisateur_etend(tmp_path):
    """Le mécanisme qui laisse le propriétaire ajouter ce que le dépôt public
    ne peut pas référencer."""
    sien = """
schema = 1
[emulator.autre]
name = "Autre"
version = "1.0"
url = "https://exemple.invalid/a.zip"
sha256 = "bb"
archive = "zip"
install_dir = "Autre"
profile = "autre"
"""
    m = manifest.load_manifest(
        ecrire(tmp_path, "core.toml", NOYAU), ecrire(tmp_path, "u.toml", sien)
    )
    assert set(m) == {"retroarch", "autre"}


def test_le_manifeste_utilisateur_remplace_une_cle_existante(tmp_path):
    sien = """
schema = 1
[emulator.retroarch]
name = "RetroArch"
version = "1.20.0"
url = "https://exemple.invalid/neuf.7z"
sha256 = "cc"
archive = "7z"
install_dir = "RetroArch"
profile = "retroarch"
"""
    m = manifest.load_manifest(
        ecrire(tmp_path, "core.toml", NOYAU), ecrire(tmp_path, "u.toml", sien)
    )
    assert m["retroarch"].version == "1.20.0"


def test_manifeste_utilisateur_absent_est_normal(tmp_path):
    """Il vit sur G:\\, qui n'est pas monté au moment du provisionnement."""
    m = manifest.load_manifest(
        ecrire(tmp_path, "core.toml", NOYAU), tmp_path / "jamais-ecrit.toml"
    )
    assert set(m) == {"retroarch"}


def test_noyau_absent_leve(tmp_path):
    """Le noyau, lui, est livré avec le paquet : son absence est un bug."""
    with pytest.raises(manifest.ManifestError):
        manifest.load_manifest(tmp_path / "jamais.toml")


def test_schema_inconnu_refuse(tmp_path):
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.load_manifest(ecrire(tmp_path, "c.toml", "schema = 99\n"))
    assert "99" in str(exc.value)


def test_champ_manquant_nomme_le_champ_et_l_emulateur(tmp_path):
    """Un manifeste utilisateur est écrit à la main : le message doit dire
    quoi corriger, pas lever un KeyError nu."""
    # Retrait par motif structurel : dépendre d'un espace de fin de
    # ligne ferait échouer ce test au premier reformatage, avec un
    # message qui ne dirait rien de la vraie cause.
    mauvais = "\n".join(l for l in NOYAU.splitlines()
                        if not l.startswith("sha256"))
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.load_manifest(ecrire(tmp_path, "c.toml", mauvais))
    assert "sha256" in str(exc.value) and "retroarch" in str(exc.value)


def test_une_panne_d_extraction_est_enveloppee(tmp_path):
    """Une archive qu'aucun garde-fou ne rejette mais que la bibliothèque
    refuse — lien symbolique échappant, en-tête corrompu — ne doit pas rendre
    une trace Python sur une machine sans clavier ni écran."""
    src = tmp_path / "corrompue.zip"
    src.write_bytes(b"PK\x03\x04 ceci n'est pas une archive valide")
    with pytest.raises(acquire.AcquireError) as exc:
        acquire.safe_extract(src, "zip", tmp_path / "cible")
    assert "corrompue.zip" in str(exc.value)


def test_lien_symbolique_echappant_est_enveloppe(tmp_path):
    """Le cas mesuré : un lien dont la cible sort de la destination, suivi d'un
    membre imbriqué. zipfile lève NotADirectoryError ; l'appelant doit voir une
    AcquireError qui nomme l'archive."""
    import stat
    src = tmp_path / "lien.zip"
    with zipfile.ZipFile(src, "w") as z:
        info = zipfile.ZipInfo("lien")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, "../../dehors")
        z.writestr("lien/evade.txt", "contenu")
    with pytest.raises(acquire.AcquireError):
        acquire.safe_extract(src, "zip", tmp_path / "cible")
    assert not (tmp_path.parent / "dehors").exists()


def test_les_archives_supplementaires_sont_chargees(tmp_path):
    """RetroArch a besoin d'une seconde archive : la principale ne contient
    aucun core, et un émulateur sans core ne lance aucun jeu."""
    avec = NOYAU + """
[[emulator.retroarch.parts]]
url = "https://exemple.invalid/cores.7z"
sha256 = "dd"
archive = "7z"
"""
    m = manifest.load_manifest(ecrire(tmp_path, "c.toml", avec))
    assert len(m["retroarch"].parts) == 1
    assert m["retroarch"].parts[0].url.endswith("cores.7z")


def test_sans_parts_la_liste_est_vide(tmp_path):
    m = manifest.load_manifest(ecrire(tmp_path, "core.toml", NOYAU))
    assert m["retroarch"].parts == ()


def test_une_archive_supplementaire_incomplete_est_refusee(tmp_path):
    mauvais = NOYAU + """
[[emulator.retroarch.parts]]
url = "https://exemple.invalid/cores.7z"
archive = "7z"
"""
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.load_manifest(ecrire(tmp_path, "c.toml", mauvais))
    assert "sha256" in str(exc.value) and "parts" in str(exc.value)


def test_le_secours_7z_prend_le_relais(tmp_path, monkeypatch):
    """py7zr ne lit pas le filtre BCJ2, celui des archives de RetroArch. Sans
    ce secours, l'émulateur qui couvre l'essentiel de la bibliothèque rétro ne
    s'installe pas — et aucun test en .zip ne le verrait."""
    binaire = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
    if not binaire:
        pytest.skip("aucun binaire 7-Zip sur cette machine")
    src = tmp_path / "vrai.7z"
    contenu = tmp_path / "dedans"
    contenu.mkdir()
    (contenu / "fichier.txt").write_text("contenu")
    subprocess.run([binaire, "a", str(src), str(contenu / "fichier.txt")],
                   capture_output=True, check=True)

    # py7zr rendu inopérant, comme il l'est réellement face au filtre BCJ2.
    import py7zr

    def refuse(*a, **k):
        raise RuntimeError("Unsupported compression method BCJ2")

    monkeypatch.setattr(py7zr, "SevenZipFile", refuse)
    cible = tmp_path / "cible"
    acquire.safe_extract(src, "7z", cible)
    assert (cible / "fichier.txt").read_text() == "contenu"


def test_sans_py7zr_ni_binaire_le_message_dit_quoi_faire(tmp_path, monkeypatch):
    import py7zr

    def refuse(*a, **k):
        raise RuntimeError("Unsupported compression method BCJ2")

    monkeypatch.setattr(py7zr, "SevenZipFile", refuse)
    monkeypatch.setattr(acquire.shutil, "which", lambda b: None)
    src = tmp_path / "x.7z"
    src.write_bytes(b"peu importe")
    with pytest.raises(acquire.AcquireError) as exc:
        acquire.safe_extract(src, "7z", tmp_path / "cible")
    assert "7zr" in str(exc.value)


def test_archive_inconnue_refusee(tmp_path):
    mauvais = NOYAU.replace('archive = "7z"', 'archive = "rar"')
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.load_manifest(ecrire(tmp_path, "c.toml", mauvais))
    assert "rar" in str(exc.value)


def test_toml_malforme_ne_leve_pas_de_trace(tmp_path):
    with pytest.raises(manifest.ManifestError):
        manifest.load_manifest(ecrire(tmp_path, "c.toml", "{ pas du TOML"))


def test_install_dir_ne_peut_pas_s_echapper(tmp_path):
    """install_dir est concaténé à la racine d'émulation. Un « .. » y écrirait
    hors du volume prévu, et un manifeste utilisateur n'est pas de confiance."""
    mauvais_dirs = list(("../ailleurs", "/absolu", "a/../..", "", ".", ".."))
    # Les formes que la garde énumérative laissait passer : un backslash
    # seul en tête, sans lettre de lecteur, et un chemin UNC. Le premier
    # écrase la racine entière — mesuré le 2026-08-26.
    mauvais_dirs += [chr(92) + "ailleurs", chr(92) * 2 + "serveur" + chr(92) + "part"]
    mauvais_dirs += ["C:" + chr(92) + "ailleurs"]
    for mauvais_dir in mauvais_dirs:
        mauvais = NOYAU.replace('install_dir = "RetroArch"',
                                f'install_dir = "{mauvais_dir}"')
        with pytest.raises(manifest.ManifestError):
            manifest.load_manifest(ecrire(tmp_path, "c.toml", mauvais))


def test_install_dir_relatif_simple_accepte(tmp_path):
    """Le pendant : une garde qui refuserait tout ne protégerait rien."""
    for bon in ("RetroArch", "a/b", "Dolphin"):
        contenu = NOYAU.replace('install_dir = "RetroArch"',
                                f'install_dir = "{bon}"')
        m = manifest.load_manifest(ecrire(tmp_path, "c.toml", contenu))
        assert m["retroarch"].install_dir == bon
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/test_manifest.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.manifest'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/manifest.py` :

```python
"""Le manifeste : quels émulateurs installer, depuis quelle URL, sous quelle
empreinte.

Deux fichiers, même schéma. Le noyau est livré avec le paquet et ne référence
que des émulateurs au statut juridique clair, puisque le dépôt est public. Le
manifeste utilisateur vit hors du dépôt et n'a pas cette limite : c'est tout
son objet.

Il est écrit à la main, donc chaque refus doit nommer ce qui ne va pas et où.
"""
from __future__ import annotations

import dataclasses
import pathlib
import tomllib

SCHEMA = 1
ARCHIVES = ("7z", "zip")
# Racine témoin pour la validation d'install_dir. Sa valeur n'a aucune
# importance : elle ne sert qu'à éprouver la jointure.
_TEMOIN = pathlib.PureWindowsPath("D:/__racine__")
_CHAMPS = ("name", "version", "url", "sha256", "archive", "install_dir", "profile")


class ManifestError(RuntimeError):
    """Un manifeste est illisible, incomplet ou incohérent."""


@dataclasses.dataclass(frozen=True)
class Part:
    """Une archive supplémentaire, extraite dans le même dossier que la
    principale. RetroArch en a besoin : son archive ne contient AUCUN core, et
    un émulateur sans core ne lance aucun jeu."""
    url: str
    sha256: str
    archive: str


@dataclasses.dataclass(frozen=True)
class Emulator:
    key: str
    name: str
    version: str
    url: str
    sha256: str
    archive: str
    install_dir: str
    profile: str
    parts: tuple[Part, ...] = ()


def _lire(path: pathlib.Path, obligatoire: bool) -> dict:
    if not path.exists():
        if obligatoire:
            raise ManifestError(f"manifeste introuvable : {path}")
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{path} n'est pas du TOML valide : {exc}") from exc
    schema = data.get("schema")
    if schema != SCHEMA:
        raise ManifestError(
            f"{path} déclare schema = {schema}, ce paquet lit le schéma {SCHEMA}"
        )
    return data.get("emulator", {})


def _valider_install_dir(cle: str, valeur: str) -> None:
    """install_dir est concaténé à la racine d'émulation.

    Un manifeste utilisateur n'est pas de confiance : il est écrit à la main et
    peut être copié depuis n'importe où. Un chemin qui s'échappe y ferait écrire
    hors du volume prévu — sur la partition système, effacée à chaque
    reconstruction de la machine, ou pire.

    La vérification est POSITIVE : la jointure doit rester sous la racine. La
    liste des formes interdites, elle, ne se termine jamais. Mesuré le
    2026-08-26 : un backslash seul en tête, sans lettre de lecteur, a
    is_absolute() faux, drive vide et aucun « .. » dans parts — et la jointure
    écrase pourtant la racine entière.

    Le refus de « .. » reste nécessaire en plus : PureWindowsPath ne normalise
    pas, donc 'D:/racine/..' a bien 'D:/racine' pour parent.
    """
    p = pathlib.PureWindowsPath(valeur)
    if valeur and ".." not in p.parts and _TEMOIN in (_TEMOIN / valeur).parents:
        return
    raise ManifestError(
        f"[emulator.{cle}] install_dir = {valeur!r} : un chemin relatif "
        "simple est attendu, qui reste sous la racine d'émulation"
    )


def load_manifest(core: pathlib.Path,
                  user: pathlib.Path | None = None) -> dict[str, Emulator]:
    """Le noyau, surchargé par le manifeste utilisateur s'il existe.

    L'absence du manifeste utilisateur est NORMALE : il vit sur le partage du
    propriétaire, qui n'est pas monté au moment du provisionnement.
    """
    brut = dict(_lire(core, obligatoire=True))
    if user is not None:
        brut.update(_lire(user, obligatoire=False))

    emulateurs = {}
    for cle, champs in brut.items():
        manquants = [c for c in _CHAMPS if c not in champs]
        if manquants:
            raise ManifestError(
                f"[emulator.{cle}] : champ(s) manquant(s) {', '.join(manquants)}"
            )
        if champs["archive"] not in ARCHIVES:
            raise ManifestError(
                f"[emulator.{cle}] archive = {champs['archive']!r} : "
                f"connu(s) {', '.join(ARCHIVES)}"
            )
        _valider_install_dir(cle, champs["install_dir"])
        parts = []
        for i, brut in enumerate(champs.get("parts", ())):
            manquants = [c for c in ("url", "sha256", "archive") if c not in brut]
            if manquants:
                raise ManifestError(
                    f"[emulator.{cle}] parts[{i}] : champ(s) manquant(s) "
                    f"{', '.join(manquants)}"
                )
            if brut["archive"] not in ARCHIVES:
                raise ManifestError(
                    f"[emulator.{cle}] parts[{i}] archive = "
                    f"{brut['archive']!r} : connu(s) {', '.join(ARCHIVES)}"
                )
            parts.append(Part(url=brut["url"], sha256=brut["sha256"],
                              archive=brut["archive"]))
        emulateurs[cle] = Emulator(key=cle, parts=tuple(parts),
                                   **{c: champs[c] for c in _CHAMPS})
    return emulateurs
```

- [ ] **Étape 4 : vérifier que les tests passent**

```bash
python3 -m pytest tests/test_manifest.py -v
```

Attendu : 11 passed.

- [ ] **Étape 5 : commit**

```bash
git add retro/manifest.py tests/test_manifest.py
git commit -m "feat(manifest): chargement et surcharge utilisateur du manifeste"
```

---

## Tâche 2 : les profils d'émulateur

**Fichiers :**
- Créer : `retro/profiles.py`
- Test : `tests/test_profiles.py`

**Interfaces :**
- Consomme : rien.
- Produit :
  - `System` — dataclass gelée : `id: str`, `name: str`,
    `extensions: tuple[str, ...]`, `launch: str`, `bios: tuple[dict, ...]`.
  - `Profile` — dataclass gelée : `id: str`, `exe: str`,
    `systems: tuple[System, ...]`, `exit_native: str`, `exit_fallback: str`,
    `steam_input: str`.
  - `load_profile(path: pathlib.Path) -> Profile`
  - `load_profiles(directory: pathlib.Path) -> dict[str, Profile]`
  - `ProfileError`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/test_profiles.py` :

```python
"""Les profils : comment on parle à un émulateur.

C'est l'abstraction qui doit permettre au sous-projet D d'ajouter dix
émulateurs sans rouvrir une ligne de code. Tout ce qui est propre à un
émulateur vit dans son TOML.
"""
import pathlib

import pytest

from retro import profiles

RETROARCH = """
schema = 1
id = "retroarch"
exe = "retroarch.exe"

[input]
steam_input = "required"

[exit]
native = "Select+Start"
fallback = "alt+f4"

[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue", ".chd", ".m3u"]
launch = '-L "cores\\\\swanstation_libretro.dll" -f "{rom}"'
bios = [{ file = "scph5501.bin", md5 = "abc", required = true }]

[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc", ".smc"]
launch = '-L "cores\\\\snes9x_libretro.dll" -f "{rom}"'
bios = []
"""


def ecrire(tmp_path, nom, contenu):
    p = tmp_path / nom
    p.write_text(contenu, encoding="utf-8")
    return p


def test_charge_un_profil(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "retroarch.toml", RETROARCH))
    assert p.id == "retroarch"
    assert p.exe == "retroarch.exe"
    assert len(p.systems) == 2


def test_les_systemes_portent_leurs_extensions(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    psx = next(s for s in p.systems if s.id == "psx")
    assert psx.extensions == (".cue", ".chd", ".m3u")
    assert psx.name == "PlayStation"


def test_les_bios_sont_declares(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    psx = next(s for s in p.systems if s.id == "psx")
    assert psx.bios[0]["file"] == "scph5501.bin"
    snes = next(s for s in p.systems if s.id == "snes")
    assert snes.bios == ()


def test_la_sortie_est_declaree(tmp_path):
    """Sans hotkey de sortie, un émulateur lancé à la manette immobilise la
    console jusqu'au redémarrage de la VM."""
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    assert p.exit_native == "Select+Start"
    assert p.exit_fallback == "alt+f4"


def test_launch_sans_rom_est_refuse(tmp_path):
    """Un gabarit sans {rom} lance l'émulateur sans jeu : il s'ouvre sur son
    propre menu, la console a l'air de marcher, et rien ne le signale."""
    mauvais = RETROARCH.replace('-f "{rom}"', "-f")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "{rom}" in str(exc.value) and "psx" in str(exc.value)


def test_extensions_vides_refusees(tmp_path):
    """Un système sans extension ne peut rien matcher : il serait absent de la
    bibliothèque sans que rien ne le dise."""
    mauvais = RETROARCH.replace('extensions = [".sfc", ".smc"]', "extensions = []")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "snes" in str(exc.value)


def test_extension_sans_point_refusee(tmp_path):
    """Le scan compare à Path.suffix, qui porte toujours son point."""
    mauvais = RETROARCH.replace('[".sfc", ".smc"]', '["sfc"]')
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "sfc" in str(exc.value)


def test_deux_systemes_de_meme_id_refuses(tmp_path):
    mauvais = RETROARCH.replace('id = "snes"', 'id = "psx"')
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))


def test_schema_inconnu_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "r.toml", "schema = 99\nid = 'x'\n"))


def test_charge_un_dossier(tmp_path):
    d = tmp_path / "profiles"
    d.mkdir()
    (d / "retroarch.toml").write_text(RETROARCH, encoding="utf-8")
    (d / "notes.txt").write_text("ignoré", encoding="utf-8")
    tous = profiles.load_profiles(d)
    assert set(tous) == {"retroarch"}


def test_dossier_vide_leve(tmp_path):
    """Aucun profil = aucun jeu ne peut être lancé. Ce n'est pas un état
    normal, c'est un paquet cassé."""
    d = tmp_path / "vide"
    d.mkdir()
    with pytest.raises(profiles.ProfileError):
        profiles.load_profiles(d)
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/test_profiles.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.profiles'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/profiles.py` :

```python
"""Comment on parle à un émulateur.

Un profil décrit les systèmes qu'un émulateur couvre, les extensions de ROM
qu'il accepte, la ligne de commande qui lance un jeu, les BIOS qu'il exige et
la façon d'en sortir à la manette.

Tout ce qui est propre à un émulateur vit ici, dans son TOML, jamais dans le
code : c'est ce qui permet d'en ajouter un sans rouvrir un module.
"""
from __future__ import annotations

import dataclasses
import pathlib
import tomllib

SCHEMA = 1


class ProfileError(RuntimeError):
    """Un profil est illisible, incomplet ou incohérent."""


@dataclasses.dataclass(frozen=True)
class System:
    id: str
    name: str
    extensions: tuple[str, ...]
    launch: str
    bios: tuple[dict, ...]


@dataclasses.dataclass(frozen=True)
class Profile:
    id: str
    exe: str
    systems: tuple[System, ...]
    exit_native: str
    exit_fallback: str
    steam_input: str


def load_profile(path: pathlib.Path) -> Profile:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{path} n'est pas du TOML valide : {exc}") from exc
    if data.get("schema") != SCHEMA:
        raise ProfileError(
            f"{path} déclare schema = {data.get('schema')}, attendu {SCHEMA}"
        )
    for champ in ("id", "exe"):
        if champ not in data:
            raise ProfileError(f"{path} : champ '{champ}' manquant")

    systemes = []
    vus = set()
    for brut in data.get("system", []):
        sid = brut.get("id", "?")
        if sid in vus:
            raise ProfileError(f"{path} : le système '{sid}' est déclaré deux fois")
        vus.add(sid)
        for champ in ("name", "extensions", "launch"):
            if champ not in brut:
                raise ProfileError(f"{path} [{sid}] : champ '{champ}' manquant")
        exts = tuple(brut["extensions"])
        if not exts:
            raise ProfileError(
                f"{path} [{sid}] : aucune extension. Ce système ne pourrait "
                "matcher aucune ROM et serait absent sans rien signaler."
            )
        # Le scan compare à Path.suffix, qui porte toujours son point.
        mauvaises = [e for e in exts if not e.startswith(".")]
        if mauvaises:
            raise ProfileError(
                f"{path} [{sid}] : extension(s) sans point : {', '.join(mauvaises)}"
            )
        if "{rom}" not in brut["launch"]:
            raise ProfileError(
                f"{path} [{sid}] : le gabarit launch ne contient pas {{rom}}. "
                "L'émulateur s'ouvrirait sur son propre menu, sans jeu, et la "
                "console aurait l'air de fonctionner."
            )
        systemes.append(System(
            id=sid, name=brut["name"], extensions=exts, launch=brut["launch"],
            bios=tuple(brut.get("bios", ())),
        ))

    if not systemes:
        raise ProfileError(f"{path} : aucun système déclaré")

    sortie = data.get("exit", {})
    entree = data.get("input", {})
    return Profile(
        id=data["id"], exe=data["exe"], systems=tuple(systemes),
        exit_native=sortie.get("native", ""),
        exit_fallback=sortie.get("fallback", "alt+f4"),
        steam_input=entree.get("steam_input", "required"),
    )


def load_profiles(directory: pathlib.Path) -> dict[str, Profile]:
    profils = {}
    for f in sorted(directory.glob("*.toml")):
        p = load_profile(f)
        profils[p.id] = p
    if not profils:
        raise ProfileError(
            f"aucun profil dans {directory} : aucun jeu ne pourrait être lancé"
        )
    return profils
```

- [ ] **Étape 4 : vérifier que les tests passent**

```bash
python3 -m pytest tests/test_profiles.py -v
```

Attendu : 11 passed.

- [ ] **Étape 5 : commit**

```bash
git add retro/profiles.py tests/test_profiles.py
git commit -m "feat(profiles): profils declaratifs d'emulateur"
```

---

## Tâche 3 : l'acquisition

Cette tâche télécharge et extrait des archives venues d'Internet dans le volume
persistant. Deux risques y sont réels et distincts : installer un binaire qui
n'est pas celui qu'on croit, et laisser une archive écrire hors du dossier
qu'on lui a désigné.

**Fichiers :**
- Créer : `retro/acquire.py`
- Test : `tests/test_acquire.py`

**Interfaces :**
- Consomme : `manifest.Emulator` (tâche 1).
- Produit :
  - `acquire(emu, emulation_root: pathlib.Path, fetch=…) -> str` — rend
    `"installé"`, `"à jour"` ou `"réinstallé"`.
  - `AcquireError`
  - `safe_extract(archive: pathlib.Path, kind: str, destination: pathlib.Path) -> None`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/test_acquire.py` :

```python
"""Téléchargement, vérification et extraction des émulateurs."""
import dataclasses
import hashlib
import pathlib
import shutil
import subprocess
import zipfile

import pytest

from retro import acquire, manifest


def faire_zip(chemin, membres):
    with zipfile.ZipFile(chemin, "w") as z:
        for nom, contenu in membres.items():
            z.writestr(nom, contenu)
    return chemin.read_bytes()


def emu(sha, archive="zip", install_dir="Truc", version="1.0"):
    return manifest.Emulator(
        key="truc", name="Truc", version=version,
        url="https://exemple.invalid/t.zip", sha256=sha,
        archive=archive, install_dir=install_dir, profile="truc",
    )


def test_installe_et_extrait(tmp_path):
    blob = faire_zip(tmp_path / "src.zip", {"truc.exe": "binaire"})
    e = emu(hashlib.sha256(blob).hexdigest())
    racine = tmp_path / "Emulation"
    assert acquire.acquire(e, racine, fetch=lambda url: blob) == "installé"
    assert (racine / "Truc" / "truc.exe").read_text() == "binaire"


def test_empreinte_fausse_refuse_avant_d_extraire(tmp_path):
    """Un binaire non vérifié ne s'installe pas — et rien ne doit subsister."""
    blob = faire_zip(tmp_path / "src.zip", {"truc.exe": "binaire"})
    e = emu("0" * 64)
    racine = tmp_path / "Emulation"
    with pytest.raises(acquire.AcquireError) as exc:
        acquire.acquire(e, racine, fetch=lambda url: blob)
    assert "empreinte" in str(exc.value).lower()
    assert not (racine / "Truc").exists()


def test_second_passage_ne_retelecharge_pas(tmp_path):
    blob = faire_zip(tmp_path / "src.zip", {"truc.exe": "binaire"})
    e = emu(hashlib.sha256(blob).hexdigest())
    racine = tmp_path / "Emulation"
    appels = []

    def fetch(url):
        appels.append(url)
        return blob

    acquire.acquire(e, racine, fetch=fetch)
    assert acquire.acquire(e, racine, fetch=fetch) == "à jour"
    assert len(appels) == 1


def test_version_differente_reinstalle(tmp_path):
    blob = faire_zip(tmp_path / "src.zip", {"truc.exe": "binaire"})
    sha = hashlib.sha256(blob).hexdigest()
    racine = tmp_path / "Emulation"
    acquire.acquire(emu(sha, version="1.0"), racine, fetch=lambda u: blob)
    assert acquire.acquire(emu(sha, version="2.0"), racine,
                           fetch=lambda u: blob) == "réinstallé"


def test_le_temoin_porte_la_version(tmp_path):
    blob = faire_zip(tmp_path / "src.zip", {"truc.exe": "binaire"})
    e = emu(hashlib.sha256(blob).hexdigest(), version="1.19.1")
    racine = tmp_path / "Emulation"
    acquire.acquire(e, racine, fetch=lambda u: blob)
    assert (racine / "Truc" / ".retro-version").read_text().strip() == "1.19.1"


# --- L'extraction ne doit jamais écrire hors de sa destination ---

def test_chemin_relatif_echappant_refuse(tmp_path):
    """Une archive téléchargée peut contenir « ../ » : l'extraire naïvement
    écrirait n'importe où sur le disque. C'est le défaut connu sous le nom de
    zip slip, et il ne se voit pas depuis le dossier de destination."""
    src = tmp_path / "mechant.zip"
    faire_zip(src, {"../../evade.txt": "dehors"})
    with pytest.raises(acquire.AcquireError) as exc:
        acquire.safe_extract(src, "zip", tmp_path / "cible")
    assert "evade" in str(exc.value) or "hors" in str(exc.value).lower()
    assert not (tmp_path.parent / "evade.txt").exists()


def test_chemin_absolu_refuse(tmp_path):
    src = tmp_path / "mechant.zip"
    faire_zip(src, {"/etc/evade.txt": "dehors"})
    with pytest.raises(acquire.AcquireError):
        acquire.safe_extract(src, "zip", tmp_path / "cible")


def test_extraction_normale_passe(tmp_path):
    src = tmp_path / "ok.zip"
    faire_zip(src, {"a/b/c.txt": "dedans"})
    cible = tmp_path / "cible"
    acquire.safe_extract(src, "zip", cible)
    assert (cible / "a" / "b" / "c.txt").read_text() == "dedans"


def test_une_panne_d_extraction_est_enveloppee(tmp_path):
    """Une archive qu'aucun garde-fou ne rejette mais que la bibliothèque
    refuse — lien symbolique échappant, en-tête corrompu — ne doit pas rendre
    une trace Python sur une machine sans clavier ni écran."""
    src = tmp_path / "corrompue.zip"
    src.write_bytes(b"PK\x03\x04 ceci n'est pas une archive valide")
    with pytest.raises(acquire.AcquireError) as exc:
        acquire.safe_extract(src, "zip", tmp_path / "cible")
    assert "corrompue.zip" in str(exc.value)


def test_lien_symbolique_echappant_est_enveloppe(tmp_path):
    """Le cas mesuré : un lien dont la cible sort de la destination, suivi d'un
    membre imbriqué. zipfile lève NotADirectoryError ; l'appelant doit voir une
    AcquireError qui nomme l'archive."""
    import stat
    src = tmp_path / "lien.zip"
    with zipfile.ZipFile(src, "w") as z:
        info = zipfile.ZipInfo("lien")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, "../../dehors")
        z.writestr("lien/evade.txt", "contenu")
    with pytest.raises(acquire.AcquireError):
        acquire.safe_extract(src, "zip", tmp_path / "cible")
    assert not (tmp_path.parent / "dehors").exists()


def test_le_secours_7z_prend_le_relais(tmp_path, monkeypatch):
    """py7zr ne lit pas le filtre BCJ2, celui des archives de RetroArch. Sans
    ce secours, l'émulateur qui couvre l'essentiel de la bibliothèque rétro ne
    s'installe pas — et aucun test en .zip ne le verrait."""
    binaire = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
    if not binaire:
        pytest.skip("aucun binaire 7-Zip sur cette machine")
    src = tmp_path / "vrai.7z"
    contenu = tmp_path / "dedans"
    contenu.mkdir()
    (contenu / "fichier.txt").write_text("contenu")
    subprocess.run([binaire, "a", str(src), str(contenu / "fichier.txt")],
                   capture_output=True, check=True)

    # py7zr rendu inopérant, comme il l'est réellement face au filtre BCJ2.
    import py7zr

    def refuse(*a, **k):
        raise RuntimeError("Unsupported compression method BCJ2")

    monkeypatch.setattr(py7zr, "SevenZipFile", refuse)
    cible = tmp_path / "cible"
    acquire.safe_extract(src, "7z", cible)
    assert (cible / "fichier.txt").read_text() == "contenu"


def test_sans_py7zr_ni_binaire_le_message_dit_quoi_faire(tmp_path, monkeypatch):
    import py7zr

    def refuse(*a, **k):
        raise RuntimeError("Unsupported compression method BCJ2")

    monkeypatch.setattr(py7zr, "SevenZipFile", refuse)
    monkeypatch.setattr(acquire.shutil, "which", lambda b: None)
    src = tmp_path / "x.7z"
    src.write_bytes(b"peu importe")
    with pytest.raises(acquire.AcquireError) as exc:
        acquire.safe_extract(src, "7z", tmp_path / "cible")
    assert "7zr" in str(exc.value)


def test_archive_inconnue_refusee(tmp_path):
    src = tmp_path / "ok.zip"
    faire_zip(src, {"a.txt": "x"})
    with pytest.raises(acquire.AcquireError):
        acquire.safe_extract(src, "rar", tmp_path / "cible")


def test_les_archives_supplementaires_se_deversent_dans_le_meme_dossier(tmp_path):
    """Sans cela, RetroArch s'installe sans un seul core et ne lance rien."""
    principal = faire_zip(tmp_path / "p.zip", {"retroarch.exe": "binaire"})
    cores = faire_zip(tmp_path / "c.zip", {"cores/snes9x.dll": "core"})
    e = dataclasses.replace(
        emu(hashlib.sha256(principal).hexdigest()),
        parts=(manifest.Part(url="https://exemple.invalid/c.zip",
                             sha256=hashlib.sha256(cores).hexdigest(),
                             archive="zip"),),
    )
    racine = tmp_path / "Emulation"
    acquire.acquire(e, racine, fetch=lambda u: cores if u.endswith("c.zip") else principal)
    assert (racine / "Truc" / "retroarch.exe").exists()
    assert (racine / "Truc" / "cores" / "snes9x.dll").exists()


def test_une_archive_supplementaire_fausse_n_installe_rien(tmp_path):
    """Un émulateur amputé de ses cores est pire qu'un émulateur absent : il
    apparaît installé et ne lance rien."""
    principal = faire_zip(tmp_path / "p.zip", {"retroarch.exe": "binaire"})
    e = dataclasses.replace(
        emu(hashlib.sha256(principal).hexdigest()),
        parts=(manifest.Part(url="https://exemple.invalid/c.zip",
                             sha256="0" * 64, archive="zip"),),
    )
    racine = tmp_path / "Emulation"
    with pytest.raises(acquire.AcquireError):
        acquire.acquire(e, racine, fetch=lambda u: principal)
    assert not (racine / "Truc").exists()


def test_panne_de_telechargement_nomme_l_emulateur(tmp_path):
    e = emu("aa")

    def fetch(url):
        raise OSError("réseau injoignable")

    with pytest.raises(acquire.AcquireError) as exc:
        acquire.acquire(e, tmp_path / "Emulation", fetch=fetch)
    assert "Truc" in str(exc.value)
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/test_acquire.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.acquire'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/acquire.py` :

```python
"""Télécharger, vérifier, extraire.

Deux risques distincts, et aucun ne se voit après coup :

1. Installer un binaire qui n'est pas celui qu'on croit. L'empreinte est donc
   vérifiée AVANT toute extraction, et un échec ne laisse rien derrière lui.
2. Laisser une archive écrire hors du dossier qu'on lui a désigné. Une archive
   venue d'Internet peut contenir « ../ » ou un chemin absolu ; l'extraire
   naïvement écrit n'importe où sur le disque, et le dossier de destination
   n'en garde aucune trace.
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
import tempfile
import zipfile

TEMOIN = ".retro-version"


class AcquireError(RuntimeError):
    """L'émulateur n'a pas pu être installé, et rien n'a été laissé à moitié."""


def _fetch(url: str) -> bytes:
    import requests
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.content


def _membres_surs(noms, destination: pathlib.Path):
    """Refuse tout membre dont le chemin résolu sort de la destination."""
    racine = destination.resolve()
    for nom in noms:
        cible = (destination / nom).resolve()
        if cible != racine and racine not in cible.parents:
            raise AcquireError(
                f"l'archive contient un chemin qui sort de sa destination : "
                f"{nom!r} — extraction refusée"
            )


# Binaires 7-Zip acceptés, par ordre de préférence. 7zr est l'extracteur
# autonome officiel : ~600 Ko, redistribuable, et il lit tous les filtres.
_BINAIRES_7Z = ("7zz", "7z", "7za", "7zr", "7zr.exe", "7z.exe")


def _extraire_7z(archive: pathlib.Path, destination: pathlib.Path) -> None:
    """Extrait une archive 7z, avec py7zr d'abord et un binaire 7-Zip ensuite.

    py7zr ne sait PAS lire le filtre BCJ2 — il le marque « Unsupported » dans
    son propre code — et c'est précisément celui qu'utilisent les archives de
    RetroArch, mesuré le 2026-08-26 sur les archives réelles. Sans ce secours,
    l'émulateur qui couvre l'essentiel de la bibliothèque rétro ne s'installe
    pas du tout, et aucun test en .zip ne peut le voir.
    """
    erreur_py7zr = None
    try:
        import py7zr
        with py7zr.SevenZipFile(archive) as z:
            _membres_surs(z.getnames(), destination)
            z.extractall(destination)
        return
    except AcquireError:
        raise
    except Exception as exc:  # noqa: BLE001 - py7zr lève des types variés
        erreur_py7zr = exc

    binaire = next((b for b in _BINAIRES_7Z if shutil.which(b)), None)
    if binaire is None:
        raise AcquireError(
            f"{archive.name} : py7zr a échoué ({erreur_py7zr}) et aucun binaire "
            f"7-Zip n'est disponible. Installer l'un de {', '.join(_BINAIRES_7Z)} "
            "— 7zr suffit et se télécharge sur https://www.7-zip.org/a/7zr.exe"
        )
    # -bb0 : silencieux. -y : ne pose aucune question, il n'y a personne pour
    # y répondre. Le binaire refuse lui-même d'écrire hors de -o.
    r = subprocess.run(
        [binaire, "x", str(archive), f"-o{destination}", "-y", "-bb0"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise AcquireError(
            f"{archive.name} : py7zr a échoué ({erreur_py7zr}) et {binaire} "
            f"aussi (code {r.returncode}) : {r.stderr.strip()[:400]}"
        )


def safe_extract(archive: pathlib.Path, kind: str,
                 destination: pathlib.Path) -> None:
    """Extrait une archive sans la laisser écrire hors de sa destination.

    `_membres_surs` ne regarde que les NOMS de membres. La protection contre un
    lien symbolique dont la cible sort de la destination repose, elle, sur les
    bibliothèques d'extraction : zipfile ne matérialise jamais de vrai lien, et
    py7zr refuse lui-même « Symlink point out of target directory ». C'est de la
    défense en profondeur réelle, mais elle est portée par du code que nous
    n'écrivons pas — d'où cette note, pour qu'un futur changement de
    bibliothèque ne rouvre pas le trou en silence.

    Toute exception est enveloppée : sur une machine de provisionnement sans
    clavier ni écran, une trace Python brute remplace le message qui nommerait
    l'archive fautive.
    """
    if kind not in ("zip", "7z"):
        raise AcquireError(f"format d'archive inconnu : {kind!r}")
    destination.mkdir(parents=True, exist_ok=True)
    try:
        if kind == "zip":
            with zipfile.ZipFile(archive) as z:
                _membres_surs(z.namelist(), destination)
                z.extractall(destination)
        else:
            _extraire_7z(archive, destination)
    except AcquireError:
        raise
    except Exception as exc:  # noqa: BLE001 - volontairement large, voir docstring
        raise AcquireError(
            f"extraction de {archive.name} impossible : {type(exc).__name__}: {exc}"
        ) from exc


def acquire(emu, emulation_root: pathlib.Path, fetch=_fetch) -> str:
    """Installe l'émulateur s'il manque ou si sa version a changé.

    Rend « installé », « à jour » ou « réinstallé ». Le témoin de version est
    ce qui rend l'opération idempotente : le provisionnement rejoue cette
    étape à chaque reconstruction, et retélécharger des gigaoctets déjà
    présents serait une panne à lui seul.
    """
    cible = emulation_root / emu.install_dir
    temoin = cible / TEMOIN
    if temoin.exists() and temoin.read_text(encoding="utf-8").strip() == emu.version:
        return "à jour"
    deja = cible.exists()

    try:
        blob = fetch(emu.url)
    except Exception as exc:  # noqa: BLE001 - toute panne réseau, nommée
        raise AcquireError(f"{emu.name} : téléchargement impossible ({exc})") from exc

    empreinte = hashlib.sha256(blob).hexdigest()
    if empreinte != emu.sha256:
        raise AcquireError(
            f"{emu.name} {emu.version} : empreinte SHA256 inattendue.\n"
            f"  attendue : {emu.sha256}\n  obtenue  : {empreinte}\n"
            "Rien n'a été installé."
        )

    # Les archives supplémentaires sont téléchargées et vérifiées AVANT que
    # quoi que ce soit ne touche à l'installation existante : une seconde
    # archive dont l'empreinte est fausse ne doit pas laisser un émulateur
    # amputé. RetroArch en dépend — son archive principale ne contient aucun
    # core, et un émulateur sans core ne lance aucun jeu.
    supplements = []
    for i, part in enumerate(emu.parts):
        try:
            b = fetch(part.url)
        except Exception as exc:  # noqa: BLE001
            raise AcquireError(
                f"{emu.name} : téléchargement de l'archive supplémentaire "
                f"{i + 1} impossible ({exc})"
            ) from exc
        h = hashlib.sha256(b).hexdigest()
        if h != part.sha256:
            raise AcquireError(
                f"{emu.name} {emu.version}, archive supplémentaire {i + 1} : "
                f"empreinte SHA256 inattendue.\n  attendue : {part.sha256}\n"
                f"  obtenue  : {h}\nRien n'a été installé."
            )
        supplements.append((b, part.archive))

    with tempfile.TemporaryDirectory() as tmp:
        racine = pathlib.Path(tmp)
        extrait = racine / "extrait"
        # Extraire à côté, puis basculer : une extraction qui échoue à
        # mi-chemin ne doit pas laisser une installation à moitié écrasée.
        principale = racine / f"{emu.key}.{emu.archive}"
        principale.write_bytes(blob)
        safe_extract(principale, emu.archive, extrait)
        # Les supplémentaires se déversent dans le MÊME dossier : c'est ce qui
        # fait cohabiter l'émulateur et ses cores.
        for i, (b, kind) in enumerate(supplements):
            sup = racine / f"{emu.key}-part{i}.{kind}"
            sup.write_bytes(b)
            safe_extract(sup, kind, extrait)
        if cible.exists():
            shutil.rmtree(cible)
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extrait), str(cible))

    temoin.write_text(emu.version + "\n", encoding="utf-8")
    return "réinstallé" if deja else "installé"
```

- [ ] **Étape 4 : ajouter `py7zr` aux dépendances**

Dans `pyproject.toml`, section `dependencies`, ajouter `"py7zr>=1.0"`.

- [ ] **Étape 5 : vérifier que les tests passent**

```bash
pip install -e '.[dev]'
python3 -m pytest tests/test_acquire.py -v
```

Attendu : 10 passed.

- [ ] **Étape 6 : commit**

```bash
git add retro/acquire.py tests/test_acquire.py pyproject.toml
git commit -m "feat(acquire): telechargement verifie et extraction sans echappement"
```

---

## Tâche 4 : le scan des ROMs

**Fichiers :**
- Créer : `retro/scan.py`
- Test : `tests/test_scan.py`

**Interfaces :**
- Consomme : `profiles.Profile`, `profiles.System` (tâche 2) ;
  `entry.RomEntry` (sous-projet B, déjà en place).
- Produit :
  - `base_title(filename: str) -> str` — titre sans marqueur de disque, clé de
    regroupement des disques d'un même jeu.
  - `discriminant(filename: str) -> str` — premier fragment parenthésé, en
    pratique la région ; départage deux titres identiques.
  - `clean_title(filename: str) -> str` — titre affiché, marqueur conservé.
  - `scan(roms_root: pathlib.Path, profils: dict[str, Profile], emulation_root: str, install_dirs: dict[str, str]) -> list[entry.RomEntry]`
  - `ScanError`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/test_scan.py` :

```python
"""Scan des ROMs : du disque du propriétaire à l'inventaire."""
import pathlib

import pytest

from retro import profiles, scan

PROFIL = """
schema = 1
id = "retroarch"
exe = "retroarch.exe"
[exit]
native = "Select+Start"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue", ".chd", ".m3u"]
launch = '-L "cores\\\\swanstation.dll" -f "{rom}"'
bios = []
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-L "cores\\\\snes9x.dll" -f "{rom}"'
bios = []
"""


@pytest.fixture
def profils(tmp_path):
    p = tmp_path / "retroarch.toml"
    p.write_text(PROFIL, encoding="utf-8")
    return {"retroarch": profiles.load_profile(p)}


def faire_roms(tmp_path, fichiers):
    for chemin in fichiers:
        f = tmp_path / "ROMs" / chemin
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    return tmp_path / "ROMs"


def scanner(racine, profils):
    return scan.scan(racine, profils, "D:\\Emulation",
                     {"retroarch": "RetroArch"})


# --- nettoyage des titres ---

@pytest.mark.parametrize("nom,attendu", [
    ("Chrono Trigger (USA).sfc", "Chrono Trigger"),
    ("Super Mario World (Europe) (Rev 1).sfc", "Super Mario World"),
    ("Jeu (USA) [!].sfc", "Jeu"),
    ("Jeu (Japan) (En,Fr,De).sfc", "Jeu"),
    ("Jeu.sfc", "Jeu"),
    ("Jeu  (USA).sfc", "Jeu"),
])
def test_nettoyage_des_titres(nom, attendu):
    assert scan.clean_title(nom) == attendu


def test_le_marqueur_de_disque_est_conserve():
    """Deux disques du même jeu produiraient sinon le même titre, donc le même
    identifiant Steam, et une seule entrée survivrait aux deux."""
    assert scan.clean_title("Final Fantasy VII (USA) (Disc 1).cue") == \
        "Final Fantasy VII (Disc 1)"
    assert scan.clean_title("Jeu (Disc 2 of 3).cue") == "Jeu (Disc 2 of 3)"


# --- scan ---

def test_scan_simple(tmp_path, profils):
    racine = faire_roms(tmp_path, ["snes/Chrono Trigger (USA).sfc"])
    inv = scanner(racine, profils)
    assert [r.title for r in inv] == ["Chrono Trigger"]
    assert inv[0].system_name == "Super Nintendo"


def test_le_chemin_de_rom_est_windows(tmp_path, profils):
    """L'inventaire décrit une machine Windows, pas celle qui scanne."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    inv = scan.scan(racine, profils, "D:\\Emulation",
                    {"retroarch": "RetroArch"}, roms_root_windows="G:\\ROMs")
    assert inv[0].rom_path == "G:\\ROMs\\snes\\Jeu.sfc"
    assert inv[0].emulator_exe == "D:\\Emulation\\RetroArch\\retroarch.exe"


def test_le_gabarit_de_lancement_vient_du_systeme(tmp_path, profils):
    racine = faire_roms(tmp_path, ["psx/Jeu.cue"])
    inv = scanner(racine, profils)
    assert "swanstation.dll" in inv[0].launch_template


def test_extension_inconnue_ignoree(tmp_path, profils):
    racine = faire_roms(tmp_path, ["snes/lisez-moi.txt", "snes/Jeu.sfc"])
    assert [r.title for r in scanner(racine, profils)] == ["Jeu"]


def test_le_bin_d_un_cue_ne_cree_pas_de_doublon(tmp_path, profils):
    """Un jeu PS1 est un .cue et un .bin. Seul le .cue est lançable, et il est
    seul déclaré par le profil — le .bin ne doit rien produire."""
    racine = faire_roms(tmp_path, ["psx/Jeu.cue", "psx/Jeu.bin"])
    assert [r.title for r in scanner(racine, profils)] == ["Jeu"]


def test_le_m3u_evince_ses_disques(tmp_path, profils):
    """Quand un .m3u regroupe les disques, lancer un disque isolé est une
    erreur : le jeu demanderait le disque suivant sans pouvoir l'obtenir."""
    racine = faire_roms(tmp_path, [
        "psx/Jeu.m3u", "psx/Jeu (Disc 1).cue", "psx/Jeu (Disc 2).cue",
    ])
    assert [r.title for r in scanner(racine, profils)] == ["Jeu"]


def test_sans_m3u_les_disques_restent_distincts(tmp_path, profils):
    racine = faire_roms(tmp_path, [
        "psx/Jeu (Disc 1).cue", "psx/Jeu (Disc 2).cue",
    ])
    assert sorted(r.title for r in scanner(racine, profils)) == \
        ["Jeu (Disc 1)", "Jeu (Disc 2)"]


def test_dossier_de_systeme_inconnu_ignore(tmp_path, profils):
    racine = faire_roms(tmp_path, ["neogeo/Jeu.zip", "snes/Jeu.sfc"])
    assert [r.title for r in scanner(racine, profils)] == ["Jeu"]


def test_racine_absente_leve(tmp_path, profils):
    """G:\\ non monté est une panne réelle et fréquente sur cette machine."""
    with pytest.raises(scan.ScanError):
        scanner(tmp_path / "jamais", profils)


def test_racine_vide_rend_une_liste_vide(tmp_path, profils):
    racine = tmp_path / "ROMs"
    racine.mkdir()
    assert scanner(racine, profils) == []


def test_les_tags_portent_le_systeme(tmp_path, profils):
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    assert scanner(racine, profils)[0].system_name == "Super Nintendo"


def test_deux_regions_du_meme_jeu_restent_distinctes(tmp_path, profils):
    """Sans désambiguïsation, les deux rendent « Jeu », donc le même
    identifiant Steam, et un seul des deux survit — un jeu qui disparaît de la
    bibliothèque sans que rien ne le signale."""
    racine = faire_roms(tmp_path, ["snes/Jeu (USA).sfc", "snes/Jeu (Europe).sfc"])
    titres = sorted(r.title for r in scanner(racine, profils))
    assert titres == ["Jeu (Europe)", "Jeu (USA)"]


def test_un_titre_unique_n_est_pas_desambigue(tmp_path, profils):
    """La désambiguïsation ne doit pas enlaidir le cas courant."""
    racine = faire_roms(tmp_path, ["snes/Chrono Trigger (USA).sfc"])
    assert [r.title for r in scanner(racine, profils)] == ["Chrono Trigger"]


def test_collision_sans_discriminant_retombe_sur_le_nom(tmp_path, profils):
    """Deux fichiers sans fragment parenthésé mais de même titre : un titre
    laid vaut mieux qu'un jeu absent."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc", "snes/Jeu.smc"])
    titres = sorted(r.title for r in scanner(racine, profils))
    assert len(set(titres)) == 2


def test_collision_sur_le_discriminant_lui_meme(tmp_path, profils):
    """Le discriminant ne retient que le PREMIER fragment parenthésé : deux
    révisions de la même région le partagent. La garantie d'unicité doit tenir
    quand même, sans quoi l'une des deux disparaît en silence."""
    racine = faire_roms(tmp_path, [
        "snes/Jeu (USA) (Rev 1).sfc", "snes/Jeu (USA) (Rev 2).sfc",
    ])
    titres = [r.title for r in scanner(racine, profils)]
    assert len(set(titres)) == 2, f"collision non résolue : {titres}"


def test_marqueur_de_disque_sans_espace(tmp_path, profils):
    """« (Disc1) » est une forme qu'on rencontre réellement."""
    assert scan.clean_title("Jeu (Disc1).cue") == "Jeu (Disc1)"


def test_le_resultat_est_deterministe(tmp_path, profils):
    """Deux scans du même disque doivent donner le même ordre, sinon
    l'inventaire diffère sans raison d'un passage à l'autre."""
    racine = faire_roms(tmp_path, ["snes/B.sfc", "snes/A.sfc", "psx/C.cue"])
    assert [r.title for r in scanner(racine, profils)] == \
           [r.title for r in scanner(racine, profils)]
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/test_scan.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.scan'`.

- [ ] **Étape 3 : implémenter**

Fichier `retro/scan.py` :

```python
"""Du disque du propriétaire à l'inventaire.

Le scan tourne sur la machine qui possède les ROMs, mais décrit une machine
Windows : les chemins de l'inventaire sont ceux que verra Steam, pas ceux du
système de fichiers qui scanne.
"""
from __future__ import annotations

import pathlib
import re

from retro.steam import entry

# Les conventions No-Intro et Redump : « Titre (Région) (Langues) [flags] ».
# Tout ce qui suit le titre est entre parenthèses ou crochets.
_PARENTHESES = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
# ... à une exception près : le marqueur de disque. Deux disques du même jeu
# donneraient sinon le même titre, donc le même identifiant Steam, et une
# seule entrée survivrait aux deux.
_DISQUE = re.compile(r"\((Disc|Disk|CD)\s*[^\)]*\)", re.IGNORECASE)


class ScanError(RuntimeError):
    """La racine des ROMs est inaccessible."""


def base_title(filename: str) -> str:
    """Le titre SANS son marqueur de disque.

    C'est la clé de regroupement : les trois disques d'un même jeu et le .m3u
    qui les rassemble ont tous le même titre de base.
    """
    tige = pathlib.PurePosixPath(filename).stem
    return _PARENTHESES.sub("", tige).strip()


def clean_title(filename: str) -> str:
    """Le titre affiché dans Steam, marqueur de disque compris.

    Le marqueur est CONSERVÉ : deux disques du même jeu donneraient sinon le
    même titre, donc le même identifiant Steam, et une seule entrée survivrait
    aux deux.
    """
    tige = pathlib.PurePosixPath(filename).stem
    m = _DISQUE.search(tige)
    if not m:
        return base_title(filename)
    sans_disque = tige[: m.start()] + tige[m.end():]
    return f"{_PARENTHESES.sub('', sans_disque).strip()} {m.group(0)}".strip()


def discriminant(filename: str) -> str:
    """Le premier fragment parenthésé d'un nom de fichier — en pratique la
    région. Sert à départager deux fichiers dont le titre nettoyé serait le
    même, et seulement dans ce cas."""
    tige = pathlib.PurePosixPath(filename).stem
    m = _PARENTHESES.search(tige)
    return m.group(0).strip(" ()[]") if m else ""


def _desambiguiser(couples: list[tuple[str, str]]) -> list[str]:
    """Rend les titres, en n'ajoutant un discriminant qu'aux titres en collision.

    Sans cela, « Jeu (USA).sfc » et « Jeu (Europe).sfc » rendent tous deux
    « Jeu », donc le même identifiant Steam, et un seul des deux survit — un
    jeu qui disparaît de la bibliothèque sans que rien ne le signale. Mesuré le
    2026-08-26 : trois régions, une seule entrée.

    Les titres uniques ne sont jamais touchés : la bibliothèque reste propre
    dans le cas courant, qui est de loin le plus fréquent.
    """
    def compter(titres):
        c = {}
        for t in titres:
            c[t] = c.get(t, 0) + 1
        return c

    titres = [t for _, t in couples]
    comptes = compter(titres)

    # Premier passage : le discriminant, en pratique la région.
    passe1 = [t if comptes[t] == 1 else f"{t} ({discriminant(n)})".replace(" ()", "")
              for n, t in couples]

    # Second passage : ce qui reste en collision reçoit son nom de fichier
    # ENTIER, extension comprise. C'est la seule clé réellement unique — un
    # système de fichiers ne porte pas deux fois le même nom au même endroit.
    #
    # Cette seconde passe n'est pas une précaution de style : le discriminant
    # ne retient que le PREMIER fragment parenthésé, donc « Jeu (USA) (Rev 1) »
    # et « Jeu (USA) (Rev 2) » le partagent. Mesuré le 2026-08-26. Garantir
    # l'unicité vaut mieux que l'espérer d'une heuristique.
    comptes2 = compter(passe1)
    return [t if comptes2[t] == 1 else f"{orig[1]} ({orig[0]})"
            for t, orig in zip(passe1, couples)]


def _systeme_par_dossier(profils):
    """Le nom du dossier désigne le système. Un même identifiant ne peut être
    servi que par un profil : le premier dans l'ordre alphabétique gagne, ce
    qui rend le résultat indépendant de l'ordre de chargement."""
    table = {}
    for pid in sorted(profils):
        for s in profils[pid].systems:
            table.setdefault(s.id, (pid, s))
    return table


def scan(roms_root: pathlib.Path, profils: dict, emulation_root: str,
         install_dirs: dict[str, str],
         roms_root_windows: str = "G:\\ROMs") -> list[entry.RomEntry]:
    if not roms_root.is_dir():
        raise ScanError(
            f"racine des ROMs introuvable : {roms_root}. Le partage est-il monté ?"
        )
    table = _systeme_par_dossier(profils)
    inventaire = []

    for dossier in sorted(p for p in roms_root.iterdir() if p.is_dir()):
        trouve = table.get(dossier.name)
        if not trouve:
            continue  # dossier qu'aucun profil ne couvre
        pid, systeme = trouve
        profil = profils[pid]
        exe = f"{emulation_root}\\{install_dirs[pid]}\\{profil.exe}"
        start_dir = f"{emulation_root}\\{install_dirs[pid]}"

        fichiers = sorted(f for f in dossier.iterdir()
                          if f.is_file() and f.suffix.lower() in
                          tuple(e.lower() for e in systeme.extensions))

        # Un .m3u regroupe les disques d'un même jeu. Lancer un disque isolé
        # alors qu'un .m3u existe est une erreur : le jeu réclamerait le disque
        # suivant sans pouvoir l'obtenir. Le titre de BASE est la clé de
        # regroupement — il ignore le marqueur de disque, que le titre affiché
        # conserve.
        titres_m3u = {base_title(f.name) for f in fichiers
                      if f.suffix.lower() == ".m3u"}
        retenus = [f for f in fichiers
                   if f.suffix.lower() == ".m3u"
                   or base_title(f.name) not in titres_m3u]
        titres = _desambiguiser([(f.name, clean_title(f.name)) for f in retenus])
        for f, titre in zip(retenus, titres):
            inventaire.append(entry.RomEntry(
                title=titre,
                rom_path=f"{roms_root_windows}\\{dossier.name}\\{f.name}",
                system_name=systeme.name,
                emulator_exe=exe,
                launch_template=systeme.launch,
                start_dir=start_dir,
                extra_tags=(),
            ))
    return inventaire
```

- [ ] **Étape 4 : vérifier que les tests passent**

```bash
python3 -m pytest tests/test_scan.py -v
```

Attendu : 19 passed (dont 6 cas paramétrés de nettoyage).

Si `test_le_m3u_evince_ses_disques` échoue, la logique d'éviction est le point
délicat de cette tâche : simplifie-la jusqu'à ce qu'elle soit lisible, en
gardant le comportement que le test décrit. Ne modifie pas le test.

- [ ] **Étape 5 : commit**

```bash
git add retro/scan.py tests/test_scan.py
git commit -m "feat(scan): inventaire des ROMs depuis le partage du proprietaire"
```

---

## Tâche 5 : le manifeste noyau et les profils réels

Les données du dépôt. Aucune logique, mais c'est ce fichier qui décide ce que
le projet installe — et ce qu'il ne référence pas.

**Fichiers :**
- Créer : `manifests/core.toml`
- Créer : `profiles/retroarch.toml`
- Créer : `profiles/dolphin.toml`
- Test : `tests/test_donnees.py`

**Interfaces :**
- Consomme : `manifest.load_manifest`, `profiles.load_profiles` (tâches 1 et 2).
- Produit : les fichiers de données que `retro install` lira.

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/test_donnees.py` :

```python
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
```

- [ ] **Étape 2 : vérifier que le test échoue**

```bash
python3 -m pytest tests/test_donnees.py -v
```

Attendu : échec sur l'absence de `manifests/core.toml`.

- [ ] **Étape 3 : écrire les données**

Créer `manifests/core.toml`. **Les URL et les empreintes doivent être réelles**
— va les chercher, ne les invente pas. Si une empreinte ne peut pas être
obtenue, ne mets pas d'espace réservé : retire l'émulateur du manifeste et
signale-le dans ton rapport. Un `sha256` faux est pire qu'un émulateur absent,
parce qu'il échouera sur la console du propriétaire et pas ici.

```toml
# Le manifeste livré avec le paquet.
#
# Il ne référence que des émulateurs au statut juridique clair : ce dépôt est
# public, et pointer vers un émulateur contesté est un acte de distribution.
# Le propriétaire ajoute ce qu'il veut dans G:\retro\emulators.toml, hors dépôt.
#
# Toute empreinte ici est vérifiée avant extraction. Un sha256 faux fait
# échouer l'installation sur la console, pas dans les tests.

schema = 1

[emulator.retroarch]
name        = "RetroArch"
version     = "…"
url         = "https://…"
sha256      = "…"
archive     = "7z"
install_dir = "RetroArch"
profile     = "retroarch"

[emulator.dolphin]
name        = "Dolphin"
version     = "…"
url         = "https://…"
sha256      = "…"
archive     = "7z"
install_dir = "Dolphin"
profile     = "dolphin"
```

Créer `profiles/retroarch.toml` avec les systèmes rétro : NES, SNES, Mega
Drive, Game Boy / Color / Advance, PlayStation, Nintendo 64, arcade. Un
`[[system]]` chacun, avec ses extensions réelles, son core libretro et ses BIOS
quand le système en exige (PlayStation notamment).

Créer `profiles/dolphin.toml` — GameCube et Wii — choisi parce que c'est un cas
NON-RetroArch : si l'abstraction de profil tient face à lui, elle tiendra pour
les huit autres du sous-projet D. Sa ligne de commande est `-b -e "{rom}"`.

- [ ] **Étape 4 : déclarer les données comme fichiers du paquet**

Dans `pyproject.toml`, s'assurer que `manifests/` et `profiles/` sont inclus à
l'installation (`[tool.setuptools.package-data]` ou `[tool.setuptools.data-files]`
selon la structure retenue). Un paquet installé sans ses données ne peut rien
installer.

- [ ] **Étape 5 : vérifier que les tests passent**

```bash
python3 -m pytest tests/test_donnees.py -v
```

Attendu : 8 passed.

- [ ] **Étape 6 : commit**

```bash
git add manifests/ profiles/ tests/test_donnees.py pyproject.toml
git commit -m "feat(donnees): manifeste noyau et profils RetroArch et Dolphin"
```

---

## Tâche 6 : les commandes `retro install` et `retro scan`

**Fichiers :**
- Modifier : `retro/cli.py`
- Créer : `retro/install.py`
- Test : `tests/test_install.py`
- Test : `tests/test_cli_install.py`

**Interfaces :**
- Consomme : tout ce qui précède.
- Produit :
  - `install_all(manifeste, emulation_root, fetch=…) -> list[tuple[str, str]]`
  - `format_install_report(resultats) -> str`
  - deux sous-commandes : `retro install`, `retro scan`

- [ ] **Étape 1 : écrire le test qui échoue**

Fichier `tests/test_install.py` :

```python
"""Installation de tous les émulateurs du manifeste."""
import hashlib
import zipfile

import pytest

from retro import install, manifest


def faire_zip(chemin, nom_membre="t.exe"):
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr(nom_membre, "binaire")
    return chemin.read_bytes()


def emu(cle, sha):
    return manifest.Emulator(
        key=cle, name=cle.title(), version="1.0",
        url=f"https://exemple.invalid/{cle}.zip", sha256=sha,
        archive="zip", install_dir=cle.title(), profile=cle,
    )


def test_installe_tous_les_emulateurs(tmp_path):
    blob = faire_zip(tmp_path / "s.zip")
    sha = hashlib.sha256(blob).hexdigest()
    m = {"a": emu("a", sha), "b": emu("b", sha)}
    res = install.install_all(m, tmp_path / "Emulation", fetch=lambda u: blob)
    assert sorted(k for k, _ in res) == ["a", "b"]
    assert (tmp_path / "Emulation" / "A" / "t.exe").exists()


def test_un_echec_n_empeche_pas_les_autres(tmp_path):
    """Un émulateur dont l'URL est morte ne doit pas priver le propriétaire des
    neuf autres. L'échec est rapporté, pas tu."""
    blob = faire_zip(tmp_path / "s.zip")
    sha = hashlib.sha256(blob).hexdigest()
    m = {"bon": emu("bon", sha), "casse": emu("casse", "0" * 64)}
    res = install.install_all(m, tmp_path / "Emulation", fetch=lambda u: blob)
    etats = dict(res)
    assert etats["bon"] in ("installé", "réinstallé")
    assert "empreinte" in etats["casse"].lower()


def test_le_rapport_nomme_les_echecs(tmp_path):
    texte = install.format_install_report([("a", "installé"), ("b", "ÉCHEC : x")])
    assert "a" in texte and "b" in texte and "ÉCHEC" in texte


def test_le_rapport_distingue_a_jour_de_installe(tmp_path):
    texte = install.format_install_report([("a", "à jour")])
    assert "à jour" in texte
```

Fichier `tests/test_cli_install.py` :

```python
"""Les sous-commandes install et scan."""
import json

from retro import cli


def test_install_sans_manifeste_echoue_proprement(tmp_path, capsys):
    code = cli.main(["install", "--manifest", str(tmp_path / "absent.toml"),
                     "--emulation-root", str(tmp_path / "Emu")])
    assert code != 0
    err = capsys.readouterr().err
    assert "absent.toml" in err and "Traceback" not in err


def test_scan_ecrit_un_inventaire(tmp_path, capsys):
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "p.toml").write_text("""
schema = 1
id = "retroarch"
exe = "retroarch.exe"
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-f "{rom}"'
bios = []
""", encoding="utf-8")
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu (USA).sfc").write_bytes(b"x")
    sortie = tmp_path / "inv.json"
    code = cli.main(["scan", "--roms", str(tmp_path / "ROMs"),
                     "--profiles", str(profils), "--output", str(sortie),
                     "--emulation-root", "D:\\Emulation"])
    assert code == 0
    d = json.loads(sortie.read_text(encoding="utf-8"))
    assert d[0]["title"] == "Jeu"
    assert d[0]["system_name"] == "Super Nintendo"


def test_scan_sur_racine_absente_echoue_proprement(tmp_path, capsys):
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "p.toml").write_text("""
schema = 1
id = "r"
exe = "r.exe"
[[system]]
id = "snes"
name = "SNES"
extensions = [".sfc"]
launch = '-f "{rom}"'
bios = []
""", encoding="utf-8")
    code = cli.main(["scan", "--roms", str(tmp_path / "jamais"),
                     "--profiles", str(profils),
                     "--output", str(tmp_path / "o.json"),
                     "--emulation-root", "D:\\Emulation"])
    assert code != 0
    assert "Traceback" not in capsys.readouterr().err


def test_l_inventaire_produit_est_lisible_par_sync(tmp_path):
    """Le contrat entre les deux sous-projets : ce que `scan` écrit, `sync`
    doit savoir le relire sans adaptation."""
    from retro.cli import _load_inventory
    profils = tmp_path / "profiles"
    profils.mkdir()
    (profils / "p.toml").write_text("""
schema = 1
id = "r"
exe = "r.exe"
[[system]]
id = "snes"
name = "SNES"
extensions = [".sfc"]
launch = '-f "{rom}"'
bios = []
""", encoding="utf-8")
    roms = tmp_path / "ROMs" / "snes"
    roms.mkdir(parents=True)
    (roms / "Jeu.sfc").write_bytes(b"x")
    sortie = tmp_path / "inv.json"
    cli.main(["scan", "--roms", str(tmp_path / "ROMs"), "--profiles", str(profils),
              "--output", str(sortie), "--emulation-root", "D:\\Emulation"])
    entries = _load_inventory(sortie)
    assert entries[0].title == "Jeu"
```

- [ ] **Étape 2 : vérifier que les tests échouent**

```bash
python3 -m pytest tests/test_install.py tests/test_cli_install.py -v
```

Attendu : `ModuleNotFoundError: No module named 'retro.install'`, puis des
erreurs d'argument inconnu sur `install` et `scan`.

- [ ] **Étape 3 : implémenter `retro/install.py`**

```python
"""Installer tous les émulateurs du manifeste.

Un émulateur dont l'URL est morte ne doit pas priver le propriétaire des neuf
autres : chaque échec est capturé, rapporté, et l'installation continue. Ce
qu'on ne fait jamais, c'est le taire.
"""
from __future__ import annotations

import pathlib

from retro import acquire


def install_all(manifeste: dict, emulation_root: pathlib.Path,
                fetch=acquire._fetch) -> list[tuple[str, str]]:
    resultats = []
    for cle in sorted(manifeste):
        try:
            etat = acquire.acquire(manifeste[cle], emulation_root, fetch=fetch)
        except acquire.AcquireError as exc:
            etat = f"ÉCHEC : {exc}"
        resultats.append((cle, etat))
    return resultats


def format_install_report(resultats: list[tuple[str, str]]) -> str:
    lignes = []
    for cle, etat in resultats:
        marque = "!" if etat.startswith("ÉCHEC") else "·"
        lignes.append(f"  {marque} {cle} : {etat}")
    echecs = [c for c, e in resultats if e.startswith("ÉCHEC")]
    if echecs:
        lignes.append(f"  {len(echecs)} émulateur(s) non installé(s) : "
                      f"{', '.join(echecs)}")
    return "\n".join(lignes)
```

- [ ] **Étape 4 : ajouter les sous-commandes dans `retro/cli.py`**

Ajouter deux sous-parseurs à la suite de `sync`, dans le même style :

```python
    i = sous.add_parser("install", help="installe les émulateurs du manifeste")
    i.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    i.add_argument("--user-manifest", default=None)
    i.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    i.set_defaults(func=_cmd_install)

    s = sous.add_parser("scan", help="produit l'inventaire des ROMs")
    s.add_argument("--roms", required=True)
    s.add_argument("--roms-windows", default="G:\\ROMs")
    s.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    s.add_argument("--emulation-root", default=DEFAULT_EMULATION_ROOT)
    s.add_argument("--output", required=True)
    s.set_defaults(func=_cmd_scan)
```

et les deux fonctions correspondantes, sur le modèle de `_cmd_sync` : tout
échec attendu (manifeste illisible, profils absents, racine des ROMs non
montée) est capturé et rendu comme un message plus un code non nul, jamais une
trace.

`_cmd_scan` écrit l'inventaire en JSON avec les mêmes clés que celles que
`_load_inventory` relit — `title`, `rom_path`, `system_name`, `emulator_exe`,
`launch_template`, `start_dir`, `extra_tags`. C'est le contrat entre les deux
sous-projets, et le dernier test de `test_cli_install.py` est ce qui l'atteste.

`DEFAULT_MANIFEST` et `DEFAULT_PROFILES` pointent vers les données livrées avec
le paquet, résolues depuis `pathlib.Path(__file__).parent.parent`.

- [ ] **Étape 5 : vérifier que les tests passent**

```bash
python3 -m pytest -v
```

Attendu : toute la suite verte, sous-projet B compris.

- [ ] **Étape 6 : commit**

```bash
git add retro/install.py retro/cli.py tests/test_install.py tests/test_cli_install.py
git commit -m "feat(cli): commandes retro install et retro scan"
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
grep -rn "requests\.\|urlopen\|http://\|https://" tests/ | grep -v "exemple.invalid"
```

Attendu : aucune ligne.

- [ ] **Aucun émulateur au statut contesté dans les données**

```bash
grep -riE "ryujinx|yuzu|citron|sudachi|switch" manifests/ profiles/
```

Attendu : aucune ligne. (`tests/test_donnees.py` l'automatise déjà.)

- [ ] **Aucun binaire, aucune ROM, aucun BIOS**

```bash
find . \( -name "*.exe" -o -name "*.7z" -o -name "*.bin" -o -name "*.sfc" \
       -o -name "*.iso" \) -not -path "./.git/*"
```

Attendu : aucune ligne.

- [ ] **Le contrat avec le sous-projet B tient**

`retro scan` produit un inventaire que `retro sync` relit sans adaptation :
c'est ce qu'atteste `test_l_inventaire_produit_est_lisible_par_sync`.

## Ce que ce sous-projet ne fait pas

- **La vérification des BIOS** — sous-projet C, avec `retro status`.
- **Les métadonnées ScreenScraper** — sous-projet C ; `extra_tags` reste vide
  ici et le scan ne remplit que le système.
- **L'étape PowerShell, la sentinelle `steam.hold`, ViGEmBus, Steam Input** —
  sous-projet C.
- **Les huit autres profils standalone** — sous-projet D. Dolphin sert ici de
  cas non-RetroArch pour éprouver l'abstraction avant d'y investir.
