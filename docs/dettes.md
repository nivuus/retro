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
