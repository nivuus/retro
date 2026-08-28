"""Steam Input, jeu par jeu — et pourquoi la console doit l'éteindre.

Steam Input ne se contente pas de remapper une manette : il la MASQUE au jeu
qu'il lance. Deux mécanismes, mesurés sur la console le 2026-08-28 :
`SDL_GAMECONTROLLER_IGNORE_DEVICES`, posée dans l'environnement — le lanceur la
retire — et `gameoverlayrenderer64.dll`, que Steam injecte dans le processus et
qui pose son propre hook sur XInput. Le second ne se neutralise pas depuis le
programme lancé : priver l'émulateur des variables Steam a été essayé, vérifié
sur le processus vivant, sans aucun effet.

Il reste une prise, et c'est celle-ci : Steam Input se désactive PAR JEU, et ce
réglage vit dans un fichier.

    userdata/<compte>/config/localconfig.vdf
      UserLocalConfigStore / apps / "<appid signé>" / UseSteamControllerConfig

`0` désactive Steam Input pour ce jeu ; toute autre valeur, et l'absence de la
clé, le laissent actif. L'identifiant est l'appid SIGNÉ du raccourci, celui que
`appid.to_signed(appid.legacy_appid(exe, appname))` calcule déjà pour l'artwork.

**Pourquoi le faire ici plutôt que de le demander au propriétaire.** Le réglage
est par jeu, et une bibliothèque en compte des dizaines. Un jeu oublié est un
jeu dont la manette ne répond pas, sans un mot pour le dire — la panne la plus
coûteuse qui soit sur une console de salon, où il n'y a ni clavier pour s'en
sortir ni journal à lire.

**Ce fichier n'est pas à nous.** Il porte les réglages personnels du compte :
amis, interface, historique. On n'y touche qu'à une clé, on sauvegarde avant, et
on n'écrit pas pendant que Steam tourne — il réécrit le fichier entier à sa
fermeture, et emporterait le travail sans rien signaler.
"""
from __future__ import annotations

import os
import pathlib
from collections.abc import Iterable

import vdf

from retro.steam import writer

FICHIER = "localconfig.vdf"
RACINE = "UserLocalConfigStore"
APPS = "apps"
CLE = "UseSteamControllerConfig"
# La valeur que Steam écrit pour « Désactiver Steam Input ». Les autres valeurs
# observées — "1", "2" — sont des degrés d'activation : tout ce qui n'est pas
# "0" laisse la manette masquée, y compris une clé absente.
DESACTIVE = "0"


class LocalConfigError(RuntimeError):
    """localconfig.vdf est absent, illisible, ou n'a pas la forme attendue."""


def _charger(path: pathlib.Path) -> dict:
    if not path.is_file():
        raise LocalConfigError(
            f"{FICHIER} introuvable ({path}) : Steam le crée dès la première "
            "connexion d'un compte. Son absence n'est pas un cas normal — "
            "vérifier que le dossier du compte est bien celui de Steam."
        )
    try:
        document = vdf.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # la bibliothèque lève des types variés
        raise LocalConfigError(f"{FICHIER} illisible : {exc}") from exc
    if RACINE not in document:
        raise LocalConfigError(
            f"racine '{RACINE}' absente de {FICHIER} ; clés trouvées : "
            f"{sorted(document)}"
        )
    return document


def etats(path: pathlib.Path) -> dict[int, str]:
    """Ce que le fichier dit de Steam Input, par appid signé.

    Seuls les jeux qui PORTENT la clé figurent ici. L'absence n'est pas
    représentée par une valeur par défaut : elle se lit dans `actifs`, où elle
    a un sens — « Steam Input s'applique » — que ce dictionnaire n'a pas à
    inventer.
    """
    apps = _charger(path)[RACINE].get(APPS, {})
    releve: dict[int, str] = {}
    for identifiant, reglages in apps.items():
        if not isinstance(reglages, dict) or CLE not in reglages:
            continue
        try:
            releve[int(identifiant)] = reglages[CLE]
        except ValueError:
            # Steam n'écrit que des entiers signés ici. Une clé qui n'en est
            # pas un n'est pas la nôtre : la sauter plutôt que faire échouer
            # la lecture de tout le fichier pour une entrée étrangère.
            continue
    return releve


def actifs(path: pathlib.Path, appids: Iterable[int]) -> list[int]:
    """Ceux de ces jeux dont Steam Input est encore actif — donc muets.

    Un appid absent du fichier compte comme actif : c'est le défaut de Steam,
    et c'est l'état de TOUT raccourci fraîchement créé. Le cas normal, donc,
    pas le cas rare.
    """
    releve = etats(path)
    return [appid for appid in appids if releve.get(appid) != DESACTIVE]


def desactiver(path: pathlib.Path, appids: Iterable[int]) -> pathlib.Path | None:
    """Éteint Steam Input pour ces jeux. Rend la sauvegarde, ou None.

    None veut dire « il n'y avait rien à changer », et c'est ce qui évite
    qu'une synchronisation sans nouveauté dépose un `.bak` de plus à chaque
    passage, indéfiniment.

    Les réglages voisins du même jeu — vibration, intensité — sont conservés :
    on écrit UNE clé dans une entrée qui ne nous appartient pas.
    """
    document = _charger(path)
    apps = document[RACINE].setdefault(APPS, {})

    change = False
    for appid in appids:
        reglages = apps.setdefault(str(appid), {})
        if reglages.get(CLE) != DESACTIVE:
            reglages[CLE] = DESACTIVE
            change = True
    if not change:
        return None

    # La garde vient APRÈS le constat de changement : refuser d'écrire alors
    # qu'il n'y a rien à écrire ferait échouer une synchronisation qui n'avait
    # rien à faire, pour un Steam ouvert qui ne gênait personne.
    writer.assert_steam_not_running(FICHIER)

    rendu = vdf.dumps(document, pretty=True)
    sauvegarde = writer.sauvegarder(path)
    temporaire = path.with_suffix(".vdf.tmp")
    temporaire.write_text(rendu, encoding="utf-8")
    os.replace(temporaire, path)  # atomique sur Windows comme sur POSIX
    return sauvegarde
