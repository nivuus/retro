# Dettes connues

Ce que la console ne fait pas encore, et que personne n'a planifié. Un plan
sous `docs/superpowers/plans/` décrit un travail engagé ; ce fichier décrit un
manque constaté, pour qu'il ne se redécouvre pas trois fois.

Chaque entrée dit **ce qui a été constaté**, **où ça se joue** dans le code, et
**ce que ça coûte aujourd'hui** — vu du canapé, parce que c'est de là que le
défaut se voit.

Les dettes qui débordent sur l'invité Windows (Apollo, le flux, le bureau) ont
leur pendant dans `nivuus/installer` :
`docs/console-dettes.md`.

---

## D1 — Aucune vibration, nulle part

**Constaté le 2026-08-28.** La manette ne vibre ni dans les émulateurs, ni dans
les jeux Steam, ni depuis le client Moonlight. Les trois se ressemblent mais ne
sont pas le même défaut, et rien ne dit aujourd'hui lequel est rompu :

| Chemin | Ce qu'il faudrait vérifier |
|---|---|
| Émulateur → SDL → ViGEmBus | aucun profil ne pose de réglage de rumble ; la plupart des émulateurs le veulent activé explicitement dans leur configuration d'entrée |
| Jeu Steam → XInput | passe par Steam Input, que la synchronisation **éteint** désormais (`retro/steam/steam_input.py`) — à mesurer : le retour de force survit-il à cette extinction ? |
| Apollo → client Moonlight | la vibration remonte du pad virtuel vers le client ; c'est le maillon hors de ce dépôt, voir `docs/console-dettes.md` de `nivuus/installer` |

**Où ça se joue ici :** la section `[input]` des profils
(`retro/data/profiles/*.toml`) et les gabarits de configuration d'entrée que le
sous-projet E écrit. Le rumble est un réglage de cette configuration, pas de la
ligne de commande : il suit exactement le chemin déjà tracé pour le mapping.

**Ce que ça coûte :** rien ne bloque une partie, mais une console de salon dont
la manette ne vibre jamais passe pour un émulateur, pas pour une console.

**Précaution :** le plan des manettes range « le retour de force fin » dans ce
qu'il ne fait pas — il parlait du réglage d'intensité. L'absence **totale** de
vibration est autre chose, et n'a jamais été mesurée maillon par maillon comme
l'a été le masquage Steam Input.

---

## D2 — Rien ne garantit une image maximale sans déformation

**Constaté le 2026-08-28.** L'objectif énoncé — chaque émulateur occupe le plus
possible de l'écran **sans étirer l'image** — n'est tenu par aucun code. Ce qui
existe traite deux questions voisines, et ni l'une ni l'autre n'est celle-là :

- `retro/render.py` mesure la résolution de la **session** au lancement, ce qui
  évite l'image étirée d'une résolution figée à la synchronisation. C'est le
  bon patron, mais il ne décide d'aucun cadrage.
- Les modes `native` / `full` choisissent une résolution interne et un ratio
  d'époque (`aspect_ratio_index` dans `retroarch.toml`, `AspectRatio` dans
  `dolphin.toml`). Un ratio d'époque **correctement** rendu sur un écran 16:9
  laisse des bandes noires : c'est voulu, et ce n'est pas de la déformation.

Ce qui manque est le troisième réglage, celui du **remplissage** : étirement
entier (integer scaling), mise à l'échelle sans déformation, et la politique
qui dit lequel s'applique par système.

