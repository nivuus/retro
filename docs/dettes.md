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

**Un maillon est devenu actionnable sans nouvelle mesure — 2026-08-29.** Le
relevé de D3 a montré que, pour DuckStation, la vibration n'est pas un réglage
à part : ce sont **deux liaisons de `[Pad1]`**, au même titre que les boutons.

```
LargeMotor = SDL-0/LargeMotor
SmallMotor = SDL-0/SmallMotor
```

Elles étaient **absentes** du `settings.ini` de la console — comme tout le
reste de `[Pad1]`, et pour la même cause : `SetupWizardIncomplete = false` saute
la page « Controller Setup », donc le seul geste qui les aurait écrites. Elles
sont désormais dans le champ `enforced` de `duckstation.toml`, reposées à
chaque lancement.

Ce que cela change pour D1 : la première ligne du tableau ci-dessus —
« aucun profil ne pose de réglage de rumble » — **n'est plus vraie pour
DuckStation**. Le maillon « émulateur → SDL → ViGEmBus » y est donc testable
tel quel, sans nouveau relevé : il suffit de jouer. Les huit autres émulateurs
restent entiers. Et cela ne dit RIEN des deux autres maillons — Steam Input,
et la remontée Apollo → client Moonlight —, qui sont des défauts distincts.

**Précaution, la même que pour D3 :** ces deux lignes n'ont **pas** été vues
faire vibrer quoi que ce soit. Elles ont été écrites par DuckStation, elles ont
la bonne forme, et c'est tout ce qu'on en sait.

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

### Où en est D2 — 2026-08-29

