# D2 — le remplissage de l'image, ce qu'il en reste — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — `superpowers:subagent-driven-development`.

**Objectif :** fermer ce qui reste ouvert de la dette **D2** — le remplissage
de DuckStation, et les six systèmes qui n'ont aujourd'hui aucun bloc de rendu.

**Dette :** `docs/dettes.md`, section D2, et ses sous-sections du 2026-08-29.
**Specs :** `docs/superpowers/specs/2026-08-26-retro-console-design.md` et
`docs/superpowers/specs/2026-08-28-amorcage-emulateurs-design.md`.
**Procédure de mesure :** `docs/releve-manettes.md` — le canal WinRM, le piège
de la session 0, et la leçon sur les libellés y sont déjà écrits.

## Ce que ce plan NE REFAIT PAS

Fait, mesuré, confirmé — n'y touche pas :

- le troisième axe existe dans `retro/render.py` : `entier` / `ajuste`, la
  politique `_REMPLISSAGE_PAR_MODE`, ses quatre états ;
- les huit systèmes de RetroArch sont couverts (`video_scale_integer`,
  `_axis = 0`, `_scaling = 0` en natif, éteint explicitement en full) ;
- GameCube et Wii sont **déclarés non réglables**, avec la preuve ;
- **le cadrage de DuckStation est CLOS** : `[Display] CropMode = Borders`,
  dans `enforced`, confirmé par le propriétaire — plus aucune bande.

---

## Contraintes globales

Chacune vient d'une faute déjà commise dans ce dépôt. Les enfreindre ne
produit **aucun message d'erreur** : c'est tout le problème.

- **Une valeur fausse se comporte exactement comme l'absence de valeur.**
  Aucun message, aucune ligne de journal, aucun symptôme distinct. Toute
  valeur que ce plan fait poser doit dire **d'où elle vient**, dans un
  commentaire, à côté d'elle.
- **Les chaînes d'un binaire donnent les LIBELLÉS de l'interface, pas les
  valeurs du fichier de configuration.** `All Borders`, `Auto (Game Native)`
  sont des libellés ; les valeurs sont dans la **source** —
  `src/core/settings.cpp`, tableau `s_display_crop_mode_names`. **Deux
  tentatives ont déjà échoué ainsi.** Ne recopie jamais une valeur depuis
  `strings`, ni depuis une documentation, ni depuis un forum.
- **« La clé a survécu » ne prouve PAS « la clé est reconnue ».**
  `DisplayCropMode`, clé **inventée**, a survécu à une réécriture complète du
  fichier par DuckStation, qui conserve ce qu'il ne comprend pas. La survie
  est un **faux oracle** : la seule preuve est l'**effet observé**.
- **MESURÉ / SUPPOSÉ, partout.** Tout ce que ce plan appelle « point de
  départ » est SUPPOSÉ et doit être confirmé dans la source. Ce que tu écris
  dans un profil doit dire lequel des deux il est.
- **La console Windows n'est pas accessible depuis la session d'un agent.**
  Toute mesure sur la machine est une **étape à faire jouer par le
  propriétaire**, écrite avec sa commande exacte et l'observation qui
  tranche. N'invente pas un résultat pour débloquer une tâche : marque-la
  bloquée et passe à la suivante.
- **Aucun test ne touche le réseau, aucun n'exige Windows.** La suite tourne
  sous `-W error`, arbre frais.
- **Un test qui passe quelle que soit l'implémentation est un défaut.**

---

## Tâche 1 : le commentaire de `render.py` ment, et c'est le premier piège

Aucune mesure. À faire en premier, parce qu'un agent qui lit `render.py`
aujourd'hui rouvre une question déjà tranchée.

Le bloc `# ARBITRAGE EN ATTENTE — DuckStation` (`retro/render.py`, entre
`_MOTIF_PAR_MODE` et `remplissage_attendu`) dit trois choses **fausses depuis
le 2026-08-29** :

- « la question appartient au propriétaire, et elle n'est pas tranchée ici » —
  **elle est tranchée, la réponse est oui**, et la stratégie `fusion` en est
  née (`retro/launcher.py`, `retro/data/launcher/retro-launch.cs`) ;
- « PAS ÉTABLI : le NOM DE LA CLÉ » — **le couple est établi** :
  `[Display] Scaling`, posé et **reconnu** ;
- « l'amorçage ne pose son fichier QUE S'IL EST ABSENT » — il y a désormais
  **deux régimes**, et `enforced` repose ses clés à chaque lancement.

Le même reproche vaut pour le profil : `retro/data/profiles/duckstation.toml`,
sous `[[system]]`, porte encore « Les y écrire écraserait les réglages du
propriétaire, ce que cet outil ne fait pas ».

**Fichiers :**
- Modifier : `retro/render.py`, `retro/data/profiles/duckstation.toml`

**Ce qu'il faut obtenir :**

- le bloc réécrit autour de **ce qui reste vrai** : DuckStation n'a toujours
  aucun réglage de rendu **en ligne de commande** (dix-sept arguments,
  vérifiés sur le binaire épinglé), donc son remplissage passera par
  `settings.ini` et par `enforced` ;
- ce qui reste **non mesuré**, énoncé comme tel et **uniquement** cela :
  personne n'a vu `NearestInteger` ni `BilinearInteger` agir sur la machine ;
  `BilinearSmooth` a été reconnu et n'a **rien** changé à la géométrie —
  `Scaling` est un **filtre**, et cela ne dit rien de ses deux valeurs
  entières ;
- **aucune valeur nouvelle n'est posée par cette tâche.** Elle ne touche que
  du commentaire. Les tests doivent passer inchangés — s'ils bougent, c'est
  que tu as fait autre chose.

---

## Tâche 2 : le relevé SOURCE — `Scaling` déplace-t-il la géométrie ?

