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

**Ce qui a été posé le 2026-08-29, et ce qui ne l'a pas été.** Aucun réglage de
rumble n'a pu être posé, et c'est la conclusion, pas un abandon : le nom de la
clé dépend, émulateur par émulateur, d'un relevé sur la machine que personne
n'a fait. Une clé recopiée d'une documentation est ignorée **en silence** —
c'est déjà ce qui a coûté quatre identifiants faux pour une seule manette au
sous-projet E. Ce qui est posé, c'est l'aveu, profil par profil : les neuf
profils livrés hors DuckStation portent désormais, dans leur bloc `[input]`,
une note qui dit qu'aucun rumble n'y est réglé, où il ira, et ce qu'il reste à
relever. `tests/test_donnees.py::test_chaque_profil_livre_dit_ou_en_est_sa_vibration`
l'exige, sur le modèle exact de la garde qui existe déjà pour l'amorçage.

| Profil | Famille | Cible supposée du gabarit d'entrée | Clé de rumble |
|---|---|---|---|
| Cemu | dédiée | `controllerProfiles\` | non relevée |
| Dolphin | dédiée | `User\Config\GCPadNew.ini` | non relevée |
| Flycast | générale | `emu.cfg` | non relevée |
| PCSX2 | générale | `inis\PCSX2.ini` | non relevée |
| PPSSPP | dédiée | `controls.ini` | non relevée |
| RetroArch | dédiée | `autoconfig\*.cfg` | non relevée |
| RPCS3 | dédiée | `config\input_configs\` | non relevée |
| Xemu | générale | `xemu.toml` | non relevée |
| Vita3K | générale | `config.yml` | non relevée, et hors de portée tant que D5 dure |
| DuckStation | générale | `settings.ini`, section `[Pad1]` | **relevée** — `LargeMotor`, `SmallMotor` — mais jamais vue vibrer |

**Aucune case de ce tableau n'est une mesure**, hors la dernière ligne : les
colonnes « famille » et « cible » reprennent le tableau de la tâche 6 du plan
des manettes, qui les donne lui-même pour des hypothèses de travail — « les
deux seules lignes mesurées sont l'émulateur personnel et DuckStation ». S'y
appuyer sans les vérifier, c'est refaire l'erreur que ce tableau annonce. La
ligne Vita3K est en outre en amont de toutes les autres : l'émulateur ne
s'installe pas (D5), aucune cible écrivable ne désigne encore son
`config.yml`, et rien n'y sera mesurable avant que ce point soit levé.

**Le rappel a joué le 2026-08-29.** DuckStation était délibérément sans note
dans son profil : sa manette entière était muette (D3), et sur un émulateur
dont aucun bouton ne répond, la vibration n'est pas mesurable. Le test
l'exemptait nommément, en disant que retirer l'exemption le jour où D3 se clôt
le rendrait rouge. **D3 s'est close, l'exemption est retirée, et elle est
désormais VIDE** (`SANS_NOTE_DE_VIBRATION` dans `tests/test_donnees.py`) : les
dix profils livrés disent tous où en est leur vibration.

Ce que DuckStation en dit, et c'est tout ce qu'on en sait : ses deux liaisons
de vibration ont été écrites par son propre assistant, elles ont la bonne
forme, et **personne ne les a vues faire vibrer quoi que ce soit**. Le maillon
« émulateur → SDL → ViGEmBus » est désormais testable sans nouveau relevé — il
suffit de jouer, avec la manette qui répond depuis la clôture de D3.

**Le maillon Apollo → client, et la procédure de mesure que le propriétaire
joue au canapé**, vivent dans `nivuus/installer`, `docs/console-dettes.md`,
C1. L'ordre y est imposé et il n'est pas négociable : le réglage du client
Moonlight d'abord, parce que c'est le seul des trois qui se teste **sans rien
modifier**.

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

Pour DuckStation, `enforced` portait au matin du 2026-08-29 **trois clés** :
`SetupWizardIncomplete`, `StartFullscreen`, `CheckAtStartup` — les trois causes
mesurées d'un lancement qui échoue. Il en porte **trente-deux** au soir : les
vingt-sept liaisons de `[Pad1]` (D3), puis `CropMode`, `ForceAnalogOnReset`, et
les trois d'origine. `ConfirmPowerOff`, `PauseOnFocusLoss`, `SaveStateOnExit`,
`InhibitScreensaver` et `HideCursorInFullscreen` restent des préférences :
changées dans l'émulateur, elles tiennent.

Un piège documenté plutôt que découvert : le relevé de la manette exige de
repasser `SetupWizardIncomplete` à `true` et de lancer DuckStation hors du
chemin de la console. Le lancement suivant par la console le remettra à
`false`, et **c'est voulu** — c'est le rôle même de `enforced`. Le profil le
dit, pour que personne ne croie son relevé saboté.

### D2 est CLOSE POUR DUCKSTATION — 2026-08-29

`[Display] CropMode = Borders`, dans `enforced`. **Confirmé par le
propriétaire : plus aucune bande.** Le cas dur énoncé en tête de cette dette —
« pour lui, ça devra passer par son `settings.ini` » — est donc réglé, par le
mécanisme de fusion que l'arbitrage du matin a permis de construire.

D2 **reste ouverte** pour tout le reste : le remplissage de DuckStation, et les
six systèmes qui n'ont aucun bloc de rendu du tout.

#### La leçon, qui vaut plus que le réglage

**Deux tentatives ont échoué avant, et pour la même raison.** Les **chaînes du
binaire** donnent les **libellés de l'interface** — `All Borders`,
`Auto (Game Native)` — et **pas** les valeurs du fichier de configuration. Les
recopier produit une clé qui a l'air posée et qui ne fait rien.

Les vraies valeurs sont dans la **source** de DuckStation,
`src/core/settings.cpp`, tableau `s_display_crop_mode_names` :

    None, Overscan, OverscanUncorrected, Borders, BordersUncorrected

La même lecture a tranché `AspectRatio` : il **n'a pas** de tableau statique —
ses valeurs sont en minuscules (`auto`, `stretch`, `PAR 1:1`) ou un ratio
littéral. **`AspectRatio = Auto` est donc faux, et a été retiré.**

Ce que ces deux échecs confirment, et c'est la règle de fond de ce dépôt :
**une valeur fausse se comporte exactement comme l'absence de valeur.** Elle ne
produit aucun message, aucune ligne de journal, aucun symptôme distinct. La
même leçon est écrite dans `docs/releve-manettes.md`, parce que c'est là qu'on
la relit avant de recopier une valeur.

#### `Scaling` est un filtre, pas un cadrage

Mesuré le 2026-08-29 : **`Scaling = BilinearSmooth` a été posé, il a été
reconnu, et il n'a rien changé à la géométrie de l'image.** Il ne fait donc
**pas** partie du correctif, et le présenter comme tel ferait croire le cadrage
réglé par lui.

Ce que cela déplace pour le **remplissage** : le couple section/clé n'est plus
l'inconnue — c'est `[Display] Scaling`. Ce qui reste non mesuré, et qui interdit
d'écrire quoi que ce soit : personne n'a vu `NearestInteger` ni
`BilinearInteger` agir sur la machine.

### 🔴 Une découverte qui invalide une hypothèse de la conception de D2

**DuckStation réécrit son `settings.ini` à une fermeture propre depuis son
interface, et il en EFFACE TOUS LES COMMENTAIRES.** Mesuré le 2026-08-29 : le
fichier est passé de **2187 à 985 octets**. Les clés ont survécu — `[Pad1]`,
`[BIOS] SearchDirectory`, `SetupWizardIncomplete` ; les commentaires, non.

Or D2 a construit ce matin même un **en-tête en trois catégories** — ce que la
console impose, ce qu'elle a posé une fois, ce qui appartient au propriétaire —
et une garde au chargement qui **refuse un profil dont le `content` ne
l'explique pas**. **Cet en-tête disparaîtra au premier lancement en
interface.** Le mécanisme `enforced` repose bien les clés au lancement suivant ;
**rien ne repose l'explication** que le propriétaire est censé lire. Sous
`-batch -nogui` — le seul mode que la console emploie — la réécriture n'a pas
lieu : c'est le passage par l'interface qui efface.

**Ce n'est pas corrigé, délibérément. L'arbitrage appartient au propriétaire :**

> **Accepte-t-on qu'un `settings.ini` puisse se retrouver sans son en-tête
> explicatif après un passage par l'interface de DuckStation — oui ou non ?**

Si **oui**, il n'y a rien à faire, et la garde du `content` protège alors le
dépôt, pas la machine : elle garantit que le profil livré porte l'explication,
pas que le fichier de la console la porte encore. Si **non**, l'en-tête devient
une chose que `enforced` doit reposer comme il repose les clés — ce que le
mécanisme de fusion ne sait pas faire aujourd'hui, puisqu'il ne connaît que des
couples section/clé.

#### Et un faux oracle, issu de la même mesure

**« La clé a survécu » ne prouve PAS « la clé est reconnue ».**
`DisplayCropMode`, une clé **inventée**, a survécu à cette réécriture aussi :
DuckStation conserve ce qu'il ne comprend pas. C'est écrit ici pour que
personne ne s'en serve comme preuve — **la seule preuve reste l'effet observé.**

---

## D3 — DuckStation : la manette ne répond pas — RÉGLÉE le 2026-08-29

> **Cette dette est réglée.** La preuve qui manquait a été faite : **Crash Team
> Racing répond à la manette**, confirmé par le propriétaire le 2026-08-29 —
> le jeu qui était le défaut d'origine. Les trois conditions de la procédure
> sont remplies.
>
> **Elle n'a pas été réglée par les liaisons seules.** Il a fallu une seconde
> clé, `[Pad1] ForceAnalogOnReset = false`, sans laquelle les vingt-sept
> liaisons étaient justes et le jeu restait muet. Deux causes, un seul
> symptôme : c'est le fait le plus utile de cette entrée.
>
> **DuckStation ne trouve toujours pas sa manette seul.** Il ne la trouve que
> parce que la console lui impose vingt-huit clés à chaque lancement. Le
> profil ne déclare donc PAS `auto` — voir plus bas.

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
  `[input] mapping`, valant alors `auto`, `a-relever` ou `inconnu`, défaut
  `inconnu`. Le champ ne porte JAMAIS un identifiant : il porte l'état du
  relevé, seule chose qu'on puisse écrire sans avoir mesuré. DuckStation valait
  `a-relever` ; les huit autres valent `inconnu`, parce que personne ne les a
  mesurés. *(Un quatrième état est né le soir même, à la clôture : voir plus
  bas.)*
- **`retro status` a une section « Manettes »**, et fait du seul `a-relever` un
  problème nommant le fichier à ouvrir, la procédure à jouer, et la phrase qui
  empêche la fausse correction : « une liaison qui ne correspond à aucun
  périphérique est ignorée en silence ».
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

### Ce qui a CLOS D3, le 2026-08-29 au soir

La procédure pose **trois** conditions pour tenir un relevé pour bon. **Les
trois sont remplies**, la troisième ce jour-là :

| Condition | État |
|---|---|
| `[Pad1]` existe et porte des clés qui n'y étaient pas | ✅ vingt-sept liaisons |
| ces lignes ont été écrites par DuckStation, pas à la main | ✅ par son assistant |
| **un jeu répond à la manette** | ✅ **Crash Team Racing, confirmé par le propriétaire** |

La troisième était celle qui comptait, et pour une raison qui n'a pas changé :
**DuckStation ne dira jamais qu'une liaison ne correspond à rien.** Une valeur
juste et une valeur fausse produisent le même silence. C'est pourquoi seule une
manette vue répondre dans un jeu pouvait clore cette dette — et pourquoi aucune
relecture de fichier n'aurait suffi.

#### Le relevé ne suffisait pas : une SECONDE cause, même symptôme

`[Pad1] ForceAnalogOnReset = false`, désormais dans `enforced`. **Confirmé par
le propriétaire : la manette répond dès le lancement, sans bascule manuelle.**

Source : `src/core/analog_controller.cpp`. `ForceAnalogOnReset` est un booléen,
**de défaut `true`**, décrit *« Forces the controller to analog mode when the
game is started/restarted »*. Crash Team Racing est un jeu **d'avant
l'analogique** : forcé en mode analogique, il ne répond pas. Le message
« passage manette 1 en mode numérique », affiché après une bascule à la main,
réparait exactement ce symptôme — c'est ce qui a mis sur la piste.

**Les vingt-sept liaisons étaient donc justes pendant que le jeu restait
muet.** Deux causes indiscernables l'une de l'autre vu du canapé, et c'est le
fait à retenir de cette entrée.

**L'arbitrage, et il se paie.** `ForceAnalogOnReset` est un réglage **global**,
pas par jeu. Les titres qui veulent l'analogique — **Gran Turismo, Ape Escape,
Metal Gear Solid** — démarreront donc en mode **numérique**. La bascule existe
en jeu et elle est mappée : `Analog = SDL-0/Guide`, le bouton Guide du pad.
Deux clés voisines ont été lues et **non retenues**, faute d'avoir été mesurées :
`AnalogDPadInDigitalMode` (défaut `true`) et `AnalogSensitivity` (défaut 1.33).

#### `[input] mapping` : aucun des trois états existants n'était vrai

Le champ vaut désormais **`releve`**, un **quatrième** état ajouté ce jour-là
(`retro/profiles.py`, `MAPPING_RELEVE`). Les trois autres ont été écartés un
par un, et le raisonnement est le cœur de cette clôture :

- **`auto`** — « cet émulateur trouve sa manette seul » — aurait été **faux**,
  et faux de la façon exacte que cette dette a réfutée : DuckStation ne trouve
  sa manette **que** parce que la console lui impose vingt-huit clés. Le jour
  où quelqu'un « simplifierait » ce champ en `auto`, plus rien dans le dépôt ne
  dirait que retirer `enforced` rend la console muette.
- **`a-relever`** — « il ne la trouve pas, rien n'est relevé » — serait devenu
  faux aussi : `retro status` annoncerait « manette muette » sur le seul
  émulateur dont un bouton ait été VU agir, et le propriétaire apprendrait à
  ignorer la section.
- **`inconnu`** effacerait la mesure.

Plutôt que de tordre l'un des trois, le vocabulaire s'est allongé. `releve` dit
exactement ce qui a été constaté : *le relevé est fait, les liaisons sont
imposées, et un bouton a été vu répondre.* `mapping_where` y reste **exigé**,
pour la raison inverse d'avant : c'est le seul endroit où vérifier que les
liaisons imposées y sont encore.

#### ⚠️ Ce que la clôture NE dit PAS

- **Rien sur la vibration.** `LargeMotor` et `SmallMotor` ont la bonne forme,
  personne ne les a vus faire vibrer quoi que ce soit — c'est D1, et le maillon
  « émulateur → SDL → ViGEmBus » y devient seulement *testable*.
- **La FRAGILITÉ 1 n'est pas levée.** `SDL-0` est un **index**, pas un GUID. Un
  pad de plus énuméré avant celui d'Apollo — une DualShock 4 laissée branchée,
  un pad du client — et les vingt-sept liaisons visent un périphérique absent.
  DuckStation ne le dira pas : le symptôme sera identique à la panne d'origine.
- **La FRAGILITÉ 2 non plus** : le propriétaire ne peut pas remapper sa manette
  depuis l'interface de DuckStation, `enforced` reposant les liaisons à chaque
  lancement. C'est le prix assumé, écrit dans le profil.
- **Un essai AU FLUX n'a toujours pas eu lieu.** Le `perm=0x3000000` du client
  appairé (`403 Permission denied` au `/launch`) bloque l'ouverture d'une
  session Moonlight. La confirmation du propriétaire vaut ce qu'elle vaut :
  une manette qui répond dans le jeu. Qui voudra vérifier dans les conditions
  du canapé — session Moonlight, pad d'Apollo — devra d'abord régler ce `perm`.
  Voir `docs/console-dettes.md` de `nivuus/installer`.

### Ce que la clôture DÉBLOQUE

**C2 et D4 attendaient « une manette qui répond » depuis le début. Elles sont
débloquées.**

- **D4** (ici même) posait l'ordre : « D3 d'abord (une manette qui répond),
  puis le type de pad, puis le mouvement. Inverser, c'est déboguer deux
  inconnues à la fois. » La première étape est franchie.
- **C2** (`docs/console-dettes.md` de `nivuus/installer`) imposait le même
  ordre pour la bascule d'Apollo vers une DualShock. Ce n'est plus une dette en
  attente d'une autre : c'est la prochaine.

**Ce que ça coûtait, et qui est réglé :** le seul émulateur PlayStation de la
console était réputé injouable. Il ne l'est plus.

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

**D4 EST DÉBLOQUÉE — 2026-08-29.** La première étape de cet ordre est
franchie : D3 est close, la manette répond dans DuckStation (Crash Team Racing,
confirmé par le propriétaire). D4 n'attend donc plus rien qu'elle-même — c'est
au type de pad de venir, et il se change dans `nivuus/installer` (C2).

Deux précautions, qui ne sont pas levées par cette clôture :

- **Ce qui rend D4 coûteuse n'a pas changé** : basculer Apollo en DualShock
  change le VID/PID, donc le GUID SDL, donc les identifiants des configurations
  d'entrée. C'est le fait n° 2 du plan des manettes.
- **Sauf pour DuckStation, et c'est mesuré.** Ses liaisons ne portent qu'un
  **index** (`SDL-0`), jamais un GUID — le relevé du matin l'a tranché sur le
  binaire. Un changement de type de pad ne les casse donc pas mécaniquement.
  Ce qui les casse, c'est un pad **de plus** énuméré avant celui d'Apollo. À
  confirmer avant de s'en servir, mais c'est ce que le binaire dit.

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
