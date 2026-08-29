# D4 — le capteur de mouvement et le type de manette — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE —
> `superpowers:subagent-driven-development`.

**Objectif :** que la console survive au changement de type de manette
virtuelle — d'un Xbox 360 vers une DualShock — sans redevenir muette en
silence, et que le mouvement soit posé là où il est atteignable, clé par clé,
chacune relevée dans la source de son émulateur.

**Dette :** `docs/dettes.md`, D4 — débloquée le 2026-08-29 par la clôture de D3.

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`

**Dépend de :** D3 (close), D1 (en cours, voir « L'ordre avec D1 »), D7 (le
jeton de chemin manquant, qui bloque deux des quatre émulateurs), et de
`nivuus/installer`, `docs/console-dettes.md`, C2 — **la moitié de cette dette
n'est pas dans ce dépôt**.

---

## Contraintes globales

- **Python 3.11 minimum.** Aucun test ne touche le réseau ni n'exige Windows.
- **Les chemins Windows sont des `str`.**
- **Aucune ROM, aucun BIOS, aucun binaire dans le dépôt.**
- **Un test qui passe quelle que soit l'implémentation est un défaut.**
- Vérifie les mutations avec `PYTHONDONTWRITEBYTECODE=1`.
- **N'écris jamais le nom de la console portable de Nintendo, ni ceux de ses
  émulateurs**, dans un fichier versionné : `test_aucun_emulateur_au_statut_conteste`
  cherche ses treize mots interdits en **sous-chaîne**. Le fichier
  `Windows\Hid\<pad de cette console>.cpp` de PPSSPP est cité plus bas par
  périphrase pour cette seule raison — ce n'est pas de la pudeur.
- **La règle de fond, et elle commande tout le reste :** *une valeur fausse se
  comporte exactement comme l'absence de valeur.* Pas de message, pas de ligne
  de journal, pas de symptôme distinct. Une clé recopiée d'une documentation
  est ignorée en silence — c'est déjà ce qui a coûté quatre identifiants faux
  pour une seule manette (`docs/releve-manettes.md`).
- **Distingue MESURÉ de SUPPOSÉ dans chaque ligne que tu écris.** Ce plan le
  fait ; ne perds pas l'information en la recopiant.

---

## Ce qui a été MESURÉ en écrivant ce plan, et qui commande la suite

### 1. La substitution d'identifiant n'existe pas — il n'y a rien à « garder »

D4 écrit : « la substitution au lancement (`retro/launcher.py`) doit **rester**
la seule source de l'identifiant ». Vérifié dans le code : **ce mécanisme n'a
jamais été écrit.**

Les seuls jetons substitués sont, exhaustivement :

| Jeton | Où | Par qui |
|---|---|---|
| `{render_config}` | `retro/launcher.py:147-160` | Python, à la synchronisation |
| `{render}`, `{rom}` | `retro/data/launcher/retro-launch.cs:839-842` | le lanceur |
| `{width}`, `{height}`, `{scale}` | `retro-launch.cs:1085-1112` | le lanceur |

**Aucun jeton de manette nulle part** : ni `{pad1}`…`{pad4}`, ni GUID, ni index.
Les tâches 2, 3 et 4 du plan des manettes — celles qui devaient créer ce
mécanisme — **n'ont pas été exécutées**. La phrase de D4 décrit donc une règle
d'architecture juste, appliquée à un mécanisme absent.

**Deux identifiants sont pourtant déjà figés, et ce plan doit les nommer :**

- **`SDL-0`, vingt-sept fois, dans `retro/data/profiles/duckstation.toml`**
  (champ `enforced`). C'est un **index**, pas un GUID : la règle « jamais de
  valeur figée » vise les valeurs qui dépendent du VID/PID, et celle-ci n'en
  dépend pas. L'arbitrage est écrit dans le profil (FRAGILITÉ 1) et il tient.
- **`Device: "XInput Pad #1"` de RPCS3**, posé **à la main sur la machine** le
  2026-08-29 (dette D7). Il n'est dans aucun fichier versionné, donc dans le
  champ d'aucune garde — et il est le premier à casser à la bascule (voir 3).

**Et une affirmation fausse est déjà écrite dans un profil livré :** le bloc
« DETTE D4 » de `retro/data/profiles/vita3k.toml` annonce « l'identifiant SDL
substitué AU LANCEMENT par `retro/launcher.py` » comme un mécanisme existant.
Il n'existe pas. La tâche 1 le corrige.

### 2. Ce qui casse à la bascule, et ce qui ne casse pas

| Ce qui est figé | Dépend du VID/PID ? | Sort de la bascule |
|---|---|---|
| `SDL-0/...` ×27, DuckStation, `enforced` | **non** (index) — mesuré sur le binaire | **survit**, sauf si un pad de PLUS s'énumère avant |
| `ForceAnalogOnReset = false`, DuckStation | non | survit |
| `Handler: XInput` + `Device: "XInput Pad #1"`, RPCS3, hors dépôt | **oui** (nom du gestionnaire) | **meurt** — et rien ne le dira |
| tout gabarit d'entrée à écrire pour les huit autres | oui, dès qu'un GUID y entre | n'existe pas encore |

L'exception DuckStation est **mesurée** (`docs/releve-manettes.md`, point 4 du
relevé du 2026-08-29 : les valeurs suivent `SDL-{}/{}`, le premier champ est un
index). Elle reste **à confirmer** avant qu'on s'en serve — c'est la tâche 7.

### 3. Le mouvement, émulateur par émulateur — lu dans les SOURCES

Lecture faite le 2026-08-29 sur la branche `master` de chaque dépôt amont.
**Ce n'est pas la révision épinglée au manifeste** : chaque tâche commence par
re-lire les mêmes symboles sur la version que la console installe réellement.

- **RPCS3 — les clés existent, et le gestionnaire actuel ne peut pas les
  porter.**
  `rpcs3/Emu/Io/pad_config.h` : `cfg_sensor motion_sensor_x{ this, "Motion Sensor X" };`
  et de même `Y`, `Z`, `G`. `struct cfg_sensor` porte trois clés :
  `cfg::string axis{ this, "Axis", "" }`, `cfg::_bool mirrored{ this, "Mirrored", false }`,
  `cfg::_int<-1023, 1023> shift{ this, "Shift", 0 }`.
  `rpcs3/Emu/Io/PadHandler.h:182` : `bool b_has_motion = false;` — **le défaut**.
  `rpcs3/Input/xinput_pad_handler.cpp` ne le passe **jamais** à `true` (il pose
  `b_has_rumble = true`, `b_has_orientation = false`, `m_name_string = "XInput Pad #"`).
  `rpcs3/Input/sdl_pad_handler.cpp:81` : `b_has_motion = true;`.
  → **`Handler: XInput` ne peut pas porter de mouvement, quel que soit le pad.**
  Le fichier de 61 octets posé à la main sur la machine devra devenir
  `Handler: SDL`, ce qui change aussi `Device:`.
  Les valeurs acceptées d'`Axis` viennent de
  `PadHandler.h:294` — `virtual std::unordered_map<u32, std::string> get_motion_axis_list() const { return {}; }` —
  donc de l'override du gestionnaire SDL : **elles ne sont pas relevées**, et
  ne se devinent pas.
- **Vita3K — il n'y a aucune clé à écrire.**
  `vita3k/config/include/config/config.h` : `code(bool, "disable-motion", false, disable_motion)`.
  Le défaut est déjà « mouvement actif ».
  `vita3k/ctrl/src/ctrl.cpp:103-108` interroge `SDL_GamepadHasSensor(..., SDL_SENSOR_GYRO)`
  puis `SDL_SENSOR_ACCEL`, et `:127` conclut
  `state.has_motion_support = found_gyro && found_accel`.
  → tout dépend du **pad**, rien du fichier.
- **PPSSPP — le mouvement ne vient pas de la manette de jeu, sous Windows.**
  Les clés existent : `Core/Config.cpp`, table `controlSettings`, donc section
  **`[Control]` de `ppsspp.ini`** (`Config.cpp:1151`) — et **non** `controls.ini`,
  que le tableau de la tâche 6 du plan des manettes désigne :
  `TiltInputEnabled` (défaut `false`), `TiltInputType` (défaut `1`),
  `TiltSensitivityX`/`Y` (60), `TiltBaseAngleY` (0.9), `TiltInvertX`/`Y`,
  `TiltAnalogDeadzoneRadius`, `TiltInverseDeadzone`, `TiltCircularDeadzone`.
  Mais `UI/EmuScreen.cpp:275` les conditionne à
  `System_GetPropertyBool(SYSPROP_HAS_ACCELEROMETER)`, que `Windows/main.cpp:488`
  résout en `g_InputManager.AnyAccelerometer()`, que `Windows/InputDevice.cpp:90`
  résout en « un périphérique a `HasAccelerometer()` ». Le seul à l'implémenter
  est le backend HID maison — `Windows/Hid/HidInputDevice.h:31-33` (`gyroValid`,
  `accelerometer[3]`, `gyro[3]`) et `:50` — dont les trois pilotes sont
  `DualShock.cpp`, `DualSense.cpp` et celui de la console portable de Nintendo.
  `Windows/XinputDevice.cpp` et `Windows/DinputDevice.cpp` : **zéro** occurrence
  de `accel` ou `gyro`. Et `Common/Input/InputState.h:36` porte
  `DEVICE_ID_ACCELEROMETER = 30,  // no longer used`.
  → **un pad X360 virtuel ne fournira jamais de mouvement à PPSSPP.** Un DS4
  virtuel *peut-être*, à deux conditions à mesurer (tâche 9). Et ce que le tilt
  pilote est le **stick analogique** : la PSP n'a pas de gyroscope.
