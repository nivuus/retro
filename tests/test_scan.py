"""Scan des ROMs : du disque du propriétaire à l'inventaire."""
import pathlib

import pytest

from retro import install, launcher, profiles, scan
from retro.steam import appid
from retro.steam import entry as entry_mod

PROFIL = """
schema = 1
id = "retroarch"
exe = 'RetroArch-Win64\\retroarch.exe'
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
    # Steam appelle le LANCEUR, pas l'émulateur : c'est lui qui mesure la
    # session et compose la commande au moment du clic.
    assert inv[0].emulator_exe == "D:\\Emulation\\_launcher\\retro-launch.exe"
    # Le dossier de travail reste celui de l'émulateur, qui en dépend.
    assert inv[0].start_dir == "D:\\Emulation\\RetroArch"


def test_le_raccourci_ne_porte_que_le_systeme_et_la_rom(tmp_path, profils):
    """La commande de l'émulateur ne passe plus par Steam.

    Elle vit dans le plan que la synchronisation écrit au lanceur — ce qui
    permet de changer de mode de rendu, ou de corriger une ligne de commande,
    sans toucher aux options d'un raccourci, donc sans changer un identifiant,
    donc sans retélécharger une seule vignette.
    """
    racine = faire_roms(tmp_path, ["psx/Jeu.cue"])
    inv = scanner(racine, profils)
    assert inv[0].launch_template == 'retroarch.psx "{rom}"' 


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


def test_deux_systemes_homonymes_gardent_chacun_leur_entree(tmp_path, profils):
    """« Tetris » existe sur presque toutes les consoles.

    Les huit systèmes de RetroArch partagent le MÊME exe, donc deux jeux
    homonymes rendaient le même couple (exe, appname) — donc le même
    identifiant Steam, et une seule des deux entrées survivait à l'écriture.
    Mesuré le 2026-08-27 : deux ROMs, un seul appid.

    C'est la désambiguïsation par région, mais appliquée trop tard : elle ne
    voyait qu'un dossier à la fois, et deux dossiers ne se rencontraient
    jamais.
    """
    racine = faire_roms(tmp_path, ["psx/Tetris.chd", "snes/Tetris.sfc"])
    inventaire = scanner(racine, profils)
    assert len(inventaire) == 2
    ids = {appid.legacy_appid(entry_mod.quote(r.emulator_exe), r.title)
           for r in inventaire}
    assert len(ids) == 2, "deux jeux, un seul identifiant Steam"
    assert sorted(r.title for r in inventaire) == \
           ["Tetris (PlayStation)", "Tetris (Super Nintendo)"]


def test_le_systeme_ne_qualifie_pas_ce_qu_il_ne_departage_pas(tmp_path, profils):
    """Deux régions du MÊME système : le nom du système ne distingue rien.

    L'ajouter tout de même rendrait « Jeu (Super Nintendo) (USA) » — le cas
    courant enlaidi pour rien par un qualificatif qui ne sert que le cas rare.
    """
    racine = faire_roms(tmp_path, ["snes/Jeu (USA).sfc", "snes/Jeu (Europe).sfc"])
    titres = sorted(r.title for r in scanner(racine, profils))
    assert titres == ["Jeu (Europe)", "Jeu (USA)"]


def test_un_meme_systeme_range_sous_deux_dossiers(tmp_path, profils):
    """Le dernier recours doit être VRAIMENT unique.

    Un système répond à son identifiant ET à son nom : « psx\\ » et
    « PlayStation\\ » désignent le même. Deux fichiers de même nom, l'un dans
    chacun, ne sont départagés ni par le système, ni par la région, ni par le
    nom de fichier — seul leur chemin les distingue, et c'est bien le seul
    qualificatif qu'un système de fichiers garantit unique.
    """
    racine = faire_roms(tmp_path, ["psx/Jeu.cue", "PlayStation/Jeu.cue"])
    inventaire = scanner(racine, profils)
    assert len(inventaire) == 2
    ids = {appid.legacy_appid(entry_mod.quote(r.emulator_exe), r.title)
           for r in inventaire}
    assert len(ids) == 2, "deux jeux, un seul identifiant Steam"


def test_le_resultat_est_deterministe(tmp_path, profils):
    """Deux scans du même disque doivent donner le même ordre, sinon
    l'inventaire diffère sans raison d'un passage à l'autre."""
    racine = faire_roms(tmp_path, ["snes/B.sfc", "snes/A.sfc", "psx/C.cue"])
    assert [r.title for r in scanner(racine, profils)] == \
           [r.title for r in scanner(racine, profils)]


# --- l'émulateur doit exister, et être complet --------------------------

