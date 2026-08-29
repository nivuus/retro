"""Le VRAI titre d'un jeu, quand son nom de fichier n'en est pas un.

« mslug2 » est un nom de romset, pas un nom de jeu : dans Steam il ne dit rien
au propriétaire, et envoyé à SteamGridDB il ne trouve AUCUNE jaquette. C'est
le défaut que ce module ferme.

TROIS CLÉS, ESSAYÉES DANS CET ORDRE, ET AUCUNE N'EST FLOUE :

  1. LE NOM DU FICHIER, comparé à celui que la base porte. Pour un jeu
     d'arcade c'est l'identité même — « mslug2.zip » EST Metal Slug 2.
  2. L'EMPREINTE MD5 du fichier. C'est la clé la plus forte : elle ne dépend
     d'aucun nom. Réservée aux fichiers assez petits pour se hacher — une
     cartouche, jamais un disque de sept gigaoctets.
  3. LE NUMÉRO DE SÉRIE gravé DANS l'image, pour les disques. C'est ce qui
     rattrape « Crash Team Racing-PSX-PAL.cue », qu'aucun nom ne reconnaît :
     ses octets disent SCES-02105, et la base répond « CTR - Crash Team
     Racing (Europe) ». Mesuré le 2026-08-29.

CE QUE CE MODULE NE FAIT PAS : deviner. Aucune comparaison approximative,
aucun score de similarité, aucun « le plus proche ». Un jeu qu'on ne
reconnaît pas GARDE SON NOM DE FICHIER, et le rapport le nomme — un titre
faux se lit exactement comme un titre juste, et personne ne le vérifierait.
"""
from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import re
import tomllib
import zipfile

from retro import lecture

TABLE = pathlib.Path(__file__).parent / "data" / "databases.toml"
SCHEMA = 1

# Au-delà, on ne hache pas : un disque ne se reconnaît pas à son empreinte de
# toute façon (une image reconstruite ou dégonflée n'a plus les mêmes octets),
# et lire sept gigaoctets par jeu ferait durer la synchronisation des minutes.
TAILLE_MAX_EMPREINTE = 96 * 1024 * 1024

# Le vocabulaire FERMÉ des extracteurs de série. Une valeur hors de cette
# liste dans databases.toml serait ignorée en silence, et le jeu resterait
# sous son nom de fichier sans que rien ne l'explique : le chargement refuse.
SERIES = ("disque-nintendo", "playstation", "psp", "ps3", "vita",
          "saturn", "dreamcast")


class TitreError(RuntimeError):
    """La table des bases est illisible ou incohérente."""


@dataclasses.dataclass(frozen=True)
class Titre:
    """Un titre reconnu, ET PAR QUOI. La provenance n'est pas un ornement :
    c'est ce qui permet de dire, en revue, pourquoi tel jeu a été renommé."""
    nom: str
    source: str


def _texte(v) -> str:
    return v.decode("ascii", "replace") if isinstance(v, bytes) else str(v or "")


def empreinte_fiche(v) -> str:
    """Le md5 d'une fiche, quelle que soit sa forme.

    MESURÉ, et c'est un piège : les bases ne s'accordent pas entre elles.
    « FBNeo - Arcade Games » stocke une CHAÎNE hexadécimale ; « Sega - Saturn »,
    « Nintendo - Nintendo DS » et « Atari - 2600 » stockent les SEIZE OCTETS
    BRUTS. Les lire toutes comme du texte donnait du charabia — donc aucune
    correspondance, et l'échec était muet.
    """
    if isinstance(v, bytes):
        return v.hex() if len(v) == 16 else v.decode("ascii", "replace").lower()
    return str(v or "").lower()


_PISTE = re.compile(r"\s*\((?:Track|Disc|Disk)\s*\d+\)\s*$", re.I)


def tige_de_fiche(rom_name) -> str:
    """La tige d'un `rom_name` de base, marqueur de piste retiré.

    Un jeu sur disque y est indexé par sa PISTE 1 (« Saturn Bomberman (USA)
    (1S) (Track 01).bin ») alors que le scan voit le .cue qui les rassemble.
    Sans ce retrait, aucun jeu multipiste ne se reconnaît par son nom.
    """
    return _PISTE.sub("", _texte(rom_name).rsplit(".", 1)[0]).strip().lower()


def normaliser_serie(v) -> str:
    """La forme sous laquelle deux numéros de série se comparent : sans
    ponctuation ni casse. « SLES_527.25 » et « SLES-52725 » sont le même."""
    return re.sub(r"[^A-Z0-9]", "", _texte(v).upper())


# --- Lire la série DANS l'image -------------------------------------------

def _serie_disque_nintendo(chemin: pathlib.Path) -> str:
    """GameCube et Wii : l'identifiant de disque tient dans les SIX PREMIERS
    octets du fichier. Il survit au dégonflage NKit, qui préserve l'en-tête —
    mesuré sur les deux images de cette console."""
    with chemin.open("rb") as f:
        return f.read(6).decode("ascii", "replace")


