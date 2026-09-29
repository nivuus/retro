# retro — notes d'implémentation

## Ce que c'est

Paquet Python (`retro`, CLI du même nom) de la suite Nivuus : fait remonter une
bibliothèque de ROMs dans Steam (`shortcuts.vdf`, artwork SteamGridDB, catégories)
sur la console, une VM Windows qui fait tourner les émulateurs. Il installe les
émulateurs depuis un manifeste épinglé (URL + SHA256), inventorie les ROMs, et
livre le source du lanceur C# que Steam appelle pour chaque jeu. Le README
(français) décrit chaque commande ; ne pas le recopier ici.

## Commandes vérifiées (2026-09-29)

```bash
pip install -e '.[dev]'      # extra dev = pytest seul
python3 -m pytest            # ~15 s, 1056 passés, 2 ignorés, 2 ÉCHECS connus (ci-dessous)
python3 -m pytest tests/steam -q          # un sous-ensemble
python3 -m build --wheel     # roue dans dist/ ; nécessite le paquet `build`
python3 -m retro.cli identite             # quelle construction tourne
```

Les tests n'utilisent ni réseau, ni Steam, ni Windows. Il n'y a ni linter ni
formateur configuré dans `pyproject.toml`.

**Échecs connus sur `main`** : `test_le_depot_porte_le_texte_de_sa_licence` et
`test_la_licence_est_versionnee` (`tests/test_donnees.py`) cherchent un fichier
`LICENSE` et `license.text == "MIT"`, alors que le dépôt porte `LICENSE.md`
(PolyForm Noncommercial 1.0.0, PR #2). Le README (« MIT — … [LICENSE] ») est périmé
sur le même point. Ne pas « réparer » en remettant du MIT : mettre les tests et le
README d'accord avec la licence en vigueur.

## Architecture

```
retro/cli.py          # argparse : sync install scan render langue identite bios status launcher
retro/scan.py, profiles.py, manifest.py, install.py, acquire.py   # inventaire, profils, manifeste, téléchargement vérifié
retro/status.py       # rapport humain (retro status)
retro/render.py, langue*.py, dialectes.py, bios.py, titres.py, rdb.py
retro/steam/          # shortcuts.vdf, appid, artwork, steam_input, reconcile, sync
retro/launcher.py     # dépose le lanceur et écrit les plans de lancement
retro/data/           # DANS le paquet (package-data) : manifests/core.toml, profiles/*.toml,
                      #   databases.toml, launcher/*.cs + compiler.cmd
outils/identite_build.py   # backend PEP 517 en arbre (voir pièges)
tests/, tests/steam/, tests/fixtures/    # les fixtures ont leur README
docs/dettes.md        # D1…D14 : ce qui manque, avec où ça se joue
docs/releve-manettes.md    # procédure à jouer sur la console
docs/superpowers/{plans,specs}/   # plans et specs datés
```

- **Un profil TOML par émulateur** (`schema = 1`, `id`, `exe`, `[input]`, sections
  d'amorçage, tables de langue, remplissage par mode). Il dit quel dossier de ROMs
  est quel système, quelles extensions, quelle ligne de commande. Deux profils
  livrés ne peuvent pas revendiquer le même système (`_refuser_systemes_partages`).
  Les commentaires des profils portent les mesures qui justifient chaque clé : les
  lire avant de modifier une valeur.
- **Lanceur C#** : cinq sources (`retro-launch.cs`, `-yaml`, `-json`, `-xml`,
  `-eeprom`) compilées sur la console par `compiler.cmd`. Il lit des plans, il ne
  décide de rien : ajouter ou changer une table exige un nouveau `retro scan`.
- **Données du propriétaire, hors dépôt** : `emulators.toml`, `secrets.toml`
  (gitignorés) et profils perso vivent sous `G:\retro\` côté VM (`--user-manifest`,
  `--user-profiles`). Le dépôt ne porte que `core.toml` et les profils livrés.

## Pièges non évidents

- **La version de la roue bouge à chaque construction.** `dynamic = ["version"]`,
  backend `identite_build` (`backend-path = ["outils"]`) : il grave
  `retro/_identite.py` (gitignoré, ne jamais versionner ni éditer) avec
  `0.1.0+<mtime UTC>.<empreinte>[.g<sha>]`. Le tout premier segment est l'horodatage
  (ordre PEP 440). Seuls `retro/` et `pyproject.toml` comptent : modifier tests ou
  docs ne change pas la version. Le SHA est lu dans `.git` sans binaire git (absent
  sur la console) ; sans `.git`, pas de segment `g`. Une roue reconstruite à la
  main sans ce backend a causé la panne du 2026-08-29 (dette D6). Toute roue
  destinée à la console passe par `python -m build` ou `pip wheel`, jamais par un
  assemblage manuel.
- **`retro/_identite.py` du checkout est un artefact** : après un build ou un
  `pip install -e`, il décrit ce build, pas l'état du dépôt. Un arbre jamais
  construit se dit `0.1.0+source`.
- **Témoin durable `package=`** (`D:\state\retro.status`) : écrit par DEUX
  écrivains hors de ce dépôt (`Write-RetroStatus` dans `retro-status.ps1` et
  `format_witness` dans `retro_sync.py`, côté `installer`). Renommer la clé d'un
  seul côté fait échouer `test_windows_guest_retro_sync.py` de l'installer.
- **Aucun binaire livré** : le lanceur est du source, compilé sur l'invité avec le
  `csc.exe` du .NET Framework. Pas de compilateur C# sur l'hôte ; pour tester du C#,
  le compiler sur l'invité.
- **`compiler.cmd` est encodé en CP850, pas en UTF-8**, volontairement (cmd coupe
  les lignes sur les octets UTF-8 accentués). Un éditeur ou un `Write` qui le
  réencode en UTF-8 le casse : n'y toucher qu'en préservant l'encodage.
- **Un émulateur n'est « installé » que si l'exécutable ET `.retro-version`
  existent**. `install` efface le dossier d'un émulateur lors d'une montée de version
  (et nomme les configs perdues).
- **7-Zip requis sur le `PATH`** pour RetroArch et RPCS3 : `py7zr` ne lit pas le
  filtre BCJ2. Les tests n'en ont pas besoin ; une vraie installation, si.
- **`--emulation-root` (chemin lu par la console) ≠ `--emulation-root-local`
  (chemin de la machine qui scanne)**, idem `--roms/--roms-windows` et
  `--steam-root/--steam-root-windows`. Sans `-local`, `scan` ne vérifie rien.
  `--manifest`/`--user-manifest`/`--user-profiles` vont avec les mêmes valeurs à
  `install` ET `scan`.
- **`retro sync` refuse si Steam tourne** et si l'inventaire ne correspond pas à
  `--emulation-root`. Changer un titre change l'appid : les vignettes sont
  retéléchargées (5 requêtes SteamGridDB par jeu).
- **La fixture `tests/fixtures/shortcuts-reel.vdf` ne se régénère pas ici** (voir son
  README).
- **Les tables de langue n'ont encore jamais été vues agir** : la preuve reste due
  sur la console (`docs/dettes.md`, D12). Ne pas écrire « fonctionne » sans elle.

## Déploiement sur la console

Ce dépôt n'a pas de commande de déploiement propre : c'est l'`installer` qui construit
la roue et la pousse sur l'invité. Procédure vérifiée le 2026-09-27 dans la mémoire
`retro-deploiement-console.md` ; contexte dans
`packages/installer/docs/claude/dev-commands.md` (garde exit 8, témoin `package=`,
`--reinstaller-le-paquet`) et `installer-console-package.md`.

1. Roue depuis un worktree PROPRE de `origin/main` (le checkout local vit souvent sur
   une branche de dette) : `fetch_payload.build_retro_wheels(...)` dans
   `installer/console/guest`.
2. `python3 retro_sync.py --reinstaller-le-paquet` (même dossier).
3. **`retro_sync` ne lance jamais `retro launcher`** : sans l'étape suivante, le
   lanceur reste l'ancien et ignore en silence les nouveautés. Sur l'invité :
   `retro launcher --emulation-root ... --emulation-root-local ...` (rc=1 =
   « lanceur périmé », attendu) puis `compiler.cmd` sous `_launcher\`.
4. Preuve : lancer un jeu comme Steam et lire le `journal.txt` du lanceur ;
   `retro-launch.exe --explain <profil>.<système> "<rom>"` pour la ligne composée.

## Conventions du dépôt

- Code, identifiants et commentaires ajoutés : anglais (la CI refuse les commentaires
  français dans le diff). Le code existant, le README et les docs sont en français.
  Messages de commit récents : anglais, conventionnels (`feat(render): …`).
- Remote `origin` en HTTPS (`https://github.com/nivuus/retro.git`) ; l'utilisateur
  root n'a pas de clé SSH. `main` est le tronc ; on y fusionne par PR, en **squash**
  (`(#N)` dans le sujet). Je n'ai pas vérifié la protection de branche de ce dépôt
  précis, seulement celle des dépôts frères.
- **Titre de PR : conventionnel ET en anglais** (`feat|fix|chore|docs|refactor|test|ci|
  perf|build|style|revert(scope)?: sujet`), jugé par `policy / Coding rules` du socle
  `nivuus/.github`. Renommer une PR ne relance pas la CI : renommer puis pousser.
- CI locale au dépôt : `.github/workflows/release.yml` seul — sur push `main`, publie
  la roue (`python -m build --wheel`, `dist/*.whl`) via le workflow partagé. Pas de
  workflow de tests dans ce dépôt.
- Limite de 500 lignes par fichier source : déjà dépassée (`profiles.py`, `status.py`,
  `launcher.py`, `cli.py`, `retro-launch.cs`). Ne pas les faire grossir ; extraire
  suivant une vraie couture quand on y touche.
- Un plan daté sous `docs/superpowers/plans/` décrit un travail engagé ; un manque
  constaté et non planifié va dans `docs/dettes.md`.