# La forme RÉELLE, celle des profils livrés : les archives officielles ont
# toutes un dossier racine, et le chemin de l'exécutable le porte en préfixe.
# Une fixture au nom plat (« retroarch.exe ») ne montre rien du seul cas qui
# compte — sous Linux, l'antislash n'est pas un séparateur.
PROFIL_DOLPHIN = """
schema = 1
id = "dolphin"
exe = 'Dolphin-x64\\Dolphin.exe'
[[system]]
id = "gc"
name = "GameCube"
extensions = [".iso"]
launch = '-b -e "{rom}"'
bios = []
"""

INSTALL_DIRS = {"retroarch": "RetroArch", "dolphin": "Dolphin"}
EXE_RETROARCH = "RetroArch-Win64\\retroarch.exe"
EXE_DOLPHIN = "Dolphin-x64\\Dolphin.exe"


@pytest.fixture
def deux_profils(tmp_path, profils):
    p = tmp_path / "dolphin.toml"
    p.write_text(PROFIL_DOLPHIN, encoding="utf-8")
    return {**profils, "dolphin": profiles.load_profile(p)}


def faire_emulation(tmp_path) -> pathlib.Path:
    """La racine d'émulation TELLE QU'ELLE EST SUR CE DISQUE.

    L'inventaire, lui, continue de décrire « D:\\Emulation » : c'est toute la
    difficulté, et c'est pourquoi les deux chemins sont deux paramètres.
    """
    racine = tmp_path / "Emulation"
    racine.mkdir(exist_ok=True)
    # Le lanceur commun fait partie d'une racine d'émulation qui fonctionne :
    # c'est lui que Steam appelle pour chaque jeu. Son absence a son propre
    # test, plus bas.
    return poser_lanceur(racine)


def poser_lanceur(racine):
    """Pose le lanceur commun, comme « retro launcher » le poserait.

    Sans lui, `scan` refuse d'inventorier : chaque raccourci Steam pointerait
    sur un exécutable absent, et aucun jeu ne démarrerait.
    """
    dossier = pathlib.Path(racine) / launcher.DIR
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / launcher.EXE).write_bytes(b"MZ")
    return racine


def installer(racine, install_dir, exe_windows, *, executable=True, temoin=True):
    """Pose un émulateur comme `retro install` le poserait.

    Le témoin de version n'est déposé qu'APRÈS que toutes les archives ont été
    vérifiées et extraites : sa présence atteste une installation complète, là
    où l'exécutable seul n'atteste que lui-même. Les deux se dissocient pour
    de vrai — dossier vidé à la main, émulateur déposé sans passer par
    `retro install` —, d'où les deux interrupteurs.
    """
    dossier = racine / install_dir
    dossier.mkdir(parents=True, exist_ok=True)
    # Le dossier de l'exécutable est créé DANS TOUS LES CAS : une extraction
    # interrompue laisse l'arborescence et pas le binaire. Vérifier le
    # dossier plutôt que le fichier passerait alors sans rien voir.
    exe = dossier.joinpath(*exe_windows.replace("\\", "/").split("/"))
    exe.parent.mkdir(parents=True, exist_ok=True)
    if executable:
        exe.write_bytes(b"MZ")
    if temoin:
        (dossier / ".retro-version").write_text("1.0\n", encoding="utf-8")
    return dossier


def test_un_systeme_dont_l_emulateur_manque_est_ignore(tmp_path, profils):
    """Le scan fabriquait le chemin de l'exécutable par concaténation, sans
    jamais vérifier qu'il existe, et la garde de `sync` l'acceptait puisqu'il
    est bien sous la racine d'émulation. Une installation ratée — URL morte,
    réseau absent au provisionnement, dossier vidé à la main — peuplait donc
    la bibliothèque Steam d'entrées qui ne démarrent pas. Une bibliothèque
    vide se diagnostique ; une bibliothèque morte se subit.
    """
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    inv = scan.scan(racine, profils, "D:\\Emulation", INSTALL_DIRS,
                    emulation_root_local=faire_emulation(tmp_path))
    assert inv == []


