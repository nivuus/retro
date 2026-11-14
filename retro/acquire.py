"""Télécharger, vérifier, extraire.

Deux risques distincts, et aucun ne se voit après coup :

1. Installer un binaire qui n'est pas celui qu'on croit. L'empreinte est donc
   vérifiée AVANT toute extraction, et un échec ne laisse rien derrière lui.
2. Laisser une archive écrire hors du dossier qu'on lui a désigné. Une archive
   venue d'Internet peut contenir « ../ » ou un chemin absolu ; l'extraire
   naïvement écrit n'importe où sur le disque, et le dossier de destination
   n'en garde aucune trace.

Un émulateur peut être livré en plusieurs archives qui se déversent dans le
même dossier. Toutes sont téléchargées et vérifiées avant que la moindre
écriture ne touche à l'installation existante : un émulateur amputé d'une de
ses parties est pire qu'un émulateur absent, parce qu'il paraît installé et ne
lance rien.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import zipfile

TEMOIN = ".retro-version"
# What the last changeover placed, kept next to the witness: the only record of
# which files in the install directory came from an archive.
MEMBRES = ".retro-files"
# The staging directory sits next to the install directory, on its volume.
STAGING_SUFFIX = ".retro-staging"
# Binaires 7-Zip acceptés, par ordre de préférence. 7zr est l'extracteur
# autonome officiel : ~600 Ko, redistribuable, et il lit tous les filtres.
_BINAIRES_7Z = ("7zz", "7z", "7za", "7zr", "7zr.exe", "7z.exe")


class AcquireError(RuntimeError):
    """L'émulateur n'a pas pu être installé, et rien n'a été laissé à moitié."""


def _fetch(url: str) -> bytes:
    import requests
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.content


def _membres_surs(noms, destination: pathlib.Path):
    """Refuse tout membre dont le chemin résolu sort de la destination."""
    racine = destination.resolve()
    for nom in noms:
        cible = (destination / nom).resolve()
        if cible != racine and racine not in cible.parents:
            raise AcquireError(
                f"l'archive contient un chemin qui sort de sa destination : "
                f"{nom!r} — extraction refusée"
            )