**L'axe existe, avec sa politique.** `retro/render.py` porte maintenant le
troisième axe, séparé des deux autres et nommé : deux valeurs, `entier` et
`ajuste`, qui sont **les deux seules façons d'agrandir sans déformer** —
l'étirement n'est pas une troisième valeur qu'on aurait écartée, il n'est pas
sur cet axe. La politique est une table explicite, comme `_ARBITRAGE` :
`native` remplit `entier` (la trame de la console est ce que le mode natif
existe pour préserver ; seul un multiple entier l'agrandit sans la
rééchantillonner), `full` remplit `ajuste` (la résolution interne est déjà
montée à la session, il n'y a plus de trame à préserver). `auto` n'a pas de
remplissage à lui : il hérite de celui du mode qu'il retient.

**La décision reste explicable**, comme le reste du module : chaque mode rend
son motif, `retro status` cite la politique en légende de sa section Rendu et
donne le remplissage de chaque système. Un profil qui contredirait la
politique est refusé au chargement — la contradiction ne se verrait sinon que
sur l'écran, sur une image floue qu'on croirait normale.

**Quatre états, jamais confondus** : réglé (`fill`), non réglable et c'est
mesuré (`fill_absent`), rien à régler parce que le mode ne passe rien
(déduit), et jamais mesuré — que `retro status` nomme dans un problème groupé.

**Couvert :** les huit systèmes de RetroArch (`video_scale_integer`,
`_axis = 0`, `_scaling = 0` en natif ; la mise à l'échelle entière éteinte
explicitement en full, parce que RetroArch réécrit son `retroarch.cfg` en
quittant). GameCube et Wii sont **déclarés non réglables** : la révision 2606a
de Dolphin n'a aucune clé de mise à l'échelle entière.

**Non couvert, et pourquoi :** PS2, PSP, Dreamcast, Xbox, PS3, Wii U n'ont
**aucun bloc de rendu du tout**. Le troisième axe ne se greffe pas avant les
deux premiers, et `retro status` les nomme déjà. C'est le travail du
sous-projet D, pas celui-ci.

**L'arbitrage DuckStation est TRANCHÉ — le propriétaire a répondu oui**, le
2026-08-29 : `retro` est autorisé à modifier un `settings.ini` qui existe.

Ce que cette réponse a permis de construire, et qui sert aussi à **D3** :
la seconde stratégie d'écriture, `fusion`, à côté de `si-absent`
(`retro/launcher.py`, `retro/data/launcher/retro-launch.cs`). Elle **modifie
sans jamais écraser** : seules les clés que le profil apporte sont réécrites,
tout le reste est préservé — les clés inconnues comme le `[BIOS]
SearchDirectory` ajouté à la main, les commentaires, l'ordre, la marque
d'octets du fichier — une sauvegarde horodatée précède chaque écriture, les
lignes posées portent une marque qui les distingue de celles du propriétaire,
et un fichier **déjà conforme n'est pas réécrit du tout**. Un profil qui
fusionne est en outre REFUSÉ au chargement si son en-tête promet encore que
les réglages ne sont jamais retouchés.

Vérifiée sur la console le 2026-08-29 : la source compile avec le `csc.exe`
du .NET Framework, et `--explain` — qui fait la fusion à blanc, sans rien
écrire — rend « 3 clé(s) posée(s) » sur un fichier neuf, puis « déjà
conforme, rien ne sera réécrit » sur le résultat. L'idempotence est donc
prouvée, et avec elle la préservation : le fichier comparé égal contenait les
clés et commentaires du propriétaire.

**L'étendue est arbitrée aussi** : le propriétaire a tranché « seulement les
clés que la console doit imposer ». Le régime est donc **structurel** dans le
profil — deux champs distincts, `content` (posé une fois, jamais retouché) et
`enforced` (reposé à chaque lancement) — et non un mode déclaré qu'on
pourrait mettre en contradiction avec ce que le bloc contient. Un même
couple section/clé dans les deux est **refusé** au chargement.

Pour DuckStation, `enforced` porte **trois clés** : `SetupWizardIncomplete`,
`StartFullscreen`, `CheckAtStartup`. Ce sont les trois causes mesurées d'un
lancement qui échoue. `ConfirmPowerOff`, `PauseOnFocusLoss`,
`SaveStateOnExit`, `InhibitScreensaver` et `HideCursorInFullscreen` restent
des préférences : changées dans l'émulateur, elles tiennent.

**Ce qui reste, et qui n'est pas une paresse** : le nom de la clé de rendu
n'est toujours pas relevé — le binaire assemble ses littéraux dans le code —
et sous `-batch -nogui` DuckStation ne réécrit jamais son fichier, donc le
relevé demande de l'ouvrir une fois hors du chemin de la console. Le geste
est écrit dans le profil ; la clé rejoindra `enforced` le jour où elle sera
relevée. **D3 n'aura qu'à ajouter sa section `[Pad1]` au même champ** — rien
d'autre à écrire.

Un piège documenté plutôt que découvert : le relevé de la manette exige de
repasser `SetupWizardIncomplete` à `true` et de lancer DuckStation hors du
chemin de la console. Le lancement suivant par la console le remettra à
`false`, et **c'est voulu** — c'est le rôle même de `enforced`. Le profil le
dit, pour que personne ne croie son relevé saboté.

---

## D3 — DuckStation : liaisons relevées, réponse en jeu NON vérifiée

> **Cette dette n'est pas réglée.** Les liaisons existent, elles ont été
> écrites par DuckStation lui-même, elles sont dans le profil livré. Il manque
> la seule preuve qui compte : **personne n'a vu un bouton faire quelque chose
> dans un jeu.** Tant que ce n'est pas fait, D3 reste ouverte.

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

### Les valeurs, relevées le 2026-08-29 par une autre voie

Au premier passage, aucune manette n'était connectée : le pad d'Apollo
(`USB\VID_045E&PID_028E`) et une DualShock 4 (`VID_054C&PID_05C4`) figuraient
tous deux dans les périphériques de l'invité avec l'état `Unknown` —
c'est-à-dire absents. Le pad n'existe que pendant une session Moonlight.

La session Moonlight **n'a pas pu être ouverte** : `403 Permission denied` au
`/launch`, le client appairé portant `perm=0x3000000` là où les clients
fonctionnels portent `0x7131f00`. Le pad a donc été créé **directement par
ViGEmBus**, sans Apollo et sans client, et l'assistant de DuckStation a été
piloté dans la session interactive jusqu'à l'appariement automatique. Les codes
IOCTL, les deux pièges d'automatisation et le détail du `403` sont dans
`docs/releve-manettes.md` — ils ont coûté cher et ne se devinent pas.

**Résultat : vingt-sept liaisons**, écrites par DuckStation lui-même, relues
dans le `settings.ini` qu'il venait d'écrire. Clés nues, identifiant `SDL-0`,
axes préfixés `+`/`-`, deux liaisons de vibration (`LargeMotor`, `SmallMotor`),
et **aucune clé `Type`** — DuckStation n'en écrit pas.

**Toute valeur non relevée sur la machine est fausse :** DuckStation n'émet
aucun message quand une liaison ne correspond à rien, et la manette reste muette
exactement comme si le fichier était vide. Une valeur recopiée d'une recette est
donc indiscernable de l'absence de valeur, à l'œil comme au journal. C'est
pourquoi ces vingt-sept lignes valent quelque chose : elles ne viennent pas
d'une recette.

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
- **La procédure de relevé est écrite** : `docs/releve-manettes.md`. Elle ne
  demande de recopier aucune valeur — elle rouvre l'assistant de DuckStation le
  temps d'un appariement automatique et fait écrire `[Pad1]` par DuckStation
  lui-même. C'est le seul relevé valide.
- **Le squelette `[Pad1]` a cédé la place au relevé réel.** Il était
  entièrement en commentaire tant que rien n'était mesuré ; les vingt-sept
  liaisons sont désormais dans `duckstation.toml`, champ **`enforced`** — donc
  reposées à chaque lancement. `content` ne les poserait sur AUCUNE console
  déjà jouée : sous `-batch -nogui`, DuckStation ne rouvre jamais son
  `settings.ini`, et le fichier existe déjà là-bas.
- **La liste gelée des clés imposées a été élargie en revue.** Elle valait
  trois clés ; elle en vaut trente. L'élargissement est délibéré et son prix
  est écrit dans le profil : **le propriétaire ne peut plus remapper sa manette
  depuis l'interface de DuckStation**, puisque le lancement suivant repose les
  liaisons.

### Ce qui reste — et pourquoi D3 N'EST PAS RÉGLÉE

La procédure pose **trois** conditions pour tenir un relevé pour bon. Deux sont
remplies, la troisième ne l'est pas :

| Condition | État |
|---|---|
| `[Pad1]` existe et porte des clés qui n'y étaient pas | ✅ vingt-sept |
| ces lignes ont été écrites par DuckStation, pas à la main | ✅ par son assistant |
| **un jeu lancé depuis Steam répond à la manette** | ❌ **non vérifié** |

C'est la troisième qui compte, et c'est celle qui manque. Ce n'est pas un
détail de forme : **DuckStation ne dira jamais qu'une liaison ne correspond à
rien.** Une valeur juste et une valeur fausse produisent le même silence. Tant
que personne n'a vu un bouton agir dans un jeu, ces vingt-sept lignes sont une
hypothèse bien fondée, pas une manette qui marche.

S'ajoute une raison matérielle de ne pas conclure : **le relevé a été restauré**
sur l'invité à la fin de l'opération. La console n'a plus de `[Pad1]`, et rien
n'y a été joué depuis. Les liaisons n'existent aujourd'hui que dans le profil ;
elles n'auront été posées qu'au prochain `retro launcher`.

**Pour la clore, dans cet ordre :**

1. Lancer `retro launcher` pour que l'amorçage repose le `settings.ini`, puis
   vérifier que `[Pad1]` y est bien et que `SetupWizardIncomplete` vaut `false`.
2. **Lancer un jeu depuis Steam, manette en main, et voir un bouton agir.**
   C'est la seule preuve. Crash Team Racing est le cas d'origine.
3. Vérifier au passage l'index : `SDL-0` désigne la PREMIÈRE manette énumérée.
   S'il y en a une autre branchée, ce n'est pas celle d'Apollo, et le symptôme
   sera identique à la panne d'origine.
4. Alors seulement basculer `[input] mapping` de `a-relever` vers ce que la
   mesure dit, dans `retro/data/profiles/duckstation.toml`.

Le champ `mapping` reste **`a-relever`** jusque-là, et `retro status` continue
donc de signaler DuckStation. C'est voulu : `auto` dirait que DuckStation trouve
sa manette seul, ce qui est faux — il ne la trouve que parce que la console lui
impose vingt-sept liaisons.

**Ce que ça coûte aujourd'hui :** le seul émulateur PlayStation de la console
est toujours réputé injouable, faute d'avoir été essayé. La différence avec
hier, c'est qu'un essai a maintenant une chance d'aboutir.

**Un essai AU FLUX reste bloqué** par le `perm=0x3000000` du client appairé
(`403 Permission denied` au `/launch`). Qui voudra vérifier dans les conditions
réelles — session Moonlight, pad d'Apollo, canapé — devra d'abord régler ce
`perm`. Voir `docs/console-dettes.md` de `nivuus/installer`.

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

Le patron se lit sur le partage, sans rien demander à l'invité (2026-08-29) :
`G:\retro\bios\` ne contient que des BIOS-fichiers, sur lesquels l'émulateur
est pointé par sa configuration — `duckstation.toml` documente déjà
`[BIOS] SearchDirectory`. Un firmware est rangé à côté, **hors** de `bios\`,
parce qu'il ne se lit pas : il s'installe. Le PUP Vita suivra ce rangement-là.

Un fait vu une fois **dans** l'invité le 2026-08-29, et que personne ne peut
re-vérifier depuis — l'accès à l'invité est fermé, il est donc consigné ici
comme une observation datée et non comme un état courant : **RPCS3 n'avait ni
`dev_flash` ni `dev_hdd0`, son firmware n'ayant jamais été installé**, et rien
dans `retro status` ne le disait. Si l'observation tient toujours, c'est
exactement la panne muette qui attend la Vita ; la reprendre demande un accès
à la machine, pas un raisonnement.

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