Aucune mesure sur la machine. C'est la lecture qui doit **prédire** le
résultat de la tâche 3 ; les deux doivent ensuite s'accorder, sinon l'une des
deux est fausse et il faut le dire plutôt que choisir.

**Fichiers :**
- Modifier : `retro/data/profiles/duckstation.toml` (commentaires seuls)

**Ce qu'il faut obtenir**, dans la source de DuckStation **au tag
`v0.1-11609`** — celui dont le manifeste porte l'empreinte, jamais `master` :

1. **Le tableau des valeurs de `Scaling`.** `src/core/settings.cpp`, à côté de
   `s_display_crop_mode_names` : le tableau statique du type
   `DisplayScalingMode`. Il donne les valeurs **du fichier**, telles quelles.
   `NearestInteger` et `BilinearInteger` sont pour l'instant des **libellés
   lus dans le binaire** — donc SUPPOSÉS. La forme réelle peut différer.
2. **Où cette valeur est CONSOMMÉE.** C'est le point de la tâche : chercher
   les usages de `DisplayScalingMode::` dans la fonction qui calcule le
   rectangle d'affichage (point de départ : `src/core/gpu_presenter.cpp`,
   `CalculateDrawRect` ou son équivalent dans cette révision). Deux issues, et
   elles ne demandent pas la même suite :
   - le calcul **branche** sur les variantes `*Integer` pour arrondir la
     taille du rectangle → `Scaling` touche à la **géométrie**, et la tâche 3
     doit le confirmer ;
   - le calcul ne s'en sert que pour choisir un **échantillonneur** →
     `Scaling` est un filtre **de bout en bout**, et DuckStation n'expose
     alors aucun réglage de remplissage. C'est un `fill_absent` **mesuré**,
     sur le modèle exact de Dolphin, et la tâche 3 devient une simple
     confirmation.
3. **Vérifier qu'aucune autre clé ne porte le remplissage.** Dans le même
   fichier, la section `Display` : chercher toute clé dont la valeur entre
   dans ce calcul de rectangle. C'est la seule façon d'écarter l'hypothèse
   « la bonne clé est ailleurs », qui a déjà coûté deux tentatives sur
   `CropMode`.

**Ce que la tâche livre :** le constat écrit dans le profil, au-dessus de
`enforced`, avec le **fichier, le symbole et le tag** — la forme exacte que
prend déjà la note de `CropMode`. **Aucune clé n'est ajoutée à `enforced` par
cette tâche.** Une lecture de source établit un nom et des valeurs ; elle
n'établit pas un effet.

---

### LE RELEVÉ — FAIT le 2026-08-29, au tag `v0.1-11609`

Lu dans la source, fichier par fichier, au tag épinglé — jamais `master`.
Chaque bloc ci-dessous a été **récupéré et relu octet par octet**, pas
résumé par une lecture de page.

**Correction de chemin, d'abord.** `src/core/gpu_presenter.cpp` **n'existe
pas** à cette révision — l'URL rend 404. Le fichier s'appelle
`src/core/video_presenter.cpp`, et la classe est `VideoPresenter`. Le point
de départ écrit en tâche 2 était donc faux ; le reste du chemin tient.

#### 1. Les valeurs du fichier — `s_display_scaling_names`

`src/core/settings.cpp`, ligne 2218 :

```cpp
static constexpr const std::array s_display_scaling_names = {
  "Nearest", "NearestInteger", "BilinearSmooth", "BilinearHybrid",
  "BilinearSharp", "BilinearInteger", "Lanczos",
};
```

Sept valeurs, dans cet ordre. `NearestInteger` et `BilinearInteger`, qui
n'étaient jusqu'ici que des **libellés lus dans le binaire**, sont donc
**confirmés comme valeurs de fichier** — c'est le premier des deux
libellés-devenus-valeurs de ce dépôt qui survit à la vérification.

**Et le piège est visible à l'œil nu, trois lignes plus bas** : le tableau
`s_display_scaling_display_names` (ligne 2221) porte, lui,
`"Nearest-Neighbor"`, `"Nearest-Neighbor (Integer)"`, `"Bilinear (Smooth)"`…
enveloppés dans `TRANSLATE_DISAMBIG_NOOP`. **Ce sont ceux-là que `strings`
remonte**, et aucun n'est jamais écrit dans le `.ini`. Les deux tableaux sont
voisins dans le fichier ; c'est exactement le couple qui a coûté deux
tentatives sur `CropMode`.

L'énumération correspondante, `src/core/types.h` ligne 193 :

```cpp
enum class DisplayScalingMode : u8
{
  Nearest, NearestInteger, BilinearSmooth, BilinearHybrid,
  BilinearSharp, BilinearInteger, Lanczos, Count
};
```

**La clé et sa section**, `Settings::Load`, `settings.cpp` lignes 387-392 :

```cpp
display_scaling =
  ParseDisplayScaling(si.GetStringViewValue("Display", "Scaling",
                        GetDisplayScalingName(DEFAULT_DISPLAY_SCALING)))
    .value_or(DEFAULT_DISPLAY_SCALING);
```

`[Display] Scaling` est confirmé — avec un jumeau `Scaling24Bit` pour le
24 bits. `ParseDisplayScaling` (ligne 2231) compare **exactement**, casse
comprise, contre `s_display_scaling_names`.

#### 🔴 2. LE FAIT QUI INVALIDE LA MESURE DU MATIN

`src/core/settings.h`, ligne 242 :

```cpp
static constexpr DisplayScalingMode DEFAULT_DISPLAY_SCALING =
  DisplayScalingMode::BilinearSmooth;
```

**`BilinearSmooth` EST LE DÉFAUT.** Deux conséquences, et elles défont
toutes deux ce que le dépôt croyait avoir mesuré le 2026-08-29 :

