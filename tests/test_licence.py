"""La licence d'un jeu PS Vita : ce que « retro » en sait, et rien de plus.

Il n'y a AUCUNE conversion à faire, et ce n'est pas une opinion : c'est ce que
la source de l'émulateur dit.

    packages/src/license.cpp, copy_license
        lit le content_id de la licence, en tire title_id = content_id.substr(7, 9),
        puis fait fs::copy_file(license_path, license_dst_path, …) — le fichier
        est copié TEL QUEL vers ux0/license/<title_id>/<content_id>.rif. Seul le
        nom change.
    main.cpp
        is_rif = (extension == ".rif") || (filename == "work.bin") -> copy_license
        — l'émulateur sait donc poser une licence depuis sa ligne de commande.

Ce que `retro` peut faire, et qui manque, c'est de DIRE si la licence est là :
son absence ne bloque rien, elle fausse un champ, et l'émulateur ne s'en plaint
que dans un journal que personne ne lit depuis un canapé.

Toutes les fixtures sont FABRIQUÉES octet par octet. Aucun dump, aucune licence
réelle n'entre dans ce dépôt.
"""
import pathlib

import pytest

from retro import licence


def _work_bin(content_id: str, taille: int = 0x200) -> bytes:
    """Un fichier de licence FABRIQUÉ, jamais copié d'un dump.

    La structure vient de packages/include/packages/license.h : content_id est
    un char[0x30] à l'offset 0x10, et la structure fait 0x200 octets — elle
    s'arrête à rsa_signature[0x100] posé en 0x100.
    """
    octets = bytearray(taille)
    octets[0x10:0x10 + len(content_id)] = content_id.encode("ascii")
    return bytes(octets)


def test_le_content_id_se_lit_a_l_offset_attendu():
    brut = _work_bin("EP9000-PCSF00012_00-0000000000000000")
    assert licence.content_id(brut) == "EP9000-PCSF00012_00-0000000000000000"


def test_le_title_id_est_le_septieme_caractere_sur_neuf():
    """substr(7, 9) dans copy_license : ce n'est PAS « ce qui suit le tiret »,
    et les deux coïncident seulement pour un préfixe de six caractères."""
    assert licence.title_id("EP9000-PCSF00012_00-0000000000000000") == "PCSF00012"
    assert licence.title_id("UP0001-PCSA00001_00-0000000000000000") == "PCSA00001"


def test_le_chemin_de_licence_est_celui_que_vita3k_cherche():
    brut = _work_bin("EP9000-PCSF00012_00-0000000000000000")
    assert licence.chemin_relatif(brut) == (
        "ux0\\license\\PCSF00012\\EP9000-PCSF00012_00-0000000000000000.rif")


def test_un_fichier_trop_court_est_refuse_en_le_nommant():
    with pytest.raises(licence.LicenceError) as exc:
        licence.content_id(b"\x00" * 0x40)
    assert "0x200" in str(exc.value)


def test_un_content_id_vide_est_refuse():
    """Un work.bin dont les octets 0x10..0x40 sont nuls donnerait un title_id
    vide, donc un dossier « ux0\\license\\ » — un chemin d'apparence normale
    que Vita3K ne lirait jamais."""
    with pytest.raises(licence.LicenceError):
        licence.content_id(bytes(0x200))


def test_un_content_id_trop_court_pour_porter_un_title_id_est_refuse():
    """substr(7, 9) sur une chaîne de moins de seize caractères rendrait un
    title_id tronqué — donc un dossier qui ressemble à un chemin correct et
    qu'aucun lecteur n'ouvrira."""
    with pytest.raises(licence.LicenceError):
        licence.title_id("EP9000-PC")


# --- ce que le rapport peut DIRE, et ce qu'il n'a pas le droit de conclure ---

CID = "EP9000-PCSF00012_00-0000000000000000"


def _dump(racine, nom: str, cid: str | None = CID,
          octets: bytes | None = None):
    """Un dossier de jeu FABRIQUÉ, avec ou sans sa licence.

    Un dump NoNpDrm porte sa licence dans sce_sys/package/work.bin — c'est le
    nom que main.cpp reconnaît (is_rif). Rien d'autre n'est écrit : ce dépôt
    ne contient aucun dump.
    """
    dossier = racine / nom
    if cid is None and octets is None:
        dossier.mkdir(parents=True)
        return dossier
    paquet = dossier / "sce_sys" / "package"
    paquet.mkdir(parents=True)
    (paquet / "work.bin").write_bytes(
        octets if octets is not None else _work_bin(cid))
    return dossier


def test_un_jeu_sans_licence_a_poser_n_est_pas_mentionne(tmp_path):
    """Un dump sans sce_sys/package/ n'a rien à faire poser : le mentionner
    ferait une ligne par jeu de la bibliothèque, et la seule qui compte s'y
    perdrait."""
    jeu = _dump(tmp_path / "jeux", "PCSF00012", cid=None)
    assert licence.etat_licences([("Un jeu", jeu)], tmp_path / "vita") == []


def test_une_licence_hors_de_portee_ne_se_conclut_pas_absente(tmp_path):
    """L'hôte n'atteint pas %APPDATA% de la console. Conclure « licence
    absente » depuis là serait annoncer un manque qu'on ne peut pas
    constater — le pire des états, et le raisonnement déjà écrit pour le
    témoin d'amorçage."""
    jeu = _dump(tmp_path / "jeux", "PCSF00012")
    etat, = licence.etat_licences([("Un jeu", jeu)], None)
    assert etat.etat == licence.HORS_DE_PORTEE
    assert etat.attendue.endswith(f"{CID}.rif")


