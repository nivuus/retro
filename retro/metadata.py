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
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations seulement : ce module ne dépend de rien de Steam
    from retro.steam.entry import RomEntry

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
        """Le fichier de cache d'une ROM. Ne lève pas, même sur un nom exotique.

        `surrogateescape` est le mode de décodage des noms de fichiers sous
        POSIX : un octet non décodable devient un demi-substitut (« \\udce9 »),
        et `str.encode()` refuse ces caractères. Un seul nom de ROM ainsi
        nommé aurait fait perdre le jeu.

        `surrogatepass` les encode plutôt que de lever, et reste INJECTIF :
        deux noms distincts gardent deux clés distinctes. Un repli qui
        remplacerait les substituts (errors="replace") ferait au contraire
        rendre la fiche du premier jeu pour le second.
        """
        empreinte = f"{system_id}/{rom_filename}".encode("utf-8", "surrogatepass")
        return self.cache_dir / f"{hashlib.sha256(empreinte).hexdigest()[:32]}.json"

    def metadata_for(self, rom_filename: str, system_id: str) -> Metadata:
        """Les métadonnées d'une ROM. AUCUNE erreur ne remonte, jamais.

        Le filet entoure TOUT le corps, et non les seuls appels qui ressemblent
        à un accès réseau ou disque : deux pannes bien réelles se cachaient
        ailleurs — `hashlib` sur un nom de ROM à demi-substitut, et
        `Path.is_file()` sur un dossier de cache illisible, qui avale ENOENT et
        ENOTDIR mais PAS EACCES. Les filets internes restent : ils distinguent
        « le cache est illisible, on refait » de « le réseau est en panne, on
        dégrade ». Celui-ci est le dernier rempart de la promesse du module.
        """
        if not self.api_key:
            return Metadata()  # dégradation gracieuse, pas une erreur
        try:
            return self._metadata_for(rom_filename, system_id)
        except Exception:  # noqa: BLE001 - voir la docstring du module
            return Metadata()

    def _metadata_for(self, rom_filename: str, system_id: str) -> Metadata:
        cache = self._chemin_cache(rom_filename, system_id)
        try:
            if cache.is_file():
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
    """Le nom du dossier de ROMs (« snes », « psx »). PAS ce que l'API attend.

    ATTENTION — dérivation connue comme fausse, laissée telle quelle :
    ScreenScraper attend un identifiant de système NUMÉRIQUE (« 4 » pour la
    SNES, « 57 » pour la PlayStation), pas le nom du profil. Le nom textuel ne
    rendra jamais rien.

    L'écart serait entièrement SILENCIEUX : un identifiant textuel produit soit
    une erreur HTTP, soit une réponse sans jeu — indiscernables, pour ce
    module, d'une clé d'API absente, d'un jeu introuvable ou d'une panne
    réseau, qui rendent tous Metadata() sans un mot. Le jour où quelqu'un
    câblera `enrich()`, cent pour cent des jeux recevraient zéro tag sans le
    moindre signal.

    Ce qu'il faut faire AVANT de câbler `enrich()` : porter l'identifiant
    numérique dans le PROFIL — un champ par système, à côté de `id`, `name` et
    `extensions` (par exemple `screenscraper_id = 4`) —, le faire transiter
    jusqu'ici, et supprimer cette dérivation. La table des identifiants
    appartient au profil, pas à ce module : c'est le profil qui décrit déjà ce
    qu'est un système. Tant que ce champ n'existe pas, `enrich()` reste non
    câblé — c'est le cas aujourd'hui, et c'est délibéré.
    """
    morceaux = entry_obj.rom_path.split("\\")
    return morceaux[-2] if len(morceaux) >= 2 else ""


def enrich(entries: list[RomEntry], client: MetadataClient,
           dimensions=("decennie", "genre")) -> list[RomEntry]:
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
