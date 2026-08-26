"""Téléchargement, vérification et extraction des émulateurs."""
import hashlib
import pathlib
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


def test_archive_inconnue_refusee(tmp_path):
    src = tmp_path / "ok.zip"
    faire_zip(src, {"a.txt": "x"})
    with pytest.raises(acquire.AcquireError):
        acquire.safe_extract(src, "rar", tmp_path / "cible")


def test_panne_de_telechargement_nomme_l_emulateur(tmp_path):
    e = emu("aa")

    def fetch(url):
        raise OSError("réseau injoignable")

    with pytest.raises(acquire.AcquireError) as exc:
        acquire.acquire(e, tmp_path / "Emulation", fetch=fetch)
    assert "Truc" in str(exc.value)