- **PCSX2 — il n'y a pas de mouvement du tout, et l'énoncé de D4 se trompe.**
  `pcsx2/SIO/Pad/` ne contient que `PadDualshock2`, `PadGuitar`, `PadJogcon`,
  `PadNegcon`, `PadPopn`, `PadNotConnected` : **aucun périphérique de capteur**.
  `PadDualshock2.cpp` : `s_bindings` porte `Pressure` ; `s_settings` porte
  `InvertL`, `InvertR`, `Deadzone`, `AxisScale`, `LargeMotorScale`,
  `SmallMotorScale`, `ButtonDeadzone`, `PressureModifier` — rien de sensoriel.
  `pcsx2/Input/SDLInputSource.cpp` ne mentionne aucun `SDL_SENSOR`.
  → **la PS2 n'avait pas de capteur de mouvement.** Il n'y a aucune clé à
  écrire pour PCSX2, et ce n'est pas un manque.

---

## L'ordre avec D1, et il n'est pas négociable

Un autre agent planifie D1 (la vibration) en parallèle. Les deux dettes
écrivent dans les **mêmes** blocs `[input]` et les mêmes gabarits d'entrée.

**Les deux plans ont été écrits séparément et disent le même ordre** —
`docs/superpowers/plans/2026-08-29-d1-vibration.md` l'écrit ainsi :
« C1 (client Moonlight) → tâche 1 (DuckStation) → D4 (type de pad) → tâche 7
(les huit autres) ». Ce qui suit en est la vue depuis D4 ; en cas de
divergence, c'est le plan de D1 qui décrit ses propres tâches, pas celui-ci.