_SERIE_PLAYSTATION = re.compile(rb"cdrom:?\\?([A-Z]{4})[_\-]?(\d{3})\.?(\d{2})", re.I)


def _serie_playstation(chemin: pathlib.Path) -> str:
    """PlayStation et PlayStation 2 : le SYSTEM.CNF du disque porte
    « BOOT = cdrom0:\\SLES_527.25;1 ». Sur un .cue, c'est la piste qui
    contient les données qu'il faut ouvrir, pas le .cue."""
    for c in _pistes(chemin)[:1]:
        m = _SERIE_PLAYSTATION.search(_tete(c, 80))
        if m:
            return (f"{m.group(1).decode()}-{m.group(2).decode()}"
                    f"{m.group(3).decode()}")
    return ""


_SERIE_PSP = re.compile(rb"(U[LC][JUEAKT][SM]|NP[JUE][HGXZ])-?(\d{5})")


def _serie_psp(chemin: pathlib.Path) -> str:
    m = _SERIE_PSP.search(_tete(chemin, 4))
    return f"{m.group(1).decode()}-{m.group(2).decode()}" if m else ""


_SERIE_PS3 = re.compile(rb"(B[CL][EJUAKH]S|NP[EUJ][ABGHXZ])(\d{5})")


def _serie_ps3(chemin: pathlib.Path) -> str:
    m = _SERIE_PS3.search(_tete(chemin, 64))
    return f"{m.group(1).decode()}{m.group(2).decode()}" if m else ""


_SERIE_VITA = re.compile(rb"(PC[SA][ABCDEFGH])(\d{5})")


def _serie_vita(chemin: pathlib.Path) -> str:
    """Un .vpk est une archive zip ; sce_sys/param.sfo y porte le TITLE_ID."""
    try:
        with zipfile.ZipFile(chemin) as z:
            for nom in z.namelist():
                if nom.lower().endswith("param.sfo"):
                    m = _SERIE_VITA.search(z.read(nom))
                    if m:
                        return f"{m.group(1).decode()}-{m.group(2).decode()}"
    except (OSError, zipfile.BadZipFile):
        return ""
    return ""


def _serie_saturn(chemin: pathlib.Path) -> str:
    for c in _pistes(chemin)[:1]:
        t = _tete(c, 1)
        i = t.find(b"SEGA SEGASATURN")
        if i >= 0:
            return t[i + 0x20:i + 0x2a].decode("ascii", "replace").strip()
    return ""


def _serie_dreamcast(chemin: pathlib.Path) -> str:
    """L'en-tête IP.BIN, « SEGA SEGAKATANA », porte le numéro de produit à
    l'offset 0x40. Il vit dans la piste de DONNÉES, la plus grosse du .gdi."""
    for c in _pistes(chemin)[:3]:
        t = _tete(c, 1)
        i = t.find(b"SEGA SEGAKATANA")
        if i >= 0:
            return t[i + 0x40:i + 0x4a].decode("ascii", "replace").strip()
    return ""


EXTRACTEURS = {
    "disque-nintendo": _serie_disque_nintendo,
    "playstation": _serie_playstation,
    "psp": _serie_psp,
    "ps3": _serie_ps3,
    "vita": _serie_vita,
    "saturn": _serie_saturn,
    "dreamcast": _serie_dreamcast,
}


def _pistes(chemin: pathlib.Path) -> list[pathlib.Path]:
    """Les fichiers où chercher, la plus grosse piste d'abord.

    Un .cue ou un .gdi ne CONTIENT rien : il décrit des pistes voisines. Le
    lire lui-même ne trouverait jamais de série.
    """
    if chemin.suffix.lower() in (".cue", ".gdi", ".ccd", ".toc", ".m3u"):
        voisins = [p for p in chemin.parent.iterdir()
                   if p.is_file() and p.suffix.lower() in (".bin", ".img", ".iso")]
        return sorted(voisins, key=lambda p: p.stat().st_size, reverse=True)
    return [chemin]


def _tete(chemin: pathlib.Path, mo: int) -> bytes:
    """Les premiers mébioctets d'un fichier. BORNÉ, et lu par tranches : une
    lecture non bornée revient VIDE au-delà de deux mébioctets sur le partage
    de cette console (voir retro/lecture.py)."""
    reste = mo * 1024 * 1024
    morceaux = []
    with chemin.open("rb") as f:
        while reste > 0:
            bloc = f.read(min(lecture.TRANCHE, reste))
            if not bloc:
                break
            morceaux.append(bloc)
            reste -= len(bloc)
    return b"".join(morceaux)


# --- La table, et la résolution -------------------------------------------

