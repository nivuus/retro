"""La licence d'un jeu PS Vita : où l'émulateur la cherche, et sous quel nom.

CE MODULE NE CONVERTIT RIEN, ET IL N'Y A RIEN À CONVERTIR. La dette D9
demandait où vivrait la « conversion » d'un `work.bin` en `.rif` ; la source de
l'émulateur répond qu'il n'y en a pas :

    packages/src/license.cpp, copy_license
        lit le content_id du fichier, en tire title_id = content_id.substr(7, 9),
        crée ux0/license/<title_id>/, puis
        fs::copy_file(license_path, license_dst_path, overwrite_existing)
        — le fichier est copié TEL QUEL. Seul le nom change.
    main.cpp
        is_rif = (extension == ".rif") || (filename == "work.bin")
        puis copy_license(emuenv, *cfg.content_path)
        — l'émulateur pose donc une licence depuis sa propre ligne de commande.

Ni `retro install` ni `retro scan` n'ont à le faire : le premier installe des
émulateurs, pas des jeux ; le second tourne sur l'hôte, qui n'atteint pas le
système de fichiers de la console virtuelle.

CE QUE CE MODULE FAIT, ET QUI MANQUAIT : DIRE si la licence est là. Son absence
ne bloque rien — `get_license` journalise un avertissement et fausse un seul
champ (`sku_flag`) — donc personne ne s'en aperçoit avant d'être en jeu, dans
un journal que personne ne lit depuis un canapé.

ET LE NOM NE SE DEVINE PAS. Le « EP9000- » du cas de la dette est le préfixe
régional de ce jeu-là, rien de plus : la règle se lit dans les octets, pas sur
un exemple.
"""
from __future__ import annotations

import dataclasses
import pathlib
from collections.abc import Sequence

from retro import install as install_mod
from retro import lecture

# LA STRUCTURE, ET D'OÙ CHAQUE NOMBRE VIENT.
#
# packages/include/packages/license.h, struct SceNpDrmLicense :
#   char content_id[0x30]; // 0x10
#   uint8_t rsa_signature[0x100]; // 0x100  <- le dernier champ
#
# Un commentaire qui ne dit pas d'où vient une constante rend cette constante
# indistinguable d'une invention — et une valeur inventée se comporte
# exactement comme une valeur absente.
OFFSET_CONTENT_ID = 0x10
TAILLE_CONTENT_ID = 0x30
# 0x100 (offset de rsa_signature) + 0x100 (sa taille) : la structure s'arrête là.
TAILLE_LICENCE = 0x200

# packages/src/license.cpp : title_id = content_id.substr(7, 9). NEUF caractères
# À PARTIR DU SEPTIÈME — ce n'est PAS « ce qui suit le tiret », et les deux ne
# coïncident que pour un préfixe de six caractères.
DEBUT_TITLE_ID = 7
LONGUEUR_TITLE_ID = 9

# packages/src/license.cpp : vita_fs_path / "ux0/license" / title_id, puis
# « {content_id}.rif ». Écrit ici en séparateurs Windows, comme tous les chemins
# de ce projet, que le lanceur consomme tels quels.
DOSSIER_LICENCES = "ux0\\license"


class LicenceError(Exception):
    """Un fichier de licence qui n'en est pas un, refusé en le nommant.

    Le refus compte autant que la lecture : un `work.bin` tronqué ou nul
    donnerait un content_id vide, donc un chemin « ux0\\license\\ » d'apparence
    parfaitement normale, que l'émulateur n'ouvrirait jamais. Le rapport
    annoncerait alors une licence absente là où c'est le FICHIER qui est
    illisible — deux causes différentes, un seul symptôme.
    """