1. **D1 mesure son maillon « émulateur → SDL → ViGEmBus » AVANT la bascule**,
   sur DuckStation, sous le pad X360 actuel. C'est gratuit — il suffit de jouer,
   `LargeMotor` et `SmallMotor` sont déjà dans `enforced` — et c'est **la seule
   fenêtre où ce maillon est mesurable sans deux inconnues**. Mesuré après la
   bascule, un silence ne dirait plus si c'est la vibration ou le pad.
2. **Puis la bascule** (tâches 5 à 7 de ce plan).
3. **Puis, dans la MÊME passe, émulateur par émulateur** : les relevés de
   vibration restants de D1 et les clés de mouvement de D4. Ouvrir deux fois le
   même fichier d'entrée pour deux dettes, c'est se garantir un conflit sur le
   même gabarit — et une console muette entre les deux.
4. **Tant que le plan D1 n'est pas fusionné**, ce plan ne touche à un profil
   que par les champs qu'il crée lui-même (`pad_releve`) et par le bloc
   « DETTE D4 » de `vita3k.toml`. **Jamais à une note de vibration.**

---

## Tâche 1 : recenser ce qui dépend du type de pad, et geler le recensement

Rien, aujourd'hui, ne dit à un lecteur ce qui casse le jour où Apollo change de
manette. C'est ce qui rend D4 coûteuse, et c'est réparable **sans la console**.