def charger_table(chemin: pathlib.Path = TABLE) -> dict[str, dict]:
    """Quelle base décrit quel système. Refuse ce qu'elle ne sait pas servir."""
    try:
        data = tomllib.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise TitreError(f"{chemin} illisible : {exc}") from exc
    if data.get("schema") != SCHEMA:
        raise TitreError(
            f"{chemin} déclare schema = {data.get('schema')}, attendu {SCHEMA}")
    table = {}
    for sid, champs in (data.get("systeme") or {}).items():
        base = champs.get("base")
        if not isinstance(base, str) or not base.strip():
            raise TitreError(
                f"{chemin} [{sid}] : 'base' manquante ou vide. Sans nom de "
                "base, ce système ne serait jamais résolu et rien ne le dirait."
            )
        serie = champs.get("serie", "")
        if serie and serie not in SERIES:
            raise TitreError(
                f"{chemin} [{sid}] : serie = {serie!r}, attendu l'un de "
                f"{', '.join(SERIES)}. Une valeur inconnue serait ignorée en "
                "silence, et le jeu resterait sous son nom de fichier."
            )
        table[sid] = {"base": base.strip(), "serie": serie}
    return table


class Resolveur:
    """Résout les titres d'une bibliothèque, une base chargée au plus une fois.

    `dossier` est le `database\\rdb\\` de RetroArch. ABSENT, ce résolveur ne
    rend jamais rien et ne lève jamais : la console qui n'a pas RetroArch
    installé garde ses noms de fichiers, ce qui est le comportement d'avant.
    """

    def __init__(self, dossier: pathlib.Path | None,
                 table: dict[str, dict] | None = None):
        self.dossier = dossier
        self.table = table if table is not None else charger_table()
        self._bases: dict[str, list[dict]] = {}
        # Ce qui n'a pas pu être résolu, et pourquoi. Le rapport le nomme :
        # « 2 jeux gardent leur nom de fichier » sans dire lesquels laisserait
        # chercher.
        self.echecs: list[str] = []
        # Les jeux qu'aucune clé n'a reconnus. Ils gardent leur nom de
        # fichier, ce qui est le comportement d'avant et n'est pas une panne —
        # mais le rapport les nomme, parce qu'un titre resté brut est le seul
        # signe visible qu'une base manque ou qu'un dump est inconnu.
        self.non_reconnus: list[str] = []

    def _base(self, sid: str) -> list[dict]:
        if sid in self._bases:
            return self._bases[sid]
        fiches: list[dict] = []
        entree = self.table.get(sid)
        if entree and self.dossier:
            f = self.dossier / f"{entree['base']}.rdb"
            try:
                from retro import rdb as rdb_mod
                fiches = rdb_mod.lire(f)
            except Exception as exc:  # noqa: BLE001
                # Une base absente ou abîmée ne doit pas emporter le scan : le
                # pire qu'il puisse arriver est de garder les noms de fichiers.
                self.echecs.append(f"{entree['base']} : {type(exc).__name__}")
        self._bases[sid] = fiches
        return fiches

    def resoudre(self, chemin: pathlib.Path, sid: str) -> Titre | None:
        fiches = self._base(sid)
        if not fiches:
            return None
        nom, tige = chemin.name.lower(), chemin.stem.lower()
        for e in fiches:
            rn = _texte(e.get("rom_name", "")).lower()
            if rn == nom or rn.rsplit(".", 1)[0] == tige \
                    or tige_de_fiche(e.get("rom_name")) == tige:
                return Titre(e["name"], "nom de fichier")
        try:
            if chemin.is_file() and chemin.stat().st_size <= TAILLE_MAX_EMPREINTE:
                h = hashlib.md5(lecture.octets(chemin)).hexdigest()
                for e in fiches:
                    if empreinte_fiche(e.get("md5")) == h:
                        return Titre(e["name"], "empreinte md5")
        except OSError:
            pass
        return self._par_serie(chemin, sid, fiches)

    def _par_serie(self, chemin, sid, fiches) -> Titre | None:
        famille = (self.table.get(sid) or {}).get("serie")
        if not famille:
            return None
        try:
            serie = normaliser_serie(EXTRACTEURS[famille](chemin))
        except OSError:
            serie = ""
        if not serie:
            return None
        for e in fiches:
            if normaliser_serie(e.get("serial")) == serie:
                return Titre(e["name"], f"série {serie}")
        # LES BASES SEGA OMETTENT LE PRÉFIXE DE L'ÉDITEUR. Mesuré : le disque
        # de Sega Rally 2 (USA) porte « MK51019 » là où la base dit « 51019 »,
        # et Saturn Bomberman « MK81070 » pour « 81070 ». On accepte donc
        # qu'une série de la base soit un SUFFIXE de celle du disque — mais
        # UNIQUEMENT si elle ne désigne qu'une fiche. Renommer un jeu d'après
        # une ambiguïté serait pire que ne pas le renommer.
        courtes = [e for e in fiches
                   if len(normaliser_serie(e.get("serial"))) >= 4
                   and serie.endswith(normaliser_serie(e.get("serial")))]
        if len(courtes) == 1:
            return Titre(courtes[0]["name"], f"série {serie} (suffixe)")
        return None
