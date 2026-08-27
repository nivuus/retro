"""Du disque du propriétaire à l'inventaire.

Le scan tourne sur la machine qui possède les ROMs, mais décrit une machine
Windows : les chemins de l'inventaire sont ceux que verra Steam, pas ceux du
système de fichiers qui scanne.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
from collections.abc import Sequence

from retro import install as install_mod
from retro.steam import entry

# Les conventions No-Intro et Redump : « Titre (Région) (Langues) [flags] ».
# Tout ce qui suit le titre est entre parenthèses ou crochets.
_PARENTHESES = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
# ... à une exception près : le marqueur de disque. Deux disques du même jeu
# donneraient sinon le même titre, donc le même identifiant Steam, et une
# seule entrée survivrait aux deux.
_DISQUE = re.compile(r"\((Disc|Disk|CD)\s*[^\)]*\)", re.IGNORECASE)


class ScanError(RuntimeError):
    """La racine des ROMs est inaccessible."""


@dataclasses.dataclass(frozen=True)
class IgnoredSystem:
    """Un système laissé de côté par le scan, faute d'émulateur installé.

    C'est la moitié « et signalé » de l'exigence : ignorer en silence
    remplacerait une bibliothèque morte par une bibliothèque incomplète, tout
    aussi inexplicable pour le propriétaire. Chaque champ sert au message :
    ce qui manque (`system_name`), quoi installer (`profile`), où on a
    cherché (`install_dir`, `emulator`), pourquoi (`reason`, vocabulaire de
    `install.emulator_state`), et ce que ça coûte (`roms`).
    """
    folder: str
    system_name: str
    profile: str
    install_dir: pathlib.Path
    emulator: pathlib.Path
    roms: int
    reason: str


def base_title(filename: str) -> str:
    """Le titre SANS son marqueur de disque.

    C'est la clé de regroupement : les trois disques d'un même jeu et le .m3u
    qui les rassemble ont tous le même titre de base.
    """
    tige = pathlib.PurePosixPath(filename).stem
    return _PARENTHESES.sub("", tige).strip()


def clean_title(filename: str) -> str:
    """Le titre affiché dans Steam, marqueur de disque compris.

    Le marqueur est CONSERVÉ : deux disques du même jeu donneraient sinon le
    même titre, donc le même identifiant Steam, et une seule entrée survivrait
    aux deux.
    """
    tige = pathlib.PurePosixPath(filename).stem
    m = _DISQUE.search(tige)
    if not m:
        return base_title(filename)
    sans_disque = tige[: m.start()] + tige[m.end():]
    return f"{_PARENTHESES.sub('', sans_disque).strip()} {m.group(0)}".strip()


def discriminant(filename: str) -> str:
    """Le premier fragment parenthésé d'un nom de fichier — en pratique la
    région. Sert à départager deux fichiers dont le titre nettoyé serait le
    même, et seulement dans ce cas."""
    tige = pathlib.PurePosixPath(filename).stem
    m = _PARENTHESES.search(tige)
    return m.group(0).strip(" ()[]") if m else ""


def _desambiguiser(couples: list[tuple[str, str]]) -> list[str]:
    """Rend les titres, en n'ajoutant un discriminant qu'aux titres en collision.

    Sans cela, « Jeu (USA).sfc » et « Jeu (Europe).sfc » rendent tous deux
    « Jeu », donc le même identifiant Steam, et un seul des deux survit — un
    jeu qui disparaît de la bibliothèque sans que rien ne le signale. Mesuré le
    2026-08-26 : trois régions, une seule entrée.

    Les titres uniques ne sont jamais touchés : la bibliothèque reste propre
    dans le cas courant, qui est de loin le plus fréquent.
    """
    def compter(titres):
        c = {}
        for t in titres:
            c[t] = c.get(t, 0) + 1
        return c

    titres = [t for _, t in couples]
    comptes = compter(titres)

    # Premier passage : le discriminant, en pratique la région.
    passe1 = [t if comptes[t] == 1 else f"{t} ({discriminant(n)})".replace(" ()", "")
              for n, t in couples]

    # Second passage : ce qui reste en collision reçoit son nom de fichier
    # ENTIER, extension comprise. C'est la seule clé réellement unique — un
    # système de fichiers ne porte pas deux fois le même nom au même endroit.
    #
    # Cette seconde passe n'est pas une précaution de style : le discriminant
    # ne retient que le PREMIER fragment parenthésé, donc « Jeu (USA) (Rev 1) »
    # et « Jeu (USA) (Rev 2) » le partagent. Mesuré le 2026-08-26. Garantir
    # l'unicité vaut mieux que l'espérer d'une heuristique.
    comptes2 = compter(passe1)
    return [t if comptes2[t] == 1 else f"{orig[1]} ({orig[0]})"
            for t, orig in zip(passe1, couples)]


def _systeme_par_dossier(profils):
    """Le nom du dossier désigne le système. Un même identifiant ne peut être
    servi que par un profil : le premier dans l'ordre alphabétique gagne, ce
    qui rend le résultat indépendant de l'ordre de chargement."""
    table = {}
    for pid in sorted(profils):
        for s in profils[pid].systems:
            table.setdefault(s.id, (pid, s))
    return table


def _verifier_racine(roms_root: pathlib.Path) -> None:
    if not roms_root.is_dir():
        raise ScanError(
            f"racine des ROMs introuvable : {roms_root}. Le partage est-il monté ?"
        )


