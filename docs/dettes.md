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

> **Plan écrit le 2026-08-29** — `docs/superpowers/plans/2026-08-29-d1-vibration.md` :
> l'ordre imposé C1 → jouer → D4 → les huit autres, et le champ `[input] rumble` qui remplace la note en commentaire.

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
| Vita3K | générale | `config.yml` | non relevée — D5 est close, mais la cible reste hors d'atteinte : aucun `target` ne désigne la racine d'émulation (D7) |
| DuckStation | générale | `settings.ini`, section `[Pad1]` | **relevée** — `LargeMotor`, `SmallMotor` — mais jamais vue vibrer |

**Aucune case de ce tableau n'est une mesure**, hors la dernière ligne : les
colonnes « famille » et « cible » reprennent le tableau de la tâche 6 du plan
des manettes, qui les donne lui-même pour des hypothèses de travail — « les
deux seules lignes mesurées sont l'émulateur personnel et DuckStation ». S'y
appuyer sans les vérifier, c'est refaire l'erreur que ce tableau annonce. La
ligne Vita3K est en outre en amont de toutes les autres, mais **plus pour la
raison écrite ici — corrigé le 2026-08-29** : l'émulateur s'installe désormais
et tourne (D5). Ce qui la bloque est ailleurs, et c'est plus étroit : aucune
cible écrivable ne désigne encore son `config.yml`, faute d'un jeton de chemin
(D7). Rien n'y sera mesurable avant que ce point-là soit levé.

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

> **Plan écrit le 2026-08-29** — `docs/superpowers/plans/2026-08-29-d2-remplissage-image.md` :
> douze tâches ; le remplissage de DuckStation est aujourd'hui **indéclarable** dans le modèle de `render.py`, et c'est à corriger avant la mesure.

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

#### ~~`Scaling` est un filtre, pas un cadrage~~ — CETTE CONCLUSION ÉTAIT FAUSSE

**Retiré le 2026-08-29 au soir. C'était un TROISIÈME faux oracle**, et il a
tenu une demi-journée.

Ce qui avait été écrit : « `Scaling = BilinearSmooth` a été posé, il a été
reconnu, et il n'a rien changé à la géométrie de l'image ».

Ce que dit la source, vérifié sur le tag épinglé :

    static constexpr DisplayScalingMode DEFAULT_DISPLAY_SCALING =
        DisplayScalingMode::BilinearSmooth;          // settings.h:242

**`BilinearSmooth` EST le défaut.** Poser cette valeur-là, c'est reposer ce que
DuckStation aurait fait sans elle. L'essai ne prouve donc **ni** que `Scaling`
est un filtre, **ni** même que la clé a été lue : `.value_or` retombe
silencieusement sur ce même défaut. Il ne prouve rien du tout.

**Et le relevé dit l'inverse de la conclusion retirée.** `Scaling` porte bien
l'axe du remplissage, et il agit sur la **géométrie** :
`IsUsingIntegerDisplayScaling` (settings.h:217) → `video_presenter.cpp:610` →
`GPU::CalculateDrawRect` (gpu.cpp:2250), qui applique un `std::floor(scale)` et
centre le résidu. Les sept valeurs sont dans `s_display_crop_mode_names`'s
voisin, `s_display_scaling_names` (settings.cpp:2218) :

    Nearest, NearestInteger, BilinearSmooth, BilinearHybrid,
    BilinearSharp, BilinearInteger, Lanczos

**Ce que cela ne change pas :** aucune valeur n'est posée. `NearestInteger` et
`BilinearInteger` n'ont toujours **jamais été vus agir** sur la machine, et
c'est la mesure T3 du plan qui tranchera. Ce qui a changé, c'est qu'on ne croit
plus savoir que la réponse est non.

**La leçon, qui est la même que les deux fois précédentes, sous un troisième
déguisement :** un essai dont la valeur posée est le défaut de l'émulateur ne
peut rien conclure. Avant de mesurer une clé, il faut lire son **défaut** dans
la source — sans quoi on mesure l'absence de changement et on l'appelle un
résultat.

**Ce qui reste vrai, et pour la raison inverse :** `CropMode = Borders` a bien
fermé le cadrage, et cette mesure-là tient — `DEFAULT_DISPLAY_CROP_MODE` vaut
`Overscan` (settings.h:237), donc la valeur posée **différait** du défaut, et
la disparition des bandes est un vrai signal.

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
> parce que la console lui impose **vingt-huit clés de `[Pad1]`** à chaque
> lancement — sur trente-deux imposées en tout, les quatre autres étant hors
> manette (`Main`, `AutoUpdater`, `Display`). Les deux comptes sont exacts et
> ne disent pas la même chose ; les confondre a déjà produit une erreur dans
> cette entrée, corrigée le 2026-08-29. Le profil ne déclare donc PAS `auto` —
> voir plus bas.

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
  trois clés ; elle en vaut **trente-deux**. L'élargissement est délibéré et
  son prix
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

> **Plan écrit le 2026-08-29** — `docs/superpowers/plans/2026-08-29-d4-mouvement-et-type-de-pad.md` :
> le filet anti-GUID d'abord, dépôt seul, **avant** toute bascule ; porte l'arbitrage RPCS3 rendu le même jour.

**Constaté le 2026-08-28.** Les émulateurs qui en ont besoin — PPSSPP, RPCS3,
Vita3K — ne reçoivent aucune donnée de gyroscope, et rien dans la chaîne ne
prétend en transmettre.

**Corrigé le 2026-08-29 :** cette phrase citait aussi **PCSX2**, et c'était
faux. La PS2 n'avait aucun capteur de mouvement ; PCSX2 n'a donc aucune clé de
mouvement à régler, et l'y chercher aurait coûté un relevé pour rien. La
mention « un futur PS Vita (D5) » est également périmée — Vita3K est installé
et tourne, et son mouvement ne dépend d'aucune clé de configuration mais de
`SDL_GamepadHasSensor`, donc du type de pad qu'Apollo annonce.

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
être la seule source de l'identifiant — jamais une valeur figée dans un
profil. Puis, par émulateur, les clés de mouvement de sa configuration
d'entrée.

**🔴 Cette phrase disait « doit RESTER », et c'était faux — corrigé le
2026-08-29.** Le mécanisme n'existe pas : il n'y a **aucune** substitution
d'identifiant dans le dépôt. Les seuls jetons sont `{render_config}` côté
Python, et `{render}`, `{rom}`, `{width}`, `{height}`, `{scale}` côté lanceur
C# — tous de rendu. Les tâches 2 à 4 du plan des manettes n'ont jamais été
faites. Il n'y a donc rien à préserver, tout à construire, et le bloc
« DETTE D4 » de `vita3k.toml` annonce ce mécanisme comme existant : c'est à
corriger avec lui. La conséquence pratique est que **le seul identifiant figé
aujourd'hui vit hors dépôt** — le `Device: "XInput Pad #1"` posé à la main dans
le `Default.yml` de RPCS3 (D7), qui n'est donc protégé par aucune garde et sera
le premier à mourir à la bascule.

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

## D5 — PS Vita — RÉGLÉE le 2026-08-29 : l'émulateur est installé, le firmware posé, un jeu se lance

**Constatée le 2026-08-28. Reprise puis CLOSE le 2026-08-29.** L'étiquette
roulante n'a pas été contournée : elle a été rangée là où elle est acceptable,
dans le manifeste du propriétaire. Ce qui reste ouvert est écrit à la fin, et
ce n'est plus la PS Vita — c'est la péremption de son empreinte.

### Ce que la clôture repose sur, mesuré le 2026-08-29