def test_un_systeme_dont_l_emulateur_existe_est_scanne(tmp_path, profils):
    """Le pendant du précédent — et le test qui manquait.

    Le chemin de l'exécutable est une chaîne WINDOWS jusque dans ses
    séparateurs : « RetroArch-Win64\\retroarch.exe ». Joint tel quel sous une
    racine POSIX, il fabrique un segment unique
    « RetroArch/RetroArch-Win64\\retroarch.exe » qu'aucun is_file() ne
    confirme — et le correctif censé empêcher une bibliothèque morte rendait
    une bibliothèque vide, en accusant chaque émulateur d'être absent.
    """
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    emulation = faire_emulation(tmp_path)
    installer(emulation, "RetroArch", EXE_RETROARCH)
    inv = scan.scan(racine, profils, "D:\\Emulation", INSTALL_DIRS,
                    emulation_root_local=emulation)
    assert [r.title for r in inv] == ["Jeu"]
    # Le raccourci appelle le lanceur ; c'est le DOSSIER de l'émulateur qui
    # reste dans le raccourci, et c'est bien celui-ci qui a été trouvé sur le
    # disque — sans quoi le système aurait été ignoré.
    assert inv[0].start_dir == "D:\\Emulation\\RetroArch"


def test_seul_le_systeme_orphelin_disparait(tmp_path, deux_profils):
    """Un émulateur manquant ne prive le propriétaire que de SES jeux."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc", "gc/Autre.iso"])
    emulation = faire_emulation(tmp_path)
    installer(emulation, "RetroArch", EXE_RETROARCH)
    inv = scan.scan(racine, deux_profils, "D:\\Emulation", INSTALL_DIRS,
                    emulation_root_local=emulation)
    assert [(r.title, r.system_name) for r in inv] == [("Jeu", "Super Nintendo")]


def test_sans_racine_locale_le_scan_ne_verifie_rien(tmp_path, profils):
    """Le paramètre est FACULTATIF : un appelant qui n'atteint pas le disque
    des émulateurs — l'hôte qui prépare un inventaire pour une autre machine —
    obtient l'inventaire complet, comme avant."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    inv = scan.scan(racine, profils, "D:\\Emulation", INSTALL_DIRS)
    assert [r.title for r in inv] == ["Jeu"]


def test_le_systeme_ignore_est_signale(tmp_path, profils):
    """Ignorer en silence recréerait le défaut sous une autre forme : une
    bibliothèque incomplète, sans explication. Le rapport porte de quoi agir :
    le système, le profil, le chemin cherché, la raison, et combien de jeux y
    restent."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc", "snes/Autre.sfc"])
    emulation = faire_emulation(tmp_path)
    (ignore,) = scan.ignored_systems(racine, profils, INSTALL_DIRS, emulation)
    assert ignore.system_name == "Super Nintendo"
    assert ignore.profile == "retroarch"
    assert ignore.install_dir == emulation / "RetroArch"
    assert ignore.emulator == \
        emulation / "RetroArch" / "RetroArch-Win64" / "retroarch.exe"
    assert ignore.reason == install.ABSENT
    assert ignore.roms == 2


def test_rien_n_est_signale_quand_l_emulateur_est_la(tmp_path, profils):
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    emulation = faire_emulation(tmp_path)
    installer(emulation, "RetroArch", EXE_RETROARCH)
    assert scan.ignored_systems(racine, profils, INSTALL_DIRS, emulation) == []


def test_un_emulateur_ampute_de_son_executable_est_ignore(tmp_path, profils):
    """Le dossier d'installation est LÀ, l'exécutable non — un dossier vidé à
    la main, une extraction interrompue. C'est le scénario même qui a motivé
    ce correctif : tester l'existence du DOSSIER l'aurait laissé passer."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    emulation = faire_emulation(tmp_path)
    installer(emulation, "RetroArch", EXE_RETROARCH, executable=False)
    (ignore,) = scan.ignored_systems(racine, profils, INSTALL_DIRS, emulation)
    assert ignore.reason == install.INCOMPLET
    assert scan.scan(racine, profils, "D:\\Emulation", INSTALL_DIRS,
                     emulation_root_local=emulation) == []


def test_un_emulateur_sans_temoin_n_est_pas_repute_installe(tmp_path, profils):
    """L'exécutable est là, mais rien n'atteste l'installation.

    `install` ne dépose le témoin qu'après avoir vérifié et extrait TOUTES les
    archives — RetroArch sans ses cores ne lance rien tout en paraissant
    installé. Le témoin est donc un signal de complétude plus fort que
    l'exécutable. Et `status` déclarait déjà « absent » ce que le scan
    inventoriait : deux commandes, deux vérités sur le même disque.
    """
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    emulation = faire_emulation(tmp_path)
    installer(emulation, "RetroArch", EXE_RETROARCH, temoin=False)
    (ignore,) = scan.ignored_systems(racine, profils, INSTALL_DIRS, emulation)
    assert ignore.reason == install.SANS_TEMOIN


