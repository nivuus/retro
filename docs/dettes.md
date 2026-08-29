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

**Ce que ça contredit :** le plan des manettes classe DuckStation parmi les
émulateurs qui « détectent bien tout seuls » leur manette (§ *Ce qui a été
mesuré*, fait n° 4). Cette phrase est fausse, ou n'est vraie que d'un pad
physique. Le pad d'Apollo n'existe que pendant la session, et DuckStation
range son mapping dans `%USERPROFILE%\Documents\DuckStation\settings.ini`,
section `[Pad1]` — que l'amorçage écrit **sans aucune** clé d'entrée.

**Où ça se joue :** `retro/data/profiles/duckstation.toml`, bloc `[bootstrap]`,
et `[input] steam_input = "required"` — que, rappel du plan, **aucun code
n'applique jamais**.

**Ce qu'il faut mesurer avant d'écrire :** ce que DuckStation attend en
`[Pad1]` — `Type`, `Bindings/...`, et sous quelle forme d'identifiant
(`SDL-0/...` ? `XInput-0/...` ?). L'outil de relevé du sous-projet E existe
pour ça. **Toute valeur non relevée sur la machine est fausse :** DuckStation
n'émet aucun message quand une liaison ne correspond à rien, et la manette
reste muette exactement comme si le fichier était vide.

**Ce que ça coûte :** le seul émulateur PlayStation de la console est
injouable, et rien dans `retro status` ne le dit.

---

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

## D5 — PS Vita : le scan sait lire une bibliothèque en dossiers, Vita3K ne s'installe toujours pas

**Constaté le 2026-08-28. Repris le 2026-08-29** : le point dur est levé, le
reste tient à une empreinte que le projet Vita3K ne permet pas d'épingler.

### Ce qui est fait

**Le point dur, l'étape 2 : le scan comptait des FICHIERS.** `_retenus`
filtrait `is_file()` sur une extension déclarée, et un dossier de système
reconnu n'est jamais ouvert plus loin — sur une bibliothèque Vita, faite
d'applications installées (`ux0:app\<TITLEID>\`) à côté des `.vpk`, le scan
rendait zéro jeu sans un mot, ce qui ressemble à une bibliothèque vide.

Deux réponses étaient possibles : généraliser le scan, ou donner au profil de
quoi déclarer qu'il scanne des dossiers. **C'est le profil qui déclare**, avec
`app_dir_marker` :

```toml
app_dir_marker = "eboot.bin"   # « un jeu peut être un DOSSIER, le voici »
```

Généraliser aurait voulu dire « tout sous-dossier est un jeu », donc une
entrée Steam pour `savedata` et pour chaque dossier d'extras, et une règle
propre à un seul émulateur logée dans le code — alors que tout ce qui est
propre à un émulateur vit dans son TOML. Le scan, lui, ne connaît toujours
aucun émulateur : il applique une règle déclarée. Sans la clé — les neuf
profils livrés — rien ne change, aucun dossier n'est retenu.

Le dossier retenu est inventorié TEL QUEL et n'est jamais ouvert : c'est ce
qui empêche l'entrée Steam par fichier de jeu que cette dette redoutait.
Vérifié de bout en bout sur une bibliothèque fabriquée — un `.vpk` posé
DANS le dossier du jeu ne produit aucune entrée.

**L'étape 2, le profil** : `retro/data/profiles/vita3k.toml` existe, avec ses
deux formes de bibliothèque (`extensions = [".vpk"]` et le marqueur ci-dessus),
sa ligne de commande, et ce qu'il ne sait pas écrit comme tel.

### Ce qui reste, et pourquoi

**L'étape 1, l'empreinte — bloquée par le projet lui-même.** Vérifié le
2026-08-29 sur son API de publication : Vita3K ne publie qu'UNE release,
l'étiquette roulante `continuous`, dont l'archive Windows s'appelle
`windows-latest.zip` et se réécrit à chaque construction. Aucune archive
versionnée n'existe. Or ce manifeste refuse les étiquettes roulantes, et pour
une raison mesurée : une empreinte qui vieillit d'un jour fait échouer
l'installation sur la console sans que rien ne l'explique.

L'entrée `[emulator.vita3k]` existe donc avec une empreinte et une version
VIDES — « pas encore relevées ». `acquire` la refuse avant de télécharger quoi
que ce soit, `retro install` affiche un échec nommé, et `retro scan` ignore
puis SIGNALE le système Vita. Rien n'apparaît dans Steam qui ne se lancerait
pas.

Pour la lever : relever ensemble version et empreinte sur la MÊME archive,
lister l'archive au passage (le profil suppose `Vita3K.exe` à la racine sans
qu'aucune archive l'ait confirmé), et savoir que le couple expire à la
construction suivante. **La place durable de Vita3K est le manifeste du
propriétaire** (`G:\retro\emulators.toml`), hors dépôt, où l'empreinte se
relève au moment de l'installation et n'engage que sa machine.

**L'étape 3, le firmware : le profil ne le couvre pas, et le dit.** Le
mécanisme `bios` vérifie des fichiers déposés dans un dossier partagé à leur
empreinte MD5 et pointe l'émulateur dessus. Le firmware Vita n'est pas de
cette nature : c'est un PUP qui s'INSTALLE une fois dans l'arborescence de
l'émulateur, comme le PS3UPDAT.PUP de RPCS3, et son empreinte change à chaque
version sans que rien de publiquement citable n'existe. Sans lui, mêmes
symptômes que DuckStation sans BIOS — le jeu apparaît, se lance, écran noir.

Le patron est mesuré sur la console (2026-08-29, invité en
`provision_version=B1`) : les BIOS-fichiers vivent dans `G:\retro\bios\` et
l'émulateur y est pointé par sa configuration (`[BIOS] SearchDirectory` chez
DuckStation) ; un firmware est rangé à part, hors de `bios\`, parce qu'il
s'installe. **RPCS3 n'a d'ailleurs sur cette machine ni `dev_flash` ni
`dev_hdd0` : son firmware n'a jamais été installé, et personne ne s'en est
aperçu** — la même panne muette attend la Vita.

Ce que Vita3K a de plus que RPCS3 : `--firmware <chemin.pup>` installe le
firmware depuis la ligne de commande, donc sans souris. Il reste à trancher où
le PUP est rangé et comment on constate qu'il est déjà installé.

**L'amorçage, bloqué par autre chose que la mesure.** Le `config.yml` de
Vita3K est chargé depuis `<Vita3K>\config.yml`, c'est-à-dire depuis son
dossier d'INSTALLATION. Or `bootstrap.target` doit être un chemin Windows
absolu ou partir d'une variable d'environnement : la racine d'émulation est un
paramètre de `retro scan`, aucune constante ne la désigne. Il faudra un jeton
substitué à la synchronisation, sur le modèle de `{render_config}`. Et, comme
pour Cemu, une configuration qui vit sous le dossier d'installation disparaît
à chaque montée de version : l'amorçage devra se rejouer.

**L'étape 4, le mouvement : c'est D4, elle n'a pas bougé.** Ce qui restera à
faire dans ce profil-ci est noté dans le profil.

**Ce que ça coûte aujourd'hui :** la PS Vita reste absente de la console — mais
elle est absente FRANCHEMENT : nommée dans le manifeste, refusée à
l'installation avec sa cause, signalée au scan. Et le scan sait désormais lire
une bibliothèque en dossiers, ce dont profitera n'importe quel émulateur qui
en aura une.