| Étape | Preuve |
|---|---|
| Empreinte | archive **téléchargée**, `hashlib.sha256` sur l'octet reçu — `f44883ea…93d04a` |
| Archive listée | 133 entrées, 20 éléments racine, **`Vita3K.exe` à la racine, à plat** |
| Options | `Vita3K.exe --help` relevé **sur le binaire installé** : `content-path`, `--fullscreen`, `--firmware`, `--installed-path`, `--config-location` |
| Installation | par `retro install` (empreinte vérifiée, extraction refusant les `../`) |
| Firmware | `Firmware Version: 0x3740000` (3.74), progression 10 % → 100 %, `os0\` 69 fichiers + `vs0\` 1473 |
| Jeu répertorié | *Uncharted Golden Abyss*, système « PS Vita », plan `vita3k.vita.ini` écrit |
| Jeu lancé | Vita3K **vivant à 50 s**, 1,4 s CPU, 129 Mo, ligne `Vita3K.exe --fullscreen "…vpk"` — voir la réserve ci-dessous |
| Jeu dans Steam | `+ Uncharted Golden Abyss`, 5 jaquettes, tag « PS Vita » |

### 🔴 Ce que ce tableau ne prouve pas — relu le 2026-08-29 au soir

**La ligne « Jeu lancé » ne prouve pas qu'un jeu tourne.** Ce qu'elle mesure,
c'est un **processus vivant** : 1,4 s de CPU et 129 Mo au bout de 50 s. C'est
aussi le profil d'un émulateur assis sur une boîte modale. Aucune capture,
aucun signe de rendu n'a été relevé. Et la ligne de commande citée porte un
`.vpk` — c'est-à-dire très exactement la voie que **D9** mesure comme
**refusée** (`A Vitamin dump was detected, aborting installation`).

Ce qui reste donc acquis, et c'est déjà beaucoup : l'émulateur s'installe, son
empreinte est relevée sur l'archive reçue, son firmware 3.74 est posé, son
plan de lancement est écrit et son entrée Steam existe. Ce qui n'est **pas**
établi : qu'un jeu ait affiché quoi que ce soit. Le titre de cette dette disait
« un jeu tourne » ; il dit désormais « un jeu se lance », qui est ce que la
mesure porte.

**Et la mention « paquet de polices : non mesuré », plus bas, est périmée** :
D9 l'a mesurée le même jour — c'est une modale bloquante « Missing Firmware »,
désarmée à la main, que rien ne repose.

**Deux mesures ont corrigé le profil**, et ni l'une ni l'autre n'était
devinable sans l'archive : la forme courte du plein écran est **`-F`
majuscule** (`-f` est `--load-config`, donc un `-f` par réflexe aurait chargé
une configuration en se comportant comme un drapeau ignoré) ; et Vita3K a
**deux racines** — sa configuration à côté de l'exécutable, ses données dans
`%APPDATA%\Vita3K\Vita3K\`, où le firmware s'est déposé.

### 🔴 Ce que la clôture a révélé, et qui vaut bien au-delà de la PS Vita

**La console faisait tourner un `retro` PÉRIMÉ.** Le paquet installé sur
l'invité (`C:\Python\Lib\site-packages\retro`) ne portait que **neuf**
profils — pas de `vita3k.toml`. Le scan y déclarait donc `Sony\PS Vita`
« dossier ne correspondant à aucun système connu », alors que le même scan
lancé depuis l'hôte, sur le dépôt courant, l'appariait sans problème.

Ce n'est pas un détail de la PS Vita : **tout correctif écrit dans ce dépôt
reste sans effet sur la machine tant que la roue n'y est pas réinstallée**, et
rien ne le signale. Les deux versions portent le même numéro (0.1.0), donc
comparer les versions ne l'aurait pas montré. C'est une dette à part entière
et elle n'existe pas encore.

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

### Ce qui reste — et ce n'est plus l'installation

**La péremption, et elle est datée.** L'empreinte inscrite au manifeste du
propriétaire vaut pour l'archive du 2026-08-09. Elle mourra à la prochaine
construction de Vita3K, et le symptôme sera un `retro install` qui échoue en
annonçant une empreinte inattendue. **Ce n'est pas une alerte de sécurité** :
c'est la péremption prévue, le geste est de re-télécharger, recalculer,
remplacer les deux lignes. C'est écrit dans le manifeste, à côté de l'entrée.

**Le paquet de polices n'est pas installé.** Vita3K le distingue du firmware
principal et écrit lui-même qu'il n'en publie pas l'URL. Rien n'a donc été
pris ailleurs. Symptôme attendu s'il manque : du texte absent en jeu, pas un
refus de démarrer. ~~**Non mesuré.**~~ **MESURÉ depuis, le 2026-08-29 — et le
symptôme attendu était faux** : ce n'est pas du texte absent, c'est une
**modale bloquante** au démarrage (« Missing Firmware […] Font package »), avec
`[Launch Anyway]` et une case à cocher. Voir **D9**. La case a été cochée à la
main et rien ne la repose.

**Le rangement du PUP n'est pas tranché.** Il a été déposé dans
`G:\retro\bios\` alors que le raisonnement ci-dessous range les firmwares
HORS de `bios\`. C'est un constat, pas une décision. Et rien ne sait encore
constater qu'un firmware est DÉJÀ installé — sans quoi un amorçage le
réinstallerait à chaque lancement, sept secondes par jeu.

### L'historique, conservé — pourquoi l'empreinte ne pouvait pas vivre au noyau

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

---

## D6 — La console tourne sur un paquet périmé, et absolument rien ne le dit — RÉGLÉE le 2026-08-29

> **CLOSE, et la preuve qui manquait a été faite sur la machine.** Les six
> mesures de la tâche 6 du plan sont consignées ci-dessous. La ligne qui clôt
> la dette est la troisième — c'était son assertion centrale, et la seule qui
> ne pouvait se mesurer nulle part ailleurs.
>
> | Mesure | Résultat |
> |---|---|
> | État de départ | `retro.exe identite` → `invalid choice: 'identite'` ; le témoin `D:\state\retro.status` **n'existait pas du tout** ; dix profils installés |
> | Le refus | **code 8**, message nommant la version de l'hôte et le remède, et **aucun effet de bord** — pas d'inventaire créé, Steam intact |
> | **Le remède** | `Found existing installation: retro 0.1.0` → `Successfully uninstalled retro-0.1.0` → **`Successfully installed retro-0.1.0+20260829174234.380c62ac.g4bf8334`** |
> | Le témoin | `package=0.1.0+20260829174234.380c62ac.g4bf8334`, identique à `identite_roue` sur l'hôte, entre `emulation_root=` et `report:` |
> | Le rapport | `retro scan` cite `paquet : 0.1.0+…` en tête |
> | Second passage | **aucun écart, aucun refus** — l'identité survit à sa propre écriture, ce que le plan désignait comme le défaut le plus probable du mécanisme |
>
> **Ce que la mesure a trouvé, et que rien dans les dépôts ne pouvait voir.**
> Trois défauts, dont aucun n'était visible depuis une suite de tests verte :
>
> 1. **Le paquet ne se construisait pas.** Les trois hooks
>    `get_requires_for_build_*` étaient réexportés tels quels ; or pip appelle
>    `get_requires_for_build_wheel` en PREMIER et setuptools y lit déjà la
>    version dynamique. Sous `--no-build-isolation` — le seul chemin que les
>    tests empruntaient — cela passait ; sous isolation, c'est-à-dire sur le
>    chemin de production, la construction mourait en
>    `ModuleNotFoundError: retro._identite`. **Le correctif de D6 ne se
>    construisait que dans le harnais qui l'avait écrit**, et se serait
>    effondré à la première vraie construction. D6 s'est attrapée elle-même.
> 2. **`ROMS_ROOT` désignait `G:\ROMs`, qui n'existe pas** (la bibliothèque
>    est dans `G:\Games`). `retro scan` échouait donc à chaque passage aux
>    valeurs par défaut, depuis que la constante existe.
> 3. **Le scan ne recevait pas les profils du propriétaire**, seulement son
>    manifeste. Le profil de l'un de ses émulateurs — celui que ce dépôt ne
>    peut pas nommer, et qui vit pour cette raison sur son partage — dit quels
>    dossiers lui appartiennent. Sans lui, le système que cet émulateur sert
>    devient **inconnu**, et la synchronisation **retire de Steam les six jeux
>    concernés**, en purgeant leur artwork, sans un mot.
>
> **Le troisième était masqué par le second**, et c'est la leçon à retenir :
> tant que le scan échouait en amont, la synchronisation n'arrivait jamais
> jusqu'au point où l'absence de profils aurait fait des dégâts. **Réparer un
> défaut en a armé un autre**, et cela s'est produit pour de vrai sur la
> console avant d'être corrigé. La bibliothèque a été restaurée au passage
> suivant — les six jeux sont revenus, dix ROMs répertoriées contre quatre.
>
> Les trois sont corrigés, chacun avec une garde vue rouge avant d'être verte.
>
> **Ce que cette clôture ne dit pas :** la mesure a été faite une fois, sur une
> console. Elle prouve que le mécanisme fonctionne, pas qu'il résistera à une
> reconstruction complète de la machine virtuelle — le provisionnement écrit
> le témoin par un autre chemin (`32-retro.ps1`), qui n'a été relu qu'en
> syntaxe. Et **D11 reste entière** : ce qui est vrai du paquet ne l'est pas
> encore du fragment de clés imposées.

> **EXÉCUTÉE DES DEUX CÔTÉS le 2026-08-29 — et TOUJOURS OUVERTE, faute de
> mesure.** Le paquet porte une identité qui bouge
> (`0.1.0+<horodatage>.<empreinte>[.g<sha>]`, gravée par un backend PEP 517 en
> arbre), `retro identite` la dit, et `scan` comme `status` la citent en tête
> de leur rapport. **Le refus existe aussi**, dans `nivuus/installer`
> (`retro-sync : l hote refuse de synchroniser un paquet qui n est pas le
> sien`) : la clé `package=` est écrite par les deux écrivains du témoin,
> `ecart_identite` est une fonction pure qui refuse en **code 8**, et
> `--reinstaller-le-paquet` est le geste de sortie — sans lui, refuser rendrait
> la console non synchronisable.
>
> **Ce qui manque pour clore, et ce n'est pas du code :** personne n'a vu `pip`
> rapporter « Successfully installed retro-0.1.0+… » là où il disait
> « Requirement already satisfied ». C'est l'assertion centrale de cette dette,
> et elle ne se mesure que sur la console. Deux suppositions l'accompagnent :
> `/var/lib/nivuus/guest/payload/retro/wheels/` n'a **jamais été vu peuplé** sur
> l'hôte — le chemin est déduit, pas observé —, et aucun PowerShell n'a
> réellement tourné.
>
> **Une correction rendue en revue, qui vaut d'être lue** : la garde d'identité
> avait été placée **avant** la sonde de session de streaming. Or
> `--reinstaller-le-paquet` lance un `pip install` dans l'invité, c'est-à-dire
> une **mutation**, et la garde de session existe précisément pour qu'aucune
> mutation n'ait lieu pendant qu'on joue. Dans cet ordre, le remède
> s'exécutait, **puis** le script refusait en code 7 : un refus qui arrive
> après coup, alors qu'un refus doit vouloir dire que rien ne s'est produit.
> L'ordre est inversé et deux assertions l'épinglent, vues rouges sur l'ancien.
>
> **Le défaut est pire que ce que cette entrée disait**, et c'est mesuré :
> `pip install --no-index --find-links … --upgrade retro` à version identique
> rend `Requirement already satisfied` — la ligne exacte de `32-retro.ps1`.
> Tant que `0.1.0` ne bougeait pas, l'installation **ne se faisait jamais**.
> Reprovisionner la console n'y aurait rien changé.
>
> **Un piège qui aurait rendu le correctif inopérant en silence**, trouvé en
> l'écrivant : `setuptools.config.expand.read_attr` charge le module désigné
> **par chemin, sans importer le paquet parent**. Lire `retro.identite.VERSION`
> — ce que prescrivait le plan — faisait échouer son `import retro._identite`,
> et **toute roue sortait en `0.1.0+source`**. C'est-à-dire : le correctif de
> D6 aurait été annulé par très exactement le genre de panne muette que D6
> existe pour tuer. La lecture porte donc sur `retro._identite.VERSION`, un
> littéral relu à l'AST, sans aucun import.

> **Plan écrit le 2026-08-29** — `docs/superpowers/plans/2026-08-29-d6-identite-du-paquet.md` :
> **EN COURS D'EXÉCUTION** — tâches 1 à 3 et 5 engagées le 2026-08-29 au soir.

**Constatée le 2026-08-29**, en cherchant pourquoi la PS Vita se comportait
différemment selon d'où le scan était lancé.

### Le symptôme, et pourquoi il égare

Le même `retro scan`, sur la même bibliothèque, rendait **deux résultats
différents** :

| Lancé depuis | Résultat |
|---|---|
| l'hôte, sur le dépôt courant | 9 ROMs, `Sony\PS Vita` apparié |
| l'invité, sur le paquet installé | 8 ROMs, `Sony\PS Vita` « ne correspond à aucun système connu » |

La cause : `C:\Python\Lib\site-packages\retro` ne portait que **neuf** profils —
pas de `vita3k.toml`. Le paquet installé sur la console datait d'avant.

### Ce qui rend cette dette dangereuse plutôt que cosmétique

**Les deux versions portent le même numéro : `0.1.0`.** Comparer les versions ne
révèle rien. Rien dans le rapport de `scan`, de `sync` ou de `status` ne
mentionne quelle révision du paquet a produit l'inventaire. Un correctif écrit,
testé et commité ici peut donc **rester sans le moindre effet sur la machine**,
et le message d'erreur qu'on obtiendra alors décrira le symptôme d'origine —
exactement comme si le correctif était faux.

C'est un multiplicateur de coût sur toutes les autres dettes : chaque heure
passée à corriger un profil peut être annulée en silence par une installation
qui n'a pas suivi.

### Ce qui l'a masquée jusqu'ici

`retro_sync.py` documente longuement que `retro scan` tourne DANS l'invité, et
c'est le bon choix — « cette machine » et « la console » y désignent le même
disque. Mais il en découle que **c'est le paquet de l'invité qui décide**, et
personne n'avait tiré cette conséquence.

### Ce qui reste à faire

Rien n'est fait, hors le dépannage : la roue courante a été construite et
réinstallée à la main sur la console le 2026-08-29, ce qui lui a rendu ses dix
profils. Le correctif durable demande deux choses, et la seconde compte plus que
la première :

1. **une version qui bouge** — un horodatage de construction ou le SHA du dépôt,
   puisque `0.1.0` ne distingue rien ;
2. **que quelque chose la CONSTATE**, côté hôte, et refuse ou signale un écart.
   Le témoin `D:\state\retro.status` existe déjà et porte le résultat de
   l'installation ; c'est le bon endroit pour y ajouter l'identité du paquet.

**Ce que ça coûte aujourd'hui :** rien ne garantit que la console exécute le
code de ce dépôt, et c'est le propriétaire qui découvrira l'écart, sous la forme
d'un correctif qui « ne marche pas ».

---

## D7 — Quatre réglages mesurés, indispensables, que le mécanisme d'amorçage ne sait pas tenir

> **PARTIELLEMENT EXÉCUTÉE le 2026-08-29 — et TOUJOURS OUVERTE.** Le mécanisme
> existe : le jeton de chemin est **`{install_dir}`** (et non `{emulation_root}`
> — l'`install_dir` est surchargeable par le manifeste du propriétaire, et le
> réécrire dans un profil ferait rater la cible en silence), un profil peut
> désormais porter **plusieurs** cibles (`[[bootstrap]]`), et le lanceur C#
> boucle dessus avec une garde qui refuse bruyamment un jeton non substitué.
> Vita3K est réglé. **Les quatre réglages ne sont pas tous posés** : RPCS3
> attend encore ses modales et sa manette.
>
> **Ce que la migration a révélé, et qui justifie à lui seul le détour :**
> `status.py` lisait `getattr(profil, "bootstrap", None)`. Après le renommage
> il aurait rendu « aucun amorçage déclaré » pour **tous** les profils, sans
> erreur ni symptôme — la panne muette exacte que ce plan combat.
>
> **Ce qui n'est pas prouvé :** il n'existe aucun compilateur C# sur l'hôte
> (ni `csc`, ni `mcs`, ni `mono`, ni `dotnet`). Le `.cs` n'est validé que par
> des tests Python qui exigent qu'il *lise* chaque clé du plan. La boucle
> réelle, la levée de la garde, le témoin par cible et la sortie `--explain`
> indicée restent à mesurer sur la console.
>
> **Conséquence à porter sur la machine :** l'ordre `retro launcher`,
> `compiler.cmd`, **puis** `retro scan` est obligatoire.
>
> **Et ce que cet ordre protège, dit exactement — parce que la formule courte
> « un lanceur d'avant échoue bruyamment sur un plan d'après » a été héritée
> ailleurs où elle est FAUSSE (voir D12).** Ici elle est vraie, et elle l'est
> pour une raison qui ne se généralise pas : **D7 a RENOMMÉ des clés.** Le
> lanceur pré-D7 appelle `Valeur(p, "bootstrap_target")` (relu dans
> `a0910c4:retro/data/launcher/retro-launch.cs`, ligne 173) ; le plan d'après
> n'écrit plus cette clé — il écrit `bootstrap_count` et
> `bootstrap_target.<n>` —, et `Valeur()` LÈVE sur une clé absente, avec un
> message qui nomme le champ manquant. Dans l'autre sens — lanceur d'après,
> plan d'avant — c'est la même levée, sur les clés indicées cette fois.
>
> **Ce garde-fou tient à la DISPARITION d'une clé, pas à l'ancienneté du
> binaire.** Une évolution qui se contente d'AJOUTER des lignes au plan n'en
> reçoit rien : le lanceur ancien ne cherche pas ce qu'il ne connaît pas, et
> `TryGetValue` ne lève sur rien. C'est le cas de la langue (D12), et c'est
> pourquoi la phrase y a été refaite plutôt que recopiée.

> **Plan écrit le 2026-08-29** — `docs/superpowers/plans/2026-08-29-d7-jeton-de-chemin-et-fusion.md` :
> **EN COURS D'EXÉCUTION** — tâches 1 à 4 engagées le 2026-08-29 au soir ; le jeton retenu est `{install_dir}`, pas `{emulation_root}`.

> **CORRIGÉ le 2026-09-04 — « tâches 1 à 4 » était PÉRIMÉ.** L'état du code a
> été mesuré contre le plan plutôt que déduit de cette phrase, et **les sept
> tâches de dépôt sont faites**, chacune avec ses tests. La tâche 7 en
> particulier — celle que cette entrée ne mentionne nulle part — existe :
> `install.configurations_effacees` et `install.format_configurations_effacees`
> nomment, après chaque installation, les configurations que `retro install`
> vient d'effacer avec le dossier, et `_cmd_install` les imprime. Ses trois
> tests sont là. Vérification : tous les noms de test que le plan prescrit
> existent dans `tests/`, à une exception près —
> `test_le_rapport_nomme_les_deux_cibles_d_un_profil`, livré sous un meilleur
> nom, `test_deux_cibles_non_amorcees_ne_donnent_pas_deux_lignes_identiques`.
>
> **CE QUI RESTE DE D7 EST LA TÂCHE 8, ET ELLE EST ENTIÈREMENT SUR LA CONSOLE.**
> Rien n'en est faisable depuis l'hôte, et c'est la seule raison pour laquelle
> cette dette reste ouverte :
>
> | | Mesure due |
> |---|---|
> | M1 | l'ordre `retro launcher` → `compiler.cmd` → `retro scan` |
> | M2 | rouvrir le `CurrentSettings.ini` que RPCS3 a écrit après décochage, et recopier de là le groupe et la forme des valeurs |
> | M3 | `--explain` à blanc sur un jeu de chaque profil touché — aucune ligne ne doit contenir `{` |
> | M4 | l'auto-réparation Vita3K, et l'idempotence de la fusion, prouvées |
> | M5 | la manette RPCS3 après une montée de version — **un bouton VU répondre**, un fichier posé ne prouve pas une manette |
>
> Et le blocage de fond n'a pas bougé : **aucun compilateur C# sur l'hôte**,
> revérifié le 2026-09-04 (ni `csc`, ni `mcs`, ni `mono`, ni `dotnet`). La
> boucle du lanceur, la levée de la garde, le témoin par cible et la sortie
> `--explain` indicée n'ont jamais été compilés, encore moins exécutés.

**Constatée le 2026-08-29**, sur **trois** émulateurs, pour deux raisons
différentes — et c'est la répétition qui en fait une dette de mécanisme plutôt
que trois notes de profil éparses.

### Les trois cas

**L'émulateur du propriétaire, hors dépôt — le tactile.** Mesuré dans sa
source : le tactile n'est alimenté que si `EnableMouse` est FAUX
(`if (_viewModel.IsActive && !ConfigurationState.Instance.Hid.EnableMouse.Value)`).
La valeur est actuellement bonne sur la machine. Si elle est cochée un jour dans
l'interface — son libellé, « Direct Mouse Access », donne envie de l'activer —
**le tactile meurt sans un mot**. Le profil ne peut pas la réimposer : la
configuration de cet émulateur est du **JSON**, et la fusion ne parle qu'INI
(`cles_ini` dans `profiles.py`, et le lanceur C# qui fusionne des
`[section] clé=valeur`). Son profil vit sur le partage du propriétaire ; c'est
donc là que la note est écrite, et ici qu'est la cause.

**Vita3K — la modale de privilèges.** Vita3K affiche à chaque lancement un
avertissement disant qu'il tourne avec des privilèges élevés — la fonction
s'appelle `prompt_admin_privileges_warning_if_needed` — et c'est une boîte
modale qu'aucune manette ne ferme. (Le message anglais n'est pas recopié ici :
il contient une chaîne que `test_aucun_emulateur_au_statut_conteste` confond
avec un nom d'émulateur interdit, voir la note en fin de dette.) Elle se désactive par
`[MainWindow] warnAdminPrivileges=false` — un **INI**, cette fois, donc la
fusion saurait le faire. Mais le fichier vit dans
`<racine d'émulation>\Vita3K\gui-configs\CurrentSettings.ini`, et
`_lire_bootstrap` exige un `target` **absolu ou commençant par une variable
d'environnement**. La racine d'émulation est un paramètre de `retro scan`, pas
une constante : aucun `target` écrivable ne la désigne.

**RPCS3 — la manette, et les sept boîtes de dialogue.** Deux réglages, tous
deux sous la racine d'émulation, tous deux vitaux :

1. `config\input_configs\global\Default.yml`. Sans ce fichier, `cfg_player`
   vaut `pad_handler::null` — relevé dans `Emu/Io/pad_config.h` — donc le joueur
   1 n'a **aucun gestionnaire de manette**. Ce n'est pas une mauvaise liaison,
   c'est l'absence de manette. Mesuré le 2026-08-29 sur LittleBigPlanet : le jeu
   tournait à 30 fps et aucun bouton ne répondait. Trois lignes suffisent —
   `Handler: XInput` et `Device: "XInput Pad #1"` — parce que
   `xinput_pad_handler::init_config()` renseigne les vingt-quatre `.def` puis
   appelle `from_default()`. Le fichier fait **61 octets** et le propriétaire a
   confirmé : les contrôles répondent.
2. `GuiConfigs\CurrentSettings.ini`, section `[main_window]`. **Huit** boîtes
   modales sont à `true` par défaut, relevées dans `rpcs3qt/gui_settings.h`
   (cette entrée a d'abord écrit « sept » en en nommant huit — le compte à
   retenir est celui de la source, pas celui de cette phrase) :
   `infoBoxEnabledWelcome`, `infoBoxEnabledInstallPUP`, `infoBoxEnabledInstallPKG`,
   `confirmationBoxBootGame`, `confirmationBoxExitGame`, `confirmationObsoleteCfg`,
   `confirmationSameButtons`, `confirmationRestart`. `confirmationBoxBootGame`
   s'interpose **à chaque lancement de jeu** ; `infoBoxEnabledInstallPUP` est ce
   qui laissait RPCS3 ouvert après l'installation du firmware.

Deux pièges de forme y sont attachés, et chacun aurait produit un réglage
d'apparence posé qui ne fait rien : la valeur est `XInput`, avec ses deux
majuscules (`pad_config_types.cpp`, `case pad_handler::xinput: return "XInput";`) ;
et `Device` **doit être cité**, car en YAML `#` ouvre un commentaire —
`XInput Pad #1` non quoté devient `XInput Pad`.

### Ce qui manque, et c'est la même pièce dans les trois cas

Un **jeton de chemin** dans `target`, sur le modèle de `{render_config}` que
`retro/launcher.py` substitue déjà — quelque chose comme
`{emulation_root}\Vita3K\gui-configs\CurrentSettings.ini`. Cela lève Vita3K
**et les deux fichiers de RPCS3** immédiatement, soit trois des quatre réglages.
L'émulateur hors dépôt demande en plus un **second dialecte de fusion**, JSON,
côté validation Python comme côté lanceur C#.

**Et un aggravant propre à RPCS3 :** ses deux fichiers vivent sous son dossier
d'installation, que `retro install` **efface à chaque montée de version**. La
manette redeviendrait donc muette à une simple mise à jour de l'émulateur, sans
qu'aucun message ne fasse le lien.

### Ce qu'il ne faut pas faire, et pourquoi c'est tentant

Poser ces valeurs une fois à la main — ce qui a été fait le 2026-08-29 pour les
deux — **donne l'illusion que c'est réglé**. Ça ne l'est pas : rien ne les
repose. C'est très exactement la distinction que les régimes `content` et
`enforced` existent pour porter, et ces deux réglages-ci sont du `enforced` :
sans eux, le tactile est mort ou une modale bloque le lancement.

**Ce que ça coûte aujourd'hui :** quatre pannes silencieuses en sommeil sur
trois émulateurs, dont aucune ne se manifestera par un message. Elles
ressembleront à « le tactile ne marche plus », « le jeu ne se lance pas », « la
manette ne répond plus » et « une fenêtre s'ouvre et rien ne la ferme ». Les
quatre réglages sont posés à la main sur la machine et **aucun n'est reposé**.

### Une note de garde-fou, découverte en écrivant cette dette

`test_aucun_emulateur_au_statut_conteste` cherche ses mots interdits en
**sous-chaîne**, sur le texte en minuscules. Or l'un d'eux — le sixième de la
liste `INTERDITS`, six lettres — est une sous-chaîne du mot anglais qui désigne
le compte super-utilisateur de Windows. C'est le compte sous lequel toute la
console tourne : il apparaît dans les messages des émulateurs comme dans
n'importe quel chemin `C:\Users\...`.

**Le garde-fou refuse donc un texte parfaitement légitime**, et le refus n'aide
pas : il nomme un émulateur qui n'est pas là, ce qui envoie chercher au mauvais
endroit.

Cette entrée en fait elle-même la démonstration : la première rédaction citait
le mot interdit pour l'expliquer, et **le test l'a refusée**. Une dette sur ce
garde-fou ne peut pas être écrite sans le déclencher — d'où la périphrase
ci-dessus, qui est laide et le restera tant que la correspondance se fera en
sous-chaîne.

Ce n'est PAS corrigé ici, délibérément : c'est un garde-fou de conformité, et le
relâcher — même vers une correspondance par frontière de mot, qui serait la
bonne réponse — se décide en revue, pas au détour d'une dette. Contourné pour
l'instant en ne recopiant pas le message anglais.

---

## D8 — PS4 : l'émulateur est installé, et rien ne peut y entrer

> **Plan écrit le 2026-08-29** — `docs/superpowers/plans/2026-08-29-d8-ps4-extraction-pkg.md` :
> commence par deux tâches de coût quasi nul qui peuvent clore la dette avant les 44 Go — la rentabilité y est jugée faible, et c'est écrit.

**Constatée le 2026-08-29**, en tentant d'installer deux jeux fournis par le
propriétaire (`CUSA07410`, base de 36 Go + mise à jour de 7,5 Go, deux `.pkg`
valides — magie `\x7FCNT`, content ID `EP9000-CUSA07410_00-00000000GODOFWAR`).

### Ce qui est en place

| | |
|---|---|
| shadPS4 **0.18.0** | inscrit au manifeste du propriétaire, empreinte relevée sur l'archive téléchargée, archive listée : **une seule entrée**, `shadPS4.exe` |
| shadPS4QtLauncher | ajouté comme **`parts`** du même émulateur — étiquette datée ET commit (`2026-08-26-d2c682c`), donc une empreinte qui ne périme pas |
| Dossier de jeux | réglé sur `G:\Games\Sony\PS4`, pour que ce qui s'y installera tombe là où `retro scan` regarde |

### Le mur, mesuré en trois temps

1. **Le build `win64-sdl` est EXCLUSIVEMENT en ligne de commande.** Il le dit
   lui-même dans une boîte au démarrage : « This is a CLI application. Please
   use the '-b' flag for Big Picture mode, or QTLauncher for a standalone GUI ».
   Toute tentative de piloter un menu sur ce binaire est vaine — il n'en a pas.
2. **Son aide n'a AUCUNE option d'installation.** Relevée sur le binaire :
   `--game`, `--patch`, `--big-picture`, `--fullscreen`, `--add-game-folder`,
   `--set-addon-folder`, `--mount`… rien qui installe un paquet.
3. **Le lanceur graphique n'en a pas non plus.** Son menu *File* porte
   exactement cinq entrées, relevées à l'écran : `Boot Game`,
   `Open/Add Elf Folder`, `Open shadPS4 Folder`, `Recent Games`, `Exit`.

**Conclusion : ce shadPS4 n'installe pas de PKG, par aucune voie.** Il attend
des jeux DÉJÀ EXTRAITS et se contente de les lister. Alimenter la PS4 demande
donc un extracteur PS4 tiers — un outil de plus à choisir, épingler et vérifier,
qui n'existe dans aucun des deux manifestes.

### Ce qu'il faut savoir avant d'y investir

God of War (2018) est rapporté comme **démarrant jusqu'aux menus sans être
jouable**. L'émulation PS4 en 2026 est à peu près là où RPCS3 était en 2017.
Même avec un extracteur, l'issue probable est un menu, pas une partie — et
c'est 44 Go à extraire pour le découvrir.

**Ce que ça coûte aujourd'hui :** un émulateur installé et épinglé qui ne peut
recevoir aucun jeu. Ce n'est pas une panne : c'est une chaîne incomplète, et
elle est incomplète d'un maillon nommé.

---

## D9 — Vita3K : installer un jeu ne marche par aucune des voies prévues

> **Plan écrit le 2026-08-29** — `docs/superpowers/plans/2026-08-29-d9-vita3k-installation-de-jeu.md` :
> dépend de D7 pour **deux** pièces : le jeton, et plusieurs cibles par profil.

**Constatée le 2026-08-29**, après la clôture de D5. L'émulateur tourne, son
firmware est posé — mais y faire entrer un jeu échoue par les deux chemins que
le profil emploie.

### Les deux échecs, mesurés

**Par l'archive.** Un `.vpk` passé en `content-path` est refusé avant tout :
`[C] [get_archive_contents_path]: A Vitamin dump was detected, aborting
installation…`. Refus légitime — mais il vaut pour l'archive seulement.

**Par le dossier.** La même bibliothèque en forme `ux0/app/<TITLEID>/` ne
déclenche PAS ce contrôle : elle passe par `install_content`, qui échoue
autrement — `[E] [install_content]: Failed to copy directory to:
"…\ux0\app\PCSF00012"` — en laissant un dossier **vide** derrière lui. Ce n'est
pas une question de place (79,9 Go libres) ni de partage : `robocopy` a copié
les mêmes 333 fichiers et 3,5 Go sans une erreur. Le contournement est donc la
copie manuelle, ce qu'aucun profil ne sait faire.

### Deux choses que le profil ignore, et qui bloqueront le prochain jeu

**La licence n'est pas où le dump la met.** Un dump NoNpDrm porte sa licence
dans `sce_sys/package/work.bin`. Vita3K, lui, la cherche ici :
`ux0/license/<TITLEID>/EP9000-<TITLEID>_00-0000000000000000.rif`. Sans elle :
« License file is corrupted or missing […] using default value ». Rien dans la
chaîne ne fait cette conversion.

**Le paquet de polices ouvre une modale bloquante.** « Missing Firmware —
Firmware is not fully installed. The following firmware components are missing:
Font package », avec `[Launch Anyway]` et une case « Don't show this warning
again ». Vita3K écrit lui-même qu'il ne publie pas l'URL de ce paquet, donc
rien n'a été pris ailleurs. La case a été cochée à la main — et comme les
quatre réglages de D7, **rien ne la repose**.

**Ce que ça coûte aujourd'hui :** le jour où un dump correct arrivera, il ne
suffira pas de le déposer. Il faudra le copier à la main, poser sa licence
ailleurs que là où elle est, et avoir désarmé une modale. Trois gestes qu'aucune
commande ne porte.

---

## D10 — Un garde-fou de conformité n'est pas gelé, et se désarme sans bruit — RÉGLÉE le 2026-08-29

> **Réglée le jour même de son constat, et la preuve a été faite dans les deux
> sens.** Avant : `SANS_NOTE_DE_VIBRATION` réhaussée à `{"xemu"}` laissait la
> suite **entièrement verte** — 635 tests, aucun rouge. Le garde-fou se
> désarmait donc bien sans un bruit. Après : la même mutation rend
> `test_le_garde_fou_ne_se_raccourcit_pas` rouge, et la suite redevient verte
> dès qu'elle est annulée. La quatrième liste est gelée comme les trois autres.

**Constatée le 2026-08-29**, en auditant la clôture de D3.

`tests/test_donnees.py` porte quatre listes qui **exemptent** ou **restreignent**
un garde-fou. Trois d'entre elles — `INTERDITS`, `EMPREINTES_A_RELEVER`,
`EXEMPTES` — sont gelées par `test_le_garde_fou_ne_se_raccourcit_pas`, dont la
docstring dit exactement pourquoi : « sans cette assertion, retirer un nom
d'INTERDITS — ou ajouter une exemption — suffisait à faire taire le garde-fou
sans qu'aucun test ne le remarque ».

**La quatrième ne l'est pas.** `SANS_NOTE_DE_VIBRATION`
(`tests/test_donnees.py:1031`) est aujourd'hui `frozenset()`, et c'est ce que
D1 célèbre : « l'exemption est retirée, et elle est désormais VIDE ». Mais y
réinscrire un nom de profil n'échouerait **nulle part** — le raisonnement
que la docstring ci-dessus tient pour les trois autres vaut mot pour mot pour
celle-là, et n'a simplement pas été appliqué.

**Ce que ça coûte aujourd'hui :** rien, tant que personne n'y touche. Le jour
où un profil gênera le test, l'y exempter sera le geste le plus court et le
moins visible — et l'aveu de vibration que D1 a construit profil par profil
disparaîtra pour celui-là, en silence. C'est très exactement le défaut contre
lequel les trois autres listes sont gelées.

**Où ça se joue :** `tests/test_donnees.py`, l'assertion de
`test_le_garde_fou_ne_se_raccourcit_pas`. Le correctif tient en une ligne. Il
n'est pas fait ici parce que ce fichier est en cours de modification pour D7,
et qu'écrire à deux dans le même fichier est un autre moyen de perdre du
travail en silence.

---

## D11 — Ce que le dépôt impose n'est pas ce que la console applique

**Constatée le 2026-08-29**, en auditant la clôture de D3. C'est **D6 à une
autre échelle** : là où D6 dit que le paquet installé peut être périmé, celle-ci
dit que même avec le bon paquet, le fragment appliqué peut l'être.

**Le fragment des clés imposées n'est écrit que par `retro scan`.**
`ecrire_plan` (`retro/launcher.py`) dépose `<profil>.impose.ini` à côté des
plans de lancement, et c'est le seul geste qui le produit. Modifier le champ
`enforced` d'un profil, relancer les tests, tout voir vert, et **ne pas
re-scanner** laisse la console fusionner l'ancien fragment. Aucun message ne
fait le lien ; le symptôme sera le réglage d'origine, c'est-à-dire le défaut
qu'on croyait corrigé.

**Et la marque de fusion est un commentaire.** Le lanceur insère
`; posé par « retro » …` devant chaque clé imposée, et c'est ce qui distingue
ses lignes de celles du propriétaire. Or DuckStation **efface tous les
commentaires** à une fermeture propre depuis son interface — mesuré, 2187 → 985
octets, c'est la découverte notée en fin de D2. Au lancement suivant, le
fichier fusionné diffère donc de l'existant, et la promesse « déjà conforme,
rien ne sera réécrit » ne tient plus : une sauvegarde horodatée et une
réécriture ont lieu **à chaque cycle**. Ce n'est pas une casse — les clés sont
justes — mais l'idempotence prouvée le 2026-08-29 ne vaut que tant que
personne n'ouvre l'interface.

**Ce que ça coûte aujourd'hui :** un correctif de profil peut être vert ici et
absent là-bas, pour une raison de plus que celle de D6 — et les deux causes
produisent le même symptôme, un correctif qui « ne marche pas ». Elles se
diagnostiqueront donc l'une pour l'autre.

**Où ça se joue :** `retro/launcher.py` (`ecrire_plan`, `enforced_name`), le
fusionneur de `retro/data/launcher/retro-launch.cs`, et le témoin que D6 est en
train de construire — c'est probablement là que l'identité du fragment doit
aller, à côté de celle du paquet.

---

## D12 — La langue est posable, et aucun profil ne dit quoi poser

**Constatée le 2026-08-30**, en livrant le mécanisme lui-même. Ce n'est pas une
panne, c'est une chaîne complète à laquelle il manque sa dernière pièce — et
cette pièce est un **relevé**, pas du code. Elle est ouverte le jour de la
livraison plutôt que découverte trois semaines plus tard : sans cette entrée,
un mécanisme qui ne pose rien se lit comme un mécanisme qui marche.

### Ce qui est livré, et testé

| Pièce | Où |
|---|---|
| La résolution — ce que la CONSOLE veut, ce qu'UN ÉMULATEUR pose, séparément | `retro/langue.py` ; les **31 noms de langue de Steam**, relevés le 2026-08-30 et non devinés (le relevé est en fin de ce fichier) |
| La déclaration : une table `[bootstrap.langue]` par entrée d'amorçage, gardée par **sept refus** au chargement, plus celui qui interdit à `enforced` et à la table de poser la même clé | `retro/profiles.py`, `_lire_langues` et `_valider_impose_contre_langues` |
| Un fragment de configuration **par langue**, déposé par `retro scan` | `retro/launcher.py`, `langue_name` et `fragments_attendus` |
| Une **ligne de plan par langue**, replis déjà résolus par Python — le lanceur lit, il ne décide pas | `retro/launcher.py`, `ecrire_plan` (`bootstrap_langue.<rang>.<langue>`) |
| `langue.txt`, relu à chaque jeu, et la commande qui l'écrit | `retro/launcher.py` (`lire_langue`, `ecrire_langue`), `retro/cli.py` (`_cmd_langue`) |
| La lecture de `HKCU\Software\Valve\Steam`, la fusion du fragment après les clés imposées, et le témoin `langue-vue.txt` | `retro/data/launcher/retro-launch.cs` |
| Le rapport : langue demandée, ce que Steam disait au dernier jeu, ce que chaque entrée posera au prochain | `retro/status.py`, `etat_langues` et `_lignes_langue` |

**Et aucun des dix profils livrés ne déclare de `[bootstrap.langue]`.** La
commande accepte les trente et une langues, et n'en pose aucune.

### Les tables qui manquent — deux cas, deux coûts

**Six profils portent déjà une entrée d'amorçage**, dix entrées en tout :
DuckStation (1), PCSX2 (1), Dolphin (2), RetroArch (2), RPCS3 (2), Vita3K (2).
Chez eux la cible est déjà mesurée et le dialecte déjà tranché ; il ne manque
que la table elle-même — le nom de la clé, et la valeur qu'elle prend pour
chaque langue. **Rien ne s'en déduit** : selon l'émulateur, cette valeur peut
être le nom de la langue, un code court, un entier ou un identifiant maison,
et c'est précisément ce qui doit se relever dans sa source ou dans un fichier
qu'il a lui-même écrit. Une valeur recopiée d'une documentation poserait une
clé d'apparence juste qui ne ferait rien — ce sont les deux pièges déjà payés
en D7 sur RPCS3, `XInput` avec ses deux majuscules et le `Device` qu'il faut
citer.

**Quatre n'ont aucune entrée d'amorçage** : `cemu`, `flycast`, `ppsspp`,
`xemu`. Chez eux, la question de la langue ne se pose même pas encore — il faut
d'abord établir **où vit le fichier de réglages**, ce qu'un `[[bootstrap]]`
répond, et chacun des quatre porte déjà en tête de profil la note qui dit que
personne n'a regardé. Conséquence facile à manquer : la section Langue de
`retro status` parcourt les **entrées d'amorçage**, pas les profils. Ces
quatre-là n'y apparaissent donc **pas du tout** — pas même une ligne « aucune
table ». Leur silence s'y lit comme une absence de sujet, alors que c'est la
même dette.

### Il manque à la langue le pendant de `fill_absent`

Le remplissage sait distinguer deux choses que la langue confond : `fill`
déclare le comportement, `fill_absent` déclare que **la question a été posée et
que la réponse est non**, et `retro status` affiche cette raison. Rien ne joue
ce rôle pour la langue. Une entrée sans `[bootstrap.langue]` rend un seul état,
« aucune table de langues déclarée », et cet état recouvre deux situations qui
n'appellent pas le même geste :

- l'émulateur **n'expose réellement aucun réglage de langue** — il n'y a rien à
  poser, et il n'y aura jamais rien ;
- **personne n'a encore relevé sa table** — c'est l'état des dix entrées
  aujourd'hui.

Tant que la dette est ouverte, les deux se confondent sans dommage : la réponse
est « aucune, partout ». **C'est sa clôture qui arme le piège.** Le jour où huit
entrées sur dix porteront leur table, les deux qui n'en auront pas seront
indiscernables — un oubli aura exactement la même trace à l'écran qu'un constat
d'impossibilité, et le rapport dira des deux la même phrase. Les quatre profils
sans amorçage portent aujourd'hui cette distinction **en commentaire** (« ce
bloc absent dit donc “personne n'a encore regardé”, pas “cet émulateur se
débrouille” ») : un commentaire n'est pas un garde-fou, et il ne remonte dans
aucun rapport.