def test_tous_les_systemes_d_un_meme_emulateur_sont_signales(tmp_path, profils):
    """RetroArch sert neuf systèmes. N'en signaler qu'un ferait chercher une
    panne là où il y en a plusieurs — et le propriétaire, ayant « réglé » le
    seul signalé, croirait le reste sain."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc", "psx/Autre.cue"])
    emulation = faire_emulation(tmp_path)
    ignores = scan.ignored_systems(racine, profils, INSTALL_DIRS, emulation)
    assert sorted(i.system_name for i in ignores) == \
        ["PlayStation", "Super Nintendo"]


def test_le_compte_des_jeux_ignores_est_celui_de_l_inventaire(tmp_path, profils):
    """Le .m3u évince ses disques : annoncer « 3 jeux ignorés » là où le scan
    n'en aurait inscrit qu'un ferait chercher deux jeux qui n'existent pas."""
    racine = faire_roms(tmp_path, [
        "psx/Jeu.m3u", "psx/Jeu (Disc 1).cue", "psx/Jeu (Disc 2).cue",
    ])
    emulation = faire_emulation(tmp_path)
    (ignore,) = scan.ignored_systems(racine, profils, INSTALL_DIRS, emulation)
    assert ignore.roms == 1


def test_un_dossier_de_rom_vide_n_est_pas_signale(tmp_path, deux_profils):
    """Un émulateur non installé dont le propriétaire n'a aucun jeu ne lui
    coûte rien : le signaler noierait les manques qui, eux, lui coûtent des
    jeux. Le dossier existe — c'est bien l'ABSENCE DE JEUX qui compte, pas
    celle du dossier."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    (racine / "gc").mkdir()
    emulation = faire_emulation(tmp_path)
    installer(emulation, "RetroArch", EXE_RETROARCH)
    assert scan.ignored_systems(racine, deux_profils, INSTALL_DIRS,
                                emulation) == []


def test_signaler_sur_une_racine_absente_leve(tmp_path, profils):
    with pytest.raises(scan.ScanError):
        scan.ignored_systems(tmp_path / "jamais", profils, INSTALL_DIRS, tmp_path)


# --- une seule source de vérité -----------------------------------------

def test_l_ensemble_fourni_fait_foi(tmp_path, profils):
    """L'appelant qui a DÉJÀ calculé les systèmes ignorés — parce qu'il doit
    les annoncer — passe son ensemble, et le scan ne recalcule pas.

    Recalculer, c'est deux vérités possibles sur un disque qui bouge : entre
    le message et l'inventaire, un émulateur qui apparaît ou disparaît les
    rendrait contradictoires.
    """
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    emulation = faire_emulation(tmp_path)
    installer(emulation, "RetroArch", EXE_RETROARCH)  # bel et bien installé
    fourni = [scan.IgnoredSystem(
        folder="snes", system_name="Super Nintendo", profile="retroarch",
        install_dir=emulation / "RetroArch",
        emulator=emulation / "RetroArch" / EXE_RETROARCH,
        roms=1, reason=install.ABSENT)]
    inv = scan.scan(racine, profils, "D:\\Emulation", INSTALL_DIRS,
                    emulation_root_local=emulation, ignored=fourni)
    assert inv == []


def test_un_ensemble_fourni_vide_n_ignore_rien(tmp_path, profils):
    """Le pendant : l'ensemble vide est une réponse, pas une absence de
    réponse. Sans quoi le scan recalculerait et contredirait l'appelant."""
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    inv = scan.scan(racine, profils, "D:\\Emulation", INSTALL_DIRS,
                    emulation_root_local=faire_emulation(tmp_path), ignored=[])
    assert [r.title for r in inv] == ["Jeu"]


# --- Une bibliothèque rangée par constructeur -----------------------------
#
# Mesuré le 2026-08-26 sur la bibliothèque réelle du propriétaire : dix-sept
# systèmes attendus, quatre dossiers de constructeur sur le disque, zéro
# rencontre, et « 0 ROM répertoriée » pour toute explication. Le scan exigeait
# une organisation à plat que personne n'a — et ce n'est pas au propriétaire
# de réorganiser sa collection pour convenir à l'outil.

