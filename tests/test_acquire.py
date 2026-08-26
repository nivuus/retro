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