def content_id(octets: bytes) -> str:
    """Le `content_id` d'un fichier de licence, lu dans ses octets."""
    if len(octets) < TAILLE_LICENCE:
        raise LicenceError(
            f"fichier de licence trop court : {len(octets)} octets, il en faut "
            f"{TAILLE_LICENCE} (0x200). La structure SceNpDrmLicense de "
            "packages/include/packages/license.h s'arrête à "
            "rsa_signature[0x100] posé en 0x100. Un fichier plus court n'est "
            "pas une licence tronquée : c'est autre chose."
        )
    brut = octets[OFFSET_CONTENT_ID:OFFSET_CONTENT_ID + TAILLE_CONTENT_ID]
    # Une chaîne C : elle s'arrête au premier octet nul, le reste est du
    # remplissage. La rendre entière collerait des zéros au nom du fichier.
    cid = brut.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
    if not cid:
        raise LicenceError(
            f"le content_id est vide (offset 0x{OFFSET_CONTENT_ID:02x}, "
            f"0x{TAILLE_CONTENT_ID:02x} octets). Il en sortirait un title_id "
            "vide, donc un dossier « ux0\\license\\ » d'apparence normale que "
            "l'émulateur n'ouvrirait jamais — un manque annoncé pour une "
            "mauvaise raison est pire qu'un manque tu."
        )
    return cid


def title_id(cid: str) -> str:
    """Le `title_id` que l'émulateur tire d'un `content_id`."""
    if len(cid) < DEBUT_TITLE_ID + LONGUEUR_TITLE_ID:
        raise LicenceError(
            f"content_id trop court pour en tirer un title_id : {cid!r}. "
            f"packages/src/license.cpp fait substr({DEBUT_TITLE_ID}, "
            f"{LONGUEUR_TITLE_ID}), donc il faut au moins "
            f"{DEBUT_TITLE_ID + LONGUEUR_TITLE_ID} caractères. Plus court, le "
            "title_id serait tronqué, et le dossier ressemblerait à un chemin "
            "correct qu'aucun lecteur n'ouvrira."
        )
    return cid[DEBUT_TITLE_ID:DEBUT_TITLE_ID + LONGUEUR_TITLE_ID]


def chemin_relatif(octets: bytes) -> str:
    """Où l'émulateur ira chercher CETTE licence, sous sa racine de système
    de fichiers Vita — `ux0\\license\\<title_id>\\<content_id>.rif`."""
    cid = content_id(octets)
    return f"{DOSSIER_LICENCES}\\{title_id(cid)}\\{cid}.rif"


# Où un dump NoNpDrm porte SA licence, avant toute installation. C'est le nom
# que l'émulateur reconnaît lui-même, main.cpp :
#   is_rif = (extension == ".rif") || (filename == "work.bin")
LICENCE_DU_DUMP = ("sce_sys", "package", "work.bin")

# LES QUATRE ÉTATS, et il faut les quatre. Les réduire à « posée / absente »
# ferait annoncer un manque là où le rapport ne peut RIEN constater — c'est le
# raisonnement déjà écrit pour le témoin d'amorçage, et le pire des états.
POSEE = "posee"
ABSENTE = "absente"
# L'hôte n'atteint pas le système de fichiers Vita. Ce n'est pas un problème
# de la console : c'est une limite de l'endroit d'où le rapport est produit.
HORS_DE_PORTEE = "hors-de-portee"
# Le work.bin existe mais n'est pas une licence. Distinct d'« absente » : les
# deux n'appellent pas le même geste.
ILLISIBLE = "illisible"


@dataclasses.dataclass(frozen=True)
class EtatLicence:
    """Ce que le rapport sait de la licence d'UN jeu, et d'où il le sait."""
    jeu: str
    etat: str
    # Le chemin que l'émulateur ouvrira, relatif à sa racine de système de
    # fichiers Vita. Rendu même hors de portée : c'est ce que le propriétaire
    # ira vérifier lui-même, et un état sans chemin est une accusation, pas un
    # diagnostic.
    attendue: str = ""
    detail: str = ""


def licence_du_dump(dossier: pathlib.Path) -> pathlib.Path | None:
    """Le `work.bin` que ce dossier de jeu porte, ou None s'il n'en a pas.

    Un dump SANS `sce_sys/package/` n'a aucune licence à faire poser : il n'a
    rien à dire au rapport. Le mentionner ferait une ligne par jeu de la
    bibliothèque, et la seule qui compte s'y perdrait.
    """
    chemin = dossier.joinpath(*LICENCE_DU_DUMP)
    try:
        return chemin if chemin.is_file() else None
    except OSError:
        # Windows LÈVE là où Linux rend False — mesuré le 2026-08-29 sur la
        # console : « [WinError 31] A device attached to the system is not
        # functioning » en descendant sous une ROM Game Boy, et `retro status`
        # mourait tout entier. Un chemin qu'on ne peut pas interroger n'est pas
        # une licence : c'est une absence de réponse, et elle ne vaut pas la
        # mort du seul écran de ce paquet fait pour être lu.
        return None


