# Console de retrogaming — conception

*2026-08-26*

## Objectif

Faire remonter une bibliothèque de jeux rétro dans Steam, sur la VM Windows que
`packages/installer` construit déjà, de sorte qu'ils soient indiscernables de
vrais jeux Steam : jaquettes, catégories, lancement à la manette, streaming par
Apollo vers Moonlight.

Le propriétaire dépose une ROM sur son NAS. Elle apparaît dans Steam Big Picture
avec sa jaquette. Il la lance à la manette, y joue, en sort à la manette. Aucun
clavier, aucun bureau, aucune configuration.

## Ce qui existe déjà

`packages/installer` a posé la moitié du chemin, et cette conception s'y appuie
plutôt que de la refaire.

| Acquis | Emplacement | Conséquence ici |
|---|---|---|
| `D:` persistant, survit à la reconstruction de `C:` | `provision/20-disk.ps1` | Les émulateurs vont sur `D:`, jamais sur `C:` |
| Steam est le shell de session (pas d'`explorer.exe`) | `provision/30-steam.ps1` | Aucune interface Windows disponible ; tout passe par Steam |
| Steam installé sur `D:\Steam` | idem | `shortcuts.vdf` survit aux reconstructions |
| Apollo + écran virtuel SudoVDA + NVENC épinglé | `provision/25-apollo.ps1` | Le streaming est acquis ; rien à ajouter côté capture |
| Partage `Console` → `G:` (`/media/data/Console`) | `provision/35-shares.ps1` | **Déclaré, jamais exploité.** Devient la racine des ROMs |
| Partage `ConsoleSave` → `H:` (`/media/backup/Console`) | idem | Les sauvegardes d'émulateurs entrent dans le backup de l'hôte |
| Exécution distante par WinRM | `windows-guest/winrm_exec.py` | Canal de déclenchement depuis l'hôte |
| Chaîne d'étapes idempotentes numérotées | `provision/run-all.ps1` | `32-retro.ps1` s'y insère naturellement |

Le vocabulaire « Console » et deux partages entiers étaient déjà réservés pour
cet usage.

## Décisions

| Sujet | Retenu | Pourquoi |
|---|---|---|
| Frontière | `packages/retro` autonome + étape mince dans `installer` | Le pont Steam intéresse bien plus de monde que cette VM ; il doit être utilisable seul |
| Pont Steam | Python, bibliothèque `vdf` (MIT) + SteamGridDB | Testable hors ligne, idempotence maîtrisée, pas d'Electron dans la VM |
| Déclenchement | Depuis l'hôte, par WinRM | Réutilise la mécanique éprouvée de `testdomain.py` |
| Binaires d'émulateurs | Téléchargés dans la VM, manifeste à empreintes épinglées | L'ISO ne grossit pas ; un bump d'émulateur est un commit |
| Périmètre | Large, jusqu'à PS3 / Wii U / Xbox original | Demandé explicitement |
| Juridique | Manifeste noyau sûr + manifeste utilisateur hors dépôt | Le dépôt public ne référence rien de contesté |
| Présentation | Steam seul, cinq assets d'artwork, tags riches | Une seule bibliothèque ; Steam Input uniformise la manette |

### Sur l'absence d'émulateur Switch

Le manifeste versionné s'arrête à PS3, Wii U et Xbox original. Yuzu a fermé en
mars 2024 à l'issue d'un procès Nintendo ; Ryujinx s'est arrêté en octobre 2024
après contact de Nintendo. Les forks communautaires héritent du même risque.

Un dépôt public qui **pointe** vers eux dans un fichier versionné commet un acte
de distribution attaquable, et une plainte ne viserait pas seulement
`packages/retro` — elle exposerait tout le dépôt.

Le mécanisme de manifeste utilisateur (ci-dessous) laisse le propriétaire ajouter
ce qu'il veut sur sa propre machine. Le code le supporte pleinement ; le dépôt
n'en dit rien.

## Architecture

```
packages/retro/
├── retro/
│   ├── manifest.py          core.toml + surcharge utilisateur
│   ├── acquire.py           téléchargement, vérification SHA256, extraction
│   ├── profiles.py          chargement et validation des profils
│   ├── scan.py              G:\ROMs → inventaire
│   ├── metadata.py          ScreenScraper → titres, genres, années (avec cache)
│   ├── bios.py              vérification des BIOS requis
│   ├── steam/
│   │   ├── accounts.py      découverte des comptes userdata
│   │   ├── vdf.py           lecture / écriture de shortcuts.vdf
│   │   ├── appid.py         dérivation de l'identifiant
│   │   ├── artwork.py       SteamGridDB → config\grid\
│   │   └── sync.py          réconciliation
│   └── cli.py
├── manifests/
│   └── core.toml            émulateurs au statut juridique clair
├── profiles/
│   ├── retroarch.toml
│   ├── dolphin.toml
│   └── ...
├── tests/
└── docs/
```

### Interfaces exposées

Trois, et rien d'autre ne franchit la frontière entre les deux paquets.

| Commande | Contrat |
|---|---|
| `retro install` | Lit les manifestes, remplit `D:\Emulation`, écrit les configurations d'émulateurs. Idempotent. |
| `retro sync` | Scanne `G:\ROMs`, réconcilie `shortcuts.vdf`, récupère l'artwork manquant. **Refuse de s'exécuter si Steam tourne.** |
| `retro status` | Rapport lisible : jeux par système, BIOS manquants, artwork absent, émulateurs installés. Ne modifie rien. |

### Emplacements

| Chemin | Contenu | Survie |
|---|---|---|
| `C:` | Rien | Effacé à chaque reconstruction |
| `D:\Emulation\<émulateur>\` | Binaires, cores, configurations | Persistant |
| `D:\Emulation\metadata\` | Cache de métadonnées et d'artwork | Persistant |
| `D:\Steam\userdata\<id>\config\` | `shortcuts.vdf`, dossier `grid\` | Persistant |
| `G:\ROMs\<système>\` | ROMs du propriétaire | Sur le NAS, hors VM |
| `G:\BIOS\` | BIOS du propriétaire | Sur le NAS, hors VM |
| `G:\retro\emulators.toml` | Manifeste utilisateur, facultatif | Sur le NAS, hors dépôt |
| `G:\retro\secrets.toml` | Clés d'API SteamGridDB / ScreenScraper | Sur le NAS, hors dépôt |
| `H:\saves\<système>\` | Sauvegardes d'émulateurs redirigées | Dans `/media/backup` de l'hôte |

Rediriger les sauvegardes vers `H:` les fait entrer dans la stratégie de backup
existante de l'hôte sans une ligne de code supplémentaire.

## Le manifeste

Deux fichiers, même schéma. Le manifeste utilisateur est fusionné par-dessus le
noyau ; une clé identique le remplace, une clé nouvelle l'étend.

```toml
schema = 1

[emulator.retroarch]
name        = "RetroArch"
version     = "1.19.1"
url         = "https://buildbot.libretro.com/stable/1.19.1/windows/x86_64/RetroArch.7z"
sha256      = "…"
archive     = "7z"
install_dir = "RetroArch"
profile     = "retroarch"
```

`acquire.py` télécharge, **vérifie l'empreinte avant d'extraire**, extrait dans
`D:\Emulation\<install_dir>`. Une empreinte qui ne correspond pas interrompt
l'étape : un binaire d'émulateur non vérifié ne s'installe pas.

L'idempotence repose sur un fichier témoin `D:\Emulation\<install_dir>\.retro-version`
contenant la version installée. Version identique, on passe. Version différente,
on réinstalle par-dessus.

## Les profils d'émulateur

Un profil décrit **comment on parle à un émulateur**. C'est l'abstraction qui
permet d'en ajouter un sans toucher au code.

```toml
schema = 1
id  = "retroarch"
exe = "retroarch.exe"

[input]
steam_input = "required"     # required | disabled
mode        = "xinput"

[exit]
native   = "Select+Start"    # hotkey configuré dans l'émulateur
fallback = "alt+f4"          # via Steam Input, toujours présent

[[system]]
id         = "psx"
name       = "PlayStation"
extensions = [".cue", ".chd", ".pbp", ".m3u"]
launch     = '-L "cores\\swanstation_libretro.dll" -f "{rom}"'
bios       = [
  { file = "scph5501.bin", sha1 = "…", required = true },
]
```

`{rom}` est la seule substitution. Les chemins relatifs sont résolus depuis
`D:\Emulation\<install_dir>`.

Le périmètre visé, couvert par des profils du même schéma : RetroArch (rétro
8/16/32 bits, arcade), Duckstation (PS1), PCSX2 (PS2), Dolphin (GameCube, Wii),
RPCS3 (PS3), Cemu (Wii U), Xemu (Xbox), PPSSPP (PSP), Flycast (Dreamcast).

## Le pont Steam

### Ce qu'on écrit

`D:\Steam\userdata\<compte>\config\shortcuts.vdf`, VDF binaire, une entrée par
ROM :

| Champ | Valeur |
|---|---|
| `appname` | Titre canonique, issu des métadonnées |
| `exe` | Chemin absolu de l'émulateur, sous `D:\Emulation\` |
| `LaunchOptions` | Gabarit `launch` du profil, `{rom}` substitué |
| `StartDir` | Dossier d'installation de l'émulateur |
| `icon` | Chemin absolu vers l'icône déposée dans `grid\` |
| `tags` | `["Rétro", "<système>", …tags dérivés]` |

**La casse des noms de champs est celle que Steam écrit, et elle n'est pas
uniforme** — mesurée sur une installation réelle le 2026-08-26 : `appid`,
`appname`, `exe`, `icon`, `sortas`, `tags` en minuscules ; `StartDir`,
`LaunchOptions`, `IsHidden`, `AllowDesktopConfig`, `AllowOverlay`, `OpenVR`,
`Devkit`, `DevkitGameID`, `DevkitOverrideAppID`, `LastPlayTime`,
`ShortcutPath`, `FlatpakAppID` en CamelCase. Un champ dans la mauvaise casse
est ignoré par Steam sans le moindre message.

`shortcuts.vdf` ne comporte **aucun champ de description, de date de sortie,
d'éditeur ou de genre**. Steam ne détient ces métadonnées que pour les appIDs de
son propre catalogue. La richesse passe donc entièrement par l'artwork et les
tags.

### Propriété d'une entrée

La réconciliation doit pouvoir supprimer ce qu'elle a créé sans jamais toucher
aux jeux non-Steam que le propriétaire a ajoutés lui-même.

Une entrée nous appartient si **les deux** conditions tiennent :

1. `tags` contient `Rétro`, **et**
2. `Exe` désigne un chemin sous `D:\Emulation\`.

Le tag seul serait ambigu : le propriétaire peut légitimement taguer un de ses
jeux « Rétro ». La double condition lève l'ambiguïté sans parier sur un champ
non documenté.

### Réconciliation

```
entrée nôtre, ROM toujours présente   → conserver, mettre à jour tags et artwork
entrée nôtre, ROM disparue            → supprimer
ROM scannée, aucune entrée            → créer
entrée non nôtre                      → ne jamais toucher
```

### Dérivation de l'identifiant

L'identifiant dérivé du couple `(exe, appname)` par CRC32 nomme aussi les
fichiers d'artwork.

**Il n'a pas à reproduire celui de Steam.** Mesure du 2026-08-26 : sur dix
raccourcis réels, un seul se recalcule — les neuf autres ont vu leurs chemins
changer depuis leur création, et Steam ne recalcule jamais l'appid d'un
raccourci existant. Il lit celui du fichier et cherche l'artwork sous ce
nombre, ce qui est vérifié sur les huit raccourcis qui en ont.

L'exigence réelle est donc le **déterminisme et la stabilité**, pas la
fidélité. On conserve CRC32 parce que c'est la convention de l'écosystème,
donc compatible avec les bibliothèques déjà constituées par d'autres outils.

Conséquence de conception : `Exe` et `AppName` déterminent l'identifiant, donc
renommer un jeu change son identifiant et orpheline son artwork. Le sync
supprime l'artwork des identifiants qu'il vient d'abandonner.

### Écriture

Steam réécrit `shortcuts.vdf` à sa fermeture. Écrire pendant qu'il tourne perd
le travail sans le signaler. `retro sync` refuse donc de s'exécuter tant qu'un
processus `steam` existe.

L'écriture est atomique : fichier temporaire, puis remplacement. L'ancien
fichier est conservé en `.bak` horodaté, dans l'esprit de `Backup-IfChanged`
dans `25-apollo.ps1`.

### Comptes

`D:\Steam\userdata\` contient un dossier par compte connecté. Deux cas à traiter
explicitement, faute de quoi ils se manifestent par une exception opaque :

- **Aucun compte** — personne ne s'est jamais connecté à Steam. Message
  explicite ; ce n'est pas une erreur de programmation.
- **Plusieurs comptes** — on synchronise **tous** les comptes, plutôt que d'en
  deviner un.

## Métadonnées et artwork

### Cinq assets, pas un

| Asset | Préfixe de fichier | Où il s'affiche |
|---|---|---|
| Grid portrait 600×900 | `<appid>p` | Vignette de bibliothèque |
| Grid paysage 920×430 | `<appid>` | Vue « récents », étagères |
| Hero 1920×620 | `<appid>_hero` | Bannière de la fiche |
| Logo transparent | `<appid>_logo` | Superposé au hero |
| Icône | `<appid>_icon` | Listes compactes |

**Les extensions ne sont pas fixes** : `.png`, `.jpg` et `.ico` coexistent pour
un même rôle — mesuré sur 18 jeux d'une installation réelle. Toute recherche
d'existence et toute purge se font donc par préfixe, jamais sur une extension
supposée. Coder `.jpg` en dur ferait retélécharger indéfiniment, à chaque
synchronisation, un portrait déjà présent en `.png`.

Les cinq vivent dans `grid\`, l'icône comprise. Le champ `icon` du raccourci
porte en plus le chemin absolu vers ce fichier.

Écrits dans `D:\Steam\userdata\<compte>\config\grid\`. Une bibliothèque munie
des cinq est indiscernable d'une bibliothèque de vrais jeux Steam ; réduite au
portrait, elle reste visiblement bricolée.

### Sources

- **SteamGridDB** pour l'artwork. Clé d'API dans `G:\retro\secrets.toml`.
- **ScreenScraper.fr** pour les métadonnées : titre canonique, genre, année,
  nombre de joueurs, éditeur, synopsis.

Les deux sont facultatives. **Sans clé, `retro sync` fonctionne normalement** :
les titres sont dérivés des noms de fichiers selon les conventions
No-Intro/Redump (`Titre (Région) (Langues) [flags].ext` → `Titre`), les tags se
limitent au système, et les vignettes sont génériques par console. L'absence
d'artwork n'est jamais bloquante.

Tout est mis en cache dans `D:\Emulation\metadata\`, indexé par empreinte de
ROM. Une seconde synchronisation ne refait aucun appel réseau.

### Tags

Chaque tag devient une catégorie filtrable dans Big Picture, navigable à la
manette. C'est le seul champ textuel libre, et il porte ce que la description
aurait dit :

```
["Rétro", "Nintendo 64", "1996", "Plateforme", "1-4 joueurs"]
```

« Les jeux de course à deux sur Dreamcast » devient un filtre natif.

Le risque est la noyade : trois mille jeux et huit tags chacun rendent la
bibliothèque illisible. Les dimensions actives sont donc **configurables**, avec
pour défaut `système + décennie + genre`.

Le synopsis, la note et l'éditeur sont récupérés et conservés dans
`D:\Emulation\metadata\<système>.json` bien que Steam ne sache pas les afficher.
Cela ne coûte qu'un fichier et évite de rescanner trois mille ROMs le jour où
quelque chose saura les lire.

## Manette

### Sortir d'un jeu sans clavier

Il n'y a ni clavier ni bureau. Un émulateur dont on ne peut pas sortir immobilise
la console jusqu'au redémarrage de la VM. Deux niveaux, systématiquement :

| Niveau | Mécanisme | Effet |
|---|---|---|
| Sortie propre | Hotkey natif déclaré dans le profil | Sauvegarde l'état, ferme proprement |
| Filet | Steam Input mappe une combinaison distincte sur `Alt+F4` | Fonctionne sur **tous** les émulateurs |

Le filet est l'argument décisif en faveur de « Steam seul » : Steam Input
s'interpose avant l'émulateur, donc la combinaison de secours est identique sur
les quinze émulateurs, y compris ceux dont la gestion des hotkeys manette est
inexistante. Aucun frontend tiers n'offre cela.

### Double entrée

Steam Input présente une manette virtuelle XInput. Un émulateur qui lit
simultanément XInput et DirectInput voit deux manettes et double chaque entrée —
le personnage court deux fois plus vite, les menus sautent une ligne sur deux.

Chaque profil déclare donc explicitement son mode d'entrée, et la configuration
générée de l'émulateur est **épinglée sur le contrôleur Steam**, jamais laissée
en auto-détection.

**Point non vérifié, à mesurer en premier dans le sous-projet C** : Steam range
les configurations de contrôleur des jeux non-Steam dans
`userdata\<compte>\config\controller_configs\`, et une partie transite par le
cloud Steam. Rien ne prouve hors ligne qu'une configuration déposée là soit
reprise telle quelle. Si elle ne l'est pas, le filet `Alt+F4` doit passer par le
hotkey natif de chaque émulateur, ce qui le rend inégal selon l'émulateur — et
c'est alors une limite à documenter, pas à contourner.

### Plein écran

L'écran virtuel SudoVDA se redimensionne selon le client Moonlight. Chaque
profil force le plein écran au lancement. Un émulateur qui démarre en fenêtre
donne une image minuscule au centre d'un cadre noir, et il n'y a pas de souris
pour la redimensionner.

## BIOS

Sans BIOS, un jeu PS1 ou Saturn apparaît dans Steam, se lance, écran noir. Rien
n'explique pourquoi, et le propriétaire n'a aucun moyen de le diagnostiquer
depuis son canapé.

Chaque profil déclare les BIOS requis avec leurs empreintes SHA-1. `retro status`
répond :

```
PlayStation      142 jeux    BIOS OK
Saturn            38 jeux    BIOS MANQUANT → G:\BIOS\sega_101.bin
PlayStation 3      6 jeux    firmware absent → G:\BIOS\PS3UPDAT.PUP
```

Un système dont le BIOS manque est **synchronisé quand même, et tagué
`bios-manquant`**. Le propriétaire voit le problème dans Big Picture, à l'endroit
même où il le rencontrera, plutôt que de constater une absence silencieuse.

## Modifications dans `packages/installer`

Trois, toutes symétriques à du code existant.

### 1. `provision/25-apollo.ps1` — vérifier ViGEmBus

L'étape vérifie explicitement le driver d'écran virtuel par son hardware ID
(`Root\SudoMaker\SudoVDA`) mais **ne vérifie pas le driver de manette virtuelle**.
L'installateur d'Apollo l'embarque normalement ; sans lecture de contrôle, son
absence est totalement muette — l'image arrive, le son arrive, la manette ne fait
rien. Pour une console de jeu, c'est le seul driver qui ne peut pas manquer.

Ajouter une vérification de la même forme que celle de SudoVDA.

### 2. `provision/assets/steam-shell.ps1` — sentinelle `steam.hold`

La boucle du shell relance Steam dès qu'il quitte la table des processus, toutes
les trois secondes. Arrêter Steam pour écrire `shortcuts.vdf` déclencherait donc
sa relance immédiate, et Steam réécrirait le fichier par-dessus le travail de
`retro sync`. Symptôme : une synchronisation qui réussit sans rien produire, par
intermittence.

Le shell teste `C:\nivuus\state\steam.hold` avant de relancer, et affiche « mise
à jour de la bibliothèque » sur le fond d'écran pendant ce temps. La sentinelle
**expire d'elle-même au bout de cinq minutes** : un `retro sync` qui plante ne
doit pas immobiliser la console sur un écran sans Steam.

### 3. `provision/32-retro.ps1` — nouvelle étape

Environ quarante lignes, entre `30-steam.ps1` et `35-shares.ps1` :
installer Python, installer le paquet `retro`, exécuter `retro install`.

Elle **n'exécute pas** `retro sync` : les partages ne sont montés qu'à l'étape 35,
donc `G:` n'existe pas encore.

Cette même absence a une seconde conséquence : le manifeste utilisateur vit sur
`G:\retro\emulators.toml`, donc l'étape 32 ne peut installer que les émulateurs
du manifeste noyau. Son absence est traitée comme normale, jamais comme une
erreur, et les émulateurs supplémentaires du propriétaire s'installent au premier
déclenchement depuis l'hôte — d'où l'ordre `install` puis `sync` ci-dessous.

`apps.json.j2` ne change pas. `Steam Big Picture` reste l'entrée unique ; les
ROMs y remontent d'elles-mêmes.

## Déclenchement depuis l'hôte

Une commande hôte, réutilisant `winrm_exec.py` :

1. `retro install` — reprend le manifeste utilisateur, désormais lisible sur `G:`.
   Steam tourne encore : cette étape ne le touche pas.
2. Poser `C:\nivuus\state\steam.hold`
3. Arrêter le processus `steam`
4. `retro sync`
5. Retirer la sentinelle
6. Relayer le rapport

L'étape 5 s'exécute **quoi qu'il arrive**, y compris si l'étape 4 échoue. Et
l'expiration de cinq minutes couvre le cas où l'hôte lui-même disparaît en cours
de route.

`install` précède `sync` parce qu'une ROM ne peut pas remonter dans Steam tant
que l'émulateur qui la lance n'est pas installé : un système présent dans un
profil mais absent de `D:\Emulation` est ignoré par le scan, et signalé.

Le paquet reste autonome : `retro sync` s'exécute tout aussi bien à la main sur
n'importe quel Windows muni de Steam. L'hôte ne fait que le déclencher.

## Gestion des erreurs

La règle du dépôt s'applique : un échec ne doit jamais ressembler à une réussite.

| Situation | Comportement |
|---|---|
| Empreinte d'un binaire non conforme | Interrompre. Ne pas installer un binaire non vérifié. |
| Steam en cours d'exécution au `sync` | Refuser, message explicite. Ne jamais écrire. |
| `userdata\` vide | Message explicite : se connecter à Steam d'abord. |
| Clé d'API absente | Dégradation gracieuse : titres depuis les noms de fichiers, vignettes génériques. |
| SteamGridDB injoignable | Le sync aboutit ; l'artwork manquant est retenté au prochain passage. |
| BIOS manquant | Synchroniser, taguer `bios-manquant`, signaler dans `status`. |
| ROM illisible ou corrompue | Ignorer cette ROM, poursuivre, la lister dans le rapport. |
| Écriture de `shortcuts.vdf` interrompue | Écriture atomique : l'ancien fichier reste intact. |

## Tests

`pytest`, comme `scripts/tests/` dans `installer`. **Aucun accès réseau.**

- `steam/vdf.py` — aller-retour contre des fixtures `shortcuts.vdf` réellement
  produites par Steam, entrées Unicode et tags multiples compris.
- `steam/appid.py` — la dérivation vérifiée contre des couples
  `(Exe, AppName) → appid` extraits de ces mêmes fixtures. Ce test est celui qui
  autorise à écrire le module.
- `steam/sync.py` — la réconciliation sur des inventaires synthétiques : entrée
  nôtre conservée, entrée orpheline supprimée, entrée étrangère intacte,
  idempotence sur double exécution.
- `manifest.py` — fusion du manifeste utilisateur par-dessus le noyau.
- `profiles.py` — chaque profil du dépôt est chargé et validé ; un gabarit
  `launch` sans `{rom}` est un échec.
- `scan.py` — nettoyage des titres selon les conventions No-Intro/Redump.
- `bios.py` — présence, absence, empreinte non conforme.
- `acquire.py` — refus sur empreinte non conforme, saut sur version identique.

Les réponses SteamGridDB et ScreenScraper sont enregistrées en fixtures.

## Hors périmètre

- Aucun émulateur Switch dans le dépôt (voir plus haut).
- Aucune ROM, aucun BIOS, aucun firmware distribué, sous aucune forme.
- Pas de frontend rétro distinct. Steam est la bibliothèque.
- Pas d'interface web de gestion : `retro status` en ligne de commande suffit.
- Pas de synchronisation de sauvegardes entre machines. `H:` est déjà dans le
  backup de l'hôte.
- Pas de succès, de classements, ni de temps de jeu par-delà ce que Steam
  compte tout seul.
- `DevkitGameID` a été envisagé comme porteur d'identité invisible, puis écarté :
  c'est un champ non documenté à cet usage, et la double condition
  tag + chemin atteint le même résultat sans pari.

## Découpage

Trop gros pour une seule implémentation. Quatre sous-projets, chacun avec son
cycle plan → implémentation.

**A — Noyau : manifeste, acquisition, profils.**
Livrable : `retro install` remplit `D:\Emulation` avec RetroArch et ses cores,
empreintes vérifiées, réexécution idempotente. Ne dépend pas de Steam.

**B — Pont Steam.**
Livrable : `retro sync` fait apparaître les ROMs dans Big Picture avec leurs cinq
assets et leurs tags, de façon idempotente et sans toucher aux entrées
étrangères. Testable intégralement sur fixtures, donc **indépendant de A** — les
deux peuvent avancer en parallèle.

**C — Intégration : hôte, manette, BIOS.**
Livrable : l'étape `32-retro.ps1`, la sentinelle `steam.hold`, la vérification
ViGEmBus, les configurations Steam Input, `retro status`. C'est le sous-projet
qui relie A et B et rend la console réellement utilisable à la manette.

**D — Extension du catalogue.**
Livrable : les profils standalone restants — Duckstation, PCSX2, Dolphin, RPCS3,
Cemu, Xemu, PPSSPP, Flycast. Répétitif par construction : si l'abstraction de
profil est juste, chacun est un fichier TOML et un test. Si elle ne l'est pas,
c'est ici qu'on l'apprend — raison pour laquelle Dolphin, cas non-RetroArch,
passe en premier.

L'ordre recommandé est A et B en parallèle, puis C, puis D.
