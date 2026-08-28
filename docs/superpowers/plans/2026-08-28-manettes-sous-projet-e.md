# Manettes (sous-projet E) — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE —
> `superpowers:subagent-driven-development`.

**Objectif :** les quatre joueurs d'une console de salon ont une manette qui
répond, dans tous les émulateurs, sans clavier — et le propriétaire peut
remplacer le mapping par défaut.

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`

**Suite de :** le sous-projet D, dont la clôture disait « les configurations de
manette — à mesurer sur la vraie machine ». C'est fait : la section suivante
consigne la mesure.

---

## Ce qui a été mesuré, et qui commande tout le reste

Le 2026-08-28, sur la machine, une manette USB branchée au client Moonlight
(Nintendo Switch) restait muette dans Ryujinx alors qu'elle répondait dans
Steam Big Picture. La chaîne a été suivie maillon par maillon :

| Maillon | Preuve | État |
|---|---|---|
| Client → Apollo | `sunshine.log` — `Gamepad 0 will be Xbox 360 controller (default)`, à chaque session où la manette est annoncée | intact |
| Apollo → ViGEmBus | `Nefarius\ViGEmBus\Gen1` présent, service `Running` | intact |
| ViGEmBus → Windows | `XnaComposite \| Xbox 360 Controller for Windows \| USB\VID_045E&PID_028E\01`, statut `OK` | intact |
| Windows → Steam | Big Picture répond aux boutons | intact |
| Windows → Ryujinx | `input_config` ne contenait **que** le clavier | **rompu** |
| Steam → émulateur | `SDL_GAMECONTROLLER_IGNORE_DEVICES` inclut `0x045e/0x028e` | **rompu** |

Trois faits en découlent, et ils sont la raison d'être de ce sous-projet :

1. **Le pad n'est pas branché à la machine : il est créé par Apollo, et il
   n'existe QUE pendant une session Moonlight.** Hors session, SDL n'énumère
   rien — vérifié. Une configuration d'entrée écrite à la synchronisation ne
   peut donc pas contenir l'identifiant réel du périphérique.
2. **Cet identifiant n'est pas prévisible.** Apollo choisit le type de pad
   virtuel selon ce que le client annonce : X360 ici, mais il sait aussi
   émuler une DualShock, dont le VID/PID — donc le GUID SDL — sont autres.
   Une valeur figée serait juste tant que rien ne change, et **fausse en
   silence** le jour où elle ne l'est plus.
3. **Steam masque la manette à tout ce qu'il lance.** Le client pose
   `SDL_GAMECONTROLLER_IGNORE_DEVICES` dans l'environnement du processus —
   relevé dans le PEB de Ryujinx vivant — avec la liste des manettes que
   Steam Input prend en charge, `0x045e/0x028e` comprise : exactement ce que
   le pad d'Apollo se déclare être. **Et il ne fournit aucun périphérique
   virtuel en échange** : aucun `VID_28DE` n'existe sur la machine pendant la
   session. Mesure directe, même outil, même session, même manette :

   | Condition | Manettes vues par SDL |
   |---|---|
   | environnement normal | **1** — `Xbox 360 Controller` |
   | `SDL_GAMECONTROLLER_IGNORE_DEVICES=0x045e/0x028e` | **0** |

   C'est la cause première, et elle vaut pour **les neuf émulateurs à la
   fois**, pas seulement pour Ryujinx : tout ce que Steam lance est aveugle à
   la manette. Corrigé le 2026-08-28 dans `retro-launch.cs`, qui retire la
   variable de l'environnement qu'il transmet — c'est le seul passage obligé
   entre Steam et les émulateurs, et le masquage étant reposé par le client à
   chaque lancement, un réglage par raccourci serait à refaire à chaque
   synchronisation.

4. **`steam_input = "required"` ne fait rien.** `profiles.py:82` le
   typographie, `profiles.py:474` le lit, et **aucun code ne l'applique
   jamais**. Le modèle réel est implicite : « l'émulateur détectera bien tout
   seul ». DuckStation et RetroArch le font. Ryujinx ne le fait pas, et
   l'inventaire des neuf émulateurs installés montre qu'**aucun** n'a de
   configuration d'entrée utilisateur, nulle part.

**Le problème est donc exactement celui de la résolution d'écran, que ce dépôt
a déjà résolu** : une donnée qui n'est connue qu'au lancement, dans une
configuration que Steam a figée à la synchronisation. La réponse est la même,
et elle n'est pas négociable : **le lanceur ne décide rien.** Python compose un
gabarit, testé, déposé dans le plan ; le lanceur substitue ce qu'il mesure.
Relire `retro/launcher.py` — `plan_systeme`, `ecrire_plan` — et
`render.RenderMode.config` avant d'écrire une ligne : le patron existe, et
`{render_config}` est son précédent direct.

---

## Ce dont la console dépend, et que le code ne garantit pas

**Steam Input masque la manette par DEUX mécanismes, et le second est hors
d'atteinte.** Le premier est la variable `SDL_GAMECONTROLLER_IGNORE_DEVICES`,
que le lanceur retire — mesuré efficace. Le second est
`gameoverlayrenderer64.dll`, que Steam injecte dans tout ce qu'il lance et qui
pose son propre hook sur XInput en dialoguant avec le client par IPC. Priver
l'émulateur des variables Steam a été essayé et **vérifié sur le processus
vivant** — `SteamAppId`, `SteamGameId`, `SteamOverlayGameId` absents,
`SteamNoOverlayUIDrawing` posé — sans aucun effet sur le masquage. Le code
correspondant a été retiré : il ne servait à rien, et il privait au passage le
jeu de l'overlay Steam, que le bouton Xbox n'ouvrait plus.

**La seule parade est un réglage du client Steam**, à poser à la main sur
chaque raccourci : *Bibliothèque → le jeu → ⚙ → Manette → « Désactiver Steam
Input »*. Vérifié le 2026-08-28 : la manette répond immédiatement après.

Trois conséquences, et ce sont des tâches :

1. **Ce réglage doit être vérifié, pas espéré.** Une console dont les manettes
   dépendent d'une case cochée dans une interface graphique, sans que rien ne
   le dise, retombera muette au premier raccourci recréé. Cherche si l'état de
   Steam Input par application est lisible dans les fichiers de configuration
   de Steam (`userdata/<id>/config/`), et si oui, fais-le dire par
   `retro status`. Si ce n'est pas lisible, écris-le dans le LISEZ-MOI de la
   console, en toutes lettres.

2. **Vérifie si le réglage survit à `retro sync`.** L'identifiant d'un raccourci
   dérive de ses options de lancement — c'est déjà écrit dans `launcher.py`, à
   propos du mode de rendu qui vit dans un fichier pour cette raison même. Si
   l'identifiant change, le réglage Steam Input est perdu avec lui, en silence.

3. **La sortie du jeu, elle, tient bon — mais pas par où le profil le dit.**
   Les profils déclarent `fallback = "alt+f4"`, et `ryujinx.toml` affirme que
   ce raccourci « émis par Steam Input est la seule sortie sans clavier ».
   C'est inexact, et la mesure du 2026-08-28 le montre : **Steam Input
   désactivé, le bouton Xbox ouvre toujours l'overlay Steam, et l'overlay
   permet de quitter la partie.** La sortie dépend de l'overlay, pas de Steam
   Input — deux mécanismes distincts que le profil confond.

   Il y a bien eu un moment, ce jour-là, où la console était un aller sans
   retour et où il a fallu tuer le processus depuis l'hôte : c'était le fait
   d'un correctif, depuis retiré, qui privait l'émulateur des variables
   `SteamAppId`/`SteamGameId` — donc de l'overlay avec elles. Le retirer a
   rendu la sortie.

   **Corrige la phrase de `ryujinx.toml`**, qui décrit un mécanisme pour un
   autre : elle enverrait le prochain lecteur chercher une panne du côté de
   Steam Input alors que la sortie n'en dépend pas. Et garde en tête, pour la
   conception, que la sortie repose tout de même sur un composant de Steam :
   une sortie côté lanceur — une combinaison de manette maintenue quelques
   secondes, le job object qu'il tient déjà — la rendrait indépendante, et
   vaudrait pour les neuf émulateurs. À arbitrer : ce n'est plus une urgence.

## Contraintes globales

- **Python 3.11 minimum.** Aucun test ne touche le réseau ni n'exige Windows.
- **Les chemins Windows sont des `str`**, jamais des `pathlib.Path`. Utiliser
  `pathlib.PureWindowsPath` pour toute comparaison.
- **Le lanceur ne décide rien.** Toute politique — quel mapping, pour quel
  joueur, sur quel émulateur — est calculée en Python et écrite dans le plan.
  Un arbitrage réimplémenté en C# aurait divergé au premier changement.
- **Un identifiant deviné est un défaut, pas une approximation.** Ryujinx
  n'émet aucun message quand l'identifiant d'une entrée ne correspond à aucun
  périphérique : l'entrée est ignorée, et la manette reste muette exactement
  comme si rien n'avait été écrit. **Toute valeur qui n'a pas été relevée sur
  la machine doit être traitée comme fausse.**
- **Rien n'écrase une configuration d'émulateur sans sauvegarde préalable ni
  sans en-tête disant qui l'a écrite.** Les fichiers du plan portent déjà
  « Écrit par « retro scan ». Toute modification sera écrasée. » — les
  configurations d'entrée porteront la même phrase, dans la syntaxe de
  commentaire de leur format.
- **Aucun binaire dans le dépôt.** Le lanceur est livré en source et compilé
  sur la machine par `compiler.cmd` ; tout outil ajouté suit la même règle.
- **Un test qui passerait quelle que soit l'implémentation est un défaut.**

---

## Tâche 1 : relever la vérité, avant d'écrire quoi que ce soit

Rien dans ce sous-projet ne peut être conçu sur une supposition : le format
exact de l'identifiant que chaque émulateur attend n'est connu que mesuré.

**Un outil de relevé existe déjà**, écrit pendant le diagnostic :
`D:\state\retro-tmp\PadProbe.cs`, compilé en
`D:\Emulation\Ryujinx\publish\retro-pad-probe.exe`. Il appelle le SDL2 de
Ryujinx, énumère les manettes et écrit `index`, GUID .NET et nom dans
`D:\state\retro-tmp\pads.txt`. Hors session il rapporte `0` manette, ce qui est
la bonne réponse.

**Ce qu'il faut obtenir :**

- le relevé **en session**, manette branchée au client : l'identifiant réel,
  au format que Ryujinx attend (`<index>-<GUID>`), et le nom SDL ;
- le même relevé avec **deux manettes**, pour établir comment les index se
  distribuent — c'est ce qui décide si `Player2` est adressable ;
- la reprise de cet outil **dans le dépôt**, sous `retro/data/launcher/`, à
  côté de `retro-launch.cs`, avec la même règle : source livrée, binaire
  jamais. Il devient une brique du lanceur, pas un fichier de diagnostic
  oublié dans un dossier temporaire.

**Le relevé a été fait le 2026-08-28**, session ouverte, manette USB branchée
au client Switch — et il a donné, successivement, QUATRE identifiants pour la
même manette physique. Un seul était le bon :

| Origine | Identifiant | Bon ? |
|---|---|---|
| déduit du VID/PID exposé par Windows | `0-00000003-045e-0000-8e02-000000000000` | non |
| SDL, réglages par défaut (pilote rawinput) | `0-69b90003-045e-0000-8e02-000000007200` | non |
| SDL, `SDL_JOYSTICK_RAWINPUT=0` (pilote xinput) | `0-67fa0003-045e-0000-8e02-000014017801` | non |
| **écrit par Ryujinx lui-même** | `0-00000003-045e-0000-8e02-000000007200` | **oui** |

Les trois premiers sont exacts *du point de vue de SDL* : le GUID encode le
pilote qui expose la manette, et le troisième a été obtenu en reproduisant à
l'identique l'initialisation de Ryujinx — mêmes hints, mêmes flags, `SDL_INIT_VIDEO`
compris, relevés dans son code source. Aucun ne correspond pourtant à ce que
Ryujinx enregistre : **il remet à zéro le CRC** que SDL insère dans les octets 2
et 3 du GUID (`69b9` → `0000`). Rien dans son code public ne l'annonce, et
`GenerateGamepadId` se lit pourtant `joystickIndex + "-" + guid.ToString()`.

**La règle qui en découle, et qui commande la tâche 6 :** l'identifiant d'un
périphérique n'est PAS une propriété du périphérique, c'est une propriété de
l'émulateur qui le nomme. Un relevé fait par un outil tiers — fût-il bâti sur
le SDL même de l'émulateur — ne vaut rien. **Le seul relevé valide est celui
que l'émulateur écrit lui-même dans sa propre configuration**, une fois la
manette choisie dans son interface.

**Comment l'obtenir sur une console sans clavier ni souris.** L'interface est
atteignable à distance, et c'est la manœuvre à réutiliser pour les huit autres
émulateurs :

- une capture d'écran de la session interactive, déposée sur le partage, dit ce
  que l'émulateur affiche — son journal, lui, ne dit rien ;
- des clics envoyés par `SetCursorPos` + `mouse_event` pilotent l'interface ;
- les deux outils doivent tourner **dans la session interactive** :
  `schtasks /create … /it` puis `/run`. Lancés par WinRM, donc en session 0, ils
  ne voient ni l'écran ni les manettes — le même outil SDL y rapporte `0`
  manette alors que le pad est présent et sain ;
- la tâche doit pointer un exécutable **compilé en `/target:winexe`**, sans quoi
  la console `cmd.exe` qu'elle ouvre vole le focus et les clics se perdent ;
- les boîtes de dialogue de Ryujinx s'ouvrent centrées sur une résolution qui
  n'est pas celle de la fenêtre : la colonne d'onglets se retrouve au-dessus du
  bord de l'écran, hors d'atteinte. Il faut repositionner la fenêtre
  (`MoveWindow`) avant de pouvoir cliquer quoi que ce soit.

**Deux pièges du diagnostic, à ne pas refaire.** Le mode `trace` de Ryujinx a
produit **506 Mo** de journal en quelques minutes, saturé la machine au point
de faire expirer les commandes WinRM, et ralenti le jeu assez pour fausser
l'essai en cours : ne l'active jamais pendant une mesure de réactivité, `debug`
suffit. Et un journal lu deux secondes après le démarrage ne prouve rien —
l'absence du message d'erreur y a été prise pour un succès alors que le fichier
en comptait 272 occurrences une minute plus tard. **Compte les occurrences sur
le fichier complet, jamais sur ses premières lignes.**

---

## Tâche 2 : le schéma `[input]` d'un profil

Le bloc `[input]` existe déjà et ne porte que du déclaratif. Il doit porter ce
qui produit un fichier.

**Fichiers :**
- Modifier : `retro/profiles.py`
- Test : `tests/test_profiles.py`

**Ce qu'il faut obtenir :**

- un **gabarit** de configuration d'entrée, déclaré dans le TOML comme
  `RenderMode.config` l'est déjà — le contenu vit dans le profil, jamais dans
  le code ;
- des **jetons** que le lanceur substituera : `{pad1}` à `{pad4}` pour les
  identifiants, et de quoi rendre un joueur absent (une session à une seule
  manette ne doit pas laisser trois entrées mortes qui feraient croire à
  l'émulateur que quatre joueurs sont connectés) ;
- la **cible** : le chemin du fichier que l'émulateur lit, exprimé en chemin
  Windows, avec les variables d'environnement qu'il faut (`%APPDATA%`) ;
- la **stratégie d'écriture**, parce que les neuf émulateurs se répartissent en
  deux familles et qu'aucune généralité ne les couvre :
  - ceux qui ont un **fichier dédié aux manettes** (Cemu, Dolphin, RPCS3,
    PPSSPP, RetroArch) — on l'écrit en entier, c'est sans risque ;
  - ceux dont les manettes vivent **dans le fichier de réglages général**
    (Ryujinx, PCSX2, DuckStation, Flycast, Xemu) — l'écrire en entier
    détruirait les réglages graphiques du propriétaire.
- `steam_input` doit **disparaître ou devenir effectif**. Un champ que le code
  lit sans jamais l'appliquer est un mensonge documenté : il a fait croire
  pendant tout le diagnostic que la question des manettes était traitée.
  Décide, et **écris la raison**.

**La question ouverte, à trancher par la mesure et non par le raisonnement :**
pour la seconde famille, vaut-il mieux fusionner dans le fichier existant, ou
donner à l'émulateur un dossier de données qui appartient à `retro` ? Ryujinx
accepte `--root-data-dir` ; s'il le fait vraiment — **à vérifier sur la
machine, pas dans une documentation** — alors `retro` possède l'intégralité de
son `Config.json` sans rien écraser à personne, et la fusion JSON en C#
disparaît du problème. Regarde si les quatre autres ont un équivalent.

---

## Tâche 3 : écrire les gabarits à la synchronisation

**Fichiers :**
- Modifier : `retro/launcher.py`
- Test : `tests/test_launcher.py`

**Ce qu'il faut obtenir :**

- le gabarit déposé dans `_launcher\systems\`, à côté des plans de système et
  des `.cfg` de rendu, sous un nom dérivé de la clé du profil ;
- son chemin substitué **en Python**, comme `{render_config}` l'est déjà, et
  pour la même raison : laisser le lanceur reconstruire une convention de
  nommage créerait un second endroit où le nom du fichier serait décidé ;
- **la purge des gabarits périmés**, au même titre que les plans et les `.cfg` :
  un gabarit resté là après qu'un émulateur a changé de profil réécrirait sa
  configuration d'entrée à chaque lancement, avec un mapping d'un autre âge ;
- le gabarit est **par profil**, pas par système : la manette d'un émulateur ne
  change pas selon la console qu'il émule.

---

## Tâche 4 : substituer au lancement

**Fichiers :**
- Modifier : `retro/data/launcher/retro-launch.cs`
- Créer : `retro/data/launcher/` — la source de l'énumérateur SDL (tâche 1)
- Test : à défaut de test C#, une vérification manuelle **écrite** dans le
  rapport, session ouverte, manette branchée.

**Ce qu'il faut obtenir :**

- l'énumération SDL au lancement, **avant** de démarrer l'émulateur ;
- la substitution des jetons par les identifiants relevés, et l'écriture du
  fichier à sa cible, avec sauvegarde du précédent au premier passage ;
- **aucune panne muette** : le lanceur affiche déjà toute erreur à l'écran et
  l'écrit au journal `_launcher\journal.txt`. Le nombre de manettes vues et le
  fichier écrit y vont aussi — c'est ce qui aurait fait gagner ce diagnostic
  entier ;
- **zéro manette détectée n'est pas une erreur** : la session peut être ouverte
  sans manette. Le jeu doit démarrer quand même, et le journal doit le dire.

**Attention à un piège vérifié :** le lanceur tourne dans la session
interactive, mais une commande WinRM tourne en session 0, où SDL n'énumère
rien. Toute vérification faite par WinRM doit passer par `schtasks /IT`, sans
quoi elle rapportera `0` manette et on croira à tort que le pad est absent.

---

## Tâche 5 : le mapping par défaut, et sa surcharge

**Ce qu'il faut obtenir :**

- **par défaut, quatre manettes Xbox**, joueurs 1 à 4, sur les index 0 à 3 —
  c'est ce que demande le propriétaire, et c'est ce qu'Apollo produit ;
- une façon de **changer le mapping d'un joueur** par `retro`, sans éditer un
  TOML livré : le manifeste et les profils ont déjà chacun leur échappatoire
  utilisateur (`emulators.toml`, dossier de profils du propriétaire), et la
  troisième doit suivre **la même règle de préséance** — deux mécanismes
  différents pour la même idée seraient une source de bugs ;
- ce que `retro status` en dit. Une manette mal mappée est aujourd'hui
  invisible : le rapport doit nommer les émulateurs dont la configuration
  d'entrée n'a jamais été écrite.

---

## Tâche 6 : les neuf émulateurs, un par un

Aucun raccourci ici : chaque format est différent, chaque emplacement est
différent, et **chacun se mesure sur la machine**. Un gabarit écrit d'après un
souvenir de forum est exactement le défaut que la contrainte globale interdit.

| Émulateur | Fichier d'entrée | Famille | Auto-détecte ? |
|---|---|---|---|
| Ryujinx | `%APPDATA%\Ryujinx\Config.json` | générale | **non** (mesuré) |
| DuckStation | `settings.ini` | générale | oui (mesuré : jouable) |
| RetroArch | `autoconfig\*.cfg` | dédiée | oui |
| Dolphin | `User\Config\GCPadNew.ini` | dédiée | à établir |
| Cemu | `controllerProfiles\` | dédiée | à établir |
| PCSX2 | `inis\PCSX2.ini` | générale | à établir |
| PPSSPP | `controls.ini` | dédiée | à établir |
| RPCS3 | `config\input_configs\` | dédiée | à établir |
| Flycast | `emu.cfg` | générale | à établir |
| Xemu | `xemu.toml` | générale | à établir |

Les colonnes « famille » et « auto-détecte » de la seconde moitié du tableau
sont des **hypothèses de travail**, pas des faits : les deux seules lignes
mesurées sont Ryujinx et DuckStation. Vérifie chaque ligne avant de t'appuyer
dessus, et corrige le tableau.

**Un émulateur qui auto-détecte correctement n'a pas besoin de gabarit** —
n'en écris pas pour le plaisir de la symétrie. Mais dis-le dans le profil, et
dis pourquoi : sans cela, rien ne distingue « cet émulateur se débrouille »
d'un bloc oublié, et c'est précisément la confusion qui a laissé Ryujinx muet.

---

## Vérification finale

- [ ] Suite complète, arbre frais, sous `-W error`
- [ ] Aucun test ne touche le réseau, aucun n'exige Windows
- [ ] Aucun identifiant écrit qui n'ait été relevé sur la machine
- [ ] Sur la console, session Moonlight ouverte, manette branchée : un jeu par
      émulateur couvert, la manette répond, et la sortie du jeu se fait à la
      manette
- [ ] `_launcher\journal.txt` nomme, à chaque lancement, le nombre de manettes
      vues et le fichier de configuration écrit
- [ ] Une configuration d'émulateur modifiée à la main est bien écrasée au
      lancement suivant, et sa sauvegarde existe

## Ce que ce sous-projet ne fait pas

- **Le mapping par jeu.** Un jeu qui veut une disposition à lui est un cas
  particulier ; la console doit d'abord marcher dans le cas général.
- **Le gyroscope, le retour de force fin, le tactile.** Apollo les transmet,
  les émulateurs les gèrent inégalement, et rien de tout cela ne bloque une
  partie.
- **Steam Input.** Le pont Steam sert à lancer et à quitter ; y ajouter une
  couche de remappage par-dessus celle des émulateurs ferait deux endroits où
  un bouton est décidé.
