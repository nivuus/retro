# PS4 — faire entrer un jeu dans shadPS4 (dette D8) — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — `superpowers:subagent-driven-development`.

**Objectif :** compléter la chaîne PS4 d'un maillon nommé — l'extraction d'un
`.pkg` vers un dossier de jeu que shadPS4 sait lire — **ou conclure, à coût
quasi nul, qu'elle ne vaut pas d'être complétée.** Les deux issues sont des
livrables.

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`
**Dette :** `docs/dettes.md`, D8.

**Architecture, en une phrase :** l'extracteur est un outil tiers, **déclaré
hors dépôt** dans le manifeste du propriétaire comme shadPS4 lui-même,
téléchargé et vérifié par le mécanisme d'acquisition existant, exécuté **à la
main, une fois**, et son résultat tombe dans `G:\Games\Sony\PS4\` où
`retro scan` le ramasse déjà par le mécanisme des dossiers d'application.

**Aucune ligne de code n'est écrite avant la tâche 5.** Les quatre premières
tâches sont des mesures, et trois d'entre elles peuvent clore la dette.

---

## Contraintes globales

- **Aucune ROM, aucun BIOS, aucun `.pkg`, aucun binaire, aucune archive dans le
  dépôt.** Un `.pkg` de 36 Go n'a évidemment pas sa place ici, mais la règle
  vaut aussi pour l'extracteur : il ne s'y installe pas, même « pour tester ».
- **Le dépôt versionné ne référence aucun outil au statut contesté.**
  `tests/test_donnees.py::test_aucun_emulateur_au_statut_conteste` balaie
  **tout** le versionné, ce fichier compris. Ce plan est un fichier versionné :
  il **nomme** des candidats, il ne **pointe** vers aucun — ni URL de
  téléchargement, ni empreinte. Voir la décision 1.
- **Un `sha256` inventé est pire qu'un outil absent** : il passe les tests ici
  et échoue sur la console, où personne ne peut le diagnostiquer. Toute
  empreinte se calcule sur l'archive réellement téléchargée, dans un dossier
  temporaire hors du dépôt, puis l'archive s'efface.
- **Aucune étiquette roulante.** `core.toml` l'écrit en tête et Vita3K l'a payé :
  une empreinte qui vieillit d'un jour fait échouer l'installation sans un mot.
- **La console Windows n'est pas accessible depuis la session qui exécutera ce
  plan** — sauf par WinRM, depuis l'hôte. Toute étape qui exige la machine est
  marquée **📏 MESURE** et s'arrête là si elle ne peut pas être faite.
- **Python 3.11 minimum. Aucun test ne touche le réseau ni n'exige Windows.**
- **Distinguer MESURÉ et SUPPOSÉ dans tout ce qu'on écrit**, y compris dans les
  commentaires du manifeste du propriétaire. Ce plan le fait ; le suivant doit
  pouvoir savoir d'où venait chaque affirmation.

---

## L'état des lieux, et d'où il vient

### Ce qui est MESURÉ (relevé sur la machine, le 2026-08-29)

| Fait | Conséquence |
|---|---|
| shadPS4 **0.18.0** installé et épinglé, dans le manifeste du PROPRIÉTAIRE ; archive à **une seule entrée**, `shadPS4.exe` | Rien à refaire côté émulateur |
| `shadPS4QtLauncher` déclaré en **`parts`** du même émulateur, étiquette datée **et** commit (`2026-08-26-d2c682c`) | Une empreinte qui ne périme pas — le modèle à suivre pour l'extracteur |
| Le build `win64-sdl` est **exclusivement en ligne de commande** : « This is a CLI application. Please use the '-b' flag for Big Picture mode, or QTLauncher for a standalone GUI » | Piloter un menu sur ce binaire est vain. Il n'en a pas |
| L'aide du binaire offre `--game`, `--patch`, `--big-picture`, `--fullscreen`, `--add-game-folder`, `--set-addon-folder`, `--mount`… — **et rien qui installe un paquet** | L'existence de `--patch` et `--add-game-folder` est acquise ; **ce qu'ils font ne l'est pas** |
| Le menu *File* du lanceur graphique porte **cinq** entrées : `Boot Game`, `Open/Add Elf Folder`, `Open shadPS4 Folder`, `Recent Games`, `Exit` | Aucune n'installe. Mais `Open/Add Elf Folder` ouvre une porte : voir la tâche 2 |
| Dossier de jeux réglé sur `G:\Games\Sony\PS4` | C'est là que le résultat doit atterrir |
| Les deux fichiers du propriétaire sont des `.pkg` valides — magie `\x7FCNT`, content ID `EP9000-CUSA07410_00-00000000GODOFWAR`, base 36 Go + mise à jour 7,5 Go | La matière existe et est lisible |

**Conclusion mesurée, qu'aucune tâche de ce plan ne rediscute :** ce shadPS4
n'installe pas de PKG, par aucune voie. Il attend des jeux **déjà extraits** et
se contente de les lister. Ne repasse pas une heure à chercher une option
cachée : elle a été cherchée.

### Ce qui est SUPPOSÉ (et que ce plan ne présente jamais autrement)

| Supposition | Pourquoi elle n'est pas une mesure |
|---|---|
| God of War (2018) démarre jusqu'aux menus sans être jouable | Rapporté par des tiers, sur d'autres machines, sur d'autres versions |
| shadPS4 rend une image sur l'écran virtuel SudoVDA | Personne n'a vu shadPS4 afficher quoi que ce soit sur cette console. Il exige Vulkan ; l'écran est virtuel |
| Une mise à jour se dépose dans un dossier frère et se détecte seule | Convention lue chez d'autres, jamais vérifiée sur ce binaire. `--patch` existe, son contrat non |
| Les deux `.pkg` du propriétaire sont extractibles | **C'est la supposition la plus lourde du plan.** Voir la tâche 1 |

---

## Décision 1 — Où l'extracteur est déclaré : **le manifeste du propriétaire**

**Tranché : `G:\retro\emulators.toml`, hors dépôt. Rien dans `core.toml`.**

Trois raisons, dans l'ordre où elles pèsent.

1. **Le dépôt est public, et un outil qui déchiffre le contenu d'un paquet PS4
   est au moins aussi contesté que ce que la spec exclut déjà.** La spec écrit
   la règle en toutes lettres : « Un dépôt public qui **pointe** vers eux dans
   un fichier versionné commet un acte de distribution attaquable, et une
   plainte ne viserait pas seulement `packages/retro` — elle exposerait tout le
   dépôt. » Le mot qui compte est *pointe* : c'est l'URL et l'empreinte qui font
   la distribution, pas le nom. C'est exactement la ligne que `docs/dettes.md`
   tient déjà en nommant shadPS4 sans jamais donner son URL.
2. **L'échappatoire existe, elle est éprouvée, et c'est son objet.**
   `load_manifest` fusionne le manifeste du propriétaire par-dessus le noyau
   (`brut.update`), l'absence du fichier est traitée comme normale, et
   `--user-manifest` / `--user-profiles` sont déjà les chemins par lesquels
   shadPS4 **et** Vita3K vivent. On n'invente rien : on emprunte le chemin que
   deux émulateurs empruntent déjà.
3. **Ça n'engage que la machine du propriétaire.** L'empreinte se relève au
   moment de l'installation, et si l'outil disparaît de la circulation, c'est un
   `emulators.toml` à corriger sur un NAS, pas un commit dans un dépôt public.

**Ce que ce plan écrit malgré tout dans le dépôt, et c'est délibéré :** les
**noms** des candidats et les **critères** de choix, pour que personne ne
refasse cette recherche. Aucune URL, aucune empreinte, aucun binaire. Le nom
d'un projet est ce que `docs/dettes.md` porte déjà pour shadPS4 ; l'URL est ce
qu'il ne porte pas. Ce plan tient la même ligne.

**Le corollaire, qui n'est pas un détail :** `retro install` ne peut installer
que ce que le manifeste décrit, et le manifeste du propriétaire vit sur `G:`,
qui n'est pas monté à l'étape 32 du provisionnement. L'extracteur ne s'installe
donc **jamais** au provisionnement, seulement au `retro install` déclenché
depuis l'hôte, partages montés. C'est le comportement voulu et il est déjà
documenté ; ne le prends pas pour une panne.

### Le détail qui casse tout en silence — à lire avant d'écrire l'entrée

`retro/cli.py:190` construit `table = {emu.profile: emu.install_dir for emu in
emulateurs.values()}`. **Deux entrées de manifeste qui déclarent le même
`profile` s'écrasent l'une l'autre**, et la dernière gagne. Si l'entrée de
l'extracteur portait `profile = "ps4"` — le profil de shadPS4 —, l'inventaire
pointerait les jeux PS4 vers le dossier d'installation de l'extracteur. Steam
créerait les entrées, le rapport annoncerait « + God of War », et **rien ne se
lancerait** : ni Steam ni ce paquet ne le signaleraient.

L'entrée de l'extracteur porte donc un `profile` qui n'est **l'identifiant
d'aucun profil**, par exemple `profile = "ps4-pkg"`. Un identifiant inconnu de
`profils` reste inerte : il occupe une clé de `table` que personne ne lit, et
il ne déclenche pas l'avertissement des « dossiers devinés » (celui-ci parcourt
les profils sans manifeste, pas l'inverse). Vérifié en lisant le code, pas
supposé.

**Et une honnêteté à écrire dans le commentaire de l'entrée :** un extracteur
n'est **pas** un émulateur, et il occupe pourtant une table `[emulator.*]`.
C'est un abus assumé. L'alternative — un second mécanisme d'épinglage pour la
même idée — est pire, et le plan du sous-projet D le dit déjà pour la fusion
des profils : « deux mécanismes différents pour la même idée seraient une
source de bugs ». Ce qu'on gagne en empruntant `[emulator.*]` : vérification
d'empreinte **avant** extraction, `safe_extract`, témoin `.retro-version`,
idempotence, et un échec qui ne laisse rien à moitié. Ce qu'on perd : le nom de
la table est faux. Le commentaire doit le dire, en une phrase.

---

## Décision 2 — Comment il s'épingle sans périmer

La règle du dépôt, transposée telle quelle à un fichier qui n'est pas dans le
dépôt — parce que la raison de la règle, elle, ne change pas de côté : une
empreinte périmée fait échouer l'installation **sur la console**, sans clavier
ni écran pour lire le message.

**La procédure, dans cet ordre, et aucune étape ne se saute :**

1. **Choisir une archive dont l'URL désigne une version, jamais une étiquette
   roulante.** Le critère de test est brutal : si la même URL peut rendre un
   contenu différent demain, elle est refusée. `core.toml` documente déjà les
   deux pièges rencontrés (« latest » chez DuckStation et Xemu, « continuous »
   chez Vita3K).
2. **Si le projet ne publie qu'une étiquette roulante**, la sortie est celle que
   shadPS4 emploie déjà pour son lanceur : une URL qui porte **et** une
   étiquette datée **et** un commit (`2026-08-26-d2c682c`). Un commit ne se
   réécrit pas. Sans cela, retire le candidat.
3. **Télécharger dans un dossier temporaire hors du dépôt** — `mktemp -d`,
   jamais un sous-dossier de `packages/retro`, pour qu'aucun `git add -A`
   distrait ne puisse emporter une archive.
4. **Calculer l'empreinte sur l'archive réellement téléchargée** :
   `python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" ARCHIVE`
   — ou `sha256sum`. **Jamais recopiée d'une page tierce** : une empreinte
   recopiée n'atteste que de la page. Si le projet publie un `.sha256` à côté de
   son archive, compare les deux et note la concordance, comme `core.toml` le
   fait pour RPCS3.
