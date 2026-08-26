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
    mauvais = NOYAU.replace('sha256 = "aa" \n', "")
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.load_manifest(ecrire(tmp_path, "c.toml", mauvais))
    assert "sha256" in str(exc.value) and "retroarch" in str(exc.value)


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
    for mauvais_dir in ("../ailleurs", "/absolu", "C:\\\\ailleurs", "a/../..") :
        mauvais = NOYAU.replace('install_dir = "RetroArch"',
                                f'install_dir = "{mauvais_dir}"')
        with pytest.raises(manifest.ManifestError):
            manifest.load_manifest(ecrire(tmp_path, "c.toml", mauvais))