C'est nommé ici et **pas implémenté** : la forme juste — un champ jumeau, ou un
`langue_absente` porteur d'une raison, sur le modèle exact de `fill_absent` et
de la `note` qu'un `args` vide exige — se décide avec la première table qu'on
relèvera pour de bon, pas avant d'en avoir vu une.

### Le témoin PAR CIBLE ne dit rien de la langue non plus

La conception promet deux choses dans la même phrase — « **le témoin par cible**
et la sortie `--explain` gagnent la langue appliquée et le fragment employé »
(`docs/superpowers/specs/2026-08-30-langue-design.md`) — et **aucune des deux
n'est livrée**. La seconde est nommée ci-dessous ; la première ne l'était nulle
part, et c'était le seul endroit où cette dette flattait l'état livré.

`InscrireTemoin` écrit toujours ses trois champs — `profil \t date \t cible` —
et rien d'autre. Ce qui existe de la langue est le témoin **global**,
`langue-vue.txt`, une ligne pour toute la console : `steam=`, `langue=`,
`motif=`. Il porte la langue **demandée**, jamais la posée, et il ne sait rien
des cibles. C'est écrit noir sur blanc dans `retro/status.py`
(`_lignes_langue`) et dans la source du lanceur, et ce n'est pas un oubli
d'écriture : c'est l'état réel.

