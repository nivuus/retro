"""Lire un fichier EN ENTIER, ou échouer — jamais rendre un fragment.

CE MODULE EXISTE À CAUSE D'UNE MESURE, et elle est du genre que ce dépôt
redoute le plus : une lecture qui rend ZÉRO OCTET sans lever la moindre
erreur.

Relevé sur la console le 2026-08-29, sur le partage SMB « G: » :

    dc_boot.bin              stat=2097152   read_bytes=0    os.read=0
    ps2-0230e-20080220.bin   stat=4194304   read_bytes=0    os.read=0
    neogeo.zip               stat=1859335   read_bytes=1859335
    sega_101.bin             stat=524288    read_bytes=524288

`stat()` donne la BONNE taille ; la lecture rend zéro. PowerShell et .NET
lisent les mêmes fichiers correctement, et une lecture PAR TRANCHES de 64 Kio
ou de 1 Mio les lit correctement aussi — c'est la requête NON BORNÉE que
`Path.read_bytes()` émet, dimensionnée sur st_size, qui revient vide au-delà
d'environ deux mébioctets.

CE QUE ÇA COÛTAIT, ET POURQUOI CE N'EST PAS UN DÉTAIL. `bios.check_bios`
hachait ce vide et concluait « corrompu » sur un fichier parfaitement valide :
le rapport accusait le propriétaire d'avoir déposé un mauvais BIOS, `retro
bios` le retéléchargeait à CHAQUE synchronisation, et aucun BIOS de deux
mébioctets ou plus ne pouvait être porté chez son émulateur — PCSX2 n'aurait
jamais reçu le sien. Un fichier juste, déclaré faux, réparé en boucle sans que
la boucle se voie.

LA RÈGLE : on lit par tranches, et on COMPTE. Un total qui ne correspond pas à
`stat()` est une erreur franche, pas un contenu.
"""
from __future__ import annotations

import hashlib
import pathlib

# 1 Mio : mesuré comme sûr sur le partage de la console, et assez grand pour
# qu'une image de BIOS de quatre mébioctets tienne en quatre passes. La
# valeur exacte n'est pas magique — 64 Kio marchait aussi — mais elle doit
# rester BORNÉE, et c'est tout l'objet de ce module.
TRANCHE = 1 << 20


class LectureCourte(OSError):
    """Le fichier a rendu moins d'octets qu'il n'en déclare.

    C'est une OSError parce que les appelants de ce paquet traitent déjà
    l'illisible comme un état — « présent et inutilisable » — et non comme un
    plantage. Ce qu'elle ajoute à `OSError`, c'est de NOMMER l'écart : sans
    elle, un fichier tronqué se confond avec un fichier au mauvais contenu, et
    les deux n'appellent pas le même geste.
    """


def octets(chemin: pathlib.Path) -> bytes:
    """Le contenu entier du fichier. Lève plutôt que de rendre un fragment."""
    attendu = chemin.stat().st_size
    morceaux = []
    lu = 0
    with chemin.open("rb") as fh:
        while True:
            bloc = fh.read(TRANCHE)
            if not bloc:
                break
            morceaux.append(bloc)
            lu += len(bloc)
    if lu != attendu:
        raise LectureCourte(
            f"{chemin} déclare {attendu} octets et n'en a rendu que {lu}. "
            "Mesuré sur un partage SMB : une lecture non bornée y revient "
            "VIDE au-delà de deux mébioctets, sans erreur. Le fichier n'est "
            "pas forcément mauvais — c'est la lecture qui a échoué."
        )
    return b"".join(morceaux)


def md5(chemin: pathlib.Path) -> str:
    """L'empreinte MD5, calculée en flux et sur un fichier ENTIER.

    En flux, parce qu'un BIOS PS2 fait quatre mébioctets et qu'un PUP en fait
    deux cents : rien n'oblige à les tenir en mémoire pour les hacher.
    """
    attendu = chemin.stat().st_size
    h = hashlib.md5()
    lu = 0
    with chemin.open("rb") as fh:
        while True:
            bloc = fh.read(TRANCHE)
            if not bloc:
                break
            h.update(bloc)
            lu += len(bloc)
    if lu != attendu:
        raise LectureCourte(
            f"{chemin} déclare {attendu} octets et n'en a rendu que {lu} : "
            "l'empreinte porterait sur autre chose que le fichier."
        )
    return h.hexdigest()
