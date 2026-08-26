"""Artwork de bibliothèque, depuis SteamGridDB.

L'accès réseau est INJECTÉ plutôt qu'appelé directement : c'est ce qui permet
aux tests de couvrir la logique — quels assets, quels noms, quoi ne pas
retélécharger — sans jamais toucher au réseau.

Aucune erreur ne remonte de ce module. L'artwork est un ornement : une panne
SteamGridDB ne doit pas faire échouer une synchronisation qui, par ailleurs,
fait très bien remonter les jeux.
"""
from __future__ import annotations

import pathlib

import requests

from retro.steam import appid as appid_mod

BASE = "https://www.steamgriddb.com/api/v2"

# Le type d'asset SteamGridDB pour chaque nom de fichier attendu par Steam.
ASSETS = (
    ("portrait", "grids", {"dimensions": "600x900"}),
    ("paysage", "grids", {"dimensions": "920x430"}),
    ("hero", "heroes", {}),
    ("logo", "logos", {}),
    ("icone", "icons", {}),
)


def _fetch_json(url: str, headers: dict) -> dict:
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def _fetch_bytes(url: str) -> bytes:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.content


class ArtworkClient:
    def __init__(self, api_key: str | None, fetch_json=_fetch_json, fetch_bytes=_fetch_bytes):
        self.api_key = api_key
        self._fetch_json = fetch_json
        self._fetch_bytes = fetch_bytes

    def fetch_for(self, title: str, legacy_appid: int, grid_dir: pathlib.Path) -> list[str]:
        if not self.api_key:
            return []  # dégradation gracieuse, pas une erreur
        prefixes = appid_mod.grid_prefixes(legacy_appid)
        # Chaque asset se décide INDIVIDUELLEMENT, via existing_asset qui
        # compare par stem (extension-agnostique). Un asset déjà présent ne
        # doit ni être écrasé ni empêcher la récupération des autres : sauter
        # globalement dès qu'un seul asset existe laisserait à jamais
        # incomplète toute bibliothèque dont une synchronisation s'est
        # interrompue en cours de boucle (panne réseau à mi-parcours, etc.).
        manquants = {k: pre for k, pre in prefixes.items()
                     if appid_mod.existing_asset(grid_dir, pre) is None}
        if not manquants:
            return []
        entetes = {"Authorization": f"Bearer {self.api_key}"}
        try:
            recherche = self._fetch_json(f"{BASE}/search/autocomplete/{title}", entetes)
            resultats = recherche.get("data") or []
            if not resultats:
                return []
            jeu_id = resultats[0]["id"]
            grid_dir.mkdir(parents=True, exist_ok=True)
            ecrits = []
            for cle, endpoint, params in ASSETS:
                if cle not in manquants:
                    continue
                suffixe = "".join(f"?{k}={v}" for k, v in params.items())
                reponse = self._fetch_json(f"{BASE}/{endpoint}/game/{jeu_id}{suffixe}", entetes)
                candidats = reponse.get("data") or []
                if not candidats:
                    continue
                url = candidats[0]["url"]
                # L'extension suit la source : Steam accepte .png, .jpg et .ico
                # indifféremment, et la conserver évite de retélécharger à chaque
                # passage un asset déjà présent sous un autre suffixe.
                ext = pathlib.PurePosixPath(url).suffix or ".png"
                nom = f"{manquants[cle]}{ext}"
                (grid_dir / nom).write_bytes(self._fetch_bytes(url))
                ecrits.append(nom)
            return ecrits
        except Exception:  # noqa: BLE001 - volontairement large, voir docstring
            return []


def prune_orphans(grid_dir: pathlib.Path, orphaned: list[int]) -> list[str]:
    """Supprime l'artwork des identifiants abandonnés.

    Renommer un jeu change son identifiant : sans cette purge, chaque
    renommage laisserait quatre fichiers que plus rien ne référence.
    """
    if not orphaned or not grid_dir.is_dir():
        return []
    # Comparaison sur le STEM entier, jamais sur un préfixe de chaîne :
    # l'appid 111 préfixe aussi 1112p.png, qui appartient à un autre jeu.
    condamnes = {pre for a in orphaned for pre in appid_mod.grid_prefixes(a).values()}
    supprimes = []
    for fichier in grid_dir.iterdir():
        if fichier.stem in condamnes:
            fichier.unlink()
            supprimes.append(fichier.name)
    return supprimes