**Où ça se joue :** `retro/render.py` (le mode est déjà substitué au lancement
par jeton `{render_config}`, donc l'endroit existe) et les blocs
`[system.render.*]` de chaque profil.

**Le cas dur, déjà documenté :** DuckStation n'expose **aucun** réglage de
rendu en ligne de commande dans la révision épinglée — dix-sept arguments,
aucun n'en est un (`duckstation.toml`, la note en bas de `[[system]]`). Pour
lui, ça devra passer par son `settings.ini`, donc par le mécanisme d'amorçage,
donc en écrasant potentiellement un réglage du propriétaire — ce que cet outil
ne fait pas aujourd'hui. À arbitrer avant d'écrire une ligne.

**Ce que ça coûte :** l'image est ce que l'émulateur a décidé tout seul. Sur
neuf émulateurs configurés par neuf équipes différentes, ce n'est pas une
console : c'est neuf comportements.

---

## D3 — DuckStation : la manette reste muette sur Crash Team Racing

**Constaté le 2026-08-28**, après les correctifs de manette du même jour
(retrait de `SDL_GAMECONTROLLER_IGNORE_DEVICES` par le lanceur, extinction de
`UseSteamControllerConfig` à la synchronisation). Le jeu démarre — c'était le
défaut précédent, et il est réglé — mais **la manette ne répond pas** dans
DuckStation.

### Ce qui a été MESURÉ le 2026-08-29, sur l'invité

Relevé sur `NIVUUS-WIN` (`provision_version = B1`, donc deux versions derrière
le payload courant), DuckStation v0.1-11609, par lectures WinRM depuis l'hôte —
aucune écriture dans l'invité. Ce canal n'est pas ouvert à tout le monde : les
constats ci-dessous sont donc à prendre comme un relevé daté, à re-mesurer par
qui en a l'accès plutôt qu'à croire sur parole.

1. **`settings.ini` ne porte aucune manette.** Il est, sur la console, octet
   pour octet le fichier que l'amorçage a posé — commentaires compris —
   augmenté de la seule section `[BIOS]` ajoutée à la main. **Aucune section
   `[Pad1]`, aucune clé d'entrée.** Sa sauvegarde `settings.ini.bak-*` porte le
   même contenu : rien n'a été perdu, il n'y a simplement jamais rien eu.
2. **DuckStation ne réécrit jamais ce fichier.** `settings.ini` datait du 28/08
   à 13:21 quand `playtime.dat` datait du même jour à 18:55 : il a joué cinq
   heures et demie après la dernière écriture sans y toucher. Sous
   `-batch -nogui`, il ne persiste pas ses réglages — donc rien ne répare
   `[Pad1]` après coup.
3. **La cause est le correctif du défaut précédent.** L'exécutable porte une
   page d'assistant nommée **« Controller Setup »**, et l'appariement
   automatique n'existe que comme geste d'interface (`Automatic Mapping`,
   `Automatic mapping failed, no devices are available`). Or l'amorçage pose
   `SetupWizardIncomplete = false` pour qu'un jeu démarre sans clavier : cela
   saute l'assistant, donc cette page, donc le seul geste qui aurait écrit
   `[Pad1]`. **Les deux réglages sont nécessaires** ; c'est la procédure de
   relevé qui les concilie, en rouvrant l'assistant une fois.
4. **La forme des clés, lue dans l'exécutable livré**, contredit ce que cette
   entrée supposait : ce sont des clés de bouton **nues** (`Square`,
   `Triangle`, `LLeft`, `RUp`…) sous des sections `Pad1`…`Pad8`, et **non** des
   clés `Bindings/…` — cette dernière forme est celle de PCSX2 et est absente
   du binaire de DuckStation. Les valeurs suivent `SDL-{}/{}` ou
   `XInput-{}/{}`.
5. **L'identifiant ne porte qu'un INDEX, jamais un GUID.** C'est une différence
   de fond avec l'émulateur personnel (`<index>-<GUID>`), et elle **desserre le
   couplage avec D4** : changer le type de pad ne réécrit pas mécaniquement les
   liaisons de DuckStation. À confirmer avant de s'en servir, mais c'est ce que
   le binaire dit.

### Ce qui n'a PAS pu être mesuré, et pourquoi

**Les valeurs des liaisons.** Aucune manette n'était connectée au moment du
relevé : le pad d'Apollo (`USB\VID_045E&PID_028E`) et une DualShock 4
(`VID_054C&PID_05C4`) figurent tous deux dans les périphériques de l'invité,
avec l'état `Unknown` — c'est-à-dire absents. Le pad n'existe que pendant une
session Moonlight, et DuckStation aurait répondu mot pour mot « Automatic
mapping failed, no devices are available ».

**Toute valeur non relevée sur la machine est fausse :** DuckStation n'émet
aucun message quand une liaison ne correspond à rien, et la manette reste muette
exactement comme si le fichier était vide. Une valeur recopiée d'une recette est
donc indiscernable de l'absence de valeur, à l'œil comme au journal.

### Ce qui a été fait le 2026-08-29

- **Le fait n° 4 du plan des manettes est rectifié** : DuckStation ne « détecte
  pas bien tout seul », et le tableau de sa tâche 6 le dit désormais.
- **Les neuf profils déclarent l'état du relevé de leur manette** —
  `[input] mapping`, valant `auto`, `a-relever` ou `inconnu`, défaut `inconnu`.
  Le champ ne porte JAMAIS un identifiant : il porte l'état du relevé, seule
  chose qu'on puisse écrire sans avoir mesuré. DuckStation vaut `a-relever` ;
  les huit autres valent `inconnu`, parce que personne ne les a mesurés.
- **`retro status` a une section « Manettes »**, avec trois formulations, et
  fait du seul `a-relever` un problème nommant le fichier à ouvrir, la
  procédure à jouer, et la phrase qui empêche la fausse correction : « une
  liaison qui ne correspond à aucun périphérique est ignorée en silence ».
- **Le squelette `[Pad1]` est posé dans le bloc `[bootstrap]`**, à l'endroit
  exact où DuckStation le lira, **entièrement en commentaire** — avec la forme
  relevée, la cause mesurée, et les valeurs marquées « À RELEVER ». Un test
  refuse toute ligne active sous une section `[Pad1]`, et tout retour à la
  forme `Bindings/…` mesurée fausse.
- **La procédure de relevé est écrite** : `docs/releve-manettes.md`. Elle ne
  demande de recopier aucune valeur — elle rouvre l'assistant de DuckStation le
  temps d'un appariement automatique, session ouverte et manette branchée, et
  fait écrire `[Pad1]` par DuckStation lui-même. C'est le seul relevé valide.

### Ce qui reste

**Jouer la procédure**, manette en main. C'est la seule partie qui exige une
session Moonlight, et elle ne peut être faite ni depuis l'hôte ni sans pad.
Ensuite seulement viendra le gabarit à jetons du sous-projet E (tâche 3), sur
le patron de `{render_config}`.

**Ce que ça coûte aujourd'hui :** le seul émulateur PlayStation de la console
est injouable. `retro status` le dit désormais ; il ne le répare pas.

## D4 — Ni capteur de mouvement, ni manette PlayStation

**Constaté le 2026-08-28.** Les émulateurs qui en ont besoin — PPSSPP, PCSX2,
RPCS3, un futur PS Vita (D5) — ne reçoivent aucune donnée de gyroscope, et rien
dans la chaîne ne prétend en transmettre.

La cause est en amont : **Apollo annonce un Xbox 360** (`Gamepad 0 will be
Xbox 360 controller (default)`, relevé dans `sunshine.log`), et un pad X360 n'a
ni gyroscope, ni tactile, ni retour haptique fin. Apollo sait émuler une
DualShock ; c'est un réglage côté invité, donc
`docs/console-dettes.md` de `nivuus/installer`.

**Ce que ça implique ici, et qui n'est pas gratuit :** changer le type de pad
change le VID/PID, donc **le GUID SDL**, donc tous les identifiants que les
configurations d'entrée contiennent. C'est précisément le fait n° 2 du plan des
manettes : « cet identifiant n'est pas prévisible ». Une console qui bascule en
DualShock avec des gabarits écrits pour un X360 redevient muette partout, en
silence.

**Où ça se joue :** la substitution au lancement (`retro/launcher.py`) doit
rester la seule source de l'identifiant — jamais une valeur figée dans un
profil. Puis, par émulateur, les clés de mouvement de sa configuration
d'entrée.

**Ordre :** D3 d'abord (une manette qui répond), puis le type de pad, puis le
mouvement. Inverser, c'est déboguer deux inconnues à la fois.

---

## D5 — Aucun émulateur PS Vita

Le manifeste (`retro/data/manifests/core.toml`) en installe neuf : RetroArch,
Dolphin, DuckStation, PCSX2, PPSSPP, Flycast, xemu, RPCS3, Cemu. **La PS Vita
n'est couverte par aucun.** Le candidat est **Vita3K**, seul émulateur Vita
utilisable.

**Ce qu'il faut, dans l'ordre où le dépôt le demande :**

1. Une entrée `[emulator.vita3k]` au manifeste : URL du projet lui-même,
   empreinte SHA256 de la version épinglée, jamais une redistribution.
2. Un profil `retro/data/profiles/vita3k.toml` : `exe`, extensions
   (`.vpk`, dossiers `ux0:app` — **à mesurer**, une Vita installée n'est pas un
   fichier unique, ce qui casse l'hypothèse « une ROM = un fichier » du scan),
   ligne de commande de lancement, `cost`, modes de rendu.
3. Son amorçage : Vita3K ouvre un assistant de première configuration et
   réclame les modules `PUP` du firmware. Sans eux, mêmes symptômes que
   DuckStation sans BIOS — le jeu apparaît, se lance, écran noir. Le mécanisme
   `bios` du profil doit donc les couvrir, ou dire honnêtement qu'il ne les
   couvre pas.
4. Le mouvement (D4) : une part notable du catalogue Vita s'en sert.

**Le point dur :** l'étape 2. Le scan compte des fichiers ; une bibliothèque
Vita est faite de dossiers d'applications installées. À trancher avant d'écrire
le profil, sous peine d'une entrée Steam par fichier de jeu.