5. **Lister l'archive au passage**, et noter le chemin réel de l'exécutable
   **dans** l'archive : `python3 -c "import zipfile,sys;print('\n'.join(zipfile.ZipFile(sys.argv[1]).namelist()))" ARCHIVE`.
   Un dossier racine oublié donne un outil installé qu'on ne sait pas appeler.
   C'est l'erreur que `core.toml` documente pour Cemu et RetroArch.
6. **Vérifier que le format est `zip` ou `7z`.** `retro/manifest.py` n'en connaît
   pas d'autres (`ARCHIVES = ("7z", "zip")`) et refuse le reste au chargement.
   Un `.tar.gz` ou un `.exe` d'installation disqualifie le candidat pour cette
   voie.
7. **Effacer le dossier temporaire.**
8. **Inscrire URL, version et empreinte dans `G:\retro\emulators.toml`**, avec
   un commentaire qui dit **la date du relevé** et **sur quoi il a porté**.

> ⚠️ **L'agent qui exécute ce plan ne télécharge rien depuis une session sans
> accès à la machine, et n'invente aucun `sha256`.** Une empreinte inventée
> passe la revue, passe les tests, et casse à l'installation sur la console.
> Si le téléchargement n'est pas possible ici, la tâche 5 s'arrête à « candidat
> retenu, empreinte à relever », et le rapport le dit. Une entrée à empreinte
> **vide** est une réponse — `acquire` la refuse avant de télécharger et
> explique pourquoi ; c'est exactement ce que `core.toml` fait pour Vita3K.

