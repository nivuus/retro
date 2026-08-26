"""Comptes Steam locaux.

Chaque compte connecté a son propre shortcuts.vdf et son propre dossier
d'artwork. On les synchronise tous : deviner lequel est « le bon » serait un
pari, et se tromper laisserait une bibliothèque muette sans rien signaler.
"""
from __future__ import annotations

import dataclasses
import pathlib


class NoSteamAccountError(RuntimeError):
    """Aucun compte Steam local : personne ne s'est jamais connecté."""


@dataclasses.dataclass(frozen=True)
class SteamAccount:
    account_id: str
    config_dir: pathlib.Path
    shortcuts_path: pathlib.Path
    grid_dir: pathlib.Path


def discover_accounts(steam_root: pathlib.Path) -> list[SteamAccount]:
    """Liste tous les comptes Steam locaux sous ``steam_root/userdata``.

    Zéro compte et plusieurs comptes sont deux situations réelles :
    - zéro compte lève une erreur explicite, avec l'action à faire ;
    - plusieurs comptes sont tous rendus, sans deviner lequel est « le bon ».
    """
    userdata = steam_root / "userdata"
    comptes = []
    if userdata.is_dir():
        for entree in sorted(userdata.iterdir()):
            # "0" est la session anonyme de Steam, pas un compte réel.
            if not entree.is_dir() or not entree.name.isdigit() or entree.name == "0":
                continue
            config = entree / "config"
            if config.is_dir():
                comptes.append(
                    SteamAccount(
                        account_id=entree.name,
                        config_dir=config,
                        shortcuts_path=config / "shortcuts.vdf",
                        grid_dir=config / "grid",
                    )
                )
    if not comptes:
        raise NoSteamAccountError(
            f"aucun compte Steam local trouvé sous {userdata} : ouvrir Steam et "
            "se connecter à un compte au moins une fois avant de synchroniser "
            "la bibliothèque"
        )
    return comptes