PROFIL_FOLDERS = """
schema = 1
id = "retroarch"
exe = 'RetroArch-Win64\\retroarch.exe'
[[system]]
id = "psx"
name = "PlayStation"
folders = ["Playstation", "PS1"]
extensions = [".cue", ".chd"]
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
def profils_folders(tmp_path):
    p = tmp_path / "ra.toml"
    p.write_text(PROFIL_FOLDERS, encoding="utf-8")
    return {"retroarch": profiles.load_profile(p)}


def _scan(tmp_path, profils):
    return scan.scan(tmp_path / "ROMs", profils, "D:\\Emulation",
                     {"retroarch": "RetroArch"}, roms_root_windows="G:\\ROMs")


def test_un_dossier_de_constructeur_est_traverse(tmp_path, profils_folders):
    """« Nintendo\\Snes\\jeu.sfc » : le constructeur n'est pas un système, il
    se traverse. C'est l'organisation de toute collection réelle."""
    faire_roms(tmp_path, ["Nintendo/Snes/Zelda.sfc"])
    inv = _scan(tmp_path, profils_folders)
    assert [e.title for e in inv] == ["Zelda"]


def test_le_chemin_de_la_rom_porte_toute_l_arborescence(tmp_path, profils_folders):
    """Le piège de la descente : reconnaître le dossier mais adresser la ROM
    par son seul nom donne une entrée Steam d'apparence normale qui ne
    démarre jamais — un échec qui ressemble à une réussite."""
    faire_roms(tmp_path, ["Nintendo/Snes/Zelda.sfc"])
    inv = _scan(tmp_path, profils_folders)
    assert inv[0].rom_path == "G:\\ROMs\\Nintendo\\Snes\\Zelda.sfc"


def test_un_nom_declare_dans_folders_est_reconnu(tmp_path, profils_folders):
    """Le propriétaire range « Playstation », le profil dit « psx »."""
    faire_roms(tmp_path, ["Sony/Playstation/Crash.cue"])
    inv = _scan(tmp_path, profils_folders)
    assert [e.system_name for e in inv] == ["PlayStation"]


def test_la_casse_du_dossier_est_ignoree(tmp_path, profils_folders):
    faire_roms(tmp_path, ["Sony/PLAYSTATION/Crash.cue"])
    assert len(_scan(tmp_path, profils_folders)) == 1


def test_un_dossier_reconnu_n_est_pas_ouvert_plus_loin(tmp_path, profils_folders):
    """Sous un système, ce sont des ROMs — pas d'autres systèmes. Un dossier
    « PS1 » d'extras à l'intérieur de « Snes » ne doit pas devenir un
    système, sans quoi la même ROM ressortirait deux fois."""
    faire_roms(tmp_path, ["Snes/PS1/piege.cue", "Snes/Zelda.sfc"])
    inv = _scan(tmp_path, profils_folders)
    assert [e.title for e in inv] == ["Zelda"]


def test_deux_systemes_homonymes_sous_deux_constructeurs(tmp_path, profils_folders):
    """Le chemin relatif, et non le nom seul, distingue les dossiers : c'est
    aussi la clé par laquelle un système ignoré est exclu."""
    faire_roms(tmp_path, ["A/Snes/Un.sfc", "B/Snes/Deux.sfc"])
    inv = _scan(tmp_path, profils_folders)
    assert sorted(e.rom_path for e in inv) == [
        "G:\\ROMs\\A\\Snes\\Un.sfc", "G:\\ROMs\\B\\Snes\\Deux.sfc"]


def test_la_descente_s_arrete_avant_de_fouiller_les_jeux(tmp_path, profils_folders):
    """Passé la profondeur admise, ce qu'on parcourt n'est plus un rangement
    mais l'intérieur d'un jeu."""
    faire_roms(tmp_path, ["a/b/c/d/Snes/Zelda.sfc"])
    assert _scan(tmp_path, profils_folders) == []


# --- Ce que le scan dit quand il ne reconnaît rien -------------------------

def test_les_dossiers_inconnus_sont_nommes(tmp_path, profils_folders):
    faire_roms(tmp_path, ["Atari/5200/jeu.a52", "Nintendo/Virtual Boy/jeu.vb"])
    vus, attendus = scan.unmatched_folders(tmp_path / "ROMs", profils_folders)
    assert vus == ["Atari\\5200", "Nintendo\\Virtual Boy"]
    assert "PlayStation" in attendus and "Super Nintendo" in attendus


def test_un_constructeur_dont_un_enfant_est_reconnu_n_est_pas_signale(
        tmp_path, profils_folders):
    """Sinon une bibliothèque parfaitement rangée listerait ses propres
    dossiers de constructeur comme autant de problèmes."""
    faire_roms(tmp_path, ["Nintendo/Snes/Zelda.sfc"])
    vus, _ = scan.unmatched_folders(tmp_path / "ROMs", profils_folders)
    assert vus == []


def test_un_lien_qui_remonte_ne_duplique_pas_les_jeux(tmp_path, profils_folders):
    """Un lien vers un ancêtre — ou une jonction Windows — fait retrouver les
    mêmes ROMs par un second chemin. Chacune recevait deux entrées Steam pour
    le même jeu, et la profondeur maximale bornait l'explosion sans empêcher
    le doublon."""
    import os
    faire_roms(tmp_path, ["Snes/Zelda.sfc"])
    racine = tmp_path / "ROMs"
    (racine / "ailleurs").mkdir()
    os.symlink(racine, racine / "ailleurs" / "boucle")
    inv = _scan(tmp_path, profils_folders)
    assert [e.title for e in inv] == ["Zelda"]


def test_un_systeme_relie_depuis_un_autre_volume_reste_lu(tmp_path, profils_folders):
    """Ne pas traverser un lien ne doit pas revenir à en ignorer un : ranger
    un système ailleurs et le relier ici est un usage légitime."""
    import os
    ailleurs = tmp_path / "volume2" / "Snes"
    ailleurs.mkdir(parents=True)
    (ailleurs / "Zelda.sfc").write_bytes(b"x")
    (tmp_path / "ROMs").mkdir(parents=True, exist_ok=True)
    os.symlink(ailleurs, tmp_path / "ROMs" / "Snes")
    assert [e.title for e in _scan(tmp_path, profils_folders)] == ["Zelda"]


def test_un_scan_sans_lanceur_est_refuse(tmp_path, profils):
    """Chaque raccourci pointera sur le lanceur commun.

    Absent, c'est TOUTE la bibliothèque qui ne démarre plus, et l'erreur que
    Steam affiche ne nomme aucun jeu : la panne la moins diagnosticable que
    cette console puisse produire. Un inventaire qui pointe sur un exécutable
    absent est un inventaire qui a l'air parfaitement normal.
    """
    racine = faire_roms(tmp_path, ["snes/Jeu.sfc"])
    emulation = tmp_path / "Emulation"
    emulation.mkdir()
    installer(emulation, "RetroArch", EXE_RETROARCH)
    with pytest.raises(scan.ScanError, match="lanceur commun est introuvable"):
        scan.scan(racine, profils, "D:\\Emulation", INSTALL_DIRS,
                  emulation_root_local=emulation)


# --- Une bibliothèque faite de DOSSIERS ------------------------------------
#
# Le scan comptait des FICHIERS, et lui seul décidait ce qu'était un jeu :
# `_retenus` filtrait `is_file()` sur une extension. Une bibliothèque PS Vita
# n'a pas cette forme — une application installée est un DOSSIER
# (« ux0:app\PCSE00123\ »), rangé à côté des .vpk. Sur une telle collection,
# l'ancien scan rendait ZÉRO jeu sans un mot : les dossiers étaient ignorés
# par `is_file()`, et un dossier de système reconnu n'est jamais ouvert plus
# loin.
#
# Ce que ces tests fixent, c'est la forme de la réponse : le PROFIL déclare
# qu'un jeu peut être un dossier, et à quoi ce dossier se reconnaît. Le scan
# ne connaît aucun émulateur ; il applique une règle déclarée.

PROFIL_APPS = """
schema = 1
id = "vita3k"
exe = "Vita3K.exe"
[[system]]
id = "vita"
name = "PS Vita"
extensions = [".vpk"]
app_dir_marker = "eboot.bin"
launch = '--fullscreen "{rom}"'
bios = []
"""


@pytest.fixture
def profils_apps(tmp_path):
    p = tmp_path / "vita3k.toml"
    p.write_text(PROFIL_APPS, encoding="utf-8")
    return {"vita3k": profiles.load_profile(p)}


def _scan_apps(tmp_path, profils):
    return scan.scan(tmp_path / "ROMs", profils, "D:\\Emulation",
                     {"vita3k": "Vita3K"}, roms_root_windows="G:\\ROMs")


def faire_app(tmp_path, chemin, marqueur="eboot.bin"):
    """Un dossier d'application installée : son marqueur, et du remplissage."""
    dossier = tmp_path / "ROMs" / chemin
    (dossier / "sce_sys").mkdir(parents=True, exist_ok=True)
    (dossier / marqueur).write_bytes(b"x")
    (dossier / "sce_sys" / "param.sfo").write_bytes(b"x")
    return dossier


