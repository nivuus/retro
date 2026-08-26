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
extensions = [".sfc", ".smc"]
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