def _dossiers_couverts(roms_root: pathlib.Path, profils: dict):
    """Les dossiers de ROMs qu'un profil couvre, dans un ordre stable.

    Partagé par `scan` et `ignored_systems` : les deux doivent parcourir le
    MÊME disque de la même façon, sinon le rapport annoncerait des systèmes
    que le scan n'a pas ignorés, ou tairait ceux qu'il a ignorés.
    """
    table = _systeme_par_dossier(profils)
    for dossier in sorted(p for p in roms_root.iterdir() if p.is_dir()):
        trouve = table.get(dossier.name)
        if trouve:  # sinon : dossier qu'aucun profil ne couvre
            yield dossier, trouve[0], trouve[1]


def _retenus(dossier: pathlib.Path, systeme) -> list[pathlib.Path]:
    """Les fichiers de ce dossier qui méritent une entrée Steam.

    Un .m3u regroupe les disques d'un même jeu. Lancer un disque isolé alors
    qu'un .m3u existe est une erreur : le jeu réclamerait le disque suivant
    sans pouvoir l'obtenir. Le titre de BASE est la clé de regroupement — il
    ignore le marqueur de disque, que le titre affiché conserve.
    """
    fichiers = sorted(f for f in dossier.iterdir()
                      if f.is_file() and f.suffix.lower() in
                      tuple(e.lower() for e in systeme.extensions))
    titres_m3u = {base_title(f.name) for f in fichiers
                  if f.suffix.lower() == ".m3u"}
    return [f for f in fichiers
            if f.suffix.lower() == ".m3u"
            or base_title(f.name) not in titres_m3u]


def ignored_systems(roms_root: pathlib.Path, profils: dict,
                    install_dirs: dict[str, str],
                    emulation_root_local: pathlib.Path | str,
                    ) -> list[IgnoredSystem]:
    """Les systèmes que `scan` laisse de côté parce que leur émulateur manque.

    « Un système présent dans un profil mais absent de D:\\Emulation est ignoré
    par le scan, ET SIGNALÉ » : voici de quoi le signaler.

    Un dossier de ROMs vide ne compte pas. Un émulateur non installé dont le
    propriétaire n'a aucun jeu n'est pas son problème, et le lui annoncer
    noierait les manques qui, eux, lui coûtent des jeux.
    """
    _verifier_racine(roms_root)
    ignores = []
    for dossier, pid, systeme in _dossiers_couverts(roms_root, profils):
        # La MÊME notion d'« installé » que `retro status` et `retro install`,
        # lue au même endroit : l'une inventoriait ce que l'autre déclarait
        # absent, sur le même disque, et le propriétaire n'avait aucun moyen
        # de trancher.
        etat = install_mod.emulator_state(
            emulation_root_local, install_dirs[pid], profils[pid].exe)
        if etat == install_mod.OK:
            continue
        jeux = len(_retenus(dossier, systeme))
        if jeux:
            ignores.append(IgnoredSystem(
                folder=dossier.name, system_name=systeme.name, profile=pid,
                install_dir=install_mod.install_path(
                    emulation_root_local, install_dirs[pid]),
                emulator=install_mod.emulator_exe(
                    emulation_root_local, install_dirs[pid], profils[pid].exe),
                roms=jeux, reason=etat,
            ))
    return ignores


def scan(roms_root: pathlib.Path, profils: dict, emulation_root: str,
         install_dirs: dict[str, str],
         roms_root_windows: str = "G:\\ROMs",
         emulation_root_local: pathlib.Path | str | None = None,
         ignored: Sequence[IgnoredSystem] | None = None,
         ) -> list[entry.RomEntry]:
    """L'inventaire des ROMs, tel que Steam le verra.

    `emulation_root_local` est le chemin par lequel CETTE machine atteint les
    émulateurs, quand `emulation_root` est celui par lequel la console les
    verra — la même paire que `--roms` et `--roms-windows`. Donné, il fait
    vérifier que l'exécutable de chaque émulateur existe VRAIMENT, et ignorer
    les systèmes dont il manque : sans cela, une installation ratée peuple la
    bibliothèque du propriétaire d'entrées qui ne démarrent pas, et la garde
    de `sync` ne peut rien y voir puisque le chemin fabriqué reste, lui, bien
    sous la racine d'émulation.

    Facultatif, parce qu'un appelant peut préparer l'inventaire d'une machine
    qu'il n'atteint pas. Absent, rien n'est vérifié ni ignoré : le
    comportement d'avant, à l'identique.

    `ignored` est pour l'appelant qui a DÉJÀ appelé `ignored_systems` — le
    CLI, qui doit annoncer ce qu'il ignore. Son ensemble fait alors foi et
    rien n'est recalculé : deux calculs, c'est deux vérités possibles sur un
    disque qui bouge, et un message qui contredit l'inventaire qu'il
    accompagne. Un ensemble vide est une réponse, pas une absence de réponse.
    """
    _verifier_racine(roms_root)
    if ignored is None and emulation_root_local is not None:
        ignored = ignored_systems(roms_root, profils, install_dirs,
                                  emulation_root_local)
    ignores = {i.folder for i in ignored or ()}
    inventaire = []

    for dossier, pid, systeme in _dossiers_couverts(roms_root, profils):
        if dossier.name in ignores:
            continue  # émulateur absent : ces jeux ne se lanceraient pas
        exe = f"{emulation_root}\\{install_dirs[pid]}\\{profils[pid].exe}"
        start_dir = f"{emulation_root}\\{install_dirs[pid]}"

        retenus = _retenus(dossier, systeme)
        titres = _desambiguiser([(f.name, clean_title(f.name)) for f in retenus])
        for f, titre in zip(retenus, titres):
            inventaire.append(entry.RomEntry(
                title=titre,
                rom_path=f"{roms_root_windows}\\{dossier.name}\\{f.name}",
                system_name=systeme.name,
                emulator_exe=exe,
                launch_template=systeme.launch,
                start_dir=start_dir,
                extra_tags=(),
            ))
    return inventaire
