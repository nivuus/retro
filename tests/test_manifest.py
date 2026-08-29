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


def test_deux_entrees_pour_le_meme_profil_sont_refusees(tmp_path):
    """`cli._install_dirs_pour` indexe les émulateurs PAR PROFIL. Deux entrées
    qui déclarent le même `profile` s'y écrasent l'une l'autre, en silence et
    selon l'ordre d'itération : les jeux du profil pointeraient vers le dossier
    d'installation de l'autre entrée. Steam créerait les raccourcis, le rapport
    annoncerait « + <titre> », et rien ne se lancerait."""
    sien = """
schema = 1
[emulator.extracteur]
name = "Extracteur"
version = "1.0"
url = "https://exemple.invalid/e.zip"
sha256 = "bb"
archive = "zip"
install_dir = "Extracteur"
profile = "retroarch"
"""
    with pytest.raises(manifest.ManifestError) as exc:
        manifest.load_manifest(ecrire(tmp_path, "core.toml", NOYAU),
                               ecrire(tmp_path, "sien.toml", sien))
    message = str(exc.value)
    assert "retroarch" in message      # la clé en conflit
    assert "extracteur" in message     # les deux entrées, nommées
