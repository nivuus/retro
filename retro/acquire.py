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
import os
import pathlib
import shutil
import subprocess
import tempfile
import zipfile

TEMOIN = ".retro-version"
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


def _basculer(source: pathlib.Path, cible: pathlib.Path) -> None:
    """Met l'arbre extrait en place, sans laisser le ménage décider du sort.

    `shutil.move` entre DEUX VOLUMES copie puis supprime la source, et une
    suppression qui échoue lève alors que la destination est déjà complète.
    C'est exactement le symptôme corrigé plus bas : installation entière,
    témoin jamais écrit. Et c'est le chemin réellement emprunté chez le
    propriétaire, dont le %TEMP% est sur C: et l'émulation sur D:.

    On copie donc explicitement, et la source reste au nettoyage tolérant du
    dossier temporaire — dont c'est le rôle, et qui n'emporte plus rien.
    """
    try:
        # Même volume : un renommage, atomique, sans rien à nettoyer ensuite.
        os.replace(source, cible)
        return
    except OSError:
        # Volumes différents (EXDEV) ou renommage refusé. Un renommage qui
        # échoue n'écrit rien à moitié ; la copie qui suit dira elle-même ce
        # qui ne va pas, en nommant le fichier fautif.
        pass
    shutil.copytree(source, cible, symlinks=True)


def acquire(emu, emulation_root: pathlib.Path, fetch=_fetch) -> str:
    """Installe l'émulateur s'il manque ou si sa version a changé.

    Rend « installé », « à jour » ou « réinstallé ». Le témoin de version est
    ce qui rend l'opération idempotente : le provisionnement rejoue cette
    étape à chaque reconstruction, et retélécharger des gigaoctets déjà
    présents serait une panne à lui seul.
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
        raise AcquireError(
            f"{emu.name} {emu.version} : empreinte SHA256 non relevée dans le "
            "manifeste. Rien n'a été téléchargé — un binaire que rien ne "
            "vérifie ne s'installe pas. Relever l'empreinte revient à "
            "télécharger l'archive hors de la console et à passer son contenu "
            "à hashlib.sha256(), puis à l'inscrire au manifeste ; le "
            "commentaire de l'entrée dit ce qui manque pour cet émulateur-là."
        )
    cible = emulation_root / emu.install_dir
    temoin = cible / TEMOIN
    if temoin.exists() and temoin.read_text(encoding="utf-8").strip() == emu.version:
        return "à jour"
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

    # ignore_cleanup_errors : le nettoyage du temporaire ne doit JAMAIS
    # emporter une installation par ailleurs terminée. Mesuré en
    # production sous Windows : le secours binaire 7-Zip laisse un
    # descripteur ouvert sur l'archive, la suppression lève [WinError 32]
    # « used by another process » — et cette exception remontait APRÈS le
    # basculement, donc avant l'écriture du témoin. L'émulateur était
    # complet, jamais attesté, et le passage suivant retéléchargeait tout.
    # Ce qu'on abandonne en tolérant l'échec est un dossier de %TEMP% que
    # l'OS reprend ; ce qu'on garde est l'ordre ci-dessous, qui reste le
    # seul juge de la complétude.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        racine = pathlib.Path(tmp)
        archive = racine / f"{emu.key}.{emu.archive}"
        archive.write_bytes(blob)
        extrait = racine / "extrait"
        # Extraire à côté, puis basculer : une extraction qui échoue à
        # mi-chemin ne doit pas laisser une installation à moitié écrasée.
        safe_extract(archive, emu.archive, extrait)
        # Les supplémentaires se déversent dans le MÊME dossier : c'est ce qui
        # fait cohabiter l'émulateur et ses cores.
        for i, (b, kind) in enumerate(supplements):
            sup = racine / f"{emu.key}-part{i}.{kind}"
            sup.write_bytes(b)
            safe_extract(sup, kind, extrait)
        if cible.exists():
            shutil.rmtree(cible)
        cible.parent.mkdir(parents=True, exist_ok=True)
        _basculer(extrait, cible)

    temoin.write_text(emu.version + "\n", encoding="utf-8")
    return "réinstallé" if deja else "installé"
