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
import urllib.parse

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


# Les seules extensions que Steam lit, et donc les seules qu'on accepte d'une
# URL. Tout le reste devient .png : mieux vaut une extension à peu près juste
# qu'un nom de fichier que le système refuse d'écrire.
_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".ico", ".webp"})


def _extension(url: str) -> str:
    """L'extension du fichier désigné par une URL, sans ce qui la suit.

    `PurePosixPath(url).suffix` sur « .../abc.png?t=1 » rend « .png?t=1 » : la
    query devient partie de l'extension. Le nom construit portait alors un
    « ? », que Windows REFUSE dans un nom de fichier — OSError, avalée par le
    filet de fetch_for, et le rapport annonçait « 0 récupéré » sans rien de
    plus. Sept jeux passaient, un échouait à chaque synchronisation, et rien
    ne distinguait ce cas d'une bibliothèque déjà complète.

    Invisible sous Linux, où « ? » est un nom de fichier parfaitement légal :
    seule la machine cible pouvait le montrer.
    """
    chemin = urllib.parse.urlsplit(url).path
    ext = pathlib.PurePosixPath(chemin).suffix.lower()
    return ext if ext in _EXTENSIONS else ".png"


class ArtworkClient:
    def __init__(self, api_key: str | None, fetch_json=_fetch_json, fetch_bytes=_fetch_bytes):
        self.api_key = api_key
        self._fetch_json = fetch_json
        self._fetch_bytes = fetch_bytes
        # Les échecs rencontrés, pour que le rapport puisse en NOMMER un.
        # Avaler l'exception reste juste — l'artwork est un ornement — mais
        # « 0 récupéré » disait la même chose pour une bibliothèque complète,
        # une clé expirée et un nom de fichier que Windows refuse d'écrire.
        # Le compteur de manquants disait COMBIEN, jamais POURQUOI, et le
        # troisième cas a demandé de rejouer la séquence à la main sur la
        # machine cible pour être seulement vu.
        self.erreurs: list[str] = []

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
                nom = f"{manquants[cle]}{_extension(url)}"
                (grid_dir / nom).write_bytes(self._fetch_bytes(url))
                ecrits.append(nom)
            return ecrits
        except Exception as exc:  # noqa: BLE001 - volontairement large, voir docstring
            self.erreurs.append(f"{title} : {type(exc).__name__} : {exc}")
            return []


def missing_assets(grid_dir: pathlib.Path, legacy_appid: int) -> list[str]:
    """Les préfixes des assets encore absents après un passage.

    fetch_for avale toute exception — l'artwork est un ornement, pas une raison
    de faire échouer une synchronisation. Mais « 0 récupéré » disait alors la
    même chose pour une bibliothèque déjà complète et pour une clé d'API
    expirée, et ce second cas ne se répare jamais tout seul. Ce compteur est ce
    qui les distingue dans le rapport.
    """
    return [pre for pre in appid_mod.grid_prefixes(legacy_appid).values()
            if appid_mod.existing_asset(grid_dir, pre) is None]


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
            try:
                fichier.unlink()
            except OSError:
                # Une vignette que le système refuse de supprimer — le client
                # Steam la tient ouverte, et Windows lève alors [WinError 32] —
                # ne doit pas faire échouer la synchronisation. L'appelant
                # écrit les raccourcis APRÈS cette purge : une exception ici
                # emporterait une bibliothèque qui, par ailleurs, remonte très
                # bien, pour un ornement orphelin. Non compté : rien n'a été
                # supprimé, et le passage suivant réessaiera.
                continue
            supprimes.append(fichier.name)
    return supprimes