**Ce que ce trou coûte, et il est plus grand que celui de `--explain` :** sur
un profil à deux cibles dont l'une déclare une table et l'autre non, ou dont
les replis diffèrent, **rien de ce que la console a réellement posé n'est
observable depuis l'hôte**. `retro status` peut dire ce qui SERA posé — il le
recalcule depuis les profils —, jamais ce qui l'a ÉTÉ. Le seul récit de ce qui
a atteint chaque fichier est le **journal** du lanceur, ligne par ligne, lisible
uniquement sur la console (« langue english : … -> … (fusion, 1 cle(s) de
langue) », dont l'étiquette a été corrigée le 2026-08-30 pour nommer la langue
POSÉE et non la demandée). Vu du canapé : le jeu n'est pas dans la bonne
langue, et le rapport ne peut que répéter sa prévision.

**Ce n'est pas corrigé ici, et le coût est mesuré** : `lire_amorcages`
(`retro/launcher.py:435`) ne retient une ligne que si `len(parts) == 3`. Un
quatrième champ ferait donc **ignorer la ligne entière, en silence**, et le
rapport dirait « pas encore amorcé » de toutes les cibles à la fois — un
lanceur neuf écrivant un témoin qu'un `retro` ancien ne lit plus. C'est une
migration à part entière, avec les deux sens à tenir, pas un détour de cette
entrée. Aujourd'hui il ne se produit rien, faute de table ; le trou naîtra avec
la première.