---

## Décision 3 — Où l'extraction se branche

**Ce n'est ni `retro install` ni `retro scan`, et ce n'est pas non plus une
nouvelle commande.**

| | |
|---|---|
| `retro install` | Installe des **émulateurs** depuis un manifeste. Il installera l'**outil** — c'est la décision 1 — mais il ne l'exécute pas, et n'a aucune raison de le faire |
| `retro scan` | **Inventorie** ce qui existe. Il ne fabrique rien. Lui faire extraire 36 Go au passage ferait d'une commande de lecture une commande d'écriture, sur une console pilotée à distance |
| Une commande `retro extract` | **Refusée dans ce plan.** Voir ci-dessous |

**Pourquoi pas une septième commande, alors que c'en serait la place logique :**

1. **Elle pointerait vers l'outil depuis du code versionné.** Une sous-commande
   dont l'unique objet est de piloter un extracteur PKG nomme cet extracteur
   dans `retro/cli.py` — un fichier public. C'est la décision 1, appliquée au
   code plutôt qu'aux données.
2. **Le coût de bord est réel et se paye immédiatement.** Le README est vérifié
   contre l'analyseur lui-même :
   `test_le_readme_annonce_toutes_les_commandes` exige un `` `retro extract` ``
   dans le README, et `test_le_readme_compte_juste_ses_commandes` exige que le
   README annonce le bon nombre **en toutes lettres**. Le dictionnaire `NOMBRES`
   de `tests/test_donnees.py` **s'arrête à six**, et il y a exactement six
   commandes aujourd'hui : ajouter la septième fait lever un `KeyError` dans le
   test avant même qu'il n'assère quoi que ce soit. Trois fichiers à modifier
   pour un geste que le propriétaire fera deux fois dans la vie de la console.
3. **YAGNI, et ici il mord.** Tant que les tâches 1 à 4 n'ont pas dit que la PS4
   rend quelque chose, écrire du code pour elle, c'est écrire du code pour un
   menu.

**Ce qui porte l'extraction, donc :** une **procédure écrite, exécutée à la
main, une fois**, depuis l'hôte par WinRM — le canal par lequel tout est déjà
piloté sur cette console sans clavier. Elle vit dans `G:\retro\`, à côté du
manifeste et des profils du propriétaire, **hors dépôt**, sous un nom explicite
(`G:\retro\ps4-extraction.md`). Le dépôt, lui, n'en garde que ce plan.

Si un jour une seconde console, ou une dizaine de jeux, rendent le geste
répétitif, la commande se justifiera d'elle-même — et le prix des trois
fichiers sera alors payé pour une raison. Ce jour n'est pas arrivé.

### Où le résultat atterrit, et par quel mécanisme il remonte dans Steam

Le dossier de jeux de shadPS4 est **déjà** réglé sur `G:\Games\Sony\PS4` (mesuré),
et c'est là que `retro scan` regarde : la racine `G:\Games` est parcourue,
`Sony` est un dossier de constructeur que `_explorer` traverse sans se
plaindre, et `PS4` est reconnu si le profil `ps4` du propriétaire le déclare
dans `folders`.

**Un jeu PS4 extrait est un DOSSIER, pas un fichier.** Le mécanisme existe
déjà et il a été écrit pour la PS Vita : `app_dir_marker`. Le profil déclare le
nom du fichier qu'une application porte à sa racine, `scan._est_application` le
cherche à la racine de chaque sous-dossier, à la casse près, et le dossier est
rendu **tel quel, jamais ouvert**. Pour la PS4, ce marqueur est `eboot.bin`.

```
G:\Games\Sony\PS4\
└── God of War\           ← inventorié : contient eboot.bin
    ├── eboot.bin
    └── sce_sys\param.sfo