1. **poser `BilinearSmooth` ne pouvait rien changer** — c'était déjà la
   valeur en vigueur. « Il n'a rien changé à la géométrie » n'est donc **pas
   une mesure** de ce que fait `Scaling` : c'est la mesure d'un non-geste.
   La conclusion « `Scaling` est un FILTRE » n'était **pas établie** ;
2. **`.value_or(DEFAULT_DISPLAY_SCALING)`** : une valeur non reconnue
   retombe **silencieusement** sur `BilinearSmooth`. Donc « la valeur a été
   reconnue » n'était pas établie non plus — une valeur reconnue et une
   valeur inconnue produisent, dans ce cas précis, **exactement le même
   résultat observable**.

**C'est un TROISIÈME faux oracle**, de la même famille que les deux déjà
écrits, et il mérite d'être nommé : *poser la valeur par défaut ne mesure
rien.* Les deux premiers disaient qu'une valeur fausse est muette et qu'une
clé survivante n'est pas une clé reconnue ; celui-ci dit qu'un essai peut
être muet **parce qu'on a réécrit ce qui était déjà là**.

#### 3. Où la valeur est CONSOMMÉE — GÉOMÉTRIE, et filtre

**Le verdict est la première des deux issues de la tâche 2 : le calcul
BRANCHE sur les variantes `*Integer` pour arrondir la taille du rectangle.**

Le pont, `src/core/settings.h` ligne 217 :

```cpp
ALWAYS_INLINE bool IsUsingIntegerDisplayScaling(bool is_24bit) const
{
  const DisplayScalingMode mode = is_24bit ? display_scaling_24bit : display_scaling;
  return (mode == DisplayScalingMode::NearestInteger ||
          mode == DisplayScalingMode::BilinearInteger);
}
```

L'appel, `src/core/video_presenter.cpp` ligne 610, dans
`VideoPresenter::PresentFrame` :

```cpp
const bool integer_scale = g_gpu_settings.IsUsingIntegerDisplayScaling(s_locals.display_texture_24bit);
```

puis `VideoPresenter::CalculateDrawRect` (ligne 1417), qui délègue à
`GPU::CalculateDrawRect` (`src/core/gpu.cpp`, ligne 2250). `integer_scale` y
sert **trois fois**, dont deux qui sont l'arrondi lui-même (lignes 2336 et
2367, le même code sur chaque axe) :

```cpp
scale = fwindow_size.x / fvideo_size.x;
if (integer_scale)
{
  // skip integer scaling if we cannot fit in the window at all
  scale = (scale >= 1.0f) ? std::floor(scale) : scale;
  padding.x = std::max<float>((fwindow_size.x - fvideo_size.x * scale) / 2.0f, 0.0f);
}
else
{
  padding.x = 0.0f;
}
```

Ce qui est arrondi, exactement : le **facteur d'échelle flottant** est
tronqué au plancher par `std::floor`, mais **seulement s'il vaut au moins
1.0** — sinon la fenêtre est trop petite et l'échelle fractionnaire est
gardée. Le résidu devient un **remplissage centré**, là où le mode non
entier met ce résidu à zéro. Le troisième usage (ligne 2264) choisit l'axe
de correction du ratio de pixel. En sortie :

```cpp
*out_draw_rect = GSVector4i(fvideo_active_rect + padding4);
*out_display_rect = GSVector4i(GSVector4::loadh(fvideo_size) + padding4);
```

**Le second rôle, distinct et réel** : la même valeur choisit aussi le
shader de présentation (`video_presenter.cpp` ligne 307) et
l'échantillonneur (ligne 916), et **les variantes `*Integer` n'ont aucun
shader propre** — `BilinearInteger` partage celui de `BilinearSmooth`,
`NearestInteger` celui de `Nearest`. Autrement dit : **`*Integer` = la même
qualité d'échantillonnage que sa variante de base, PLUS l'arrondi
géométrique.** C'est la seule différence entre `BilinearSmooth` et
`BilinearInteger` — et c'est ce qui rend la mesure de la tâche 3 concluante
si elle compare précisément ces deux-là.

#### 4. Aucune autre clé `[Display]` ne porte le remplissage

Écarté : `IntegerScaling` et `LinearFiltering` **n'existent plus** à cette
révision — absentes de `settings.cpp` comme de `settings.h`, fondues dans
l'énumération `Scaling`. `Stretch` n'existe que sous `#ifdef __ANDROID__`,
comme migration héritée : **inopérante sur cette plateforme**.

Les clés `[Display]` qui touchent bien à la géométrie, et ce qu'elles font —
aucune n'est le remplissage :

| Clé | Ce qu'elle fait |
|---|---|
| `Scaling` / `Scaling24Bit` | **le remplissage** : arrondi entier + résidu centré |
| `AspectRatio` | le ratio — étire la taille sur un axe (deuxième axe, pas le troisième) |
| `Alignment` | répartit le résidu sur l'axe mineur, ne change pas sa taille |
| `Rotation` | échange largeur et hauteur à 90°/270° |
| `FineCropMode`, `FineCrop*` | rognage fin, en amont |
| `CropMode` | **le cadrage — déjà posé**, en amont du calcul, via le CRTC |
| `ActiveStartOffset`, `ActiveEndOffset`, `LineStartOffset`, `LineEndOffset` | décalent les bornes actives, en amont |
| `Force4_3For24Bit` | force le ratio en 24 bits, en amont |

L'hypothèse « la bonne clé est ailleurs » — celle qui a coûté deux
tentatives sur `CropMode` — est donc **écartée par lecture**, pas par
conviction.

#### Ce que ce relevé change pour la suite

- **la tâche 3 doit CONFIRMER un effet géométrique**, pas en chercher un.
  L'issue B de la tâche 4 est celle qui se prépare, pas l'issue A ;
- **les trois captures de la tâche 3 restent nécessaires telles quelles**,
  et la première — `Scaling` absent — devient d'autant plus importante que
  l'absence et `BilinearSmooth` sont maintenant connues équivalentes : c'est
  la comparaison 1↔2 et 1↔3 qui porte l'information ;