def jeux_locaux(inventaire: Sequence[object], roms_root_windows: str,
                roms_root: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    """(titre, dossier sur CE disque) pour chaque entrée de l'inventaire.

    Les chemins de l'inventaire sont des chaînes WINDOWS — c'est ce que la
    console verra. Sous Linux, l'antislash n'est pas un séparateur : joints
    tels quels, ils font un segment unique qu'aucun `is_file()` ne confirme,
    et le rapport conclurait « aucune licence à poser » sur une bibliothèque
    qui en porte. C'est exactement le défaut que `install.local_path` existe
    pour fermer, et c'est lui qui traduit.

    Une entrée qui ne vient pas de cette racine est LAISSÉE DE CÔTÉ : la
    traduire fabriquerait un dossier au hasard sous elle, et le rapport
    parlerait d'un jeu qui n'y est pas.
    """
    prefixe = roms_root_windows.rstrip("\\/")
    jeux = []
    for rom in inventaire:
        chemin = str(getattr(rom, "rom_path", ""))
        if not chemin.startswith(prefixe + "\\"):
            continue
        local = install_mod.local_path(roms_root, chemin[len(prefixe) + 1:])
        # SEULS LES DOSSIERS. Une licence vit dans un dump, qui est un dossier
        # (`ux0/app/<TITLEID>/sce_sys/package/work.bin`) ; une ROM qui est un
        # FICHIER n'en porte aucune. Les retenir toutes faisait descendre sous
        # un fichier, ce que Windows refuse en levant — le rapport entier
        # mourait sur une Game Boy. Mesuré sur la console le 2026-08-29.
        try:
            if not local.is_dir():
                continue
        except OSError:
            continue
        jeux.append((rom.title, local))
    return jeux


def etat_licences(jeux: Sequence[tuple[str, pathlib.Path]],
                  racine_vita: pathlib.Path | None) -> list[EtatLicence]:
    """L'état de la licence de chaque jeu qui en porte une.

    `racine_vita` est la racine du système de fichiers de la console
    virtuelle — celle qui contient `ux0` —, ATTEIGNABLE DEPUIS CET HÔTE, ou
    None quand elle ne l'est pas. Elle ne l'est pas par défaut : l'émulateur
    range ses données dans le profil Windows de l'utilisateur, que l'hôte ne
    monte pas. Tant que `pref-path` ne l'a pas sortie de là, le seul état
    honnête est « hors de portée ».
    """
    etats = []
    for titre, dossier in jeux:
        fichier = licence_du_dump(dossier)
        if fichier is None:
            continue
        try:
            attendue = chemin_relatif(lecture.octets(fichier))
        except (LicenceError, OSError) as exc:
            # OSError AUSSI, et pas seulement LicenceError. `lecture.octets`
            # lève quand le partage rend moins d'octets que le fichier n'en
            # déclare, et Windows lève là où Linux se tait (mesuré le
            # 2026-08-29 : [WinError 31] en descendant sous une ROM Game Boy).
            # Sans cette branche, le seul écran de ce paquet fait pour être lu
            # mourrait tout entier sur une licence illisible.
            etats.append(EtatLicence(jeu=titre, etat=ILLISIBLE,
                                     detail=str(exc)))
            continue
        if racine_vita is None:
            etats.append(EtatLicence(
                jeu=titre, etat=HORS_DE_PORTEE, attendue=attendue,
                detail="la console range son système de fichiers Vita dans le "
                       "profil Windows, que cet hôte n'atteint pas"))
            continue
        # `install.local_path` traduirait un chemin Windows ; celui-ci est
        # construit ici, et ses segments sont connus. Les rejoindre nous-mêmes
        # évite d'importer `install` pour trois noms.
        pose = racine_vita.joinpath(*attendue.split("\\"))
        etats.append(EtatLicence(
            jeu=titre, etat=POSEE if pose.is_file() else ABSENTE,
            attendue=attendue))
    return etats
