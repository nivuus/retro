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
