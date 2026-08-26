"""Ce que Steam sait afficher d'un jeu non-Steam : des tags, et rien d'autre.

`shortcuts.vdf` n'a aucun champ de description, de date de sortie ou
d'éditeur — c'est une limite du format, pas un oubli. Toute la richesse passe
donc par les tags, qui deviennent des catégories filtrables à la manette dans
Big Picture.

Aucune erreur ne remonte de ce module. Les métadonnées sont un ornement : une
panne de l'API ne doit jamais empêcher un jeu de remonter dans Steam.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib

BASE = "https://api.screenscraper.fr/api2/jeuInfos.php"
DIMENSIONS = ("decennie", "genre", "joueurs")


@dataclasses.dataclass(frozen=True)
class Metadata:
    title: str = ""
    year: str = ""
    genre: str = ""
    players: str = ""
    publisher: str = ""
    synopsis: str = ""


def _premier(liste, *cles):
    """Le premier texte d'une liste de traductions, quelle que soit la forme.

    L'API rend des fiches très inégales : listes vides, champs absents,
    langues variables. L'absence d'un champ ne doit pas faire perdre les
    autres.
    """
    if not isinstance(liste, list):
        liste = [liste] if liste else []
    for element in liste:
        if isinstance(element, dict):
            for cle in cles:
                if element.get(cle):
                    return str(element[cle])
    return ""


def _lire(jeu: dict) -> Metadata:
    genres = jeu.get("genres") or []
    genre = ""
    if genres and isinstance(genres[0], dict):
        genre = _premier(genres[0].get("noms"), "text")
    date = _premier(jeu.get("dates"), "text")
    return Metadata(
        title=_premier(jeu.get("noms"), "text"),
        year=date[:4] if date[:4].isdigit() else "",
        genre=genre,
        players=str((jeu.get("joueurs") or {}).get("text", "")),
        publisher=str((jeu.get("editeur") or {}).get("text", "")),
        synopsis=_premier(jeu.get("synopsis"), "text"),
    )


def _fetch_json(url: str, params: dict) -> dict:
    import requests
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


class MetadataClient:
    """Passerelle vers ScreenScraper, avec cache disque et clé optionnelle.

    L'accès réseau est INJECTÉ plutôt qu'appelé directement, comme dans
    `retro/steam/artwork.py` : c'est ce qui permet aux tests de couvrir le
    cache, la dégradation gracieuse et l'extraction sans jamais toucher au
    réseau.
    """

    def __init__(self, api_key: str | None, cache_dir: pathlib.Path,
                 fetch_json=_fetch_json):
        self.api_key = api_key
        self.cache_dir = cache_dir
        self._fetch_json = fetch_json

    def _chemin_cache(self, rom_filename: str, system_id: str) -> pathlib.Path:
        cle = hashlib.sha256(f"{system_id}/{rom_filename}".encode()).hexdigest()[:32]
        return self.cache_dir / f"{cle}.json"

    def metadata_for(self, rom_filename: str, system_id: str) -> Metadata:
        if not self.api_key:
            return Metadata()  # dégradation gracieuse, pas une erreur
        cache = self._chemin_cache(rom_filename, system_id)
        if cache.is_file():
            try:
                return Metadata(**json.loads(cache.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001 - un cache illisible se refait
                pass
        try:
            brut = self._fetch_json(BASE, {
                "devid": "", "softname": "retro", "output": "json",
                "ssid": "", "sspassword": "", "romnom": rom_filename,
                "systemeid": system_id, "devpassword": self.api_key,
            })
            jeu = (brut.get("response") or {}).get("jeu")
            if not jeu:
                return Metadata()
            meta = _lire(jeu)
        except Exception:  # noqa: BLE001 - volontairement large, voir docstring
            return Metadata()
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # La clé d'API ne fait PAS partie de ce qu'on écrit : le cache vit
            # sur le volume de jeux, que d'autres outils lisent.
            cache.write_text(json.dumps(dataclasses.asdict(meta),
                                        ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001 - un cache non écrit n'est pas fatal
            pass
        return meta

    def tags_for(self, rom_filename: str, system_id: str,
                 dimensions=DIMENSIONS) -> tuple[str, ...]:
        m = self.metadata_for(rom_filename, system_id)
        tags = []
        if "decennie" in dimensions and m.year:
            tags.append(f"{m.year[:3]}0s")
        if "genre" in dimensions and m.genre:
            tags.append(m.genre)
        if "joueurs" in dimensions and m.players:
            tags.append(f"{m.players} joueur" + ("s" if m.players != "1" else ""))
        return tuple(tags)


def _systeme_de(entry_obj) -> str:
    """L'identifiant de système que l'API attend, dérivé du chemin de la ROM.

    Le dossier porte l'identifiant du profil (« snes », « psx »), qui est
    exactement ce que le scan a utilisé pour ranger la ROM.
    """
    morceaux = entry_obj.rom_path.split("\\")
    return morceaux[-2] if len(morceaux) >= 2 else ""


def enrich(entries: list, client: MetadataClient,
           dimensions=("decennie", "genre")) -> list:
    """Rend un inventaire dont les extra_tags sont remplis.

    Les entrées sont RECONSTRUITES, jamais modifiées : RomEntry est gelée, et
    un inventaire à moitié enrichi serait plus difficile à diagnostiquer qu'un
    inventaire non enrichi.
    """
    sortie = []
    for e in entries:
        nom = e.rom_path.rsplit("\\", 1)[-1]
        tags = client.tags_for(nom, _systeme_de(e), dimensions=dimensions)
        sortie.append(dataclasses.replace(e, extra_tags=tuple(tags)))
    return sortie