- **la lecture ne remplace pas la mesure.** Elle établit un nom, des valeurs
  et un chemin de code ; elle n'établit pas que le binaire livré se comporte
  comme sa source au tag. C'est la règle du dépôt, et le tableau de la
  tâche 3 reste le juge.

---

## Tâche 3 : la mesure sur la console — BLOQUÉE PAR LE PROPRIÉTAIRE

**À jouer par le propriétaire.** Un agent n'atteint pas la console. Tant que
cette tâche n'a pas rendu son observation, la tâche 4 ne peut pas écrire de
valeur — et écrire quand même produirait exactement ce que D2 combat : un
réglage qui a l'air posé et qui ne fait rien.

**Fichiers :** aucun. C'est une mesure.

**Ce qu'il faut avant de commencer :**
- une session Moonlight ouverte, sinon l'écran virtuel n'est pas à la
  résolution du salon et le relevé mesure autre chose ;
- `retro sync` passé, Steam fermé — comme pour le relevé des manettes.

**L'observation qui tranche, et elle seule : le nombre de lignes noires en
haut et en bas de l'image capturée.** C'est une observation **numérique**, pas
une impression : « ça a l'air pareil » n'est pas une mesure.

Sur une sortie PlayStation de 240 lignes utiles, écran de session en
1080 lignes :

| Ce que `Scaling` vaut | Ce qu'on doit compter |
|---|---|
| valeur entière qui AGIT | 240 × 4 = **960 lignes d'image**, **120 lignes noires** (60 en haut, 60 en bas) |
| valeur entière SANS EFFET, ou filtre | **1080 lignes d'image**, **aucune bande** horizontale |

Trois captures, dans cet ordre, la même scène de jeu à chaque fois — un écran
fixe (menu, écran-titre), jamais une image en mouvement :

1. `Scaling` **absent** du fichier — l'état de référence ;
2. `Scaling = <la valeur « nearest integer » relevée en tâche 2>` ;
3. `Scaling = <la valeur « bilinear integer » relevée en tâche 2>`.

**La manœuvre**, par le canal WinRM de `nivuus/installer`
(`console/guest/winrm_exec.py`, voir `docs/releve-manettes.md`) :

- **Écrire la clé à la main** dans
  `%USERPROFILE%\Documents\DuckStation\settings.ini`, section `[Display]`,
  **après avoir copié le fichier** sous `settings.ini.avant-releve-scaling`.
  Cette écriture à la main **survit au lancement par la console** : la fusion
  ne touche qu'aux clés qu'elle apporte, et `Scaling` n'est pas encore dans
  `enforced`. C'est ce qui rend l'essai propre.
- **Lancer le jeu depuis Steam**, à la manette, comme une partie ordinaire.
  Sous `-batch -nogui`, DuckStation ne réécrit **jamais** son `settings.ini` :
  la valeur posée reste celle qu'on a posée. C'est mesuré, et c'est ce qui
  rend l'essai reproductible.
