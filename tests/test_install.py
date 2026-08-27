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


# --- où est un émulateur sur CE disque, et est-il complet ? ---------------

EXE = "RetroArch-Win64\\retroarch.exe"


def poser(racine, install_dir="RetroArch", *, executable=True, temoin=True):
    dossier = racine / install_dir
    dossier.mkdir(parents=True, exist_ok=True)
    # Le dossier de l'exécutable est créé DANS TOUS LES CAS : une extraction
    # interrompue laisse l'arborescence et pas le binaire. Tester l'existence
    # du dossier plutôt que du fichier passerait alors sans rien voir.
    exe = dossier / "RetroArch-Win64" / "retroarch.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    if executable:
        exe.write_bytes(b"MZ")
    if temoin:
        (dossier / ".retro-version").write_text("1.22.2\n", encoding="utf-8")
    return dossier


def test_le_chemin_local_traduit_les_antislashs(tmp_path):
    """`exe` et `install_dir` sont des chaînes WINDOWS jusque dans leurs
    séparateurs : les archives officielles ont toutes un dossier racine, et
    les profils livrés portent « RetroArch-Win64\\retroarch.exe ». Sous Linux
    l'antislash n'est pas un séparateur : joint tel quel, il fabrique un
    segment unique qu'aucun is_file() ne confirme, et le scan déclare absent
    un émulateur parfaitement intact.
    """
    chemin = install.emulator_exe(tmp_path / "Emulation", "RetroArch", EXE)
    assert chemin.parts[-3:] == ("RetroArch", "RetroArch-Win64", "retroarch.exe")
    assert "\\" not in str(chemin)


def test_un_install_dir_peut_porter_un_sous_chemin(tmp_path):
    """Un manifeste utilisateur n'est pas tenu à un nom plat."""
    chemin = install.emulator_exe(tmp_path, "emus\\RetroArch-1.22", EXE)
    assert chemin.parts[-4:] == ("emus", "RetroArch-1.22",
                                 "RetroArch-Win64", "retroarch.exe")


def test_l_etat_est_ok_quand_temoin_et_executable_sont_la(tmp_path):
    poser(tmp_path)
    assert install.emulator_state(tmp_path, "RetroArch", EXE) == install.OK


def test_l_etat_est_absent_quand_rien_n_est_installe(tmp_path):
    assert install.emulator_state(tmp_path, "RetroArch", EXE) == install.ABSENT


def test_l_etat_est_incomplet_quand_l_executable_manque(tmp_path):
    """Le témoin dit « installé », le disque dit le contraire : dossier vidé à
    la main, extraction interrompue. Regarder le DOSSIER ne verrait rien."""
    poser(tmp_path, executable=False)
    assert install.emulator_state(tmp_path, "RetroArch", EXE) == install.INCOMPLET


def test_l_etat_est_sans_temoin_quand_rien_n_atteste_l_installation(tmp_path):
    """`acquire` ne dépose le témoin qu'après avoir vérifié et extrait TOUTES
    les archives : RetroArch sans ses cores ne lance rien tout en paraissant
    installé. Un exécutable posé à la main n'atteste que lui-même."""
    poser(tmp_path, temoin=False)
    assert install.emulator_state(tmp_path, "RetroArch", EXE) == \
        install.SANS_TEMOIN


def test_la_version_installee_est_celle_du_temoin(tmp_path):
    poser(tmp_path)
    assert install.installed_version(tmp_path, "RetroArch") == "1.22.2"


def test_un_temoin_vide_ne_vaut_pas_version(tmp_path):
    dossier = poser(tmp_path)
    (dossier / ".retro-version").write_text("  \n", encoding="utf-8")
    assert install.installed_version(tmp_path, "RetroArch") is None