def test_une_licence_posee_se_dit(tmp_path):
    jeu = _dump(tmp_path / "jeux", "PCSF00012")
    vita = tmp_path / "vita"
    pose = vita / "ux0" / "license" / "PCSF00012" / f"{CID}.rif"
    pose.parent.mkdir(parents=True)
    pose.write_bytes(_work_bin(CID))
    etat, = licence.etat_licences([("Un jeu", jeu)], vita)
    assert etat.etat == licence.POSEE


def test_une_licence_absente_se_dit_quand_on_peut_le_constater(tmp_path):
    """Racine atteignable, dossier lisible, fichier absent : là, et seulement
    là, le rapport a le droit de dire qu'il manque."""
    jeu = _dump(tmp_path / "jeux", "PCSF00012")
    vita = tmp_path / "vita"
    vita.mkdir()
    etat, = licence.etat_licences([("Un jeu", jeu)], vita)
    assert etat.etat == licence.ABSENTE
    assert etat.attendue == (
        f"ux0\\license\\PCSF00012\\{CID}.rif")


def test_un_work_bin_illisible_ne_passe_pas_pour_une_licence_absente(tmp_path):
    """Deux causes, un seul symptôme si on les confond : le fichier illisible
    et la licence jamais posée n'appellent pas le même geste."""
    jeu = _dump(tmp_path / "jeux", "PCSF00012", octets=b"\x00" * 0x40)
    etat, = licence.etat_licences([("Un jeu", jeu)], tmp_path / "vita")
    assert etat.etat == licence.ILLISIBLE
    assert "0x200" in etat.detail


# --- de l'inventaire au disque local ---------------------------------------

class _Entree:
    """Le peu qu'une entrée d'inventaire doit porter pour être traduite."""

    def __init__(self, title, rom_path):
        self.title = title
        self.rom_path = rom_path


def test_un_chemin_windows_d_inventaire_s_ouvre_sur_le_disque_local(tmp_path):
    """L'inventaire porte des chaînes WINDOWS — c'est ce que la console verra.
    Jointes telles quelles sous Linux, elles font un segment unique qu'aucun
    is_file() ne confirme : le rapport conclurait « aucune licence à poser »
    sur une bibliothèque qui en porte."""
    # Le dump EXISTE : depuis le 2026-08-29, seuls les dossiers sont retenus
    # (une ROM qui est un fichier ne porte aucune licence, et descendre sous
    # elle fait lever Windows). Une fixture sans dossier ne mesurerait plus la
    # traduction, mais le filtre.
    (tmp_path / "Sony" / "PSVita" / "PCSF00012").mkdir(parents=True)
    jeux = licence.jeux_locaux(
        [_Entree("Un jeu", "G:\\ROMs\\Sony\\PSVita\\PCSF00012")],
        "G:\\ROMs", tmp_path)
    assert jeux == [("Un jeu", tmp_path / "Sony" / "PSVita" / "PCSF00012")]


def test_une_entree_d_une_autre_racine_est_laissee_de_cote(tmp_path):
    """Traduire un chemin qui ne vient pas de cette racine fabriquerait un
    dossier au hasard sous elle, et le rapport parlerait d'un jeu qui n'y est
    pas."""
    assert licence.jeux_locaux(
        [_Entree("Un jeu", "H:\\Autre\\PCSF00012")], "G:\\ROMs", tmp_path) == []


# --- Mesuré sur la console le 2026-08-29 : `retro status` PLANTAIT ---------
#
# [WinError 31] A device attached to the system is not functioning:
#   'G:\Games\Nintendo\Gameboy\Pokemon ... .gb\sce_sys\package\work.bin'
#
# `jeux_locaux` retenait TOUTE entrée sous la racine, y compris les ROMs qui
# sont des FICHIERS. `licence_du_dump` joignait alors `sce_sys/package/work.bin`
# SOUS un fichier. Sous Linux, `is_file()` y rend False sans broncher — c'est
# pourquoi aucune fixture ne l'a vu ; sous Windows, il LÈVE, et le rapport
# entier mourait. Une licence vit dans un dump, qui est un DOSSIER.

def test_une_rom_fichier_n_est_pas_un_jeu_a_licence(tmp_path):
    """Le seul rapport fait pour être lu ne doit pas mourir sur une Game Boy."""
    (tmp_path / "Nintendo" / "Gameboy").mkdir(parents=True)
    rom = tmp_path / "Nintendo" / "Gameboy" / "Pokemon.gb"
    rom.write_bytes(b"\x00" * 32)
    dump = tmp_path / "Sony" / "PS Vita" / "PCSF00012"
    dump.mkdir(parents=True)

    class Entree:
        def __init__(self, titre, chemin):
            self.title, self.rom_path = titre, chemin

    jeux = licence.jeux_locaux(
        [Entree("Pokemon", r"G:\Games\Nintendo\Gameboy\Pokemon.gb"),
         Entree("Uncharted", r"G:\Games\Sony\PS Vita\PCSF00012")],
        r"G:\Games", tmp_path)
    titres = [t for t, _ in jeux]
    assert titres == ["Uncharted"], (
        "une ROM qui est un fichier ne porte aucun dump, donc aucune licence ; "
        f"la retenir fait descendre sous un fichier — reçu {titres}")


def test_un_chemin_illisible_ne_tue_pas_le_rapport(tmp_path, monkeypatch):
    """Windows lève là où Linux rend False. Le rapport doit survivre aux deux :
    un chemin qu'on ne peut pas interroger n'est pas une licence, c'est une
    absence de réponse — et elle ne vaut pas la mort du seul écran lisible."""
    def leve(self):
        raise OSError(31, "A device attached to the system is not functioning")
    monkeypatch.setattr(pathlib.Path, "is_file", leve)
    assert licence.licence_du_dump(tmp_path) is None