**Fichiers :**
- Modifier : `retro/data/profiles/vita3k.toml` (bloc « DETTE D4 » seulement)
- Test : `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- une garde `test_aucun_profil_livre_ne_fige_un_identifiant_de_peripherique` :
  aucun fichier de `retro/data/profiles/` ne doit contenir un **GUID SDL** —
  la forme `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` en hexadécimal, ou la forme
  compacte de 32 chiffres hexadécimaux que l'émulateur personnel écrit
  (`0-00000003-045e-0000-8e02-000000007200`). L'index `SDL-0` de DuckStation
  n'en est **pas** un et doit rester accepté : le message d'échec doit dire
  pourquoi, sans quoi le prochain lecteur croira la garde cassée ;
- la **correction du bloc « DETTE D4 » de `vita3k.toml`** : il annonce un
  mécanisme de substitution qui n'existe pas. Il doit dire ce qui est vrai —
  qu'aucun jeton de manette n'est substitué nulle part aujourd'hui, que les
  tâches 2 à 4 du plan des manettes restent à faire, et que le mouvement de
  Vita3K ne se règle de toute façon par **aucune clé** (`disable-motion` est
  déjà à son défaut utile) ;
- **ne touche à aucune autre ligne de ce profil** : la note de vibration
  appartient à D1.

**Vérification :** la garde échoue si l'on colle un GUID d'exemple dans un
profil, et passe sur l'arbre livré.

---

## Tâche 2 : `[input] pad_releve` — sous quel pad la mesure a été faite

Un relevé n'est vrai que **du pad sous lequel il a été fait**. Aujourd'hui le
profil dit « relevé » sans dire « de quoi », et cette information n'existe
nulle part.

**Fichiers :**
- Modifier : `retro/profiles.py`, les dix `retro/data/profiles/*.toml`
- Test : `tests/test_profiles.py`, `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- un champ `pad_releve` dans `[input]`, **à côté** de `mapping` et
  `mapping_where`, lu par `_lire_mapping` sur le même modèle ;
- un vocabulaire **gelé** — `PADS_CONNUS = ("x360", "ds4")` — avec un test qui
  fige l'ensemble, comme `test_le_garde_fou_ne_se_raccourcit_pas` fige
  `INTERDITS`. Ajouter un type de pad doit être un acte explicite ;
- il est **exigé quand `mapping == "releve"`**, et **interdit ailleurs** :
  `a-relever` veut dire que rien n'a été relevé, y déclarer un pad serait un
  mensonge de même famille que `steam_input = "required"` ;
- `duckstation.toml` déclare `pad_releve = "x360"` — c'est ce que l'invité
  portait le 2026-08-29 (`USB\VID_045E&PID_028E`) ;
- `rpcs3.toml` déclare `pad_releve = "x360"` **et** dit dans son commentaire
  que son `Handler: XInput` ne survivra pas à la bascule — c'est la seule ligne
  du dépôt qui reliera la panne à sa cause le jour venu.

---

## Tâche 3 : lire le témoin des manettes, et en faire un problème nommé

C'est **le filet** : constater la casse autrement qu'en jouant. Le format du
fichier est défini ici et écrit par la tâche 4 — le même partage des rôles que
`bootstrap.txt` (`retro/launcher.py::lire_amorcages` lit, `retro-launch.cs::InscrireTemoin`
écrit).

**Fichiers :**
- Modifier : `retro/launcher.py`, `retro/status.py`
- Test : `tests/test_launcher.py`, `tests/test_status.py`

**Le format, `_launcher\pads.txt`** — un instantané, réécrit en entier à chaque
lancement (et non fusionné comme `bootstrap.txt`, qui est un journal) :

```
2026-09-01 21:14:33	2
0	045e:028e	Controller (Xbox 360 Controller for Windows)
1	054c:05c4	Wireless Controller
```

Première ligne : date `yyyy-MM-dd HH:mm:ss` en `InvariantCulture` — **le même
contrat que `lire_amorcages`, et pour la même raison** — puis le nombre de
manettes vues. Puis une ligne par manette : index d'énumération, `vid:pid` en
hexadécimal minuscule, nom.

**Ce qu'il faut obtenir :**

- `launcher.TEMOIN_PADS = "pads.txt"` et
  `launcher.lire_pads(emulation_root_local) -> tuple[str, list[Pad]]`, tolérant
  exactement comme `lire_amorcages` : fichier absent ou illisible → `("", [])`,
  jamais une exception. **C'est une trace, jamais une source de vérité** ;
- `status` ajoute à sa section « Manettes » une ligne d'état du **dernier
  lancement**, avec quatre formulations distinctes :
  - témoin absent → « le lanceur n'a jamais relevé de manette » — **pas** un
    problème : `lanceur_perime` porte déjà ce signal ;
  - zéro manette → « aucune manette au dernier lancement » — **pas** un
    problème : une session peut s'ouvrir sans manette, c'est la règle de la
    tâche 4 du plan des manettes ;
  - une manette → son type et son nom ;
  - deux ou plus → voir ci-dessous ;
- **deux problèmes, et deux seulement :**
  1. **plus d'une manette vue** — c'est la FRAGILITÉ 1 de `duckstation.toml`
     rendue visible : ses vingt-sept liaisons visent `SDL-0`, un **index**. Le
     problème nomme les profils dont `mapping == "releve"` et leur
     `mapping_where` ;
  2. **le pad d'index 0 n'est pas du type déclaré en `pad_releve`** — le
     problème nomme chaque profil concerné, son fichier, et porte la phrase qui
     empêche la fausse correction : *une liaison qui ne correspond à aucun
     périphérique est ignorée en silence ; le symptôme est identique avant et
     après une valeur inventée* ;
- la correspondance `vid:pid` → type de pad est une table **courte et gelée**,
  au même endroit que `PADS_CONNUS` : `045e:028e` → `x360`,
  `054c:05c4` → `ds4`. Un `vid:pid` inconnu n'est pas une erreur — il s'affiche
  brut, et ne déclenche aucun problème : accuser sur une table incomplète serait
  pire que se taire.

**Tout est testable sans Windows** : les tests écrivent un `pads.txt` de
fixture et vérifient le rapport.

---

## Tâche 4 : faire écrire ce témoin par le lanceur

**Fichiers :**
- Modifier : `retro/data/launcher/retro-launch.cs`
- Test : à défaut de test C#, une **vérification manuelle écrite** dans le
  rapport — le précédent est la tâche 4 du plan des manettes.

**Ce qu'il faut obtenir :**

- l'énumération des manettes **avant** de démarrer l'émulateur, par
  `joyGetNumDevs` / `joyGetDevCapsW` de `winmm.dll` : la structure `JOYCAPS`
  porte `wMid` (le VID), `wPid` (le PID) et `szPname`. **Ce choix évite de
  toucher `compiler.cmd`** — dont l'encodage CP850 est gardé par un test —
  puisqu'il ne demande aucune référence d'assemblage supplémentaire, là où
  `System.Management` en exigerait une ;
- l'écriture de `pads.txt` au format de la tâche 3, et **le nombre de manettes
  vues au journal** `_launcher\journal.txt` à chaque lancement ;
- **aucune de ces opérations ne doit pouvoir empêcher un jeu de démarrer** :
  `InscrireTemoin` est le modèle exact — `try` / `catch` / `Noter(...)`, et on
  lance quand même ;
- **zéro manette n'est pas une erreur**, et le témoin doit le dire
  explicitement plutôt que de ne pas être écrit : un fichier absent et un
  fichier à zéro manette sont deux constats différents.

**⚠ Le piège qui invalide toute vérification :** une commande WinRM tourne en
**session 0**, où aucune manette n'existe. Toute vérification passe par
`schtasks /create … /it` puis `/run`, sinon elle rapportera zéro manette sur une
console où le pad est présent et sain.

---

## Tâche 5 : la demande à `nivuus/installer` (C2) — ce plan ne la fait pas

**Le type de pad se change dans Apollo, pas ici.** Cette tâche est une demande
écrite, et la liste des preuves à rapporter.

**Ce qu'il faut obtenir de là-bas, et qui doit revenir MESURÉ :**

- Apollo annonce une **DualShock 4** au lieu de `Gamepad 0 will be Xbox 360
  controller (default)` — la ligne de `sunshine.log` qui a servi au constat
  d'origine, relue après le changement ;
- le `VID_054C&PID_05C4` de l'invité passe de l'état `Unknown` à `OK` pendant
  une session (`Get-PnpDevice`) — c'est la preuve que le pad **existe** ;
- **et surtout, la chaîne du mouvement, qui est un problème distinct du type de
  pad :** un DS4 virtuel n'a de gyroscope que si (a) le client Moonlight envoie
  les données de mouvement, (b) Apollo les reçoit, et (c) le rapport transmis à
  ViGEmBus porte les champs de capteur. **Aucun des trois maillons n'est
  mesuré.** Un pad annoncé DualShock sans données de capteur donnerait
  exactement le même silence qu'aujourd'hui, pour une autre raison.
  Ce plan **suppose** que le maillon (c) exige le rapport étendu de ViGEmBus
  plutôt que son rapport court ; cela se tranche dans la source d'Apollo, pas
  ici, et pas dans une documentation.

**Le `403 Permission denied` reste un préalable :** le client appairé porte
`perm=0x3000000` là où les clients fonctionnels portent `0x7131f00`, et aucune
session Moonlight ne s'ouvre depuis l'hôte tant qu'il vaut cela
(`docs/releve-manettes.md`). Aucune mesure « au flux » n'est possible avant.

**Ordre imposé :** les tâches 1 à 4 sont livrées **avant** que la bascule ait
lieu. Un filet posé après la casse ne sert qu'à la constater.

---

## Tâche 6 : MESURE — ce que la console voit du nouveau pad

**Se joue sur la console**, session Moonlight ouverte, manette branchée au
client. Elle ne modifie rien.

**Procédure :**

1. `retro status` sur l'hôte : la section « Manettes » doit maintenant lire le
   témoin de la tâche 4. Noter le `vid:pid` et l'index du pad vu.
2. Confirmer par l'invité — le pad ne doit plus être `Unknown` :
   ```bash
   python3 <installer>/console/guest/winrm_exec.py ps 'Get-PnpDevice | Where-Object { $_.InstanceId -match "VID_054C" } | Select-Object Status,FriendlyName,InstanceId'
   ```
3. **Vérifier qu'il n'y a qu'UN pad**, et que son index est `0`. Deux pads, ou
   un index différent, et les vingt-sept liaisons de DuckStation visent un
   périphérique absent — sans un mot.
4. **Le point qui décide de Vita3K et de RPCS3 :** SDL voit-il un capteur sur
   ce pad ? La réponse ne se déduit d'aucune documentation. Elle se lit dans le
   journal d'un émulateur qui l'interroge : lancer **Vita3K** dans la session
   interactive (`schtasks /it`) et relire son journal, `state.has_motion_support`
   étant calculé par `SDL_GamepadHasSensor` à la connexion du pad
   (`vita3k/ctrl/src/ctrl.cpp:103-127`).

**Ce qui sort de cette tâche :** la valeur de `pad_releve` pour la suite, le
nombre de pads, et un oui/non sur les capteurs SDL. Écris les trois dans le
rapport, avec leur date.

**⚠ « Ça a l'air de marcher » n'est pas une mesure.** Compte les occurrences sur
le **fichier de journal complet**, jamais sur ses premières lignes : le
2026-08-28, l'absence d'un message a été prise pour un succès alors que le
fichier en comptait 272 une minute plus tard.

---

## Tâche 7 : MESURE — confirmer l'exception DuckStation

D4 dit que les liaisons de DuckStation ne portent qu'un **index** et survivent
donc à la bascule. C'est **ce que dit le binaire**, et c'est écrit comme
« à confirmer avant de s'en servir ». Voici comment on le confirme.

**Procédure, dans cet ordre — le premier échec arrête la tâche :**

1. **Relire `settings.ini` sur l'invité.** `[Pad1]` doit porter exactement les
   vingt-sept liaisons en `SDL-0/...` plus `ForceAnalogOnReset = false` :
   `enforced` les repose à chaque lancement, donc leur absence signalerait une
   panne du mécanisme d'imposition, pas de la manette.
   ```bash
   python3 <installer>/console/guest/winrm_exec.py ps 'Get-Content "$env:USERPROFILE\Documents\DuckStation\settings.ini"'
   ```
2. **Lancer Crash Team Racing depuis Steam** — le jeu qui a clos D3, sous le
   nouveau pad. **Un bouton vu répondre est la seule preuve** : DuckStation ne
   dira jamais qu'une liaison ne correspond à rien.
3. **Si la manette est muette**, ne récrire aucune liaison. Vérifier d'abord
   les deux causes déjà connues, dans cet ordre : le pad est-il bien à l'index
   `0` (tâche 6, point 3) ? et `ForceAnalogOnReset` est-il toujours à `false` ?
   Deux causes ont déjà produit ce symptôme unique le 2026-08-29 ; une
   troisième explication ne s'invente qu'après avoir écarté celles-là.

**Ce qui sort :** ou bien l'exception est confirmée — et `duckstation.toml`
garde `pad_releve = "x360"` avec une note disant qu'un pad `ds4` a été vu
répondre sur les mêmes liaisons —, ou bien elle est réfutée, et **le fait n° 5
du relevé de D3 est faux** : dis-le dans `docs/releve-manettes.md`, c'est plus
important que la correction elle-même.

---

## Tâche 8 : PCSX2 — écrire que le mouvement n'existe pas

La seule des quatre qui se traite **sans la console**, et la seule dont la
réponse est un non.

**Fichiers :**
- Modifier : `retro/data/profiles/pcsx2.toml` (commentaire seulement)
- Test : `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- une note qui dit, **avec ses sources** : `pcsx2/SIO/Pad/` ne contient aucun
  périphérique de capteur (`PadDualshock2`, `PadGuitar`, `PadJogcon`,
  `PadNegcon`, `PadPopn`, `PadNotConnected`), `PadDualshock2.cpp` porte
  `Pressure`, `PressureModifier`, `LargeMotorScale`, `SmallMotorScale` et rien
  de sensoriel, et **la PS2 n'avait pas de capteur de mouvement** ;
- la note doit être **re-vérifiée sur la révision épinglée au manifeste** avant
  d'être écrite : la lecture ci-dessus est faite sur `master` ;
- **ne pas toucher à la vibration.** `LargeMotorScale` et `SmallMotorScale` sont
  des **échelles**, pas des liaisons — les confondre avec les `LargeMotor` /
  `SmallMotor` de DuckStation produirait un réglage d'apparence posé qui ne fait
  rien. Cette information appartient à D1 ; transmets-la à son agent plutôt que
  de l'écrire ici.

---

## Tâche 9 : PPSSPP — la condition est un pad HID, pas une clé

**Fichiers :**
- Modifier : `retro/data/profiles/ppsspp.toml` (commentaire seulement)
- Test : `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- **d'abord la re-lecture des cinq symboles** sur la version épinglée
  (v1.20.4 au manifeste), parce que le backend HID de Windows est récent et
  peut être absent de cette version :
  `Windows/Hid/HidInputDevice.h` (`HasAccelerometer`), `Windows/main.cpp`
  (`SYSPROP_HAS_ACCELEROMETER`), `Windows/InputDevice.cpp`
  (`AnyAccelerometer`), `UI/EmuScreen.cpp` (la condition sur
  `bTiltInputEnabled`), `Core/Config.cpp` (les dix clés `Tilt*`) ;
- **la mesure qui décide** : le pad DualShock virtuel d'Apollo est-il pris par
  le backend HID de PPSSPP ? C'est un pilote HID **maison**, qui ne passe ni par
  XInput ni par SDL : il faut donc que ViGEmBus expose un vrai périphérique HID
  DualShock, et que PPSSPP le reconnaisse. Se constate en lançant PPSSPP dans
  la session interactive et en regardant si l'entrée de menu du contrôle par
  inclinaison est **atteignable** — elle est masquée quand
  `SYSPROP_HAS_ACCELEROMETER` est faux ;
- **si la mesure est négative**, écris-le et arrête : `TiltInputEnabled = true`
  posé sur une console sans accéléromètre est très exactement une valeur fausse
  qui se comporte comme l'absence de valeur ;
- **si elle est positive**, les clés vont dans `[Control]` de `ppsspp.ini` —
  **et non dans `controls.ini`**, que le tableau de la tâche 6 du plan des
  manettes désigne. Corrige ce tableau : il désigne le fichier de **mappage**,
  pas celui des réglages ;
- dis dans la note ce que le tilt fait réellement : il pilote le **stick
  analogique**. La PSP n'a pas de gyroscope, et aucun jeu n'en lira un.

---

## Tâche 10 : RPCS3 — changer de gestionnaire, et le faire tenir

**Bloquée par D7** : `config\input_configs\global\Default.yml` vit sous la
racine d'émulation, qu'aucun `target` de `[bootstrap]` ne sait désigner. Tant
que le jeton de chemin n'existe pas, tout ce qui est posé ici l'est **à la
main**, et `retro install` l'efface à la première montée de version.

**Fichiers :**
- Modifier : `retro/data/profiles/rpcs3.toml` (commentaire, et `[bootstrap]` le
  jour où D7 est levée)
- Test : `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- **le constat, qui est le vrai livrable de cette tâche** :
  `Handler: XInput` **ne peut pas** porter de mouvement — `b_has_motion` vaut
  `false` par défaut (`Emu/Io/PadHandler.h`) et le gestionnaire XInput ne le
  passe jamais à `true`, là où le gestionnaire SDL le fait
  (`Input/sdl_pad_handler.cpp`). Le fichier de 61 octets posé le 2026-08-29 est
  donc à refaire, pas à compléter ;
- **le relevé, par RPCS3 lui-même**, exactement comme pour DuckStation :
  choisir le gestionnaire SDL et le pad dans l'interface de RPCS3, lancée dans
  la session interactive, puis **relire le `Default.yml` qu'il a écrit**. Les
  clés attendues sont `Handler`, `Device`, et les quatre nœuds
  `Motion Sensor X` / `Y` / `Z` / `G`, chacun portant `Axis`, `Mirrored`,
  `Shift` (`Emu/Io/pad_config.h`). **Les valeurs d'`Axis` ne sont pas
  relevées** : elles viennent de `get_motion_axis_list()` du gestionnaire
  (`Emu/Io/PadHandler.h`), et se lisent dans le fichier que RPCS3 écrit — pas
  ailleurs ;
- **deux pièges de forme déjà payés**, qui valent aussi pour le nouveau
  fichier : la valeur du gestionnaire porte ses majuscules
  (`pad_config_types.cpp` : `case pad_handler::sdl: return "SDL";`), et
  `Device` **doit être cité** — en YAML, `#` ouvre un commentaire, donc un nom
  de périphérique non quoté qui en contient un est tronqué en silence ;
- **écris dans le profil que rien ne repose ce fichier** (D7), et que
  `retro install` l'efface : c'est la panne la plus silencieuse du lot.

---

## Tâche 11 : Vita3K — rien à écrire, tout à mesurer

**Bloquée par D7** (aucun `target` ne désigne son `config.yml` sous la racine
d'émulation) **et par D9** (installer un jeu n'y marche par aucune voie).

**Fichiers :**
- Modifier : `retro/data/profiles/vita3k.toml` (bloc « DETTE D4 », déjà touché
  par la tâche 1)
- Test : `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- la note dit, avec sa source, qu'**il n'y a aucune clé de mouvement à
  écrire** : `disable-motion` vaut `false` par défaut
  (`vita3k/config/include/config/config.h`), et le mouvement dépend
  entièrement de ce que SDL rapporte du pad —
  `SDL_GamepadHasSensor(..., SDL_SENSOR_GYRO)` puis `SDL_SENSOR_ACCEL`, et
  `has_motion_support = found_gyro && found_accel` (`vita3k/ctrl/src/ctrl.cpp`) ;
- **les deux capteurs sont exigés** : un gyroscope sans accéléromètre ne suffit
  pas, et c'est le genre de demi-réussite qui se lit comme une panne totale ;
- la note redit ce que le profil dit déjà et qui reste vrai : **l'écran tactile
  avant et le pavé arrière de la Vita** n'existent sur aucune manette, DualShock
  comprise — c'est un manque distinct du gyroscope, et il n'est traité nulle
  part ;
- **ne rien poser tant que D7 tient.** Un `config.yml` écrit à la main sur la
  console donnerait l'illusion que c'est réglé, et rien ne le reposerait — la
  faute que D7 nomme explicitement.

---

## Vérification finale

- [ ] Suite complète, arbre frais, sous `-W error`
- [ ] Aucun test ne touche le réseau, aucun n'exige Windows
- [ ] Aucun identifiant, aucune clé de mouvement écrits qui n'aient été relevés
      sur la machine ou lus dans la **source** de la révision épinglée — jamais
      dans une documentation, jamais dans les **chaînes** d'un binaire (qui
      donnent les libellés d'interface, pas les valeurs de fichier)
- [ ] Les tâches 1 à 4 sont livrées AVANT que le type de pad change
- [ ] `retro status` nomme la discordance entre `pad_releve` et le pad vu au
      dernier lancement, et le cas « plus d'une manette »
- [ ] Sur la console, pad DualShock, session ouverte : Crash Team Racing répond
      toujours à la manette dans DuckStation (tâche 7)
- [ ] Chaque profil touché dit ce qui est MESURÉ et ce qui est SUPPOSÉ
- [ ] Aucune note de vibration modifiée : elles appartiennent à D1

## Ce que ce plan ne fait pas

- **Il ne change pas le type de pad.** Cela se fait dans `nivuus/installer`,
  `docs/console-dettes.md`, C2. La tâche 5 dit ce qu'on en attend et ce qui
  doit revenir mesuré ; elle ne prétend pas le faire.
- **Il ne crée pas le mécanisme de substitution d'identifiant.** Les tâches 2,
  3 et 4 du plan des manettes — les jetons `{pad1}`…`{pad4}`, les gabarits
  d'entrée déposés à la synchronisation, la substitution au lancement — restent
  entières. Ce plan **constate** qu'elles n'ont pas été faites, pose la garde
  qui empêche un identifiant figé d'entrer d'ici là, et s'arrête là : bâtir ce
  mécanisme est le sous-projet E, pas une dette.
- **Il ne lève ni D7 ni D9**, dont deux des quatre émulateurs dépendent
  entièrement. Ce qui est écrit pour RPCS3 et Vita3K est un constat et une
  note ; rien n'y sera **reposé** avant le jeton de chemin.
- **Il ne mesure pas la vibration.** C'est D1, et l'ordre entre les deux est
  écrit plus haut.
- **Il ne traite ni le tactile, ni le retour haptique fin.** L'écran tactile de
  la Vita, son pavé arrière et le pavé tactile d'une DualShock sont trois
  manques distincts du gyroscope ; aucun n'est planifié.
- **Il ne lève pas la FRAGILITÉ 1 de DuckStation.** `SDL-0` reste un index : le
  filet de la tâche 3 fait qu'un pad de plus se **voit** dans `retro status`,
  il n'empêche pas la panne.
- **Il ne fait rien par jeu.** Un titre qui veut une disposition ou une
  sensibilité de gyroscope à lui est un cas particulier ; la console doit
  d'abord marcher dans le cas général.


---

## ⚖ Arbitrage rendu le 2026-08-29 par la conduite de projet — RPCS3, `Handler:`

**Les plans D4 et D7, écrits séparément, se contredisent sur une ligne.** D7
prescrit de poser `Handler: XInput` (mesuré : le propriétaire a confirmé que
les contrôles répondent). D4 a relevé dans la source que `b_has_motion` reste
`false` sous XInput, quel que soit le pad — donc que ce choix **interdit le
mouvement pour toujours**, et qu'il faudrait `Handler: SDL`.

**Décision : `Handler: XInput` est posé, et D4 ne le change pas sans mesure.**

Trois raisons, dans cet ordre :

1. **XInput est la seule des deux valeurs qui ait été vue fonctionner.** SDL
   n'a jamais été essayé sur cette machine. La règle du dépôt est de ne jamais
   troquer une valeur mesurée contre une valeur supposée — une valeur fausse se
   comporte exactement comme l'absence de valeur, et ici l'absence de valeur
   signifie `pad_handler::null`, c'est-à-dire pas de manette du tout.
2. **Le coût du choix est borné, et il ne touche qu'une dette.**
   `xinput_pad_handler.cpp` pose `b_has_rumble = true` : XInput ne bloque donc
   **pas D1**. Il ne coûte que le mouvement, c'est-à-dire D4 — une dette qui,
   elle, attend de toute façon un changement de type de pad dans
   `nivuus/installer` (C2) qu'aucun des deux plans ne contrôle.
3. **Basculer maintenant, ce serait déboguer deux inconnues à la fois** — le
   défaut nommé que D4 s'interdit elle-même dans sa section « Ordre ».

**Ce que cette décision impose aux deux plans, et c'est la partie qui coûte :**

- **D7 ne doit pas poser `Default.yml` en `si-absent` sans dire comment on en
  sort.** `si-absent` copie des octets et ne réécrit jamais : le jour où D4
  voudra `Handler: SDL`, le fichier existera déjà et **rien ne le remplacera**.
  Le geste de sortie — supprimer le fichier, ou une option qui le force — doit
  être écrit dans le profil, sans quoi la bascule de D4 échouera en silence,
  ce qui est très exactement le défaut que ces deux plans existent pour éviter.
- **D4 ne planifie pas la bascule à l'aveugle.** Elle devient une tâche à deux
  temps : (a) mesurer que `Handler: SDL` + son `Device:` rendent une manette
  qui répond — un bouton vu répondre, rien de moins ; (b) alors seulement
  relever les valeurs d'`Axis`, qui viennent de l'override SDL de
  `get_motion_axis_list()` et **ne sont pas relevées à ce jour**.
- **Aucun des deux plans ne fige `Handler` dans une liste gelée** sans y écrire
  que la valeur est un arbitrage réversible, daté d'aujourd'hui, et non un fait
  mesuré sur l'émulateur.

**Ce que cet arbitrage ne tranche pas :** si le mouvement vaut, à l'usage, le
risque de reperdre une manette qui marche. C'est une question de valeur, pas de
fait, et elle appartient au propriétaire — le jour où D4 arrivera à cette
tâche, pas aujourd'hui.