def test_un_dossier_d_application_donne_une_entree(tmp_path, profils_apps):
    faire_app(tmp_path, "vita/PCSE00123")
    inv = _scan_apps(tmp_path, profils_apps)
    assert [e.title for e in inv] == ["PCSE00123"]
    assert inv[0].rom_path == "G:\\ROMs\\vita\\PCSE00123"
    assert inv[0].system_name == "PS Vita"


def test_le_contenu_d_une_application_ne_fait_pas_d_entrees(tmp_path,
                                                            profils_apps):
    """Le défaut que cette dette nommait : une entrée Steam PAR FICHIER de jeu.

    Un dossier d'application contient des dizaines de fichiers, dont certains
    portent une extension déclarée. C'est le DOSSIER qui est le jeu ; ce qu'il
    contient ne doit jamais être inventorié.
    """
    dossier = faire_app(tmp_path, "vita/PCSE00123")
    (dossier / "patch.vpk").write_bytes(b"x")
    (dossier / "sce_sys" / "autre.vpk").write_bytes(b"x")
    inv = _scan_apps(tmp_path, profils_apps)
    assert [e.title for e in inv] == ["PCSE00123"]


def test_les_vpk_a_cote_restent_des_entrees(tmp_path, profils_apps):
    """« à côté des .vpk » : les deux formes cohabitent dans le même dossier."""
    faire_app(tmp_path, "vita/PCSE00123")
    faire_roms(tmp_path, ["vita/Super Jeu (USA).vpk"])
    inv = _scan_apps(tmp_path, profils_apps)
    assert sorted(e.title for e in inv) == ["PCSE00123", "Super Jeu"]