```

**Le nom du dossier devient le titre Steam.** `CUSA07410\` donnerait une entrée
« CUSA07410 » dans la bibliothèque du salon. Nommer le dossier « God of War »
est gratuit et donne le bon titre — **📏 MESURE** : vérifier que shadPS4 accepte
un dossier dont le nom n'est pas le title ID (il lit le titre dans
`param.sfo` — supposé, pas mesuré).

### Le piège de la mise à jour, à lire avant de l'extraire

`app_dir_marker` retient **tout** sous-dossier portant un `eboot.bin`. Une mise
à jour extraite en porte un aussi. Un dossier `CUSA07410-UPDATE\` posé à côté
de la base **produirait donc une seconde entrée Steam**, d'apparence normale,
qui lancerait le correctif tout seul — soit rien de jouable. Personne ne le
signalerait : le scan aurait fait exactement son travail.

Deux issues, et il faut **mesurer** laquelle shadPS4 exige avant d'extraire
7,5 Go :

| Issue | Ce qu'elle donne | Ce qu'elle coûte |
|---|---|---|
| Le dossier de mise à jour vit **hors** de `G:\Games\Sony\PS4` et lui est désigné par `--patch` | Une seule entrée Steam. Le gabarit `launch` du profil porte le chemin du patch | `--patch` doit accepter un chemin — **son existence est mesurée, son contrat non** |
| Le dossier de mise à jour vit à côté de la base et shadPS4 le détecte seul | Rien à configurer | **Deux entrées Steam**, à moins de renommer le dossier pour qu'il ne porte pas d'`eboot.bin` à sa racine — ce qui casserait probablement la détection |

**Ne jamais extraire la mise à jour PAR-DESSUS la base.** Il n'existe aucun
retour en arrière, et le prix de l'erreur est 36 Go à ré-extraire. Extraire
dans un dossier distinct, toujours.

---

## Décision 4 — Faut-il seulement y investir ? Tranché avant la première ligne

**Non, pas sans preuve.** Ce plan ne présente pas D8 comme rentable.

Ce qu'on sait : l'émulation PS4 en 2026 est à peu près là où RPCS3 était en
2017, et God of War (2018) est **rapporté** — pas mesuré ici — comme démarrant
jusqu'aux menus sans être jouable. L'issue probable de tout ce travail est un
menu, et c'est 44 Go à extraire pour le découvrir, sur un partage réseau, pour
une console dont l'unique usage est de jouer au salon.

À quoi s'ajoute un risque plus court, et personne ne l'a regardé : **rien ne
garantit que ces deux `.pkg` soient extractibles du tout.** Un paquet PS4 est
chiffré ; un extracteur tiers n'y entre qu'avec le mot de passe du paquet, ou
avec les clés qui en dérivent. Les paquets refaits pour consoles ouvertes
portent tous le même mot de passe conventionnel — trente-deux zéros ; ceux qui
viennent tels quels de la boutique ne se déchiffrent pas hors de la console
d'origine. Lequel des deux le propriétaire possède **n'a pas été mesuré**, et
c'est la question la moins chère de tout ce plan.

**D'où l'ordre imposé ci-dessous, et il n'est pas négociable :** trois mesures,
de la moins chère à la plus chère, chacune capable de clore la dette. On
n'engage 44 Go qu'après les trois.

| | Tâche | Coût | Ce qu'un échec conclut |
|---|---|---|---|
| 1 | Lire l'en-tête des deux `.pkg` | quelques kilo-octets | **D8 se clôt** : ces fichiers-là n'entreront jamais. La dette devient « il faut d'autres fichiers », ce qui n'est pas un problème de code |
| 2 | Faire démarrer un homebrew `.elf` | quelques mégaoctets | **D8 se clôt autrement** : le problème n'est pas le PKG, c'est shadPS4 qui ne rend rien sur cette console. Un extracteur n'y changerait rien |
| 3 | Décider, par écrit | zéro | — |
| 4 | Extraire la **base seule** | 36 Go, une fois | Un menu → on s'arrête là et on l'écrit |

---

## Tâche 1 — 📏 MESURE : ces deux `.pkg` sont-ils seulement ouvrables ?

**Cette tâche peut clore la dette pour quelques kilo-octets lus. Elle passe en
premier pour cette seule raison.**

**Fichiers :** aucun. Rien n'est modifié.

**Où :** là où les deux `.pkg` sont lisibles. **📏 MESURE préalable** : dire
**où ils vivent**. `G:` est le partage `Console`, qui est `/media/data/Console`
sur l'hôte Linux (spec, tableau des partages) — s'ils sont sous cette racine,
l'hôte les lit **localement**, sans WinRM et sans réseau. Sinon, par WinRM
depuis l'hôte. Note la réponse : la tâche 6 en dépend.

**Ce qu'il faut obtenir :**

- l'en-tête du paquet, sur les premiers kilo-octets, et **rien de plus** : la
  magie `\x7FCNT` (déjà mesurée, à reconfirmer comme point de contrôle de la
  procédure), le content ID, et **le type de DRM / le drapeau de contenu** ;
- de cette valeur, la réponse à la seule question qui compte : **s'agit-il d'un
  paquet refait pour console ouverte (mot de passe conventionnel connu) ou d'un
  paquet de boutique (dont le mot de passe n'est pas dérivable) ?**
- la réponse écrite pour **chacun des deux fichiers** : rien ne garantit que la
  base et la mise à jour aient la même origine.

**La façon la moins chère de l'obtenir**, et dans cet ordre :

1. Un outil candidat de la tâche 5 sait **inspecter** un paquet sans l'extraire
   (lister les entrées, afficher le `param.sfo`). C'est un téléchargement de
   quelques mégaoctets, une lecture de quelques kilo-octets, aucune écriture.
   C'est le chemin recommandé — il vérifie **en même temps** que l'outil sait
   parler à ces fichiers-là.
2. À défaut, une lecture d'octets en Python sur les premiers 4 Kio du fichier,
   contre la description publique du format d'en-tête. Ce chemin est plus
   fragile : les décalages de champs se recopient d'un wiki, et une valeur mal
   située se lit comme une réponse.

**Ce qui est interdit ici :** ouvrir les 36 Go. Cette tâche lit un en-tête.

**Ce qu'on écrit à la fin, quoi qu'il arrive :** deux lignes dans le rapport,
une par fichier, disant le type constaté et **par quel moyen** il a été lu.

**Porte de sortie :** si l'un des deux fichiers n'est pas ouvrable, **arrête le
plan** et rends compte. D8 devient un constat sur des fichiers, pas une dette
de code, et c'est une conclusion parfaitement légitime — obtenue pour le prix
d'une lecture.

---

## Tâche 2 — 📏 MESURE : shadPS4 rend-il quoi que ce soit sur cette console ?

**Deuxième tâche parce qu'elle est la deuxième moins chère, et parce qu'un
échec ici rendrait tout le reste sans objet.**

Personne n'a jamais vu shadPS4 afficher une image sur cette machine. Ce qui a
été vu, c'est **une boîte de dialogue** disant qu'il s'agit d'une application
en ligne de commande. C'est la preuve que le binaire démarre ; ce n'est pas la
preuve qu'il dessine, ni qu'il dessine sur l'écran **virtuel** SudoVDA, ni que
l'image traverse Apollo jusqu'au client Moonlight, ni que la manette y répond.

Le menu *File* du lanceur porte `Open/Add Elf Folder` — **mesuré**. C'est la
porte : un exécutable homebrew se charge **sans aucun paquet**, ne pèse que
quelques mégaoctets, et se distribue librement.

**Fichiers :** aucun.

**Ce qu'il faut obtenir, dans l'ordre, et chaque réponse s'écrit :**

1. un homebrew PS4 (`.elf` ou `.self`) déposé dans un dossier de test **hors**
   de `G:\Games\Sony\PS4` — sinon il remonterait dans Steam ;
2. shadPS4 le charge — soit par `--game`, soit par le dossier d'ELF du lanceur ;
3. **une image apparaît sur l'écran virtuel**, et elle arrive jusqu'au client
   Moonlight ;
4. la manette y fait quelque chose ;
5. on **sort** du programme sans clavier. La spec l'exige de tout émulateur, et
   un émulateur dont on ne peut pas sortir immobilise la console jusqu'au
   redémarrage de la VM.

**Ce qui se mesure au passage, gratuitement :** le pilote graphique de la VM
expose-t-il Vulkan dans sa version requise ? Un refus au démarrage nomme
généralement ce qui manque ; note le message **tel quel**.

**Porte de sortie :** pas d'image, ou pas de Vulkan → **arrête le plan**. La
dette n'est plus « rien ne peut entrer dans l'émulateur », elle est « cet
émulateur ne tourne pas sur cette machine », et c'est une autre dette, à
écrire, dont l'extracteur n'est pas le maillon.

---

## Tâche 3 — La décision d'investir, écrite

**Fichiers :** aucun. C'est une tâche de jugement, et elle a un livrable : un
paragraphe.

**Ce qu'il faut obtenir :** un « on continue » ou un « on s'arrête », **motivé
par les mesures des tâches 1 et 2**, et qui répond aux trois questions :

1. Les paquets sont-ils ouvrables ? (tâche 1)
2. L'émulateur rend-il une image jouable sur cette console ? (tâche 2)
3. Le propriétaire accepte-t-il de dépenser 44 Go et une heure de partage
   réseau pour, très probablement, atteindre un menu ?

La troisième question ne se répond pas à sa place. **Si elle n'a pas été
posée, le plan s'arrête ici** et le rapport dit ce qu'on sait désormais : les
deux mesures sont acquises, elles ne périment pas, et la reprise coûtera
l'extraction et rien d'autre.

Un « on s'arrête » à ce stade est un **succès** de ce plan : deux mesures
gagnées et 44 Go non dépensés.

---

## Tâche 4 — Choisir l'extracteur : les candidats et les critères

**Fichiers :** aucun dans le dépôt. Le livrable est un choix motivé, à porter
dans `G:\retro\emulators.toml` à la tâche 5.

### Le contexte, mesuré sur les publications des projets le 2026-08-29

L'installation de PKG a été **retirée** de shadPS4 en amont — ce n'est pas une
particularité du build `win64-sdl` du propriétaire. La position du projet est
que l'on installe des dossiers déjà extraits. Cela ferme définitivement la
piste « trouver le bon build de shadPS4 » : **le maillon manquant est bien un
outil tiers**, et non un binaire mieux choisi.

### Les critères, dans l'ordre où ils éliminent

| # | Critère | D'où il vient |
|---|---|---|
| 1 | **Sait ouvrir les paquets du propriétaire**, du type constaté en tâche 1 | Sans cela le reste est sans objet |
| 2 | **Pilotable entièrement en ligne de commande** | La console n'a **ni clavier ni bureau** : Steam est le shell de session. Le seul canal est WinRM. Un outil uniquement graphique est **inutilisable** ici, quelles que soient ses qualités |
| 3 | **Publié en archive VERSIONNÉE** (ou à défaut étiquette **et** commit) | Décision 2. Une étiquette roulante est refusée |
| 4 | **Archive `zip` ou `7z`** | `retro/manifest.py`, `ARCHIVES = ("7z", "zip")`. Un installeur `.exe` ou un `.tar.gz` disqualifie pour la voie du manifeste |
| 5 | **Windows x64**, ou exécutable sur l'hôte Linux si la tâche 6 emprunte cette voie | Deux réponses possibles, voir tâche 6 |
| 6 | **Autonome** : pas de runtime à installer sur la console | Un outil qui exige un environnement d'exécution transforme une tâche en projet. **📏 MESURE** : le lancer et voir |
| 7 | **Code source public** | Un outil qui écrit 36 Go sur le NAS du propriétaire et qu'on ne peut pas lire est un pari |

### Les candidats — **à vérifier sur la machine, aucun n'est épinglé ici**

Ni URL ni empreinte : décision 1. Les noms suffisent à les retrouver.

| Candidat | Ce qui est mesuré sur ses publications | Ce qui reste à mesurer |
|---|---|---|
| **`AzaharPlus/shadPS4Plus`**, extracteur autonome tiré du code qui était dans shadPS4 | Étiquettes **versionnées** (`PKG_EXTRACTOR_1_1`), archive **Windows `.zip`** nommée par sa version. Coche les critères 3, 4 et 5 | **Ligne de commande ou graphique ?** (critère 2, éliminatoire). Autonomie (6) |
| **`maxton/LibOrbisPkg`** — `PkgTool` / `PkgEditor` | Publication **unique et versionnée**, figée depuis 2020 : une empreinte qui **ne périmera jamais**. Archives `.zip` séparées pour l'outil en ligne de commande, **et une variante Linux x64** — ce qui ouvre la voie « extraction sur l'hôte » de la tâche 6. Extraction documentée avec un paramètre de mot de passe. Source publique | Sait-il ouvrir **ces** paquets-là (critère 1) ? Exige-t-il un runtime (critère 6) ? Son âge est un atout pour l'épinglage, une inconnue pour la compatibilité |
| **`xXJSONDeruloXx/ps4-pkg-tools`** | **Éliminé, et la raison est mesurée** : ses publications ne portent **aucune archive Windows** (Linux et macOS seulement), et ses étiquettes sont horodatées. Échoue aux critères 3 et 5 | À reconsidérer **uniquement** si la tâche 6 choisit l'extraction sur l'hôte Linux |
| Les outils graphiques distribués hors publication de projet (archives de forum) | — | **Éliminés d'office** : critère 2 (graphique) et critère 3 (rien à épingler). Ne pas y passer de temps |
| Les greffons qui injectent une bibliothèque dans le lanceur shadPS4 | — | **Éliminés.** Modifier un binaire épinglé rendrait son empreinte mensongère : le manifeste attesterait une archive qui n'est plus ce qui tourne |

**Ce qu'il faut obtenir :** un candidat retenu, un candidat de repli, et **la
raison écrite** de l'élimination de chaque autre — y compris de ceux découverts
en chemin. Le prochain lecteur doit pouvoir ne pas refaire cette recherche.

---

## Tâche 5 — Épingler l'extracteur dans le manifeste du propriétaire

**Fichiers :**
- Modifier : `G:\retro\emulators.toml` — **hors dépôt**
- Ne modifier : **ni `retro/data/manifests/core.toml`, ni aucun fichier de
  `retro/`, ni aucun test**

**Ce qu'il faut obtenir :**

- une entrée `[emulator.<clé>]` complète — `name`, `version`, `url`, `sha256`,
  `archive`, `install_dir`, `profile` — le manifeste refuse au chargement toute
  entrée incomplète, en nommant les champs manquants ;
- `profile` = **un identifiant qu'aucun profil ne porte** (voir décision 1, le
  piège de `cli.py:190`). Pas `"ps4"` ;
- `install_dir` = un chemin relatif simple, qui reste sous la racine
  d'émulation : `_valider_install_dir` refuse le reste, et il refuse aussi un
  antislash seul en tête ;
- `sha256` **relevé selon la décision 2**, ou **laissé vide** si le relevé n'a
  pas pu être fait — une empreinte vide est refusée par `acquire` **avant** tout
  téléchargement, avec un message qui explique comment la relever. C'est ce que
  `core.toml` fait pour Vita3K, et c'est une réponse, pas un oubli ;
- un **commentaire** au-dessus de l'entrée, sur le modèle de ceux de
  `core.toml`, disant : la date du relevé, ce que l'archive contenait (nombre
  d'entrées, dossier racine éventuel, chemin réel de l'exécutable), que
  l'empreinte a été calculée sur l'archive téléchargée et non recopiée, et
  **que cet outil n'est pas un émulateur** — pourquoi il occupe tout de même
  cette table.

**📏 MESURE, sur la console, après l'écriture :**

```
retro install --user-manifest 'G:\retro\emulators.toml'
```

Attendu : la ligne de l'extracteur passe à « installé », et l'exécutable existe
sous `D:\Emulation\<install_dir>\<chemin relevé dans l'archive>`. Relancer :
la ligne doit passer à « à jour » — c'est le témoin `.retro-version` qui le
prouve, et c'est ce qui garantit qu'une reconstruction de la console ne
retéléchargera rien.