- **Capturer l'écran depuis la SESSION INTERACTIVE**, jamais par WinRM
  directement : une commande WinRM tourne en session 0 et ne rend que le VGA
  de secours, pas l'affichage virtuel. Donc `schtasks /create … /it` puis
  `/run`, avec un PowerShell `-WindowStyle Hidden` — sans quoi la console
  PowerShell passe au premier plan et vole l'image. Déposer le PNG sur le
  partage `Console` (`G:`, vu de l'hôte `/media/data/Console`), d'où l'hôte
  le lit.
- **Compter les lignes** sur le PNG, depuis l'hôte. Les dimensions du PNG
  donnent au passage la résolution de session, qu'il faut noter : le tableau
  ci-dessus ne veut rien dire sans elle.

**Restaurer** ensuite le fichier depuis la copie, quelle que soit l'issue.

**Ce que la tâche rend :** une ligne par capture — valeur posée, résolution de
session, lignes d'image, lignes noires — et la conclusion : **quelle valeur, si
l'une d'elles, déplace la géométrie**. Si les trois captures sont identiques,
la réponse est **non**, et c'est un résultat, pas un échec.

---

## Tâche 4 : poser le résultat — et le chaînon qui manque au modèle

Bloquée par la tâche 3. Deux issues, et la seconde est beaucoup moins chère
que la première.

### Issue A — aucune valeur ne déplace la géométrie

DuckStation n'expose aucun réglage de remplissage. On l'écrit comme Dolphin :

**Fichiers :** `retro/data/profiles/duckstation.toml`

- `fill_absent` sur **les deux** modes `[system.render.native]` et
  `[system.render.full]`, avec le texte qui dit **où on a cherché** (le
  tableau de `settings.cpp`, la fonction de calcul du rectangle, le tag) et
  **ce qui a été observé** (trois captures, mêmes lignes noires) ;
- la phrase que porte déjà Dolphin : *NON VÉRIFIÉ : ce que DuckStation fait de
  lui-même sur cet axe*. Ce n'est pas une coquetterie — `fill_absent` dit « il
  n'y a pas de réglage », jamais « l'image est bonne » ;
- `[Display] Scaling` **n'entre pas** dans `enforced`. Une clé qui ne change
  rien n'a rien à faire dans ce que la console impose.

Rien d'autre à écrire : `resoudre_remplissage` traite déjà `fill_absent` en
premier, et le refus de `_lire_remplissage` sur un mode vide ne porte que sur
`fill`. Les tests existants couvrent le cas. D2 est alors **close pour
DuckStation**, cadrage et remplissage.

### Issue B — une valeur déplace la géométrie

Alors il faut la poser, et le modèle **ne sait pas encore la décrire**. C'est
le point que ce plan a découvert en lisant le code, et il est structurel :

**Le troisième axe ne connaît que `args` et `config`.** `resoudre_remplissage`
rend `NON_REGLABLE` — « ce mode ne passe rien à l'émulateur, remplissage
compris » — dès qu'un mode a `args` et `config` vides, ce qui est le cas des
deux modes de DuckStation. Et `_lire_remplissage` **refuse** un `fill` déclaré
sur un mode qui ne passe rien. Un remplissage posé par `[bootstrap] enforced`
est donc, aujourd'hui, **indéclarable** — et le rapport dirait « rien à
régler » sur un émulateur dont la console règle le cadrage. C'est exactement
le genre de phrase fausse que ce dépôt refuse ailleurs.

**Second fait structurel : le réglage est UNIQUE, les modes sont DEUX.**
`enforced` est un fragment **par profil**, posé une fois par lancement, avant
que le mode ne soit résolu. `[Display] Scaling` vaudra donc la même chose en
`native` et en `full`, alors que la politique retient `entier` pour l'un et
`ajuste` pour l'autre.

**La valeur à retenir est `entier`, et voici la raison à écrire dans le
profil :** le motif qui justifie `ajuste` en mode `full` est « la résolution
interne est déjà montée à la session, il n'y a plus de trame à préserver ». Ce
motif est **faux pour DuckStation** : ses deux modes ne passent rien, donc
`full` ne monte aucune résolution interne — il n'y a pas de trame agrandie à
ajuster. Des deux valeurs, `entier` est la seule que cet émulateur puisse
garantir sans rééchantillonner.

**L'alternative écartée, et pourquoi :** un fragment `enforced` **par mode**
(deux fichiers déposés par `scan`, deux lignes de plan, le lanceur choisissant
après avoir résolu le mode). Rejetée ici : les deux modes de DuckStation ne
diffèrent par **rien d'autre**, donc ce mécanisme servirait une distinction
sans contenu. Elle redeviendra la bonne réponse le jour où la résolution
interne et le ratio de DuckStation entreront eux aussi dans `enforced` — ce
qui n'est pas le périmètre de ce plan.

**Fichiers :**
- Modifier : `retro/render.py`, `retro/profiles.py`, `retro/status.py`,
  `retro/data/profiles/duckstation.toml`
- Test : `tests/test_render.py`, `tests/test_profiles.py`,
  `tests/test_status.py`, `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- **deux champs dans `[system.render]`** — la table qui porte déjà
  `native_height` et `max_scale`, c'est-à-dire ce qui vaut pour **les deux
  modes** :
  - `fill_enforced` — le remplissage mesuré, `entier` ou `ajuste` ;
  - `fill_enforced_where` — **commençant par `[Section] Clé`**, puis la valeur
    et sa provenance en clair. Le préfixe n'est pas décoratif : c'est ce que
    la garde ci-dessous analyse ;
- **`Render` porte les deux champs**, et `_lire_render` refuse : une valeur
  hors de `REMPLISSAGES` ; un `fill_enforced` sans son `where` ; un `where`
  qui ne commence pas par `[Section] Clé` ; et un `fill_enforced` **coexistant
  avec un `fill` ou un `fill_absent` de mode** — deux endroits décideraient du
  même réglage, et c'est la faute que `_valider_regimes` refuse déjà pour les
  deux régimes de l'amorçage ;
- **une garde après construction du profil**, sur le modèle de
  `_refuser_systemes_partages` : le couple `[Section] Clé` nommé par
  `fill_enforced_where` doit figurer dans `cles_ini(bootstrap.enforced)`.
  Sans elle, un profil pourrait annoncer un remplissage que rien ne pose —
  muet, comme toujours ;
- **`resoudre_remplissage` gagne le cas**, et il passe **avant** celui du mode
  vide, sinon DuckStation reste `NON_REGLABLE`. L'ordre devient :
  `fill_absent` → **imposé par l'amorçage** → mode qui ne passe rien → `fill`
  → jamais mesuré. Son motif doit dire les trois choses que le propriétaire ne
  peut pas deviner : que le réglage vient de l'amorçage, **où** il est posé, et
  qu'il est **le même dans les deux modes** parce que cet émulateur ne règle
  rien en ligne de commande ;
- **la politique n'est pas contredite, elle est hors de portée** — et le
  rapport le dit. Ne la relâche pas dans `_lire_remplissage` : ce chemin-là ne
  passe pas par elle ;
- **`retro status` doit cesser de se taire.** `_lignes_rendu` **sort tôt**
  quand `pilote` est faux (`continue` après les notes), donc les lignes de
  remplissage ne sont **jamais imprimées pour DuckStation**. Les imprimer dans
  cette branche aussi, avant les notes ;
- **`[Display] Scaling` entre dans `enforced`**, avec sa valeur relevée, et
  `DUCKSTATION_IMPOSE` dans `tests/test_donnees.py` gagne la ligne
  `("Display", "Scaling")` — c'est la garde qui fait passer un élargissement
  de ce que la console impose devant un relecteur.

**Les tests à écrire** (chacun doit échouer avant, pour la bonne raison) :

- `resoudre_remplissage` rend la valeur imposée sur un mode **vide**, et son
  motif nomme le `where` ;
- l'ordre des cas : un mode vide qui porte à la fois un `fill_absent` et un
  `fill_enforced` rend bien `fill_absent` — la mesure « il n'y a rien à
  régler » l'emporte sur une déclaration ;
- les quatre refus de `_lire_render`, chacun avec le chemin du fichier fautif
  dans le message ;
- la garde de cohérence : un profil qui déclare `fill_enforced_where` sur une
  clé **absente** de `enforced` est refusé ;
- le rapport imprime la ligne de remplissage pour un émulateur qui **ne pilote
  pas** son rendu ;
- `test_chaque_mode_livre_tranche_sur_le_remplissage` cesse d'être désarmé
  pour DuckStation.

---

## Tâche 5 : la question de l'en-tête — À POSER AU PROPRIÉTAIRE

**Ce n'est pas à toi d'y répondre.** Pose-la telle quelle, et n'écris rien
avant d'avoir la réponse.

> **Accepte-t-on qu'un `settings.ini` puisse se retrouver sans son en-tête
> explicatif après un passage par l'interface de DuckStation — oui ou non ?**

Le fait mesuré, le 2026-08-29 : **DuckStation réécrit son `settings.ini` à une
fermeture propre depuis son interface, et il en efface TOUS les
commentaires** — le fichier est passé de 2187 à 985 octets. Les clés ont
survécu ; l'en-tête en trois catégories que `content` pose, non. Sous
`-batch -nogui` — le seul mode que la console emploie — la réécriture n'a pas
lieu : c'est le passage par l'interface qui efface. Et un tel passage n'est pas
théorique : c'est **la procédure de relevé elle-même** qui l'exige.

### Branche « oui » — rien à écrire dans le code

Mais il faut dire ce que la garde protège alors **réellement**, parce que ce
n'est pas ce qu'on croit en la lisant. `_valider_regimes` refuse un profil qui
impose des clés sans que son `content` distingue les trois catégories. Elle
garantit donc :

- que le **profil livré** porte l'explication — une garantie de **dépôt**,
  vérifiable en revue, jamais une garantie sur le fichier de la console ;
- que l'en-tête est là au **premier dépôt** : une console qui n'a jamais vu
  l'interface de DuckStation garde son en-tête ;
- que quiconque **élargit** `enforced` doit écrire, dans le même geste, ce que
  la console reprend au propriétaire.

Elle **ne garantit pas** que le fichier de la console porte encore
l'explication. Cette phrase doit être écrite dans `retro/profiles.py`, dans la
docstring de `_valider_regimes`, et dans `docs/dettes.md` en clôture de D2.

### Branche « non » — chiffrage

L'en-tête devient une chose que `enforced` doit reposer. La fusion ne sait pas
le faire : elle ne connaît que des couples section/clé, et elle **ne reporte
délibérément pas** les commentaires du fragment source — la limite est écrite
dans `retro-launch.cs`, au-dessus de `Fusionner`, avec sa raison : un
commentaire reporté sans être reconnu **s'empile à chaque lancement**.

| Ce qu'il faut écrire | Fichier | Ordre de grandeur |
|---|---|---|
| un champ `header` dans `[bootstrap]`, ou deux marques de début/fin encadrant l'en-tête de `content`, avec ses refus | `retro/profiles.py` | ~40 lignes, 3 refus |
| dépose du fragment d'en-tête à côté des autres, **purge** comprise, et une ligne `bootstrap_header=` dans **chaque** plan de système — vide quand il n'y en a pas | `retro/launcher.py` | ~25 lignes |
| la repose **idempotente** : retirer ce qui est entre les deux marques à la lecture, réinsérer en tête à l'écriture, et **rejoindre la comparaison « déjà conforme »** pour qu'un fichier conforme ne soit toujours pas réécrit | `retro/data/launcher/retro-launch.cs` | ~70 lignes — **c'est la partie risquée** |
| `--explain` le dit sans rien écrire ; `retro status` le dit | `retro-launch.cs`, `retro/status.py` | ~15 lignes |
| les tests | `test_profiles`, `test_launcher`, `test_donnees`, `test_status` | ~8 tests |
| la vérification sur la console — le dépôt n'a pas de tests C# | manuelle | 1 passage complet |

**Total : cinq fichiers, ~150 lignes, ~8 tests, une vérification sur la
machine.** Le passage de vérification est le suivant, et il n'est pas
facultatif : poser l'en-tête, ouvrir DuckStation **en interface**, le fermer
proprement, relancer un jeu **par la console**, relire le fichier — l'en-tête
doit être revenu, **une seule fois**, et un second lancement ne doit rien
réécrire du tout.

**Deux risques à écrire dans le plan de cette branche :**

1. **l'idempotence est le seul vrai danger.** Un en-tête qui ne se reconnaît
   pas s'empile ; à dix lancements, le fichier du propriétaire est illisible.
   Les marques de début et de fin sont ce qui rend la repose reconnaissable —
   elles ne sont pas un détail de forme ;
2. **le caractère de commentaire dépend du format.** La fusion est un
   fusionneur **INI**. Écrire un `;` dans un `config.yml` ou un `settings.xml`
   corromprait le fichier. Le mécanisme doit rester INI, et le dire — sinon le
   prochain émulateur en hérite sans que personne ne l'ait décidé.

---

## Tâche 6 : la méthode pour les six systèmes sans bloc de rendu

PS2, PSP, Dreamcast, Xbox, PS3, Wii U n'ont **aucun** bloc de rendu. Le
troisième axe **ne se greffe pas avant les deux premiers** : on ne déclare pas
un `fill` sur un mode qui ne passe rien.

Cette tâche n'écrit aucun profil. Elle fixe la méthode, les critères
d'acceptation et l'ordre. Les six tâches qui suivent l'appliquent, **une par
système, un commit par système**.

**La méthode, dans cet ordre, pour chaque émulateur :**

1. **Lire l'analyseur d'arguments dans la SOURCE, au tag épinglé au
   manifeste.** Toujours en premier : un réglage atteignable en ligne de
   commande ne passe pas par un fichier, donc pas par la fusion, donc pas par
   l'amorçage. C'est le chemin court, et Flycast en est probablement le cas.
2. **Lire le site d'ENREGISTREMENT des réglages**, dans la même révision.
   C'est lui qui donne le **nom exact** de la section et de la clé — la chaîne
   littérale passée à la fonction d'enregistrement, jamais un nom déduit d'un
   libellé d'interface.
3. **Lire le TABLEAU STATIQUE DES VALEURS** de chaque énumération employée
   (ratio, mode de mise à l'échelle). **Jamais les chaînes du binaire** : ce
   sont des libellés, et c'est la faute qui a coûté deux tentatives sur
   `CropMode`.
4. **Vérifier le FORMAT du fichier de configuration.** La fusion de
   `retro-launch.cs` est un fusionneur **INI**. YAML (RPCS3) et XML (Cemu)
   **sont hors de sa portée** : si le réglage n'est atteignable que par un tel
   fichier, la conclusion est « bloqué, et voici par quoi », écrite dans le
   profil — pas un fragment écrit à l'aveugle.
5. **Écrire le bloc**, avec ce que le schéma exige : `cost` (`light` /
   `medium` / `heavy` — il est **obligatoire** dès qu'un bloc `render` existe),
   `{render}` **dans le gabarit `launch`** (son absence est refusée au
   chargement), et `native_height` / `max_scale` **seulement si** `{scale}`
   est employé.
6. **Le troisième axe seulement ensuite**, et seulement s'il est établi :
   `fill` quand les arguments le produisent, `fill_absent` quand la source
   montre qu'il n'existe pas. Le modèle de rédaction d'un `fill_absent` est
   celui de Dolphin dans `dolphin.toml` : les fichiers fouillés, le symbole,
   la révision, et la phrase *NON VÉRIFIÉ : ce que l'émulateur fait de
   lui-même sur cet axe*.

**Critère d'acceptation, identique pour les six :** chaque nom de clé et
chaque valeur écrits dans un profil doivent être accompagnés, en commentaire,
du **fichier source, du symbole et du tag** où on les a lus. Une clé sans cette
trace est à retirer — elle est indiscernable d'une clé inventée.

**Ce que ces tâches ne peuvent PAS établir depuis un hôte Linux :** l'effet à
l'écran. Aucune de ces six tâches ne peut clore quoi que ce soit par
l'observation ; elles posent des réglages **lus dans la source**, et chaque
profil doit le dire.

**Fichiers, pour les six :**
- Modifier : `retro/data/profiles/<émulateur>.toml`
- Test : `tests/test_donnees.py` (les gardes existantes s'appliquent d'office :
  `test_aucun_reglage_livre_n_etire_l_image`,
  `test_chaque_mode_livre_tranche_sur_le_remplissage`,
  `test_chaque_gabarit_livre_guillemete_la_rom`,
  `test_chaque_profil_livre_lance_en_plein_ecran`)

**L'ordre** est celui de la valeur pour une console de salon, et c'est celui
des tâches 7 à 12 : PS2, PSP, Dreamcast, Xbox, PS3, Wii U.

---

## Tâches 7 à 12 : un système, un relevé, un commit

Tout ce qui suit est un **point de départ SUPPOSÉ** : un nom de fichier
plausible dans un projet qui a pu le déplacer entre deux versions. Le critère
n'est pas « ce fichier existe », c'est « **la chaîne littérale de la clé y est
lue** ». Si le fichier n'est pas là, la clé est ailleurs dans la même
révision — cherche-la, ne la devine pas.

### Tâche 7 — PS2 (PCSX2 v2.6.3)

- Arguments : `pcsx2-qt/QtHost.cpp`, la fonction qui analyse la ligne de
  commande (même famille que DuckStation, dont le profil cite déjà
  `ParseCommandLineParametersAndInitializeConfig`).
- Enregistrement : `pcsx2/Pcsx2Config.cpp`, le `LoadSave` des options
  graphiques — les littéraux y donnent la section (`EmuCore/GS`) et les clés
  de **résolution interne**, de **ratio** et de **mise à l'échelle entière**.
- Valeurs : les tableaux de noms statiques du même fichier.
- Fichier : `%USERPROFILE%\Documents\PCSX2\inis\PCSX2.ini` — **INI, donc à
  portée de la fusion.** C'est le seul des six dans ce cas avec PPSSPP.
- Rappel du contexte : PCSX2 a le **même assistant obligatoire** que
  DuckStation, et n'a **aucun bloc `[bootstrap]`**. Le rendu par fichier ne
  servira à rien tant que l'amorçage n'est pas mesuré — dis-le dans le profil
  plutôt que de poser un fragment que rien ne lira.

### Tâche 8 — PSP (PPSSPP v1.20.4)

- Arguments : `UI/NativeApp.cpp` (l'initialisation qui consomme `argv`), et
  `Windows/main.cpp`. Le profil passe déjà `--fullscreen` et
  `--pause-menu-exit`.
- Enregistrement : `Core/Config.cpp` — les tables de réglages, dont **le
  premier littéral EST la clé du fichier**, groupées par section (`Graphics`).
  Y chercher la résolution interne, le ratio, et toute clé de mise à l'échelle
  entière.
- Fichier : `memstick\PSP\SYSTEM\ppsspp.ini` — **INI**.
- Attention : PPSSPP écrit son `ppsspp.ini` **en quittant**. Si c'est le cas
  dans cette révision, un réglage posé « si absent » sera écrasé par
  l'émulateur, exactement comme RetroArch — et c'est ce qui a obligé
  `retroarch.toml` à **éteindre explicitement** la mise à l'échelle entière en
  mode `full`. Vérifie-le dans la source avant de conclure.

### Tâche 9 — Dreamcast (Flycast v2.7)

**Le cas probablement le plus simple des six, et donc celui qui prouve la
méthode.** Le profil passe déjà `-config window:fullscreen=yes` : Flycast
accepte des réglages **en ligne de commande**, sous la forme
`-config <section>:<clé>=<valeur>`.

- Arguments : l'analyseur qui traite `-config` (point de départ :
  `core/nullDC.cpp` / `core/emulator.cpp`).
- Enregistrement : `core/cfg/option.h` et `core/cfg/option.cpp` — chaque
  option y porte **sa section et son nom, littéralement**. C'est là que se
  lisent la résolution interne, le ratio et l'éventuelle mise à l'échelle
  entière.
- **Si aucune option de mise à l'échelle entière n'existe dans cette
  révision**, c'est un `fill_absent` **mesuré** — la même réponse que Dolphin,
  rédigée de la même façon.
- Aucun fichier de configuration n'est nécessaire si tout passe par `-config`.
  C'est le meilleur résultat possible : rien à amorcer, rien à fusionner.

### Tâche 10 — Xbox (xemu v0.8.136)

- Arguments : l'endroit où `-full-screen` et `-dvd_path` sont analysés — le
  profil les emploie déjà, donc ils sont une **entrée** dans le code, pas une
  supposition.
- Enregistrement : le schéma de configuration de xemu (point de départ :
  `ui/xemu-settings.h` / `.c`), qui **génère** le `xemu.toml`. Les réglages
  d'affichage y vivent sous des chemins pointés (`display.ui.*`,
  `display.quality.*`) : c'est le schéma qui donne les noms exacts et les
  valeurs des énumérations.
- Fichier : `xemu.toml` — **TOML à sections imbriquées, hors de portée du
  fusionneur INI.** Si le réglage n'est pas atteignable par la ligne de
  commande, la conclusion est « bloqué par le format du fichier », écrite dans
  le profil avec cette raison.
- **Le piège de xemu**, à vérifier : un mode d'ajustement à l'écran qui
  comprend une valeur d'**étirement**. Elle ne doit apparaître nulle part —
  `test_aucun_reglage_livre_n_etire_l_image` la refuserait, et c'est
  exactement le rôle de ce test.

### Tâche 11 — PS3 (RPCS3 v0.0.42-19843)

- Arguments : `rpcs3/main.cpp`. Le profil passe déjà `--no-gui --fullscreen`.
  Vérifier au passage si cette révision accepte de désigner un **fichier de
  configuration** : ce serait un contournement propre du format.
- Enregistrement : `rpcs3/Emu/system_config.h` — chaque nœud de configuration
  y porte **son nom YAML littéral**. La résolution, le ratio et l'éventuelle
  mise à l'échelle entière s'y lisent tels quels.
- Fichier : `config\config.yml` — **YAML, hors de portée du fusionneur INI.**
  À dire dans le profil, avec la conséquence : tant que ce chemin n'est pas
  ouvert, RPCS3 n'aura pas de bloc de rendu piloté par fichier, et l'écrire
  quand même produirait un fragment que rien ne pose.
- RPCS3 a aussi des configurations **par jeu**, qui l'emportent sur la
  globale. Si c'est confirmé dans cette révision, écris-le : un réglage global
  posé et silencieusement dominé par une configuration par jeu est exactement
  la panne muette que ce plan combat.

### Tâche 12 — Wii U (Cemu 2.6)

- Arguments : l'analyseur qui traite `-f` et `-g`, que le profil emploie déjà.
- Enregistrement : `src/config/CemuConfig.h` / `.cpp` — les noms d'éléments
  **XML** du `settings.xml`, et les énumérations d'affichage.
- Fichier : `settings.xml` — **XML, hors de portée du fusionneur INI.** Même
  conclusion que RPCS3, écrite dans le profil.
- Cemu pose une seconde question, déjà notée dans la spec d'amorçage : sa
  configuration vit **sous le dossier d'installation**, que `acquire.acquire`
  supprime à chaque montée de version. Le profil doit dire ce qu'il en est
  dans la version 2.6 épinglée — c'est ce qui décide si un réglage posé
  survit à une mise à jour, ou disparaît sans un mot.

---

## Vérification finale

- [ ] Suite complète, arbre frais, sous `-W error`,
      `PYTHONDONTWRITEBYTECODE=1`
- [ ] Aucun test ne touche le réseau, aucun n'exige Windows
- [ ] **Aucune valeur écrite dans un profil sans son fichier source, son
      symbole et son tag en commentaire à côté d'elle**
- [ ] `retro status` dit quelque chose du remplissage pour **chaque** système
      livré — y compris ceux qui ne pilotent pas leur rendu
- [ ] Aucun profil livré ne porte de réglage d'étirement
      (`test_aucun_reglage_livre_n_etire_l_image`)
- [ ] `DUCKSTATION_IMPOSE` est à jour, et son écart est passé en revue
- [ ] Le bloc de commentaire de `render.py` ne décrit plus un arbitrage rendu
      ni une clé inconnue
- [ ] `docs/dettes.md` — D2 mise à jour à la toute fin, une fois les tâches
      closes : ce qui reste ouvert, et ce qui ne l'est plus

---

## Ce que ce plan ne fait pas

- **Il ne mesure rien lui-même.** La console n'est pas accessible depuis la
  session d'un agent. Les tâches 3 et la vérification de la branche « non » de
  la tâche 5 sont à jouer par le propriétaire, et elles bloquent ce qui les
  suit.
- **Il ne tranche pas la question de l'en-tête.** Elle appartient au
  propriétaire, et la tâche 5 la pose sans y répondre.
- **Il ne règle ni la résolution interne ni le ratio de DuckStation.** Ils
  vivent dans le même `settings.ini` et pourraient y entrer par `enforced`,
  mais c'est un autre travail — et c'est celui qui rendrait utile un fragment
  `enforced` **par mode**, écarté ici faute de contenu à distinguer.
- **Il ne construit aucun fusionneur YAML ni XML.** RPCS3 et Cemu resteront
  bloqués par le format de leur configuration, en le disant, jusqu'à ce que
  quelqu'un décide d'ouvrir ce chemin.
- **Il ne vérifie pas l'image à l'écran des six systèmes.** Un réglage lu dans
  la source est un réglage lu dans la source ; chaque profil doit porter la
  phrase qui le dit.
- **Il ne touche pas à l'amorçage des huit émulateurs non mesurés.** Un bloc
  de rendu par fichier ne sert à rien tant que l'émulateur ouvre son assistant
  à la place d'un jeu : c'est la spec d'amorçage, pas celle-ci.