def test_un_dossier_sans_marqueur_n_est_pas_un_jeu(tmp_path, profils_apps):
    """Compter TOUT sous-dossier ferait une entrée Steam de « savedata ».

    C'est pour cela que le marqueur est déclaré et non deviné : le scan
    reconnaît une application à un fichier qu'elle porte, pas au fait d'être
    un dossier.
    """
    faire_app(tmp_path, "vita/PCSE00123")
    (tmp_path / "ROMs" / "vita" / "savedata" / "PCSE00123").mkdir(parents=True)
    inv = _scan_apps(tmp_path, profils_apps)
    assert [e.title for e in inv] == ["PCSE00123"]


def test_le_marqueur_se_compare_sans_la_casse(tmp_path, profils_apps):
    """Le scan tourne sous Linux et décrit une machine Windows, où la casse
    d'un nom de fichier ne distingue rien. « EBOOT.BIN » et « eboot.bin » sont
    le même fichier là où le jeu se lancera."""
    faire_app(tmp_path, "vita/PCSE00123", marqueur="EBOOT.BIN")
    assert [e.title for e in _scan_apps(tmp_path, profils_apps)] == ["PCSE00123"]


def test_le_point_d_un_nom_de_dossier_n_est_pas_une_extension(tmp_path,
                                                              profils_apps):
    """« Jeu v1.02 » est un nom entier. Retirer « .02 » comme on retire une
    extension renommerait le jeu dans Steam, en silence."""
    faire_app(tmp_path, "vita/Jeu v1.02")
    assert [e.title for e in _scan_apps(tmp_path, profils_apps)] == ["Jeu v1.02"]


def test_un_dossier_d_application_est_desambigue_comme_un_fichier(
        tmp_path, profils_apps):
    """Un .vpk et un dossier de même titre rendraient le même identifiant
    Steam, et une seule des deux entrées survivrait à l'écriture."""
    faire_app(tmp_path, "vita/Jeu")
    faire_roms(tmp_path, ["vita/Jeu.vpk"])
    titres = [e.title for e in _scan_apps(tmp_path, profils_apps)]
    assert len(titres) == 2
    assert len(set(titres)) == 2


def test_sans_marqueur_declare_aucun_dossier_n_est_compte(tmp_path, profils):
    """Les neuf profils livrés n'en déclarent aucun : leur scan ne change pas.

    Un dossier sous un système de ROMs est un dossier d'extras ou de disques,
    pas un jeu — le compter donnerait une entrée Steam qui ne lance rien.
    """
    faire_roms(tmp_path, ["snes/Extras/notice.txt", "snes/Zelda.sfc"])
    assert [e.title for e in scanner(tmp_path / "ROMs", profils)] == ["Zelda"]


def test_une_application_compte_dans_les_systemes_ignores(tmp_path,
                                                          profils_apps):
    """Le compte annoncé au propriétaire est celui de l'inventaire.

    Un émulateur absent doit dire combien de jeux il coûte : sur une
    bibliothèque en dossiers, ce compte serait resté à zéro et le système
    n'aurait même pas été signalé.
    """
    faire_app(tmp_path, "vita/PCSE00123")
    faire_roms(tmp_path, ["vita/Super Jeu (USA).vpk"])
    emulation = tmp_path / "Emulation"
    emulation.mkdir()
    ignores = scan.ignored_systems(tmp_path / "ROMs", profils_apps,
                                   {"vita3k": "Vita3K"}, emulation)
    assert [i.roms for i in ignores] == [2]


# --- Le dossier de mise à jour, qui porte le MÊME marqueur ------------------
#
# `app_dir_marker` retient tout sous-dossier portant le fichier déclaré. Une
# mise à jour extraite en porte un aussi : posée à côté de sa base, elle donne
# une SECONDE entrée Steam pour le même jeu, d'apparence normale, qui lance le
# correctif seul — soit rien de jouable. Mesuré le 2026-08-29 sur un profil
# `app_dir_marker = "eboot.bin"` : deux dossiers, deux entrées, pas un mot.
#
# Le scan la garde et la SIGNALE, il ne l'écarte pas : voir la docstring de
# `suspected_update_dirs`.


