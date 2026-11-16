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
    """A record field as text.

    RDB text is msgpack `str`, i.e. UTF-8, and `retro.rdb` already decodes it.
    A field written as msgpack `bin` (the converter does so for `serial`, and
    a name can be stored the same way) declares no encoding of its own;
    RetroArch handles every name as UTF-8, so bytes are read as UTF-8 too.
    ASCII-only values such as serials and hex digests are unaffected, and a
    non-English title keeps its script instead of turning into `?` runs.
    """
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v or "")


def empreinte_fiche(v) -> str:
    """Le md5 d'une fiche, quelle que soit sa forme.

    MESURÉ, et c'est un piège : les bases ne s'accordent pas entre elles.
    « FBNeo - Arcade Games » stocke une CHAÎNE hexadécimale ; « Sega - Saturn »,
    « Nintendo - Nintendo DS » et « Atari - 2600 » stockent les SEIZE OCTETS
    BRUTS. Les lire toutes comme du texte donnait du charabia — donc aucune
    correspondance, et l'échec était muet.
    """
    if isinstance(v, bytes):
        return v.hex() if len(v) == 16 else _texte(v).lower()
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
    """Le TITLE_ID, lu dans sce_sys/param.sfo.

    Une application Vita INSTALLÉE est un dossier — c'est la seule forme que
    la bibliothèque porte depuis le 2026-08-30 — et son param.sfo s'y lit
    directement. Un .vpk, lui, est une archive zip qu'il faut ouvrir. Les deux
    cas sont traités : un dossier dont on ne lirait pas le param.sfo
    retomberait sur son nom, qui est justement ce qu'on cherche à dépasser.
    """
    if chemin.is_dir():
        sfo = chemin / "sce_sys" / "param.sfo"
        try:
            m = _SERIE_VITA.search(lecture.octets(sfo)) if sfo.is_file() else None
        except OSError:
            return ""
        return f"{m.group(1).decode()}-{m.group(2).decode()}" if m else ""
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


class _Index:
    """The records of one database, keyed once for every lookup.

    Built in one pass over the records. Each lookup keeps the FIRST record in
    file order that matches, which is what the linear scans it replaces did.
    """

    def __init__(self, fiches: list[dict]):
        self._noms: dict[str, int] = {}
        self._tiges: dict[str, int] = {}
        self._md5: dict[str, int] = {}
        self._series: dict[str, int] = {}
        self._fiches = fiches
        self._courtes: list[tuple[str, int]] = []
        for i, e in enumerate(fiches):
            rn = _texte(e.get("rom_name", "")).lower()
            self._noms.setdefault(rn, i)
            self._tiges.setdefault(rn.rsplit(".", 1)[0], i)
            self._tiges.setdefault(tige_de_fiche(e.get("rom_name")), i)
            h = empreinte_fiche(e.get("md5"))
            if h:
                self._md5.setdefault(h, i)
            s = normaliser_serie(e.get("serial"))
            if s:
                self._series.setdefault(s, i)
                if len(s) >= 4:
                    self._courtes.append((s, i))

    def par_nom(self, nom: str, tige: str) -> dict | None:
        """The first record whose file name, or file stem, is this one."""
        trouves = [i for i in (self._noms.get(nom), self._tiges.get(tige))
                   if i is not None]
        return self._fiches[min(trouves)] if trouves else None

    def par_md5(self, empreinte: str) -> dict | None:
        i = self._md5.get(empreinte)
        return None if i is None else self._fiches[i]

    def par_serie(self, serie: str) -> dict | None:
        i = self._series.get(serie)
        return None if i is None else self._fiches[i]

    def series_suffixes(self, serie: str) -> list[dict]:
        """The records whose serial is a suffix of `serie`."""
        return [self._fiches[i] for s, i in self._courtes if serie.endswith(s)]


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
        # One index per database, built on first use: resolving a library is
        # then O(games), not O(games x records).
        self._index: dict[str, _Index] = {}
        # md5 of files already hashed, keyed by what makes the content change
        # (path, size, mtime): a file is read once per run, however many times
        # it is asked about.
        self._empreintes: dict[tuple, str] = {}
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

    def _indexer(self, sid: str, fiches: list[dict]) -> "_Index":
        if sid not in self._index:
            self._index[sid] = _Index(fiches)
        return self._index[sid]

    def _md5(self, chemin: pathlib.Path) -> str:
        """The md5 of a file, streamed, and remembered for this run."""
        st = chemin.stat()
        cle = (str(chemin), st.st_size, st.st_mtime_ns)
        if cle not in self._empreintes:
            self._empreintes[cle] = lecture.md5(chemin)
        return self._empreintes[cle]

    def resoudre(self, chemin: pathlib.Path, sid: str) -> Titre | None:
        fiches = self._base(sid)
        if not fiches:
            return None
        index = self._indexer(sid, fiches)
        e = index.par_nom(chemin.name.lower(), chemin.stem.lower())
        if e is not None:
            return Titre(_texte(e["name"]), "nom de fichier")
        try:
            if chemin.is_file() and chemin.stat().st_size <= TAILLE_MAX_EMPREINTE:
                e = index.par_md5(self._md5(chemin))
                if e is not None:
                    return Titre(_texte(e["name"]), "empreinte md5")
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
        index = self._indexer(sid, fiches)
        e = index.par_serie(serie)
        if e is not None:
            return Titre(_texte(e["name"]), f"série {serie}")
        # LES BASES SEGA OMETTENT LE PRÉFIXE DE L'ÉDITEUR. Mesuré : le disque
        # de Sega Rally 2 (USA) porte « MK51019 » là où la base dit « 51019 »,
        # et Saturn Bomberman « MK81070 » pour « 81070 ». On accepte donc
        # qu'une série de la base soit un SUFFIXE de celle du disque — mais
        # UNIQUEMENT si elle ne désigne qu'une fiche. Renommer un jeu d'après
        # une ambiguïté serait pire que ne pas le renommer.
        courtes = index.series_suffixes(serie)
        if len(courtes) == 1:
            return Titre(_texte(courtes[0]["name"]), f"série {serie} (suffixe)")
        return None