### Et `--explain` ne rend rien de la langue

`--explain` est le seul contrôle lisible à distance, sans lancer de jeu. Il ne
porte **aucune ligne** sur la langue : ni la valeur lue chez Steam, ni celle
qui serait retenue, ni le fragment qui serait fusionné. La décision de langue
est prise après le point où `--explain` rend son rapport et sort.

Pire, et c'est ce qui en fait une dette plutôt qu'un manque de confort :
`amorcage_a_poser.<n>` ne consulte que `bootstrap_enforced.<n>`. Une entrée qui
ne porterait **qu'une table de langues** — aucune clé imposée — et dont la
cible existe déjà obtiendrait « non (la cible existe) », alors que sa fusion de
langue, elle, aura bien lieu au prochain jeu. Le commentaire voisin dit
exactement pourquoi le cas imposé a été traité : « répondre "non (la cible
existe)" quand il y en a mentirait sur le seul contrôle vérifiable à
distance ». La langue rouvre ce mensonge par l'autre porte. Aujourd'hui il ne
se produit pas, faute de table ; il naîtra avec la première.

### Rien de tout cela n'a été compilé

**Il n'existe aucun compilateur C# sur l'hôte** — ni `csc`, ni `mcs`, ni
`mono`, ni `dotnet` — c'est la dette D7, et elle vaut ici à l'identique. Le
`.cs` n'est validé que par des tests Python qui exigent qu'il *lise* chaque clé
du plan. **Restent à mesurer sur la console :** la lecture réelle du registre,
la **double fusion** — les clés imposées puis la langue, sur la même cible et
au même lancement —, l'écriture du témoin `langue-vue.txt`, et le fait qu'une
langue changée à chaud soit bien reprise au jeu suivant.