def test_un_dossier_de_mise_a_jour_est_signale(tmp_path, profils_apps):
    faire_app(tmp_path, "vita/God of War")
    faire_app(tmp_path, "vita/CUSA07410-UPDATE")
    assert scan.suspected_update_dirs(tmp_path / "ROMs", profils_apps) == [
        "vita\\CUSA07410-UPDATE"]


def test_le_dossier_de_mise_a_jour_reste_dans_l_inventaire(tmp_path,
                                                           profils_apps):
    """SIGNALÉ, jamais écarté : le scan ne sait pas ouvrir un dossier
    d'application, donc il ne peut pas PROUVER qu'il tient une mise à jour. Un
    dossier retiré sur une devinette est un jeu perdu sans un mot."""
    faire_app(tmp_path, "vita/God of War")
    faire_app(tmp_path, "vita/CUSA07410-UPDATE")
    titres = [e.title for e in _scan_apps(tmp_path, profils_apps)]
    assert sorted(titres) == ["CUSA07410-UPDATE", "God of War"]


def test_un_titre_qui_contient_le_mot_par_hasard_n_est_pas_signale(
        tmp_path, profils_apps):
    """« Dispatch » contient « patch ». La reconnaissance porte sur des MOTS,
    pas sur des sous-chaînes — sans quoi le rapport accuserait un jeu."""
    faire_app(tmp_path, "vita/Dispatch")
    assert scan.suspected_update_dirs(tmp_path / "ROMs", profils_apps) == []


def test_un_dossier_sans_marqueur_n_est_jamais_signale(tmp_path, profils_apps):
    """Ce qui n'entre pas dans l'inventaire ne peut pas le doubler."""
    (tmp_path / "ROMs" / "vita" / "update").mkdir(parents=True)
    assert scan.suspected_update_dirs(tmp_path / "ROMs", profils_apps) == []


def test_sans_marqueur_declare_rien_n_est_signale(tmp_path, profils):
    """Les neuf profils livrés n'en déclarent aucun : rien ne change pour eux."""
    faire_roms(tmp_path, ["snes/Zelda.sfc"])
    (tmp_path / "ROMs" / "snes" / "Zelda patch").mkdir(parents=True)
    assert scan.suspected_update_dirs(tmp_path / "ROMs", profils) == []


# --- le titre reconnu l'emporte sur le nom de fichier ----------------------

class _ResolveurFactice:
    """Rend un titre pour les fichiers qu'on lui nomme, rien pour les autres."""

    def __init__(self, par_nom):
        self.par_nom = par_nom
        self.echecs = []
        self.non_reconnus = []

    def resoudre(self, chemin, sid):
        from retro.titres import Titre
        nom = self.par_nom.get(chemin.name)
        return Titre(nom, "essai") if nom else None


def test_un_titre_reconnu_remplace_le_nom_de_fichier(tmp_path, profils):
    """« mslug2 » est un nom de romset : dans Steam il ne dit rien au
    proprietaire, et envoye a SteamGridDB il ne trouve aucune jaquette."""
    racine = faire_roms(tmp_path, ["snes/mslug2.sfc"])
    inv = scan.scan(racine, profils, "D:\\Emulation",
                    {"retroarch": "RetroArch"},
                    resolveur=_ResolveurFactice(
                        {"mslug2.sfc": "Metal Slug 2 (World)"}))
    assert [e.title for e in inv] == ["Metal Slug 2"]


def test_un_jeu_non_reconnu_garde_son_nom_et_est_nomme(tmp_path, profils):
    """Ce n'est pas une panne — c'est le comportement d'avant — mais le
    rapport le NOMME : un titre reste brut est le seul signe visible qu'une
    base manque ou qu'un dump est inconnu."""
    racine = faire_roms(tmp_path, ["snes/inconnu.sfc"])
    r = _ResolveurFactice({})
    inv = scan.scan(racine, profils, "D:\\Emulation",
                    {"retroarch": "RetroArch"}, resolveur=r)
    assert [e.title for e in inv] == ["inconnu"]
    assert r.non_reconnus == ["Super Nintendo : inconnu.sfc"]


def test_sans_resolveur_le_comportement_ne_change_pas(tmp_path, profils):
    racine = faire_roms(tmp_path, ["snes/mslug2.sfc"])
    assert [e.title for e in scanner(racine, profils)] == ["mslug2"]