def _extraire_7z(archive: pathlib.Path, destination: pathlib.Path) -> None:
    """Extrait une archive 7z, avec py7zr d'abord et un binaire 7-Zip ensuite.

    py7zr ne sait PAS lire le filtre BCJ2 — il le marque « Unsupported » dans
    son propre code — et c'est précisément celui qu'utilisent les archives de
    RetroArch, mesuré le 2026-08-26 sur les archives réelles. Sans ce secours,
    l'émulateur qui couvre l'essentiel de la bibliothèque rétro ne s'installe
    pas du tout, et aucun test en .zip ne peut le voir.
    """
    erreur_py7zr = None
    try:
        import py7zr
        with py7zr.SevenZipFile(archive) as z:
            _membres_surs(z.getnames(), destination)
            z.extractall(destination)
        return
    except AcquireError:
        raise
    except Exception as exc:  # noqa: BLE001 - py7zr lève des types variés
        erreur_py7zr = exc

    binaire = next((b for b in _BINAIRES_7Z if shutil.which(b)), None)
    if binaire is None:
        raise AcquireError(
            f"{archive.name} : py7zr a échoué ({erreur_py7zr}) et aucun binaire "
            f"7-Zip n'est disponible. Installer l'un de {', '.join(_BINAIRES_7Z)} "
            "— 7zr suffit et se télécharge sur https://www.7-zip.org/a/7zr.exe"
        )
    # -bb0 : silencieux. -y : ne pose aucune question, il n'y a personne pour
    # y répondre. Le binaire garde l'extraction sous -o : mesuré le 2026-08-26
    # avec 7-Zip 25.01, un membre nommé « ../../evade.txt » atterrit DANS la
    # destination, pas au-dessus. Attention à la nuance : il assainit le chemin
    # là où py7zr, lui, fait rejeter l'archive par _membres_surs. Rien ne
    # s'échappe dans les deux cas, mais seul le premier chemin est bavard.
    r = subprocess.run(
        [binaire, "x", str(archive), f"-o{destination}", "-y", "-bb0"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        raise AcquireError(
            f"{archive.name} : py7zr a échoué ({erreur_py7zr}) et {binaire} "
            f"aussi (code {r.returncode}) : {r.stderr.strip()[:400]}"
        )


def safe_extract(archive: pathlib.Path, kind: str,
                 destination: pathlib.Path) -> None:
    """Extrait une archive sans la laisser écrire hors de sa destination.

    `_membres_surs` ne regarde que les NOMS de membres. La protection contre un
    lien symbolique dont la cible sort de la destination repose, elle, sur les
    bibliothèques d'extraction : zipfile ne matérialise jamais de vrai lien, et
    py7zr refuse lui-même « Symlink point out of target directory ». C'est de la
    défense en profondeur réelle, mais elle est portée par du code que nous
    n'écrivons pas — d'où cette note, pour qu'un futur changement de
    bibliothèque ne rouvre pas le trou en silence. Le secours binaire de
    `_extraire_7z` s'appuie, lui, sur 7-Zip lui-même, qui maintient
    l'extraction sous son `-o` — vérifié, mais par du code qui n'est pas le
    nôtre non plus.

    Toute exception est enveloppée : sur une machine de provisionnement sans
    clavier ni écran, une trace Python brute remplace le message qui nommerait
    l'archive fautive.
    """
    if kind not in ("zip", "7z"):
        raise AcquireError(f"format d'archive inconnu : {kind!r}")
    destination.mkdir(parents=True, exist_ok=True)
    try:
        if kind == "zip":
            with zipfile.ZipFile(archive) as z:
                _membres_surs(z.namelist(), destination)
                z.extractall(destination)
        else:
            _extraire_7z(archive, destination)
    except AcquireError:
        raise
    except Exception as exc:  # noqa: BLE001 - volontairement large, voir docstring
        raise AcquireError(
            f"extraction de {archive.name} impossible : {type(exc).__name__}: {exc}"
        ) from exc


class Outcome(str):
    """What `acquire` did. It compares and prints as its state string.

    `replaced` and `removed` are the paths (relative to the install
    directory, "/"-separated) that the changeover overwrote or deleted: a state
    string alone cannot say which files an upgrade touched, and `install`
    must name exactly those, nothing more.
    """

    replaced: frozenset[str]
    removed: frozenset[str]

    def __new__(cls, state: str, replaced=(), removed=()):
        outcome = super().__new__(cls, state)
        outcome.replaced = frozenset(replaced)
        outcome.removed = frozenset(removed)
        return outcome


def path_key(rel: str) -> str:
    """The identity of a relative path on THIS filesystem.

    NTFS is case-insensitive: "Foo.dll" shipped by one version and "foo.dll"
    by the next are the same file, and comparing them as strings would take
    the shipped file for the owner's and keep the old one forever.
    """
    return os.path.normcase(rel)


def _staged(staging: pathlib.Path) -> tuple[list[str], list[str]]:
    """(files, directories) under `staging`, relative and "/"-separated."""
    files, directories = [], []
    for root, dirs, names in os.walk(staging):
        base = pathlib.Path(root)
        # os.walk lists a link to a directory among `dirs` without entering
        # it: as an archive member, it is a single entry, like a file.
        links = [d for d in dirs if (base / d).is_symlink()]
        for name in [*names, *links]:
            files.append((base / name).relative_to(staging).as_posix())
        for name in dirs:
            if name not in links:
                directories.append((base / name).relative_to(staging).as_posix())
    return sorted(files), sorted(directories)


def _read_members(target: pathlib.Path) -> list[str] | None:
    """The files the previous changeover placed, or None for an older install.

    Every install made before member lists existed has none: then nothing
    says which files the old archive shipped, and none may be deleted.
    """
    path = target / MEMBRES
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        files = data["files"]
    except (ValueError, KeyError, TypeError) as exc:
        raise AcquireError(
            f"{path} is unreadable ({exc}): without it, the files the "
            "previous version shipped cannot be told from the owner's. "
            "Nothing was changed."
        ) from exc
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise AcquireError(f"{path} does not hold a list of paths. Nothing "
                           "was changed.")
    return files


def _write_atomically(path: pathlib.Path, text: str) -> None:
    """Write `text` to `path` so that a reader sees the old or the new file."""
    partial = path.with_name(path.name + ".partial")
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)


def _write_members(target: pathlib.Path, files) -> None:
    _write_atomically(target / MEMBRES, json.dumps(
        {"schema": 1, "files": sorted(files)}, ensure_ascii=False, indent=0))


def _ensure_replaceable(paths) -> None:
    """Refuse the changeover while a file it must change is held open.

    Windows refuses to replace or delete a file another process has open,
    and the emulator itself is the usual culprit. Opening each such file for
    writing (without truncating it) meets the same refusal BEFORE the changeover
    starts, while the old install is still whole. It narrows the window, it
    does not close it: a process may open a file after this check, and the
    changeover is then interrupted and repaired by the next run.
    """
    for path in paths:
        try:
            with open(path, "r+b"):
                pass
        except OSError as exc:
            raise AcquireError(
                f"{path} cannot be replaced ({exc}) — is the emulator "
                "running? Nothing was changed; close it and run the install "
                "again."
            ) from exc


def _put_in_place(staging: pathlib.Path, target: pathlib.Path,
                  witness: pathlib.Path) -> tuple[list[str], list[str]]:
    """Put the staged tree in place over `target`, file by file.

    Replacing shipped files in place, rather than swapping whole
    directories, is what keeps the owner's data where it is: saves, memory
    cards and installed firmware can weigh tens of gigabytes, live inside
    the install directory, and are never moved, copied or opened here. Each
    file is renamed from a staging directory on the same volume, so each
    step is a single rename.

    Rules, against the member list the previous changeover recorded:
    - a file the new archive ships is placed when the path is free, or when
      the previous version shipped it (or, for an install older than member
      lists, always); a file there that the previous version did NOT ship is
      the owner's and stays;
    - a file the previous version shipped and the new one does not is
      removed; for an install older than member lists, nothing is removed.

    Order, which makes an interruption anywhere repairable by re-running:
    the witness goes first (the install is no longer attested), then the
    member list grows to cover every file this changeover may place, then the
    files move, then the final member list, and the witness is written last
    by the caller. A run cut short leaves a tree with no witness, which
    `install` reports as not attested, and the next run redoes the changeover
    from the recorded list without losing anything.

    Returns (replaced, removed).
    """
    shipped, shipped_dirs = _staged(staging)
    previous = _read_members(target)
    known = {path_key(f) for f in previous or ()}
    shipped_keys = {path_key(f) for f in shipped}
    obsolete = [f for f in previous or () if path_key(f) not in shipped_keys
                and (target / f).is_file()]
    obsolete_keys = {path_key(f) for f in obsolete}

    to_place, replaced, clashes = [], [], []
    for rel in shipped:
        dest = target / rel
        if dest.is_dir() and not dest.is_symlink():
            clashes.append(rel)
        elif os.path.lexists(dest):
            if previous is None or path_key(rel) in known:
                to_place.append(rel)
                replaced.append(rel)
        else:
            to_place.append(rel)
    must_be_dirs = set(shipped_dirs)
    for rel in to_place:
        must_be_dirs.update(p.as_posix()
                            for p in pathlib.PurePosixPath(rel).parents
                            if p.as_posix() != ".")
    clashes += [d for d in sorted(must_be_dirs)
                if os.path.lexists(target / d) and not (target / d).is_dir()
                and path_key(d) not in obsolete_keys]
    if clashes:
        raise AcquireError(
            f"the new version ships {', '.join(clashes[:5])} where "
            f"{target} holds something of another kind (a file where a "
            "directory goes, or the reverse) that the previous version did "
            "not ship. Nothing was changed; move it aside and run the "
            "install again."
        )
    _ensure_replaceable([target / f for f in [*replaced, *obsolete]])

    target.mkdir(parents=True, exist_ok=True)
    witness.unlink(missing_ok=True)
    _write_members(target, {*(previous or ()), *to_place})
    for rel in obsolete:
        (target / rel).unlink()
    for rel in sorted(must_be_dirs):
        (target / rel).mkdir(parents=True, exist_ok=True)
    for rel in to_place:
        os.replace(staging / rel, target / rel)
    _write_members(target, to_place)
    return replaced, obsolete


def acquire(emu, emulation_root: pathlib.Path, fetch=_fetch) -> Outcome:
    """Install the emulator when it is missing or its version changed.

    Returns an `Outcome` whose state says installed, up to date or
    reinstalled, carrying the paths the changeover replaced or removed. The
    version witness makes the step idempotent: provisioning replays it on
    every rebuild, and downloading gigabytes already present would be an
    outage by itself. An upgrade goes through `_put_in_place`, which keeps every
    file the previous archive did not ship.
    """
    # Une empreinte VIDE dit « pas encore relevée », et c'est une réponse :
    # elle vaut mieux qu'une empreinte inventée, qui passerait la revue et
    # casserait à l'installation, sur la console, sans rien expliquer. Le
    # refus vient donc avant le téléchargement — comparer l'archive à une
    # empreinte vide aurait fait télécharger cent mégaoctets pour rendre
    # « attendue :  », un message qui n'envoie nulle part.
    #
    # `install_all` capture cet échec comme les autres : les émulateurs
    # épinglés s'installent quand même.
    if not emu.sha256.strip():
        # La version est vide elle aussi quand l'empreinte l'est : les deux
        # décrivent la même archive et se relèvent ensemble. On ne laisse donc
        # pas un blanc traîner au milieu du message.
        raise AcquireError(
            f"{emu.name} {emu.version}".strip()
            + " : empreinte SHA256 non relevée dans le "
            "manifeste. Rien n'a été téléchargé — un binaire que rien ne "
            "vérifie ne s'installe pas. Relever l'empreinte revient à "
            "télécharger l'archive hors de la console et à passer son contenu "
            "à hashlib.sha256(), puis à l'inscrire au manifeste ; le "
            "commentaire de l'entrée dit ce qui manque pour cet émulateur-là."
        )
    cible = emulation_root / emu.install_dir
    temoin = cible / TEMOIN
    if temoin.exists() and temoin.read_text(encoding="utf-8").strip() == emu.version:
        return Outcome("à jour")
    deja = cible.exists()

    try:
        blob = fetch(emu.url)
    except Exception as exc:  # noqa: BLE001 - toute panne réseau, nommée
        raise AcquireError(f"{emu.name} : téléchargement impossible ({exc})") from exc

    empreinte = hashlib.sha256(blob).hexdigest()
    if empreinte != emu.sha256:
        raise AcquireError(
            f"{emu.name} {emu.version} : empreinte SHA256 inattendue.\n"
            f"  attendue : {emu.sha256}\n  obtenue  : {empreinte}\n"
            "Rien n'a été installé."
        )

    # Les archives supplémentaires sont téléchargées et vérifiées AVANT que
    # quoi que ce soit ne touche à l'installation existante : une seconde
    # archive dont l'empreinte est fausse ne doit pas laisser un émulateur
    # amputé. RetroArch en dépend — son archive principale ne contient aucun
    # core, et un émulateur sans core s'installe sans rien pouvoir lancer.
    # Un émulateur amputé est pire qu'un émulateur absent : il paraît installé.
    supplements = []
    for i, part in enumerate(emu.parts):
        try:
            b = fetch(part.url)
        except Exception as exc:  # noqa: BLE001 - toute panne réseau, nommée
            raise AcquireError(
                f"{emu.name} : téléchargement de l'archive supplémentaire "
                f"{i + 1} impossible ({exc})"
            ) from exc
        h = hashlib.sha256(b).hexdigest()
        if h != part.sha256:
            raise AcquireError(
                f"{emu.name} {emu.version}, archive supplémentaire {i + 1} : "
                f"empreinte SHA256 inattendue.\n  attendue : {part.sha256}\n"
                f"  obtenue  : {h}\nRien n'a été installé."
            )
        supplements.append((b, part.archive))

    # The archives stay in the system temp directory, whose clean-up is
    # tolerant (ignore_cleanup_errors): measured in production on Windows,
    # the 7-Zip fallback keeps a handle open on the archive, and a failed
    # clean-up must never cost an install its witness. The extracted tree,
    # on the other hand, is staged NEXT TO the target, on its volume: from
    # the system temp directory every file would have to be copied across
    # volumes instead of renamed.
    staging = cible.parent / f".{cible.name}{STAGING_SUFFIX}"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        racine = pathlib.Path(tmp)
        archive = racine / f"{emu.key}.{emu.archive}"
        archive.write_bytes(blob)
        # A staging directory left by an interrupted run holds only what
        # that run extracted: it is ours, and it is stale.
        if staging.exists():
            shutil.rmtree(staging)
        safe_extract(archive, emu.archive, staging)
        # Les supplémentaires se déversent dans le MÊME dossier : c'est ce qui
        # fait cohabiter l'émulateur et ses cores.
        for i, (b, kind) in enumerate(supplements):
            sup = racine / f"{emu.key}-part{i}.{kind}"
            sup.write_bytes(b)
            safe_extract(sup, kind, staging)
        try:
            replaced, removed = _put_in_place(staging, cible, temoin)
            # What is left are directories and the new version's copies of
            # files kept as the owner's. Removed BEFORE the witness: an
            # attested install leaves nothing behind it.
            shutil.rmtree(staging)
            _write_atomically(temoin, emu.version + "\n")
        except OSError as exc:
            if temoin.exists():
                left = "The previous install is unchanged."
            else:
                left = ("The install is not attested (no witness) and may be "
                        "incomplete; no file the previous version did not "
                        "ship was touched. Run the install again to finish it.")
            raise AcquireError(
                f"{emu.name} : the changeover to version {emu.version} in {cible} "
                f"failed ({exc}). {left}"
            ) from exc

    return Outcome("réinstallé" if deja else "installé", replaced, removed)