**L'ordre sur la machine est obligatoire** : `retro launcher`, `compiler.cmd`,
**puis** `retro scan`. Mais **pas pour la raison que D7 donne**, et cette
entrée portait la phrase de D7 telle quelle : « un lanceur d'avant échoue
bruyamment sur un plan d'après ». **Elle est fausse de cette fonctionnalité,
dans les deux sens** — parce que la langue n'a RENOMMÉ aucune clé, elle en a
seulement ajouté, et c'est le renommage qui faisait crier D7 (voir l'encadré
de D7, corrigé le 2026-08-30).

- **Lanceur d'avant, plan d'après** — un binaire ancien ne connaît pas
  `bootstrap_langue.*` et ne les cherche donc jamais. Il pose les clés
  imposées, ne pose **aucune langue**, et rien n'échoue. Pendant ce temps
  `retro status` annonce la langue que le plan résout : deux juges qui ne se
  contredisent jamais à voix haute. Et le témoin ne rattrape pas : un lanceur
  d'avant n'écrit pas non plus `langue-vue.txt`, donc le rapport dit « aucun
  jeu lancé depuis », le seul état sous lequel une absence n'accuse personne.
  `retro/status.py` le dit d'ailleurs noir sur blanc là où il en parle —
  `_probleme_lanceur_perime` : « un lanceur compilé avant une évolution du plan
  ignore EN SILENCE les lignes qu'il ne connaît pas ». C'est ce problème-là,
  et lui seul, qui couvre ce sens.
- **Lanceur d'après, plan d'avant** — muet aussi, pour la langue :
  `FragmentDeLangue` lit ses lignes par `TryGetValue`, pas par `Valeur()`, donc
  leur absence rend `""` et il n'y a « rien à poser ». `Valeur()` ne lève que
  sur les clés qu'un lanceur EXIGE — celles de D7 —, et un plan écrit avant la
  langue les porte toutes.

**Donc la langue ne porte aucun garde-fou de version, dans aucun des deux
sens.** Seules la discipline d'ordre et l'alerte « lanceur périmé » de
`retro status` l'évitent — et cette alerte compare le binaire à la SOURCE
déposée à côté, pas au plan.

**Ce que ça coûte aujourd'hui :** rien qui casse — et c'est ce qui rend la
dette facile à oublier. Une commande existe, elle répond, elle écrit son
fichier, et **aucun jeu ne change de langue**.

Ce n'est plus muet, depuis le 2026-08-30. Cette entrée décrivait un
propriétaire qui pose `french`, lance Crash Team Racing et voit le jeu démarrer
en anglais « sans le moindre message, parce qu'il n'y a rien à signaler » —
c'était le raisonnement qu'il ne fallait pas tenir : **il y avait quelque chose
à signaler, et c'était même la seule chose utile à dire.** `retro langue`
charge désormais les profils, écrit la langue comme avant, puis avertit sur la
sortie d'erreur qu'aucun profil ne déclare de table — donc que ce choix ne sera
appliqué par personne — et rend **1**. C'est le raisonnement déjà écrit sur
place pour le lanceur absent : « le taire ferait croire au propriétaire que son
choix s'applique. » `retro status` le dit toujours, lui, entrée par entrée
(« aucune table de langues déclarée »), mais il n'est plus le seul, ni celui
qu'il faut penser à aller lire.

**Cet avertissement disparaîtra de lui-même** le jour où la première table sera
relevée : il ne parle que si AUCUNE entrée n'en déclare. Le test
`test_les_profils_livres_ne_peuvent_pas_appliquer_une_langue`
(`tests/test_cli.py`) tombera ce jour-là, et c'est voulu — il tient cette dette
en vue depuis la suite.

**Où ça se joue :** les tables `[bootstrap.langue]` dans
`retro/data/profiles/*.toml` — c'est là qu'est tout le travail restant —, la
distinction manquante dans `retro/profiles.py` (`_lire_langues`) et son rendu
dans `retro/status.py` (`_lignes_langue`), la sortie `--explain` et
`InscrireTemoin` de `retro/data/launcher/retro-launch.cs`, et le format à trois
colonnes de `retro/launcher.py` (`lire_amorcages`) que le témoin par cible
devrait franchir.

### Où en est D12 — 2026-09-04

**Cette entrée était PÉRIMÉE quand elle a été relue.** Elle dit « aucun des dix
profils livrés ne déclare de `[bootstrap.langue]` » ; quatre profils en
portaient déjà, posés le 2026-08-30 au soir — DuckStation, RetroArch (deux
entrées), PCSX2, Dolphin (une troisième cible ajoutée pour cela). Les trois
commits qui les ont posées n'ont pas touché ce fichier. C'est la démonstration
la plus courte de ce que dit l'en-tête de ce document : une dette qu'on fait
avancer sans l'écrire est une dette qu'on redécouvre.

#### Les tables : c'est FINI, et la garde qui le tient

**Onze entrées d'amorçage, et les onze disent où en est leur langue.** Sept
portent une table, quatre déclarent que la question a été posée et que la
réponse est non. La distinction « deux cas, deux coûts » de cette dette est donc
close — mais elle est close par les DEUX bouts, et le second n'existait pas :

