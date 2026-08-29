"""Installation de tous les émulateurs du manifeste."""
import dataclasses
import hashlib
import zipfile

import pytest

from retro import install, manifest, profiles


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


# --- ce que `retro install` vient d'effacer -------------------------------
#
# Trois des quatre réglages mesurés le 2026-08-29 vivent SOUS le dossier
# d'installation de leur émulateur, que `acquire` supprime (shutil.rmtree) à
# chaque montée de version. Le mécanisme les repose au lancement suivant — mais
# rien ne fait le lien, et c'est la moitié de la dette D7 : une manette muette
# après une mise à jour ne ressemble pas à une mise à jour.

def profil_avec_cible(tmp_path, pid: str, cible: str):
    """Un profil livrable minimal, dont l'unique amorçage vise `cible`."""
    f = tmp_path / f"{pid}.toml"
    f.write_text(f"""
schema = 1
id = "{pid}"
exe = "x.exe"

[[bootstrap]]
target = '{cible}'
content = '''
; Écrit par « retro »
'''

[[system]]
id = "{pid}-s"
name = "Un système"
extensions = [".rom"]
launch = '"{{rom}}"'
bios = []
""", encoding="utf-8")
    return profiles.load_profile(f)


def test_une_reinstallation_nomme_la_configuration_effacee(tmp_path):
    """« réinstallé » a effacé le dossier ; « à jour » n'a rien touché.

    Confondre les deux ferait annoncer une configuration perdue à chaque
    `retro install`, y compris ceux qui ne téléchargent rien — et un message
    qui crie tous les jours ne se lit plus le jour où il est vrai.
    """
    cible = "{install_dir}\\config\\input_configs\\global\\Default.yml"
    profils = {"rpcs3": profil_avec_cible(tmp_path, "rpcs3", cible)}
    emulateurs = {"rpcs3": emu("rpcs3", "0" * 64)}
    for etat in ("installé", "réinstallé"):
        assert install.configurations_effacees(
            [("rpcs3", etat)], emulateurs, profils) == [("rpcs3", cible)]
    assert install.configurations_effacees(
        [("rpcs3", "à jour")], emulateurs, profils) == []


def test_une_cible_hors_du_dossier_d_installation_n_est_pas_nommee(tmp_path):
    """Un %USERPROFILE% survit à toutes les montées de version.

    Sans ce test, une fonction qui rendrait TOUT passerait le précédent : elle
    annoncerait effacé un fichier intact, ce qui envoie chercher une panne là
    où il n'y en a pas.
    """
    cible = "%USERPROFILE%\\Documents\\ailleurs.ini"
    profils = {"ailleurs": profil_avec_cible(tmp_path, "ailleurs", cible)}
    emulateurs = {"ailleurs": emu("ailleurs", "0" * 64)}
    assert install.configurations_effacees(
        [("ailleurs", "réinstallé")], emulateurs, profils) == []


def test_le_lien_manifeste_profil_passe_par_le_champ_profile(tmp_path):
    """La clé du manifeste n'est PAS l'identifiant du profil, et les confondre
    rendrait la liste vide sans erreur — le silence exact que ce message
    existe pour rompre."""
    cible = "{install_dir}\\x.ini"
    profils = {"le-profil": profil_avec_cible(tmp_path, "le-profil", cible)}
    e = emu("la-cle", "0" * 64)
    emulateurs = {"la-cle": dataclasses.replace(e, profile="le-profil")}
    assert install.configurations_effacees(
        [("la-cle", "installé")], emulateurs, profils) == [("le-profil", cible)]


def test_le_message_nomme_le_profil_et_la_cible(tmp_path):
    """Un message qui dirait seulement « des configurations ont été effacées »
    n'aide personne : c'est le NOM du fichier qui permet d'aller voir."""
    texte = install.format_configurations_effacees(
        [("rpcs3", "{install_dir}\\config\\Default.yml")])
    assert "rpcs3" in texte and "Default.yml" in texte
    assert install.format_configurations_effacees([]) == ""


def test_les_etats_qui_effacent_sont_ceux_qu_acquire_rend(tmp_path):
    """Le couplage entre les deux modules est une CHAÎNE, et une chaîne qui
    changerait d'un côté rendrait la liste vide de l'autre — sans erreur, sans
    symptôme, et le message se tairait le jour où il compte. Le seul garde
    possible est de faire tourner une vraie installation et de lire l'état
    qu'elle rend, puis de la refaire pour obtenir celui qui n'efface rien.
    """
    blob = faire_zip(tmp_path / "s.zip")
    sha = hashlib.sha256(blob).hexdigest()
    m = {"a": emu("a", sha)}
    (_, premier), = install.install_all(m, tmp_path / "Emu",
                                        fetch=lambda u: blob)
    assert premier in install.ETATS_EFFACANTS
    (_, second), = install.install_all(m, tmp_path / "Emu",
                                       fetch=lambda u: blob)
    assert second not in install.ETATS_EFFACANTS