**Ce qui doit rester vrai, et se vérifie ici :** les autres émulateurs
s'installent toujours. `install_all` capture chaque échec et poursuit, mais un
manifeste **illisible** — TOML invalide, `schema` erroné — fait échouer le
chargement entier et prive le propriétaire de **tous** ses émulateurs. Relis le
fichier après l'avoir écrit.

---

## Tâche 6 — Extraire la BASE seule, et regarder

**Fichiers :**
- Créer : `G:\retro\ps4-extraction.md` — **hors dépôt** : la procédure, écrite
  au fur et à mesure qu'elle est exécutée, pour qu'elle soit rejouable
- Écrire : `G:\Games\Sony\PS4\<nom du jeu>\` — le résultat

**📏 MESURE préalable — où l'extraction tourne.** Deux voies, et la réponse
dépend de la tâche 1 :

| Voie | Quand la choisir | Ce qu'elle coûte |
|---|---|---|
| **Sur la console**, par WinRM, l'outil installé par `retro install` | Voie par défaut : c'est là que vivent le manifeste, l'épinglage, le témoin et toute la discipline | 36 Go **lus** et 36 Go **écrits** à travers le partage SMB. C'est le prix, et il est réel |
| **Sur l'hôte Linux**, l'outil lancé à la main sur `/media/data/Console/…` | Si la tâche 1 a montré que les `.pkg` vivent sous le partage, **et** que le candidat publie une variante Linux | Disque à disque, sans réseau. Mais **hors** de toute la mécanique d'épinglage : l'empreinte se relève alors à la main, et le manifeste du propriétaire n'a plus rien à installer |

Choisis, et **écris la raison dans `ps4-extraction.md`**. Ce n'est pas un
détail d'exécution : les deux voies ne laissent pas la même trace derrière
elles.

**Ce qu'il faut obtenir :**

1. **La base seule.** Pas la mise à jour. Elle vient à la tâche 7, et seulement
   si celle-ci a une raison d'exister.
2. **Vérifier l'espace libre avant de commencer.** 36 Go extraits en plus des
   36 Go du paquet. Un partage plein à mi-chemin laisse un dossier de jeu
   incomplet qui porte quand même son `eboot.bin` — donc une entrée Steam
   d'apparence normale qui ne lance rien. C'est le même piège que « un
   émulateur amputé est pire qu'un émulateur absent ».
3. **Extraire vers un dossier temporaire, puis basculer** dans
   `G:\Games\Sony\PS4\`. C'est exactement ce que fait `acquire` et pour la
   raison qu'il documente : une extraction interrompue ne doit pas laisser une
   installation à moitié écrite là où le scan regarde.
4. **Nommer le dossier final avec le titre du jeu**, pas avec le title ID — le
   nom du dossier devient le titre Steam (voir décision 3). **📏 MESURE** :
   confirmer que shadPS4 le liste quand même.
5. **Vérifier la forme du résultat** : un `eboot.bin` **à la racine** du dossier
   et un `sce_sys\param.sfo`. Le marqueur est cherché à la racine, jamais plus
   bas : un niveau de dossier en trop et le scan rend zéro jeu, sans un mot.
6. **📏 MESURE, la seule qui compte :** lancer le jeu dans shadPS4 sur la
   console. **Écrire ce qu'on voit** : rien / un logo / un menu / une partie
   jouable, et **combien d'images par seconde**.

**Porte de sortie :** un menu, ou moins. **Arrête le plan**, et écris-le. Les
7,5 Go de la tâche 7 ne changeront pas un menu en jeu — une mise à jour
corrige un jeu qui tourne, elle ne fait pas tourner un jeu qui ne tourne pas.
C'est la conclusion la plus probable de ce plan, et ce n'est pas un échec :
c'est la réponse à la question de la décision 4, obtenue une fois pour toutes.

---

## Tâche 7 — La mise à jour de 7,5 Go, si et seulement si la tâche 6 a donné un jeu

**Fichiers :** `G:\Games\…` et `G:\retro\ps4-extraction.md`. Rien dans le dépôt.

**Ce qu'il faut obtenir :**

1. **📏 MESURE d'abord, extraction ensuite** : comment ce shadPS4 attend-il une
   mise à jour ? Deux hypothèses, décision 3. L'aide du binaire mentionne
   `--patch` — **son existence est mesurée, son contrat ne l'est pas.**
   Relève ce que `shadPS4.exe --help` en dit exactement, puis essaie.
2. **Jamais par-dessus la base.** Dossier distinct, toujours. Pas de retour en
   arrière, et 36 Go à refaire.
3. **Vérifier qu'il n'apparaît pas une seconde entrée Steam.** Après
   extraction, relancer `retro scan` sur `G:\Games` et **compter les entrées
   PS4 de l'inventaire** : il doit y en avoir **une**. Deux signifie que le
   dossier de mise à jour porte un `eboot.bin` là où le scan le voit — sors-le
   de l'arborescence scannée et désigne-le autrement.
4. **📏 MESURE finale** : le jeu, mis à jour, va-t-il plus loin qu'à la tâche 6 ?

---

## Tâche 8 — Le profil `ps4` du propriétaire

**À faire seulement si la tâche 6 a produit un jeu qui démarre** — un profil
qui décrit comment lancer un jeu que rien ne fait tourner ne décrit rien.

**Fichiers :**
- Créer ou modifier : `G:\retro\profiles\ps4.toml` — **hors dépôt**, le dossier
  que `--user-profiles` désigne
- Ne modifier : **aucun** `retro/data/profiles/*.toml`

**Ce qu'il faut obtenir**, et chaque point est une contrainte que
`retro/profiles.py` **refuse** au chargement, pas un conseil :

- `id = "ps4"`, `exe` = le chemin de `shadPS4.exe` **tel qu'il est dans
  l'archive** — l'archive n'a qu'une entrée, donc pas de dossier racine
  (mesuré) ;
- un système `id`, `name`, `extensions`, `launch`. **`extensions` ne peut pas
  être vide** : le chargement le refuse explicitement, parce qu'un système sans
  extension ne matcherait rien et serait absent sans rien signaler. Déclare
  `[".elf", ".self"]` — c'est **vrai** (c'est ce que le lanceur sait ouvrir,
  mesuré : `Open/Add Elf Folder`) et c'est ce qui permet aussi d'inventorier un
  homebrew ;
- **surtout pas `.pkg` dans `extensions`.** Un `.pkg` laissé dans
  l'arborescence scannée produirait une entrée Steam qui passerait un paquet à
  un émulateur qui ne sait pas l'ouvrir — la panne exacte de cette dette,
  transformée en raccourci d'apparence normale. Range les `.pkg` **hors** de
  `G:\Games` ;
- `app_dir_marker = "eboot.bin"` — c'est lui qui fait reconnaître un jeu
  extrait. Sans lui, aucun dossier n'est jamais inventorié et le système rend
  zéro jeu ;
- `folders` : les noms sous lesquels le propriétaire range réellement ses jeux
  (`"PS4"`, `"PlayStation 4"`). Chaque entrée est le nom d'**un** dossier,
  jamais un chemin : `"Sony\PS4"` est refusé au chargement, et le scan descend
  tout seul dans les dossiers de constructeur ;
- `launch` **doit contenir `{rom}`**, guillemeté — c'est refusé sinon, et la
  raison est écrite dans le code : l'émulateur s'ouvrirait sur son propre menu
  et la console aurait l'air de fonctionner ;
- le **plein écran** dans le gabarit : `--fullscreen` existe (mesuré). Un
  émulateur qui démarre en fenêtre donne une image minuscule au centre d'un
  cadre noir, et il n'y a pas de souris pour la redimensionner ;
- **de quoi sortir à la manette, sans clavier** : le bloc `[exit]`. Le filet
  `alt+f4` par Steam Input est le défaut ; s'il existe un raccourci natif,
  relève-le sur le binaire plutôt que de le recopier d'une documentation ;
- le bloc `[input]` : `mapping` dit **où en est le relevé**, jamais un
  identifiant de manette. `inconnu` est le seul état vrai tant que personne n'a
  tenu le pad devant ce jeu. `releve` exige un témoin humain et **ne peut
  jamais être écrit sans avoir vu un bouton répondre**. Si tu écris
  `a-relever`, `mapping_where` devient obligatoire — nomme le fichier et la
  section que le propriétaire ouvrira.

**📏 MESURE finale :**

```
retro scan --roms /media/data/Console/Games --roms-windows 'G:\Games' \
           --user-manifest 'G:\retro\emulators.toml' \
           --user-profiles 'G:\retro\profiles' \
           --output <inventaire>
```

Attendu : **une** entrée PS4, dont le chemin d'émulateur pointe vers le dossier
d'installation **de shadPS4** — et non vers celui de l'extracteur. C'est la
vérification concrète du piège de la décision 1.

---

## Tâche 9 — Rendre compte

**Fichiers :**
- Modifier : `docs/dettes.md`, section D8, **et rien d'autre dans le dépôt**

**Ce qu'il faut obtenir :** D8 mise à jour selon ce qui s'est réellement passé,
dans la langue du fichier — **ce qui a été constaté**, **où ça se joue**, **ce
que ça coûte aujourd'hui**. Quatre issues possibles, et **trois d'entre elles
sont des fins légitimes** :

| Issue | Ce qu'on écrit |
|---|---|
| Tâche 1 négative | D8 **se clôt sur un constat de matière** : ces fichiers-là n'entreront pas. Nommer ce qu'il faudrait à la place |
| Tâche 2 négative | D8 **change de nature** : ce n'est plus l'entrée qui manque, c'est l'émulateur qui ne tourne pas ici. Ouvrir la dette qui correspond |
| Tâche 6 s'arrête sur un menu | D8 **se clôt sur une mesure** : la chaîne est complète, le jeu ne l'est pas. Écrire les images par seconde vues, et que 44 Go ont répondu à la question |
| Le jeu tourne | D8 **se clôt** ; noter que l'extracteur vit hors dépôt et que rien du dépôt ne le connaît |

⚠️ **`docs/dettes.md` est un fichier partagé.** D'autres travaux le touchent.
Ne réécris **que** la section D8, relis le fichier après, et ne commite pas
autre chose avec.

---

## Vérification finale

- [ ] Suite complète, arbre frais, sous `-W error` — elle doit être **inchangée**
      par ce plan : aucune tâche ne modifie de code ni de test
- [ ] `git status` ne montre que `docs/dettes.md` (et ce plan)
- [ ] Aucun binaire, aucune archive, aucun `.pkg`, aucun dossier de jeu dans le
      dépôt — `git status --ignored` pour en être sûr
- [ ] Aucune URL ni empreinte d'extracteur dans un fichier versionné
- [ ] `retro install --user-manifest …` reste idempotent (« à jour » au second
      passage) et n'a privé aucun autre émulateur
- [ ] `retro scan` rend **une** entrée PS4, pointant vers shadPS4
- [ ] Chaque affirmation écrite est marquée MESURÉE ou SUPPOSÉE

---

## Ce que ce plan ne fait pas

- **Il n'épingle aucun extracteur.** Il en nomme trois, en élimine deux avec
  leur raison, et laisse le choix à une mesure sur la machine. Aucune URL,
  aucune empreinte : les inventer, c'est fabriquer une panne que personne ne
  peut diagnostiquer depuis le canapé.
- **Il n'ajoute aucune commande à `retro`**, et il dit pourquoi (décision 3).
  Le jour où le geste devient répétitif, la commande se justifiera — et le prix
  du README, du compte en toutes lettres et du dictionnaire `NOMBRES` sera payé
  pour une raison.
- **Il ne touche ni `core.toml`, ni les profils livrés, ni aucun test.** Tout ce
  qui concerne la PS4 vit hors dépôt, et c'est la décision 1.
- **Il ne promet pas que God of War sera jouable.** Il promet de le savoir pour
  le prix le plus bas possible, et d'écrire la réponse.
- **Il ne traite pas les DLC ni les sauvegardes PS4.** `--set-addon-folder`
  existe (mesuré), son contrat n'a pas été relevé, et la question ne se pose
  pas avant qu'un jeu tourne.
- **Il ne règle pas la manette PS4 ni la vibration** — D1 et D4 les portent, et
  aucune des deux ne se mesure sur un jeu qui n'a pas démarré.
- **Il ne récupère ni jaquette ni métadonnées PS4.** ScreenScraper est indexé
  par nom de fichier ; un dossier nommé « God of War » suffira ou ne suffira
  pas, et cela se verra après.