| Profil | Cible | Ce qu'elle dit de la langue |
|---|---|---|
| dolphin | `GCPadNew.ini` | aucune — mesuré : ce fichier ne porte que des liaisons |
| dolphin | `WiimoteNew.ini` | aucune — mesuré, même raison |
| dolphin | `Dolphin.ini` | table : interface + langue système GameCube |
| duckstation | `settings.ini` | table : interface seule (la PS1 n'a pas de langue système) |
| pcsx2 | `PCSX2.ini` | table |
| retroarch | `retroarch.cfg` | table : langue de l'interface |
| retroarch | `melonDS.opt` | table : langue du firmware que les JEUX lisent |
| rpcs3 | `GuiConfigs\CurrentSettings.ini` | table : interface — **relevée sur l'archive**, voir plus bas |
| rpcs3 | `Default.yml` | aucune — mesuré : `cfg_player` ne porte que la manette |
| vita3k | `gui-configs\CurrentSettings.ini` | aucune — mesuré : `gui_settings.h` énumère onze groupes, aucune langue |
| vita3k | `config.yml` | table : `sys-lang`, la langue système de la PS Vita |

`test_chaque_cible_d_amorcage_dit_ou_en_est_sa_langue` (`tests/test_donnees.py`)
tient cet état : elle a été vue ROUGE en nommant les six cibles muettes, et elle
refuse qu'une douzième entrée se taise. **Elle n'a aucune liste d'exemptions** —
une entrée en sort en déclarant une table OU un aveu, jamais en s'y inscrivant.
C'est la leçon de D10, appliquée d'avance.

#### Le pendant de `fill_absent` existe : `langue_absente`

Nommé et non implémenté par cette dette, il l'est depuis le 2026-09-04
(`retro/profiles.py`, `_lire_langue_absente`). Il porte une RAISON et jamais un
booléen — même motif que `fill_absent` et que la `note` d'un `args` vide : un
« non » sans son motif ne se distingue pas d'un « non » recopié sans avoir
regardé. Trois refus l'encadrent, transposés un pour un de `fill` /
`fill_absent` : les deux à la fois, un aveu vide, un aveu qui n'est pas du
texte. **Ni l'un ni l'autre reste permis** — c'est l'état « personne n'a
regardé », celui dont ce champ existe pour sortir, pas celui qu'il interdit.

`retro status` rend une phrase distincte qui cite la raison. Le piège que cette
dette annonçait — « le jour où huit entrées sur dix porteront leur table, les
deux qui n'en auront pas seront indiscernables » — est donc désarmé le jour même
où il s'armait.

#### Ce que le rendu du rapport devait à ces tables, et qu'il ne payait pas

Deux défauts sont nés avec les tables, et aucun des deux n'existait avant :

1. **La phrase collective accusait à tort.** « un émulateur sans table pose ses
   propres défauts : ses jeux resteront dans SA langue » se déclenchait sur
   toute entrée sans table — donc sur le fichier de manettes de Dolphin, d'un
   émulateur qui pose sa langue par une AUTRE cible. Elle ne parle plus que de
   ce qui ne pose rien nulle part.
2. **Les quatre profils sans amorçage étaient invisibles**, ce que cette dette
   nommait déjà (« pas même une ligne "aucune table" »). `cemu`, `flycast`,
   `ppsspp`, `xemu` ont désormais leur ligne, et elle dit la cause qui leur est
   propre : il ne leur manque pas une table, il leur manque le fichier de
   réglages où la poser.

#### Le témoin par cible : la moitié hôte est faite, la moitié console reste due

Cette dette chiffrait le blocage avant de l'ouvrir : `lire_amorcages` ne
retenait une ligne qu'à `len(parts) == 3`, donc un quatrième champ aurait fait
ignorer la ligne ENTIÈRE, en silence. **Ce n'est plus vrai.** Le lecteur accepte
trois colonnes OU quatre ; la quatrième est la langue réellement POSÉE sur cette
cible-là, et son absence se lit « ce lanceur n'écrit pas la langue », jamais
« aucune langue posée ». Au-delà de quatre, la ligne est ignorée : deviner une
cinquième colonne poserait au rapport une valeur que personne n'a écrite.

**Le changement de forme a attrapé un défaut au passage**, et il vaut d'être
noté parce qu'il était invisible depuis une suite verte : `status.etat_amorcage`
dépliait le témoin en DEUX valeurs. Aucun test ne l'avait vu, parce que tous
fabriquaient le témoin à la main dans une forme que le lecteur ne produit pas.
Sur la seule voie réelle — `retro status` avec un vrai témoin — le rapport
levait un `ValueError` au lieu de s'afficher.

**Reste dû, et cela exige la console :** le lanceur C# n'écrit pas cette
quatrième colonne. Le côté hôte l'accepte, donc le jour où il l'écrira rien ne
cassera — c'était tout l'objet de faire cette moitié-ci d'abord.

#### 🔴 Le mensonge d'`--explain` n'est plus hypothétique : il est NÉ

Cette dette écrivait « Aujourd'hui il ne se produit pas, faute de table ; il
naîtra avec la première. » **Il est né.** `dolphin.toml`, troisième cible
(`Dolphin.ini`), déclare une table de langues et **aucune** clé `enforced` —
`tests/test_donnees.py` l'exige même explicitement (`SANS_MANETTE`). Le plan
écrit donc `bootstrap_enforced.3=` vide, `amorcage_a_poser.3` ne consulte que
cette ligne, et `--explain` répondra **« non (la cible existe) »** sur une cible
où une fusion de langue aura bel et bien lieu au prochain jeu.

C'est le seul contrôle vérifiable à distance, et il ment désormais sur une
cible livrée. **Ce n'est pas corrigé, et la raison est le périmètre :** le
correctif est entièrement en C#, et **il n'existe aucun compilateur C# sur
l'hôte** — ni `csc`, ni `mcs`, ni `mono`, ni `dotnet`, vérifié le 2026-09-04.
Livrer du C# qu'on n'a pas vu compiler dans un fichier dont dépend le lancement
de TOUS les jeux échange un rapport qui ment contre une console qui ne démarre
plus. Le correctif est donc rangé avec les mesures de console, où il attend un
compilateur.

**Ce qui reste dû sur la console, et rien de tout cela n'est faisable d'ici :**

- compiler `retro-launch.cs` — aucune ligne de ce fichier n'a jamais été
  compilée, langue comprise ;
- `--explain` : les lignes de langue (valeur lue chez Steam, langue retenue,
  fragment fusionné) et la correction d'`amorcage_a_poser.<n>`, qui doit
  compter la fusion de langue et non le seul `bootstrap_enforced.<n>` ;
- `InscrireTemoin` : écrire la quatrième colonne, que l'hôte sait déjà lire ;
- la double fusion — clés imposées PUIS langue, sur la même cible, au même
  lancement ;
- la lecture réelle du registre de Steam, et qu'une langue changée à chaud soit
  reprise au jeu suivant ;
- **et la seule preuve qui vaille pour chaque table posée : un jeu VU dans la
  langue demandée.** Aucune des sept tables n'a été vue agir. Elles sont
  relevées, pas mesurées — c'est la distinction que D3 a payée cher.

#### 🔴 Un silence NEUF, que les tables viennent de créer — à arbitrer

`retro langue` avertit quand **aucune** entrée ne déclare de table. Cette
condition est désormais fausse, donc l'avertissement ne sort plus jamais — et
la disparition est voulue, cette dette l'annonçait. Mais elle découvre un cas
que personne n'avait à traiter tant qu'il n'y avait aucune table : **une langue
déclarée par CERTAINES entrées et pas par les autres.**

Couverture mesurée le 2026-09-04, sur les sept entrées qui portent une table :

| Langue | Entrées qui la déclarent |
|---|---|
| english, french, german, italian, spanish | 7 / 7 |
| schinese, japanese, polish, portuguese, brazilian, swedish, latam | 6 / 7 |
| dutch, finnish, koreana, russian, turkish | 5 / 7 |
| tchinese, norwegian | 4 / 7 |
| arabic, czech, danish, greek, hungarian, indonesian, ukrainian | 3 / 7 |
| romanian, vietnamese | 2 / 7 |
| **bulgarian, malay, thai** | **1 / 7** |

Le propriétaire qui pose `malay` voit sa commande réussir sans un mot, et six
entrées sur sept partiront dans leur repli. C'est **exactement** le raisonnement
déjà écrit dans `_cmd_langue` — « le taire ferait croire au propriétaire que son
choix s'applique » — appliqué à un cas que ce code ne couvre pas.

**Et ce n'est pas toujours un défaut**, ce qui est précisément ce qui rend
l'arbitrage nécessaire : la PS Vita n'a pas de thaï, la GameCube n'a que six
langues système. Le repli est alors la réponse JUSTE, pas une lacune. Un
avertissement qui ne ferait pas cette différence crierait à tort — et une garde
qui crie à tort est une garde qu'on finit par désarmer.

**Ce n'est pas implémenté, délibérément :** c'est une évolution de la commande,
donc une décision de portée, et `retro status` dit déjà la chose entrée par
entrée. **Question au propriétaire :** `retro langue --langue malay` doit-elle
dire « six entrées sur sept poseront leur repli » — et si oui, est-ce un
avertissement qui change le code de retour, ou une simple note ?

#### Deux fragilités que les tables apportent avec elles

- **RPCS3 : la liste des langues est une propriété de l'ARCHIVE, pas du code.**
  `GetAvailableLanguageCodes()` énumère `rpcs3_*.qm` dans le dossier de
  traductions ; les douze codes ont donc été relevés sur l'archive épinglée
  elle-même, téléchargée et comparée à l'empreinte du manifeste. Un code absent
  de l'archive ne produit **aucune erreur** : RPCS3 retombe sur l'anglais **et
  réécrit `language=en`** dans le fichier. Comme la console repose la table à
  chaque lancement, les deux se contrediraient en boucle, sans un mot. **Cette
  table se re-relève à chaque montée de version de RPCS3.**
- **Vita3K : `sys-lang` est un ENTIER.** Un entier faux n'est pas une valeur
  invalide — c'est une AUTRE langue, parfaitement valide. C'est le piège déjà
  écrit pour le cœur melonDS, et il est ici sur un axe que le propriétaire voit
  depuis son canapé. Les rangs viennent de `locale_tag_for_sys_lang`
  (`vita3k/lang/src/lang.cpp`), dont le tableau est indexé par `sys-lang`, et
  une seconde source indépendante les confirme rang pour rang : RPCS3 sérialise
  le même vocabulaire Sony pour la PS3
  (`fmt_class_string<CellSysutilLang>::format`).

#### Ce qui n'est PAS posable, et c'est mesuré

**La langue système de la PS3 — celle qu'un jeu interroge.** Elle existe et elle
est relevée : `System: Language:` dans le `config.yml` de RPCS3, vingt valeurs
exactes lues dans `Emu/Cell/Modules/cellSysutil.cpp`, défaut `English (US)`
(`Emu/system_config.h`). Elle n'est pas posable **parce que c'est un YAML
IMBRIQUÉ** : les deux dialectes de fusion ne connaissent que l'INI à sections et
le YAML **PLAT** (`retro/profiles.py`, `cles_yaml` — « seul le PREMIER NIVEAU
compte »). Poser `Language:` au premier niveau du fichier écrirait une clé
qu'aucun lecteur YAML ne rattacherait au nœud `System`, et RPCS3 continuerait en
anglais sans un mot.

Ce n'est donc pas un relevé qui manque, c'est un troisième dialecte — ou une
profondeur ajoutée au second. **C'est une décision de conception, elle n'est pas
prise ici**, et elle a un voisin : la langue d'interface de Vita3K
(`user-lang`), qui n'est pas déclarée non plus mais pour une raison différente —
ses valeurs se découvrent dans l'archive, et l'archive de Vita3K n'est épinglée
par aucune empreinte (D5).
---

## D13 — Deux juges de la langue, et une seule indulgence sur deux

**Constatée le 2026-08-30**, en relisant le mécanisme de D12 des deux côtés à
la fois. Les deux lectures de `langue.txt` — celle de Python et celle du
lanceur — ne traitent pas de la même façon une valeur que Steam ne nomme pas.
Aucune des deux n'a tort prise seule ; ensemble, elles font dire deux choses
différentes à deux juges qui ne se contrediront jamais à voix haute.

### Le fait, des deux côtés

| | Ce qu'elle fait d'une valeur hors liste |
|---|---|
| `launcher.lire_langue` (`retro/launcher.py:602`) | **la ramène à `auto`** — `return valeur if valeur in langue_mod.VALEURS else langue_mod.AUTO` |
| `LangueChoisie()` (`retro/data/launcher/retro-launch.cs:1591`) | **ne valide rien** : elle rend la valeur telle quelle, en minuscules |

L'écart est délibéré des deux côtés, et chacun porte sa raison écrite. Python
lit pour **rendre un rapport**, et `test_un_fichier_illisible_retombe_sur_auto`
(`tests/test_launcher.py:185`) tient que « un fichier abîmé ne doit pas
empêcher un jeu de se lancer ». Le lanceur, lui, lit pour **lancer un jeu**, et
son commentaire dit pourquoi il ne valide pas : « AUCUNE LISTE DE LANGUES ICI,
contrairement aux trois modes de rendu : valider demanderait de porter les noms
de Steam dans ce fichier, donc d'y décider quelque chose. »

**Et c'est bien une exception, pas le motif de la maison.** Pour le rendu, les
deux côtés normalisent : `ModeChoisi()` (`retro-launch.cs:1570`) teste
`native | auto | full` et retombe sur `auto`, exactement comme `lire_mode`. Les
deux juges du rendu disent donc toujours la même chose. La langue est le seul
endroit où ils divergent.

### Ce que ça produit

Sur un `langue.txt` portant, disons, `frensh` :

1. **`retro status`** lit `auto` — la valeur a été normalisée avant qu'il ne la
   voie — et annonce donc la langue de **Steam** : « langue demandée :
   “english” — “auto” : Steam dit “english” ».
2. **Le lanceur** prend `frensh` pour une langue posée à la main, ne trouve
   aucun `bootstrap_langue.<rang>.frensh` dans le plan, et retombe sur la ligne
   `defaut` — c'est-à-dire le **repli** du profil, celui prévu pour « Steam
   muet ». Ce n'est ni `english`, ni `frensh`.
3. **Le témoin ne rattrape pas l'écart, il le maquille.** `langue-vue.txt`
   portera `langue=frensh` et `motif=posee a la main` ; `retro status` verra
   que cette valeur diffère de celle qu'il annonce et écrira « le dernier jeu a
   demandé “frensh” […] : **le réglage a changé depuis, le prochain suivra la
   ligne ci-dessus** ». Cette phrase est fausse : rien n'a changé, et le
   prochain jeu fera exactement pareil. Le seul indice visible envoie donc
   chercher un changement de réglage qui n'a pas eu lieu.

Avant le premier jeu, il n'y a pas même cet indice : sans témoin, le rapport
dit « aucun jeu lancé depuis », et l'écart est entièrement muet.

### Comment on y arrive — et c'est ce qui borne la gravité

**`retro langue` ne peut pas produire cet état.** La valeur est refusée deux
fois : par `choices=langue_mod.VALEURS` à l'analyse des arguments
(`retro/cli.py:953`), puis par `ecrire_langue`, qui lève devant le
propriétaire — c'est ce que garde
`test_une_langue_inconnue_est_refusee_a_l_ecriture`
(`tests/test_launcher.py:195`). Il faut donc **éditer `langue.txt` à la main**
pour y arriver.

Une seconde voie est plausible et **n'a pas été mesurée** : `ecrire_langue`
écrit directement, sans le basculement atomique dont `shortcuts.vdf` bénéficie,
donc une écriture interrompue laisserait un nom tronqué — `fren` — qui produit
exactement le même écart. C'est une déduction de lecture, pas un constat ; elle
est notée pour qu'on sache où regarder, pas pour être crue.

**Et rien de tout cela ne coûte quoi que ce soit aujourd'hui** : aucun profil
ne déclare de table de langues (D12), donc le plan ne porte aucune ligne
`bootstrap_langue.*` et le lanceur ne pose rien, quelle que soit la valeur
qu'il a lue. Comme le trou de `--explain`, cette dette naît le jour où la
première table est relevée.

### Pourquoi elle n'est pas corrigée ici

Parce que la corriger, c'est **choisir lequel des deux juges cède**, et les
deux indulgences ont été écrites exprès, chacune pour sa raison. Toucher celle
de Python touche un test écrit pour empêcher qu'un fichier abîmé bloque un
lancement ; toucher celle du C# revient sur le refus, argumenté dans la source,
d'y porter une liste de langues. C'est une décision de conception, et le dépôt
s'applique déjà cette règle en D7 : ça **se décide en revue, pas au détour
d'une dette**.

### Les deux issues, sans trancher

- **Le lanceur valide contre ce que porte le plan.** Il n'y porterait alors
  aucune liste : le plan écrit déjà une ligne `bootstrap_langue.<rang>.<langue>`
  par langue de Steam, donc la liste y est. Reste une question ouverte, et elle
  n'est pas mineure : une entrée **sans** table n'écrit aucune de ces lignes, et
  il n'y aurait alors rien contre quoi valider.
- **Python cesse de normaliser, et le rapport nomme la valeur inconnue.**
  `retro status` sait déjà dire cette phrase-là — `_motif_sans_langue`
  (`retro/status.py:1438`) écrit « Steam dit “…”, un nom que “retro” ne connaît
  pas » — mais il ne la dit que de la valeur de **Steam**, jamais de celle du
  propriétaire. Le coût est le test cité plus haut, qu'il faudrait rouvrir.

**Ce que ça coûte aujourd'hui :** rien de mesurable, et c'est exactement le
profil d'une dette qu'on oublie. Le jour où les tables existeront, un fichier
touché à la main enverra les jeux dans une langue que personne n'a demandée,
pendant que le rapport en annoncera une autre — et la seule ligne qui en parle
accusera un changement de réglage inexistant. Vu du canapé : le jeu n'est pas
dans la bonne langue, `retro status` dit qu'il devrait l'être, et les deux ont
l'air d'accord.

**Où ça se joue :** `retro/launcher.py` (`lire_langue`, et l'écriture non
atomique d'`ecrire_langue`), `LangueChoisie()` et `FragmentDeLangue()` dans
`retro/data/launcher/retro-launch.cs`, le rendu du témoin dans
`retro/status.py` (`_lignes_temoin_langue`), et le test
`test_un_fichier_illisible_retombe_sur_auto` de `tests/test_launcher.py`, qui
est la contrainte à rouvrir si c'est Python qui cède.

### Les deux issues, MESURÉES — 2026-09-04. L'arbitrage reste au propriétaire.

Cette entrée posait deux issues sans les chiffrer. Elles le sont ici, et **rien
n'est décidé** : le dépôt s'applique la règle de D7, ça se décide en revue.
Trois faits ont été mesurés depuis, et l'un d'eux déplace le coût annoncé.

#### 🔴 La contrainte que l'issue 2 devait « rouvrir » ne protège pas ce qu'elle dit

`test_un_fichier_illisible_retombe_sur_auto` justifie l'indulgence de Python
par : *« Un fichier abîmé ne doit pas empêcher un jeu de se lancer. »*

**`lire_langue` ne peut empêcher aucun jeu de se lancer.** Mesuré le
2026-09-04, ses appelants sont exactement deux, et les deux ne font que
rapporter :

| Appelant | Ce qu'il en fait |
|---|---|
| `retro/cli.py`, `_cmd_status` | passe la valeur à `build_report` |
| `retro/cli.py`, `_cmd_langue` sans `--langue` | l'imprime |

Le chemin de LANCEMENT ne passe pas par là : c'est le lanceur C# qui lit
`langue.txt`, sur la console, et Python n'est pas dans la boucle. La phrase de
cette docstring est vraie de `lire_mode` — dont la valeur part dans le plan —
et a été héritée ici où elle ne l'est pas. **Le coût de l'issue 2 est donc plus
petit que ce que cette dette annonçait :** la contrainte à rouvrir protège une
propriété que la fonction n'a pas.

Une propriété réelle demeure, et elle est plus étroite : `lire_langue` ne doit
pas **lever**, sans quoi `retro status` s'interromprait. Rendre la valeur brute
ne lève pas.

#### Ce que coûte l'issue 1 — le lanceur valide contre le plan

**Elle est entièrement en C#, donc elle n'est pas mesurable d'ici et pas
livrable d'ici** : aucun compilateur C# sur l'hôte. C'est déjà un coût.

Et elle a **deux trous**, dont un seul était nommé :

1. *(nommé)* une entrée sans table n'écrit aucune ligne `bootstrap_langue.*`,
   donc il n'y a rien contre quoi valider. Mesuré aujourd'hui : **quatre des
   onze entrées** sont dans ce cas.
2. *(non nommé, et il est pire)* le plan est **PAR SYSTÈME**. Les quatre profils
   sans amorçage — `cemu`, `flycast`, `ppsspp`, `xemu` — n'écrivent **aucune**
   ligne de langue, jamais. Valider contre le plan ferait donc juger la MÊME
   valeur de `langue.txt` valide au lancement d'un jeu DuckStation et
   invalidable au lancement d'un jeu Xbox. La console tiendrait deux avis sur
   un fichier unique, selon le jeu — et l'écart resterait entier exactement là
   où il est le moins visible.

#### Ce que coûte l'issue 2 — Python cesse de normaliser

Entièrement côté hôte, testable, sans console. Trois endroits :

- `launcher.lire_langue` rend la valeur brute au lieu de la ramener à `auto`, et
  sa docstring cesse de promettre une protection qu'elle n'exerce pas ;
- `status._decision_langue` rend `None` sur une valeur hors liste, et
  `_lignes_langue` n'écrit alors **plus rien** de la langue demandée : le
  silence remplacerait la normalisation, ce qui n'est pas mieux. Il faut donc
  nommer la valeur — `_motif_sans_langue` sait déjà écrire cette phrase-là,
  mais seulement de la valeur de **Steam** ;
- `_lignes_temoin_langue` : la phrase fausse que cette dette relève — « le
  réglage a changé depuis, le prochain suivra la ligne ci-dessus » — doit être
  gardée, sinon l'issue 2 la laisse intacte et ne corrige que la moitié visible.

Trois tests à rouvrir (`test_un_fichier_illisible_retombe_sur_auto` et ses deux
voisins), et le rendu de la section Langue à compléter.

#### Une troisième voie, qui n'était pas dans la liste

**Distinguer « illisible » de « lisible mais inconnu ».** Les deux tombent
aujourd'hui sur `auto` par la même ligne, et ce ne sont pas les mêmes faits :
un `OSError` veut dire « il n'y a pas de fichier », un `frensh` veut dire
« quelqu'un — ou une écriture interrompue — a mis ça là, et c'est exactement ce
que le lanceur va lire ». Le premier mérite `auto` sans commentaire ; le second
mérite d'être nommé. C'est l'issue 2, resserrée sur le seul cas qui produit
l'écart, et elle laisse `auto` intact partout où il est juste.

#### Ce que la recommandation serait, et pourquoi elle ne tranche pas

Sur ces mesures, l'issue 1 est plus chère qu'annoncé (C# non compilable ici,
deux trous dont un qui fait tenir deux avis à la console) et l'issue 2 moins
chère qu'annoncé (la contrainte invoquée ne protège pas ce qu'elle dit). Mais
**les deux ne règlent pas la même chose** : l'issue 2 fait dire la vérité au
RAPPORT, l'issue 1 change ce que la console POSE. Aucune des deux ne rend l'autre
inutile, et choisir la seconde seule laisse un jeu partir dans le repli pendant
que le rapport, lui, ne mentira plus.

**Question au propriétaire, et elle est en une ligne :** un `langue.txt` touché
à la main doit-il faire **dire la vérité au rapport** (issue 2, hôte, faisable
tout de suite), ou faire **refuser la valeur au lanceur** (issue 1, console,
avec les deux trous ci-dessus) — ou les deux, dans cet ordre ?

**Rien n'est implémenté ici**, et l'écart reste sans coût tant qu'aucun jeu n'a
été vu poser une langue.
---

## Relevé — où Steam dit sa langue, et sous quels noms — 2026-08-30

Fait pour la tâche 1 de
`docs/superpowers/plans/2026-08-30-langue-de-la-console.md`, dont tout le
reste dépend : le spec disait explicitement que ce point n'était pas prouvé.

### La clé de registre : elle existe

Commande jouée depuis l'hôte, par le canal WinRM du dépôt
(`packages/installer/console/guest/winrm_exec.py`, transport NTLM) :

```
reg query "HKCU\Software\Valve\Steam" /v Language
```

Sortie :

```
HKEY_CURRENT_USER\Software\Valve\Steam
    Language    REG_SZ    english
```

**Ce que ça tranche :** la clé existe, elle est de type `REG_SZ`, et sa valeur
est le NOM de la langue **en minuscules** — `english`, pas `English` ni `en`.
Le lanceur peut donc la lire par `Microsoft.Win32.Registry`, qui vit dans
`mscorlib` : aucune référence supplémentaire à passer à `csc.exe`.

**Ce que ça ne tranche PAS, et qui n'est pas mesuré :** à quel moment cette
valeur suit un changement de langue fait dans l'interface de Steam — tout de
suite, ou seulement après un redémarrage du client. Le mesurer demande une
interaction graphique en session 1 et modifie l'environnement du
propriétaire. **Le témoin rend la question sans objet** : `retro status`
affiche la valeur BRUTE lue chez Steam, donc un décalage éventuel se voit
de lui-même dans le rapport. Aucun avertissement « redémarrez Steam » n'est
écrit, parce qu'il serait déduit d'un fait qu'on n'a pas.

### Les noms de langue : trente et un, et la liste n'était pas devinable

Relevés sur `partner.steamgames.com/doc/store/localization/languages`, colonne
« API language code » — **les noms, pas les codes web** (`french`, jamais
`fr`) :

```
arabic, bulgarian, schinese, tchinese, czech, danish, dutch, english,
finnish, french, german, greek, hungarian, indonesian, italian, japanese,
koreana, malay, norwegian, polish, portuguese, brazilian, romanian, russian,
spanish, latam, swedish, thai, turkish, ukrainian, vietnamese
```

**Ce relevé a corrigé une faute.** La liste écrite de mémoire dans le plan en
comptait trente et **oubliait `malay`**. C'est exactement la raison pour
laquelle cette liste se relève au lieu de se deviner : `koreana` n'est pas
`korean`, `brazilian` n'est pas `portuguese_br`, `latam` ne ressemble à rien,
et une langue manquante est une ligne de plan absente — donc un jeu qui ne
se lance pas, sur une console dont le propriétaire parle malais.
