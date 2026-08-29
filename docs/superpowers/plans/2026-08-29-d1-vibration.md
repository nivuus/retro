# D1 — la vibration, maillon par maillon — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE —
> `superpowers:subagent-driven-development`.

**Objectif :** que la console cesse de ne rien savoir de sa vibration — savoir
lequel des trois maillons est rompu, l'écrire là où le propriétaire le lit, et
ne poser un réglage que là où il a été relevé.

**Dette :** `docs/dettes.md`, D1 — « Aucune vibration, nulle part ».

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`

**Suite de :** `docs/superpowers/plans/2026-08-28-manettes-sous-projet-e.md`,
dont D1 est le prolongement direct. Ce plan ne rouvre pas le sous-projet E : il
prend son vocabulaire (`mapping` / `mapping_where`), sa procédure
(`docs/releve-manettes.md`) et sa règle de fond, et les applique à un second
axe.

---

## Les trois maillons, et un seul est dans ce dépôt

C'est la distinction que ce plan existe pour tenir. Les confondre est l'erreur
à éviter : les trois donnent au canapé **exactement le même symptôme** — rien
ne vibre — et aucun des trois n'émet le moindre message.

| Maillon | Où il vit | Ce que ce plan en fait |
|---|---|---|
| **(a)** émulateur → SDL → ViGEmBus | **ici** — `retro/data/profiles/*.toml` | le mesure (tâche 1), puis l'écrit (tâches 2 à 4) |
| **(b)** jeu Steam → XInput sous Steam Input, que la synchronisation ÉTEINT | mesurable ici, décidé par `retro/steam/steam_input.py` | le mesure et arbitre (tâche 5) |
| **(c)** Apollo → client Moonlight | `nivuus/installer`, `docs/console-dettes.md`, **C1** | **rien** — il ne lui appartient pas (tâche 6) |

**L'ordre de C1 est imposé et non négociable** : le réglage du client Moonlight
d'abord, parce que c'est le seul des trois qui se teste **sans rien modifier**.
Ce plan ne le contourne pas — il en dépend, et la tâche 1 dit exactement en
quoi.

## Ce qui est MESURÉ, et ce qui est SUPPOSÉ

**Mesuré :**

- DuckStation porte, dans le champ `enforced` de son profil, deux liaisons de
  vibration — `LargeMotor = SDL-0/LargeMotor`, `SmallMotor = SDL-0/SmallMotor`.
  Elles n'ont pas été recopiées : **DuckStation les a écrites lui-même**, par
  son assistant, le 2026-08-29 (`docs/releve-manettes.md`).
- Elles sont **reposées à chaque lancement** (`enforced`, régime `fusion` de
  `retro/launcher.py`), donc elles sont sur la console, et pas seulement dans
  le dépôt.
- **Personne ne les a vues faire vibrer quoi que ce soit.** C'est écrit trois
  fois — dette, profil, procédure — et c'est la seule chose qu'on en sait.
- La manette **répond** dans DuckStation depuis la clôture de D3 : un bouton a
  été vu agir, témoin humain à l'appui (Crash Team Racing).

**Supposé, et à ne jamais traiter autrement :**

- Le tableau des neuf cibles de la dette (`controllerProfiles\`,
  `GCPadNew.ini`, `emu.cfg`, `PCSX2.ini`, `controls.ini`, `autoconfig\*.cfg`,
  `input_configs\`, `xemu.toml`, `config.yml`) est **explicitement non
  mesuré** : il reprend le tableau de la tâche 6 du plan des manettes, qui se
  donne lui-même pour des hypothèses de travail. Les deux seules lignes
  mesurées de ce tableau sont l'émulateur personnel et DuckStation.
- Qu'un émulateur ait un réglage de rumble, et que ce réglage vive dans sa
  configuration d'entrée, est une hypothèse par émulateur — pas un fait.
- Que la vibration survive à l'extinction de Steam Input est une **question**,
  pas une crainte : personne n'a essayé.

## Ce que la lecture du code a trouvé, et qui précise la dette

Quatre faits, relevés dans le dépôt en écrivant ce plan. Aucun n'exige la
machine ; ils changent tous ce que la tâche 1 doit faire.

1. **La clé qui a clos D3 est une cause candidate de l'absence de vibration.**
   `[Pad1] ForceAnalogOnReset = false` est dans `enforced` : la manette démarre
   donc en mode **numérique**. Une manette PlayStation ne porte ses moteurs que
   dans son type analogique — ce que ce dépôt n'a **pas** mesuré, et qui doit
   être lu dans la source de DuckStation, jamais déduit. Conséquence : « il
   suffit de jouer » reste vrai, mais un résultat **négatif** aura deux causes
   candidates au lieu d'une, et la seconde est déjà dans le fichier. La bascule
   est gratuite au canapé — le profil lie `Analog = SDL-0/Guide`, c'est-à-dire
   le bouton Guide du pad.
2. **DuckStation n'écrit AUCUNE clé `Type`**, et le profil ne lui en ajoute pas
   (le test `tests/test_donnees.py` l'interdit nommément). Le type de manette
   est donc le **défaut** de DuckStation, que personne n'a relevé. S'il désigne
   un type sans moteurs, les deux liaisons sont justes et inertes — troisième
   cause candidate du même symptôme.
3. **Le maillon Steam a un couple section/clé, et il est déjà sous les yeux du
   dépôt.** `tests/fixtures/localconfig-extrait.vdf` porte, **sur l'entrée même
   que `retro` possède**, à côté de `UseSteamControllerConfig` :
   `SteamControllerRumble = "-1"` et `SteamControllerRumbleIntensity = "320"`.
   L'en-tête de la fixture dit qu'elle reproduit **la forme du fichier réel
   relevé sur la console le 2026-08-28**. Et la docstring de
   `steam_input.desactiver` annonce explicitement que « les réglages voisins du
   même jeu — vibration, intensité — sont conservés ». **Ce qui n'est pas
   mesuré :** ce que valent `-1` et `320`, et si `UseSteamControllerConfig = 0`
   les rend simplement sans objet. La fixture est synthétique quant au contenu :
   sa forme est un relevé, ses valeurs ne prouvent rien de l'effet.
4. **`retro status` ne dit RIEN de la vibration** — aucune section, aucun
   problème, aucune ligne. L'aveu de la dette vit uniquement dans des
   commentaires TOML, que personne ne lit depuis un canapé. C'est exactement
   l'écart que le sous-projet E reproche à `steam_input = "required"` : un état
   consigné là où il ne sert à rien.

Et une fragilité de forme, qui n'est pas un détail dans ce dépôt : **le bloc
`[input]` ne refuse aucune clé inconnue**, contrairement à `render` et
`render.<mode>` (`_CLES_MODE`, `_CLES_RENDER` dans `retro/profiles.py`). Un
`rumbl = "vu"` mal orthographié retomberait en silence sur le défaut — une
valeur fausse se comportant exactement comme l'absence de valeur, une fois de
plus.

---

## Contraintes globales

- **Python 3.11 minimum.** Aucun test ne touche le réseau ni n'exige Windows.
- **Les chemins Windows sont des `str`**, jamais des `pathlib.Path` ;
  `pathlib.PureWindowsPath` pour toute comparaison.
- **Une valeur fausse se comporte exactement comme l'absence de valeur.** Aucun
  message, aucun journal, aucun symptôme distinct. C'est la règle de fond du
  dépôt, et elle commande tout ce plan.
- **D'où vient une valeur.** Jamais d'une documentation, jamais des **chaînes**
  d'un binaire — celles-ci donnent les **libellés de l'interface**, et les
  recopier a déjà coûté deux tentatives sur `CropMode` (D2). Une valeur vient
  de la **source** de l'émulateur, ou d'un **relevé** que l'émulateur a écrit
  lui-même. Chaque tâche qui fait poser une valeur dit laquelle des deux.
- **Un témoin humain, ou rien.** « Ça vibre » ne se déduit d'aucun fichier :
  c'est un état qui exige quelqu'un, la manette en main, devant la télévision.
  Aucun champ, aucun test, aucun rapport ne doit pouvoir l'affirmer sans lui.
- **Un test qui passerait quelle que soit l'implémentation est un défaut.**
- **Rien n'est écrit dans une configuration d'émulateur sans sauvegarde ni
  en-tête disant qui l'a écrite** — le mécanisme existe (`fusion`), il ne se
  réinvente pas.
- Vérifier les mutations avec `PYTHONDONTWRITEBYTECODE=1`.

---

## Tâche 1 : jouer — la mesure gratuite du maillon (a)

C'est la première tâche parce qu'elle ne coûte rien et qu'elle commande les
autres : DuckStation porte déjà ses deux liaisons, reposées à chaque
lancement. **Rien n'est à écrire pour mesurer.**

**Étape de mesure — sur la console, pas ici.** Elle n'est jouable ni depuis
cette session ni depuis l'hôte : elle exige la télévision, une session
Moonlight et une main sur la manette.

**Ce qu'il faut avant de commencer :**

- **C1 d'abord, et c'est ce qui rend la mesure interprétable.** Si le réglage
  de vibration du client Moonlight est éteint, **rien ne vibrera nulle part**,
  y compris dans un DuckStation parfaitement configuré. Un résultat POSITIF —
  ça vibre — est concluant seul et clôt le maillon (a). Un résultat NÉGATIF ne
  vaut rien tant que C1 n'a pas dit que le client, lui, est prêt à vibrer.
  L'ordre imposé de `docs/console-dettes.md` n'est donc pas une politesse :
  c'est ce qui donne un sens au « non ».
- Une **session Moonlight ouverte, manette branchée au client** — le pad
  n'existe que pendant une session, et la vibration remonte par ce chemin.
  Attention : la voie Moonlight était **bloquée** le 2026-08-29,
  `403 Permission denied` au `/launch`, le client appairé portant
  `perm=0x3000000` là où les clients fonctionnels portent `0x7131f00`
  (`docs/releve-manettes.md`). Tant que ce `perm` n'est pas réglé, aucun essai
  au flux ne passe — et le contournement par ViGEmBus qui a servi au relevé
  des liaisons **ne convient pas ici** : sans client, il n'y a rien à faire
  vibrer.
- **Un jeu dont on sait qu'il vibre.** Le choix n'est pas neutre : un titre
  sans vibration donnerait un « non » qui ne dit rien de la chaîne. Crash Team
  Racing est le jeu de référence de D3 — c'est celui dont on sait que les
  boutons répondent — mais il ne prouvera rien de la vibration si le titre n'en
  émet pas. **Deux titres au minimum**, et l'un d'eux choisi pour sa vibration.

**Ce qu'il faut obtenir :**

- **Le fait**, sous la seule forme qui compte : quelqu'un a senti, ou n'a pas
  senti, la manette vibrer, dans tel jeu, à tel moment de jeu.
- **La bascule analogique essayée**, si rien ne vibre : appuyer sur **Guide**
  (`Analog = SDL-0/Guide`), qui bascule le mode de la manette, et rejouer la
  même scène. C'est gratuit, ça ne modifie aucun fichier, et c'est ce qui
  départage la cause n° 1 de la découverte ci-dessus.
- **Le type de manette de DuckStation, lu dans sa SOURCE** — jamais dans les
  chaînes du binaire : quel type est le défaut quand aucune clé `Type` n'est
  écrite, et lequel des types porte des moteurs. Cette lecture-là se fait
  ailleurs qu'à la console, et elle peut être faite avant la partie.
- **Trois conclusions possibles, et une seule s'écrit :**
  1. *ça vibre* → le maillon (a) est clos pour DuckStation, et le maillon (c)
     l'est du même coup pour ce chemin — la vibration a traversé Apollo et le
     client pour arriver dans la main. C'est la conclusion la plus riche des
     trois ;
  2. *ça ne vibre qu'en mode analogique* → l'arbitrage global de
     `ForceAnalogOnReset` se rouvre, et ce n'est plus une question de
     vibration : c'est un choix entre « CTR répond » et « les titres
     analogiques vibrent ». Il appartient au propriétaire, en question fermée,
     comme l'a été celui de D2 ;
  3. *ça ne vibre dans aucun mode, C1 dit le client prêt* → le maillon (a) est
     rompu, et l'inconnue redevient le type de manette ou le chemin SDL. Ne
     rien écrire dans le profil à ce stade : il n'y a pas encore de valeur.

**Ce qu'il ne faut surtout pas faire :** conclure depuis un fichier. Aucune
lecture de `settings.ini`, aucune survie de clé, aucune ligne de journal ne
prouve une vibration — « la clé a survécu » ne prouve même pas « la clé est
reconnue », mesuré sur cet émulateur avec une clé inventée (D2).

---

## Tâche 2 : la vibration devient un champ, pas un commentaire

Aujourd'hui, l'état de la vibration de chaque profil vit dans un commentaire
TOML. C'est ce que la dette a pu poser sans mesure, et c'était le bon geste ;
c'en est aussi la limite — aucun code ne le lit, `retro status` ne le dit pas,
et rien n'empêche un profil de se contredire. Le sous-projet E a déjà fait ce
chemin une fois, de la prose de `steam_input` vers `mapping` : **suivre le
même, à l'identique.**

Cette tâche ne dépend d'aucune mesure : elle range ce qu'on sait déjà.

**Fichiers :**
- Modifier : `retro/profiles.py`
- Modifier : `retro/data/profiles/*.toml` (les dix)
- Test : `tests/test_profiles.py`

**Ce qu'il faut obtenir :**

- un champ `[input] rumble`, à **vocabulaire fermé**, sur le modèle exact de
  `MAPPINGS` (`retro/profiles.py:94-103`). Cinq états, et il en faut cinq —
  chacun dit une chose que les quatre autres ne disent pas :

  | État | Ce qu'il affirme | Qui peut l'écrire |
  |---|---|---|
  | `inconnu` (**défaut**) | personne n'a mesuré | tout le monde |
  | `a-relever` | mesuré muet, **aucune clé relevée** | après un essai au canapé |
  | `pose` | un réglage est posé, **jamais vu agir** | après un relevé écrit par l'émulateur |
  | `vu` | quelqu'un a **senti** la manette vibrer | témoin humain, et lui seul |
  | `absent` | mesuré : cet émulateur **n'a aucun réglage** de rumble | après lecture de la SOURCE |

- `inconnu` est le défaut, pour la raison qui a fait choisir `MAPPING_INCONNU` :
  tout autre défaut affirmerait sur neuf émulateurs quelque chose que personne
  n'a regardé ;
- `pose` est **l'état de DuckStation aujourd'hui**, et aucun des quatre autres
  ne le décrit : `vu` mentirait, `a-relever` effacerait un relevé fait, `absent`
  serait faux, `inconnu` effacerait la mesure. C'est très exactement la
  situation qui a fait naître `MAPPING_RELEVE` le 2026-08-29 ;
- `absent` existe pour la même raison que `fill_absent` dans les blocs de
  rendu : « il n'y a rien à régler, et c'est mesuré » n'est pas « personne n'a
  regardé » ;
- un champ `rumble_where`, **exigé** pour `a-relever`, `pose` et `vu` — le
  fichier et la section que le propriétaire ouvrira, comme `mapping_where`. Il
  ne porte **jamais** un nom de clé deviné ;
- un champ `rumble_witness`, **exigé pour `vu` et pour lui seul** : qui a senti,
  quel jeu, quelle date. C'est la traduction de la contrainte « un témoin
  humain, ou rien » — et `vu` est le seul état de ce vocabulaire qui ne puisse
  jamais être déduit d'un fichier ;
- **le refus des clés inconnues dans `[input]`**, sur le modèle de `_CLES_MODE`
  et `_CLES_RENDER`. Sans lui, `rumbl = "vu"` retombe en silence sur le défaut,
  et le rapport se tait sur le seul émulateur concerné ;
- les dix profils livrés déclarent leur état : **`pose` pour DuckStation**
  (`rumble_where` = son `settings.ini`, section `[Pad1]`), **`inconnu` pour les
  neuf autres**. Aucun autre état n'est écrit par cette tâche — aucune mesure
  ne l'autorise encore.

**Ce que devient la note d'aveu des neuf profils :** elle **reste**, et elle
change de rôle. Le champ porte désormais **l'état** ; le commentaire porte le
**pourquoi** — que le rumble est un réglage de la configuration d'entrée et non
de la ligne de commande, que la cible est une hypothèse du plan des manettes et
non un fait, et que la clé n'a été relevée dans aucun fichier que l'émulateur
ait écrit. Le jour où un relevé aboutit sur un émulateur, c'est le **champ** qui
bascule et la **cible supposée** qui devient mesurée dans le commentaire : la
note ne disparaît pas, elle cesse d'être un aveu pour devenir une provenance.

---

## Tâche 3 : `retro status` dit où en est la vibration

Un rapport qui se tait sur une manette muette est précisément ce que le
sous-projet E reproche au reste du dépôt. Il se tait aujourd'hui sur une
manette qui ne vibre pas.

**Fichiers :**
- Modifier : `retro/status.py`
- Test : `tests/test_status.py`

**Ce qu'il faut obtenir :**

- une section **Vibration**, bâtie sur `_lignes_manettes`
  (`retro/status.py:794`) : une formulation par état, cinq états, et pour les
  trois qui nomment un fichier, le fichier ;
- un **problème** pour le seul état `a-relever`, exactement comme
  `_probleme_manettes` n'en lève que pour `MAPPING_A_RELEVER` : c'est le seul
  qui dise « quelqu'un a constaté, et il y a un geste à faire ». `inconnu` est
  **nommé sans être accusé** ; `pose` est nommé aussi, et c'est important — il
  dit « un réglage est là, personne ne l'a vu agir », qui est l'état exact de
  DuckStation et qu'aucun rapport ne sait dire aujourd'hui ;
- le renvoi vers la procédure de relevé, comme `PROCEDURE_RELEVE`
  (`retro/status.py:139`) le fait déjà pour le mapping ;
- **aucune ligne qui affirme que la vibration marche.** Le rapport rend ce que
  les profils déclarent, et un profil ne déclare `vu` qu'avec un témoin.

---

## Tâche 4 : le test évolue sans devenir complaisant

`tests/test_donnees.py::test_chaque_profil_livre_dit_ou_en_est_sa_vibration`
(ligne 1034) exige aujourd'hui trois mots dans les commentaires d'un profil :
« vibration », « d1 », « mesur ». C'est la bonne garde tant que rien n'est
mesuré — et c'est une garde qui, une fois le champ posé, passerait pour
n'importe quelle implémentation, y compris une qui mentirait dans le champ.

**Fichiers :**
- Modifier : `tests/test_donnees.py`
- Test : le même fichier

**Ce qu'il faut obtenir :**

- **la garde de la note se désarme profil par profil**, sur le modèle **exact**
  de `test_chaque_profil_livre_dit_ou_en_est_son_amorcage` (ligne 585), qui
  saute le profil qui PORTE un bloc `[bootstrap]` : le profil qui déclare un
  état **mesuré** (`pose`, `vu`, `absent`) n'a plus d'aveu à écrire — son champ
  le dit, et `retro status` le relaie. Ceux qui restent en `inconnu` ou
  `a-relever` gardent l'exigence entière ;
- **et trois gardes structurelles qui, elles, ne se désarment jamais** — ce sont
  elles qui empêchent le test de devenir tautologique :
  1. `rumble` appartient au vocabulaire fermé, `rumble_where` est présent pour
     les états qui nomment un fichier, `rumble_witness` pour `vu` — un profil
     qui déclare `vu` sans témoin est **refusé au chargement**, pas seulement
     signalé ;
  2. un profil qui déclare `pose` ou `vu` doit **porter effectivement un
     réglage de vibration** — pour DuckStation, les deux liaisons `LargeMotor`
     et `SmallMotor` dans `enforced`. Déclarer un état posé sans rien poser doit
     rendre le test ROUGE. La garde existante des deux liaisons (ligne 985) s'y
     rattache : elle cesse d'être une vérification isolée pour devenir la preuve
     matérielle de l'état déclaré ;
  3. aucun profil ne déclare `vu` **sans** que le témoin soit daté et nomme un
     jeu. La formule libre est acceptable ; l'absence ne l'est pas.
- **le désarmement doit être vérifié par mutation** : passer un profil de
  `inconnu` à `pose` sans lui donner de réglage doit faire échouer la suite. Un
  test qui ne casse pas sous cette mutation n'a rien gardé.

---

## Tâche 5 : le maillon (b) — la vibration survit-elle à l'extinction de Steam Input ?

C'est la question que la dette pose et que personne n'a essayée. Elle est
mesurable ici, et elle dépend d'un choix de `retro/steam/steam_input.py` : la
synchronisation **éteint** Steam Input sur toutes les entrées que `retro`
possède, et personne ne sait ce que cette extinction fait au retour de force.

**Fichiers :**
- Lire : `retro/steam/steam_input.py`, `tests/fixtures/localconfig-extrait.vdf`
- Modifier, **seulement si la mesure le dit** : `retro/steam/steam_input.py`
- Test : `tests/steam/test_steam_input.py`

**Étape de mesure — sur la console.** Elle ne se fait pas ici : elle exige
Steam, un jeu Steam qui vibre, et une main sur la manette.

**Ce qu'il faut obtenir :**

- **le relevé du fichier réel**, d'abord : `localconfig.vdf` du compte de la
  console porte-t-il, sur les entrées que `retro` possède,
  `SteamControllerRumble` et `SteamControllerRumbleIntensity` ? La fixture dit
  que oui **en forme** ; le fichier réel est la seule preuve. Steam étant fermé
  pendant la lecture, comme pour toute manipulation de ce fichier ;
- **la mesure croisée**, sur **un vrai jeu Steam** — pas un émulateur, sinon
  c'est le maillon (a) qu'on mesure :

  | Condition | Ce qu'on note |
  |---|---|
  | Steam Input **actif** (`UseSteamControllerConfig` absent ou ≠ `0`) | ça vibre, oui ou non |
  | Steam Input **éteint** par `retro sync` (`= "0"`) | ça vibre, oui ou non |

  Deux lignes, un seul jeu, la même scène. C'est la mesure entière ;
- **la provenance de toute valeur qu'on poserait ensuite** : `-1` et `320` sont
  des valeurs **lues dans un fichier**, pas comprises. Si la mesure conclut
  qu'il faut écrire quelque chose, la valeur se relève de la seule façon
  valide — la poser **dans l'interface de Steam**, fermer Steam, relire le
  fichier, et recopier ce que Steam a écrit. Jamais un wiki, jamais une
  déduction sur le signe de `-1` ;
- **l'arbitrage, en question fermée au propriétaire**, si et seulement si la
  mesure montre que l'extinction tue la vibration : entre une manette qui
  répond dans les émulateurs (l'extinction, mesurée indispensable le
  2026-08-28) et une manette qui vibre dans les jeux Steam, lequel — et sur
  quelles entrées ? `retro` ne possède que les raccourcis d'émulateur ; un jeu
  Steam natif n'est pas à lui, et il n'a pas à y toucher ;
- **si la mesure conclut que la vibration survit**, alors le maillon (b) est
  clos et rien n'est à écrire : ce résultat-là se consigne dans la dette et
  dans la docstring de `steam_input.py`, qui promet aujourd'hui de préserver
  des réglages de vibration dont personne ne sait s'ils servent.

---

## Tâche 6 : le maillon (c) n'appartient pas à ce dépôt

**Aucun fichier de ce dépôt n'est modifié par cette tâche**, et c'est le
propos.

**Ce qu'il faut obtenir :**

- la trace, dans `docs/dettes.md` D1, de ce que la tâche 1 a appris du maillon
  (c) — car une vibration **sentie** dans DuckStation prouve du même coup que
  le chemin Apollo → client → manette fonctionne, et cela intéresse C1 plus que
  ce dépôt ;
- **rien d'autre.** Le réglage du client Moonlight, la procédure que le
  propriétaire joue au canapé, et le `perm=0x3000000` qui bloque le `/launch`
  vivent dans `nivuus/installer`, `docs/console-dettes.md`, C1. Y toucher
  depuis ici créerait un second endroit où la même chose serait décidée.

---

## Tâche 7 : les huit autres émulateurs — la procédure, pas les valeurs

**Fichiers :**
- Modifier : `docs/releve-manettes.md`
- Modifier : `retro/data/profiles/*.toml`, **au fur et à mesure des relevés**

**Cette tâche est BLOQUÉE par deux choses, et l'ordre n'est pas négociable :**

1. **La tâche 1 d'abord.** Tant qu'aucune vibration n'a été sentie nulle part,
   relever une clé de rumble sur un huitième émulateur revient à écrire huit
   valeurs dont aucune ne pourra être vérifiée : le symptôme sera identique
   qu'elles soient justes ou fausses.
2. **D4 ensuite — et c'est l'adhérence à ne pas rater.** Basculer Apollo en
   DualShock (dette D4, `nivuus/installer` C2) change le VID/PID, **donc le
   GUID SDL**, donc tous les identifiants que les configurations d'entrée
   contiennent. Une console qui bascule en DualShock avec des gabarits écrits
   pour un X360 redevient muette partout, **en silence**. Écrire huit gabarits
   de vibration avant D4, c'est les réécrire après.

   **Sauf pour DuckStation, et c'est mesuré :** ses liaisons ne portent qu'un
   **index** (`SDL-0`), jamais un GUID — un changement de type de pad ne les
   casse donc pas mécaniquement. C'est pourquoi la tâche 1 peut, elle, passer
   **avant** D4. Ce qui les casserait, c'est un pad **de plus** énuméré avant
   celui d'Apollo.

   **L'ordre est donc : C1 (client Moonlight) → tâche 1 (DuckStation) → D4
   (type de pad) → tâche 7 (les huit autres).** Inverser, c'est déboguer deux
   inconnues à la fois — la même phrase que D4 écrit déjà pour le mouvement.

**Ce qu'il faut obtenir, le jour où le blocage est levé :**

- **une section de `docs/releve-manettes.md`** consacrée à la vibration, sur le
  modèle de celle du mapping : activer la vibration **dans l'interface de
  l'émulateur**, le fermer, relire le fichier qu'il a écrit, et **recopier ce
  qu'il a écrit lui-même**. C'est le seul relevé valide, pour la même raison
  qu'un identifiant de manette : la clé de rumble n'est pas une propriété de la
  manette, c'est une propriété de l'émulateur qui la nomme ;
- **la vérification que la cible supposée est la bonne**, avant tout : les neuf
  lignes du tableau de la dette sont des **hypothèses**. Le fichier que
  l'émulateur écrit réellement est ce qu'on regarde ; s'il diffère, **c'est le
  tableau de la dette qui est faux**, et il se corrige ;
- **le piège RetroArch, déjà documenté ailleurs :** RetroArch **réécrit** son
  `retroarch.cfg` en quittant (constaté pour D2, qui éteint pour cette raison
  la mise à l'échelle entière explicitement). Une clé de rumble posée là est
  soumise au même sort, et un régime « si-absent » ne la reposerait jamais ;
- **le cas Vita3K, en amont de tous les autres** : il est hors de portée tant
  qu'aucune cible écrivable ne désigne son `config.yml`. Le dire, ne pas
  l'essayer ;
- **rien pour un émulateur dont le relevé n'a pas abouti.** Le profil passe à
  `a-relever` avec son `rumble_where`, `retro status` le nomme, et **aucune
  clé n'est écrite**. Un profil à quatre émulateurs mesurés vaut mieux qu'un
  profil à neuf dont cinq sont faux.

---

## Vérification finale

- [ ] Suite complète, arbre frais : `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -W error`
- [ ] Aucun test ne touche le réseau, aucun n'exige Windows
- [ ] **Aucune clé de rumble écrite qui n'ait été relevée sur la machine**, ou
      lue dans la source de l'émulateur — et le profil dit laquelle des deux
- [ ] Aucun profil ne déclare `vu` sans témoin humain daté
- [ ] La mutation « passer un profil en `pose` sans lui donner de réglage »
      fait échouer la suite
- [ ] `retro status` nomme les dix profils sur l'axe de la vibration, et ne
      lève un problème que pour `a-relever`
- [ ] `docs/dettes.md` D1 dit, maillon par maillon, ce qui a été mesuré et ce
      qui reste supposé — le tableau des neuf cibles y est corrigé ou confirmé
      ligne par ligne, jamais laissé tel quel avec un air de fait

## Ce que ce plan ne fait pas

- **Le retour de force FIN** — intensité, courbes, effets par jeu. Le plan des
  manettes le range déjà dans ce qu'il ne fait pas, et il avait raison : c'est
  un réglage de confort. Ce plan traite l'absence TOTALE, qui est autre chose.
- **Le maillon (c).** Le réglage du client Moonlight, la procédure au canapé et
  le `perm=0x3000000` du client appairé appartiennent à `nivuus/installer`,
  `docs/console-dettes.md`, C1. Ce plan en dépend et ne l'exécute pas.
- **Le changement de type de pad (D4).** Il se décide dans `nivuus/installer`
  (C2). Ce plan dit seulement dans quel ordre les deux se font, et pourquoi
  l'inverser coûterait huit relevés.
- **L'arbitrage de `ForceAnalogOnReset`.** S'il faut le rouvrir, c'est une
  question fermée posée au propriétaire — « les titres analogiques qui vibrent,
  ou Crash Team Racing qui répond ? » — pas une décision d'agent.
- **Écrire une clé de rumble pour les huit émulateurs non mesurés.** C'est la
  seule chose que ce plan refuse explicitement de faire vite : une clé
  plausible produirait exactement le symptôme d'aujourd'hui, en donnant en plus
  l'impression que le problème est traité.
- **Toucher `docs/dettes.md` avant que les tâches aient produit quelque
  chose.** La dette se met à jour avec des mesures, pas avec des intentions.
