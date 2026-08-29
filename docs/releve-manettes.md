# Relever la manette d'un émulateur

Cette page est une **procédure à jouer sur la console**, pas une explication.
Elle se joue à la manette depuis le canapé pour l'essentiel, et depuis l'hôte
pour deux commandes. `retro status` y renvoie chaque fois qu'un profil déclare
`[input] mapping = "a-relever"`.

Elle ne demande de **recopier aucune valeur** : elle fait écrire sa
configuration d'entrée par l'émulateur lui-même, ce qui est le seul relevé
valide.

---

## Pourquoi une procédure, et pas une valeur écrite dans un profil

Un identifiant de manette **n'est pas une propriété du périphérique : c'est une
propriété de l'émulateur qui le nomme.**

Le relevé du 2026-08-28 (plan des manettes, tâche 1) a produit **quatre**
identifiants pour une seule manette physique — celui déduit du VID/PID exposé
par Windows, deux relevés SDL sous deux pilotes différents, et celui que
l'émulateur avait écrit lui-même. Le dernier était le seul bon : l'émulateur
remettait à zéro deux octets que SDL insère dans le GUID, et rien dans son code
public ne l'annonce.

Deux conséquences, et ce sont les fondations de cette page :

1. **Un relevé fait par un outil tiers ne vaut rien**, fût-il bâti sur le SDL
   même de l'émulateur. Un tel outil n'existe d'ailleurs pas dans ce dépôt :
   `retro/data/launcher/` ne contient que le lanceur et son script de
   compilation — et le plan des manettes, qui en annonçait un, conclut
   lui-même qu'il ne suffirait pas.
2. **Une valeur non relevée est fausse, et sa fausseté est invisible.**
   L'émulateur ignore en silence une liaison qui ne correspond à aucun
   périphérique ; la manette reste muette exactement comme si le fichier était
   vide. Il n'y a donc **aucun moyen de distinguer** « j'ai recopié une recette
   qui ne marche pas » de « je n'ai rien écrit ». C'est pour cela que le
   squelette `[Pad1]` livré dans `duckstation.toml` est entièrement en
   commentaire.

### La leçon du 2026-08-29 : les chaînes d'un binaire donnent les LIBELLÉS, pas les valeurs

Elle ne vient pas du relevé des manettes mais de celui du cadrage (dette D2), et
elle vaut pour **tout** ce qu'on écrit dans un fichier de configuration — donc
pour cette page.

**Deux tentatives ont échoué avant la bonne, et pour la même raison.** Chercher
les valeurs de `CropMode` dans les **chaînes** de l'exécutable de DuckStation
rend `All Borders`, `Auto (Game Native)` : ce sont les **libellés affichés dans
l'interface**. Les valeurs que le fichier attend sont ailleurs — dans la
**source**, `src/core/settings.cpp`, tableau `s_display_crop_mode_names` :
`None`, `Overscan`, `OverscanUncorrected`, **`Borders`**,
`BordersUncorrected`. La bonne valeur a fonctionné du premier coup une fois
lue là.

La même lecture a tranché `AspectRatio` : il **n'a pas** de tableau statique —
ses valeurs sont en minuscules (`auto`, `stretch`, `PAR 1:1`) ou un ratio
littéral. `AspectRatio = Auto` était donc faux, et a été retiré.

**Ce que ces deux échecs confirment, et qui est la règle de cette page :**

> **Une valeur fausse se comporte exactement comme l'absence de valeur.**

Pas de message, pas de ligne de journal, pas de symptôme distinct. C'est vrai
d'une liaison de manette, c'est vrai d'un mode de cadrage, et c'est pour cela
qu'une valeur se relève au lieu de se recopier.

**Deux corollaires mesurés le même jour, sur le même émulateur :**

- **« La clé a survécu » ne prouve pas « la clé est reconnue ».**
  `DisplayCropMode`, une clé **inventée**, a survécu à une réécriture complète
  du fichier par DuckStation. Il conserve ce qu'il ne comprend pas. La survie
  est donc un **faux oracle** — la seule preuve est l'effet observé.
- **Une clé reconnue peut ne pas faire ce qu'on croit.** `Scaling =
  BilinearSmooth` a été posé, il a été reconnu, et il n'a **rien** changé à la
  géométrie de l'image : `Scaling` est un **filtre**, pas un cadrage.

---

## Ce qu'il faut avant de commencer

- **Une session Moonlight ouverte, manette branchée au client.** Le pad de la
  console n'est pas branché à la machine : il est **créé par Apollo, et il
  n'existe QUE pendant une session**. Hors session, SDL n'énumère rien —
  vérifié. Une mesure faite sans session rapporte « 0 manette » et ne prouve
  rien.
- **La manette doit répondre ailleurs**, sinon ce n'est pas cette panne-là.
  Vérification en trente secondes : Steam Big Picture répond aux boutons.
- **`retro sync` a été passé, Steam fermé.** Il éteint `UseSteamControllerConfig`
  sur les entrées qu'il possède ; sans cela Steam masque la manette à tout ce
  qu'il lance, et le relevé mesurerait ce masquage au lieu de l'émulateur.
  `retro status` nomme les jeux dont Steam Input est resté actif.

### Parler à l'invité

Les commandes de cette page passent par l'exécuteur WinRM du dépôt
`nivuus/installer` — `console/guest/winrm_exec.py`, transport NTLM. **Ce canal
n'est pas ouvert à tout le monde** : les étapes qui écrivent, et l'étape 3 qui
lance DuckStation, sont à jouer par le propriétaire.

```bash
python3 <installer>/console/guest/winrm_exec.py ps '<commande PowerShell>'
```

`cmd` au lieu de `ps` pour du CMD. C'est ce canal qui a servi aux relevés
ci-dessous.

### Le piège qui invalide tout : la session 0

Une commande passée par WinRM depuis l'hôte tourne en **session 0**, où il n'y
a ni écran ni manette. Le même outil SDL y rapporte `0` manette alors que le
pad est présent et sain — et un émulateur lancé par ce canal ne verra rien non
plus.

**Tout ce qui doit voir la manette se lance donc par une tâche planifiée
interactive** (`schtasks /create … /it` puis `/run`), jamais directement. La
commande exacte est à l'étape 3 de la procédure.

---

## Ce qui a DÉJÀ été relevé pour DuckStation

Relevé le **2026-08-29**, sur l'invité `NIVUUS-WIN`
(`provision_version = B1`), DuckStation v0.1-11609. **Attention :** l'invité
portait alors un provisionnement plus ancien de deux versions que le payload
courant ; ce qui suit décrit ce qui EST sur cette machine, pas ce que les
gabarits du dépôt produiraient aujourd'hui.

Les cinq points ci-dessous n'ont **pas** à être refaits : ils sont là pour que
le prochain lecteur sache d'où viennent les conclusions, et pour qu'il puisse
les contredire s'il mesure autre chose. Ce qu'ils NE donnent pas, c'est la
valeur des liaisons — c'est l'objet de la procédure qui les suit.

**1. Le fichier ne porte aucune manette.**

```bash
python3 <installer>/console/guest/winrm_exec.py ps 'Get-Content "$env:USERPROFILE\Documents\DuckStation\settings.ini"'
```

Constaté : le fichier est **octet pour octet celui que « retro » a posé** —
commentaires compris — augmenté de la seule section `[BIOS]` ajoutée à la
main. **Aucune section `[Pad1]`, aucune clé de manette.** Sa sauvegarde
`settings.ini.bak-*` porte le même contenu.

**2. DuckStation ne réécrit jamais ce fichier.**

`settings.ini` datait du 28/08 à 13:21 quand `playtime.dat` datait du même jour
à 18:55. DuckStation a donc **joué cinq heures et demie après la dernière
écriture du fichier sans y toucher**. Sous `-batch -nogui`, il ne persiste pas
ses réglages : rien ne viendra réparer `[Pad1]` tout seul.

**3. La cause : c'est le correctif du défaut précédent.**

L'exécutable porte une page d'assistant nommée **« Controller Setup »**, et
l'appariement automatique n'existe que comme geste d'interface (`Automatic
Mapping`, `Automatic mapping failed, no devices are available`). Or le bloc
`[bootstrap]` du profil pose `SetupWizardIncomplete = false` — pour qu'un jeu
puisse démarrer sans clavier, ce qui était le défaut d'origine. **Cela saute
l'assistant, donc sa page « Controller Setup », donc le seul geste qui aurait
écrit `[Pad1]`.**

Les deux réglages sont nécessaires, et c'est la procédure ci-dessous qui les
concilie : elle rouvre l'assistant une fois, le temps du relevé.

**4. La forme des clés, lue dans l'exécutable livré.**

- sections `Pad1` … `Pad8`, plus une section `ControllerPorts` ;
- une clé `Type` ;
- des clés de bouton **nues** — `Square`, `Triangle`, `LLeft`, `LRight`,
  `LUp`, `LDown`, `RLeft`, `RRight`, `RUp`, `RDown`… — et **non** des clés
  `Bindings/…`. Cette dernière forme est celle de PCSX2 ; elle est **absente**
  du binaire de DuckStation, et `docs/dettes.md` la supposait à tort ;
- les valeurs suivent les gabarits `SDL-{}/{}`, `SDL-{}/Button{}`,
  `SDL-{}/Hat{}{}`, `SDL-{}/+{}`, `SDL-{}/-{}`, et la même famille en
  `XInput-{}/…`.

**Le premier champ est un INDEX de manette, jamais un GUID.** C'est une
différence de fond avec l'émulateur personnel, dont l'identifiant est
`<index>-<GUID>` : une liaison DuckStation ne dépend pas du VID/PID du pad, et
**un changement de type de pad (dette D4) ne l'invalide donc pas** de la même
façon. À vérifier avant de s'en servir, mais c'est ce que le binaire dit.

**5. Les valeurs, au premier passage : aucune.**

Aucune manette n'était connectée. Le pad d'Apollo
(`USB\VID_045E&PID_028E`) et une DualShock 4 (`VID_054C&PID_05C4`) figurent
tous deux dans les périphériques de l'invité, mais avec l'état `Unknown` —
c'est-à-dire **absents**. Le pad n'existe que pendant une session Moonlight, et
DuckStation aurait répondu mot pour mot « Automatic mapping failed, no devices
are available ».

Les vingt-sept liaisons ont été obtenues **le même jour**, par une autre voie —
un pad virtuel créé directement par ViGEmBus, sans session Moonlight. C'est
l'objet de la section suivante ; elles sont depuis dans
`retro/data/profiles/duckstation.toml`, champ `enforced`.

---

## Ce que ce relevé a coûté, et qui n'était pas devinable

Cette section n'est pas une procédure : c'est ce qu'il a fallu apprendre le
2026-08-29 pour faire écrire `[Pad1]` par DuckStation **sans manette physique
et sans session Moonlight**. Rien de tout cela n'est dans une documentation ; le
prochain qui automatisera un relevé le paiera deux fois s'il ne le lit pas ici.

### Les codes IOCTL de ViGEmBus

ViGEmBus crée le pad virtuel qu'Apollo emploie. On peut le piloter directement,
sans Apollo et sans client : c'est ce qui a rendu le relevé possible depuis
l'hôte. Ses codes de contrôle ne sont **pas** documentés dans le pilote livré,
et la valeur qu'on devine est fausse.

**La base de fonction est `0x801`, PAS `0x800`.** C'est le seul point dur ;
tout le reste en découle :

| Opération | IOCTL |
|---|---|
| `PLUGIN` | `0x2AA004` |
| `UNPLUG` | `0x2AA008` |
| `CHECK_VERSION` | `0x2AA00C` |
| `WAIT_READY` | `0x2AA010` |
| `XUSB_SUBMIT_REPORT` | `0x2AA808` |

L'interface à ouvrir :

```
\\?\ROOT#SYSTEM#0001#{96e42b22-f5e9-42f8-b043-ed0f932f014f}
```

**Comment ces codes ont été obtenus**, parce que la méthode se réemploie :
balayage de l'espace `FILE_DEVICE_BUS_EXTENDER`, en lisant le code d'erreur
plutôt que le succès —

- code **inconnu** → erreur **50** (`ERROR_NOT_SUPPORTED`) ;
- code **connu** → erreur **122** (`ERROR_INSUFFICIENT_BUFFER`), le pilote
  ayant commencé à traiter la requête avant de se plaindre de la taille.

C'est cette différence 50/122 qui sépare « ce code n'existe pas » de « ce code
existe, mon tampon est mauvais ». Sans elle, un balayage ne rapporte que des
échecs indiscernables.

### Deux pièges d'automatisation de l'assistant

L'assistant de DuckStation doit être piloté dans la **session interactive**
(voir « le piège qui invalide tout » plus haut). Deux choses y font échouer
l'automatisation sans rien dire :

1. **La console PowerShell d'une tâche `schtasks /it` passe au premier plan et
   FERME le popup.** La fenêtre de l'assistant perd le focus au moment précis
   où la tâche démarre, et le geste suivant tombe dans le vide. Correctif :
   lancer PowerShell avec `-WindowStyle Hidden`.
2. **`InvokePattern.Invoke()` n'ouvre PAS un `QMenu`.** L'automatisation UI
   accepte l'appel, ne signale aucune erreur, et rien ne s'ouvre — Qt ne câble
   pas ce motif sur ses menus. Il faut un **clic souris synthétisé**
   (`SetCursorPos` + `mouse_event`). Et il faut cliquer **le bouton ET l'entrée
   de menu dans la même exécution** : le menu se referme entre deux tâches, donc
   un découpage en deux appels ne clique jamais que dans le vide.

### La voie Moonlight n'a pas abouti : `403 Permission denied`

La première voie essayée était d'ouvrir une session Moonlight depuis l'hôte pour
faire exister le pad. Elle **échoue au `/launch`** avec `403 Permission denied`.

La cause est mesurée : le client appairé porte `perm=0x3000000`, là où les
clients fonctionnels portent `0x7131f00`. C'est un défaut d'appairage, pas un
défaut de relevé — et la voie ViGEmBus l'a remplacée, ce qui est pourquoi cette
page ne l'exige plus.

**Ce que cela laisse à faire à qui voudra un essai AU FLUX** — c'est-à-dire
vérifier qu'un jeu répond à la manette dans les conditions réelles, la
troisième condition de l'étape 4 : régler ce `perm` sur le client appairé.
Tant qu'il vaut `0x3000000`, aucun lancement par Moonlight ne passera.

---

## La procédure, pour DuckStation

### 1. Ouvrir la session, manette branchée

Session Moonlight ouverte depuis le client de la console, **manette branchée au
client**. Vérifier d'abord que la manette répond dans Steam Big Picture : si
elle n'y répond pas, ce n'est pas cette panne-là.

Contrôle depuis l'hôte — le pad doit maintenant être `OK` et non `Unknown` :

```bash
python3 <installer>/console/guest/winrm_exec.py ps 'Get-PnpDevice | Where-Object { $_.InstanceId -match "VID_045E&PID_028E" } | Select-Object Status,FriendlyName,InstanceId'
```

### 2. Sauvegarder, puis rouvrir l'assistant

`settings.ini` est le fichier du propriétaire : on le copie avant de le
toucher, et sous un nom qui dit pourquoi.

```bash
python3 <installer>/console/guest/winrm_exec.py ps '$f="$env:USERPROFILE\Documents\DuckStation\settings.ini"; Copy-Item $f "$f.avant-releve-manette"; (Get-Content $f) -replace "^SetupWizardIncomplete = false$","SetupWizardIncomplete = true" | Set-Content $f'
```

C'est le seul moment où l'on écrit dans l'invité, et c'est une bascule d'un
booléen — pas une liaison inventée.

### 3. Laisser DuckStation faire le relevé lui-même

Le lancer **dans la session interactive**. Une commande passée par WinRM tourne
en session 0, où il n'y a ni écran ni manette : le même outil y rapporte
`0` manette alors que le pad est présent et sain.

```bash
python3 <installer>/console/guest/winrm_exec.py ps 'schtasks /create /tn retro-releve /tr "<racine de l installation>\DuckStation\duckstation-qt-x64-ReleaseLTCG.exe" /sc once /st 00:00 /it /f; schtasks /run /tn retro-releve'
```

`/it` est ce qui compte : sans lui, la tâche tourne hors de la session
interactive et DuckStation ne verra aucune manette.

Sur la télévision, l'assistant s'ouvre. Sur sa page **« Controller Setup »**,
lancer l'**appariement automatique**, puis **terminer l'assistant** — c'est ce
geste qui repose `SetupWizardIncomplete = false` et **écrit le fichier**,
`[Pad1]` compris.

Si le bouton d'appariement répond « Automatic mapping failed, no devices are
available », la manette n'est pas vue par DuckStation : revenir à l'étape 1,
ne pas continuer. Écrire une liaison à la main ici serait exactement la faute
que cette page existe pour empêcher.

Trois pièges relevés le 2026-08-28, à ne pas redécouvrir :

- si l'outil lancé par la tâche est un exécutable maison, il doit être compilé
  en `/target:winexe` : sinon la console `cmd.exe` qu'ouvre la tâche vole le
  focus et les clics se perdent. Pour DuckStation lui-même, la question ne se
  pose pas ;
- les boîtes de dialogue de certains émulateurs s'ouvrent **centrées sur une
  résolution qui n'est pas celle de la fenêtre** : la colonne d'onglets se
  retrouve au-dessus du bord de l'écran, hors d'atteinte. Il faut alors
  repositionner la fenêtre (`MoveWindow`) avant de pouvoir cliquer. Les clics
  s'envoient par `SetCursorPos` + `mouse_event`, **dans la session interactive
  elle aussi** ;
- **ne jamais activer le mode `trace`** pendant une mesure : il a produit
  506 Mo de journal en quelques minutes, saturé la machine, fait expirer les
  commandes WinRM et ralenti le jeu au point de fausser l'essai. `debug`
  suffit.

### 4. Relire, et savoir qu'on a la bonne valeur

```bash
python3 <installer>/console/guest/winrm_exec.py ps 'Get-Content "$env:USERPROFILE\Documents\DuckStation\settings.ini"'
```

**Le relevé est bon si, et seulement si, les trois conditions sont réunies :**

1. la section `[Pad1]` **existe** et porte des clés de bouton qui n'y étaient
   pas — c'est la seule preuve **matérielle** que DuckStation a écrit ;
2. ces lignes ont été écrites **par DuckStation**, pas à la main. Une valeur
   qui vient d'ailleurs — d'une recette, d'un autre émulateur, d'un outil SDL —
   est fausse même quand elle « a l'air » juste, et son échec est
   indiscernable de l'absence de valeur ;
3. **un jeu, lancé depuis Steam, répond à la manette.** C'est la seule preuve
   qui compte : DuckStation ne dira jamais qu'une liaison ne correspond à rien.

Vérifier aussi que `SetupWizardIncomplete` est bien **revenu à `false`** : s'il
est resté à `true`, l'assistant se rouvrira à la place du prochain jeu, et la
console redeviendra injouable pour l'autre raison.

En cas d'échec, restaurer et repartir de l'étape 1 :

```bash
python3 <installer>/console/guest/winrm_exec.py ps '$f="$env:USERPROFILE\Documents\DuckStation\settings.ini"; Copy-Item "$f.avant-releve-manette" $f -Force'
```

### 5. Ce qu'on en fait

- **Ce qui a été fait pour DuckStation le 2026-08-29, et qui n'est pas la règle
  générale.** Les vingt-sept liaisons relevées ont été figées TELLES QUELLES
  dans le profil livré, champ `enforced` de
  `retro/data/profiles/duckstation.toml`. C'est défendable ici pour une raison
  précise : l'identifiant de DuckStation est un **index** (`SDL-0`), pas un
  GUID — il ne porte donc ni VID, ni PID, ni rien qui soit propre à la machine
  de mesure. Un émulateur dont l'identifiant contient un GUID (l'émulateur
  personnel, `<index>-<GUID>`) ne peut PAS être traité ainsi : il lui faudra le
  gabarit à jetons substitué au lancement (le patron de `{render_config}`,
  tâche 3 du plan des manettes).
- **Le prix de ce figeage, et il est réel.** Un index dépend de l'ORDRE
  d'énumération : qu'un autre pad s'énumère avant celui d'Apollo, et les
  vingt-sept liaisons visent un périphérique absent — en silence, DuckStation ne
  dit rien. Et comme elles sont dans `enforced`, elles sont reposées à chaque
  lancement : le propriétaire ne peut plus remapper sa manette depuis
  l'interface de DuckStation. Les deux fragilités sont écrites dans le profil,
  à côté du fragment.
- **`enforced` ou `content` n'est pas un détail de rangement.** Sous
  `-batch -nogui`, DuckStation ne rouvre jamais son `settings.ini` : un régime
  « posé si absent » ne poserait ces liaisons sur AUCUNE console déjà jouée. Une
  manette relevée doit donc être IMPOSÉE, ou elle n'arrivera jamais là où elle
  manque.
- **Basculer le profil** : `retro/data/profiles/duckstation.toml`, bloc
  `[input]`, de `mapping = "a-relever"` vers ce que la mesure dit. **Fait le
  2026-08-29 : le champ vaut `releve`.** Les trois conditions de l'étape 4 sont
  remplies — Crash Team Racing répond à la manette, confirmé par le
  propriétaire. `retro status` a cessé de le signaler comme un problème, et
  continue de le nommer avec son fichier.
  **Ce n'est PAS `auto`**, et la distinction est le cœur de la clôture : `auto`
  veut dire « l'émulateur trouve sa manette seul », et DuckStation ne la trouve
  **que** parce que la console lui impose vingt-huit clés. Aucun des trois
  états d'origine ne pouvait dire cela ; un quatrième a donc été ajouté.
- **Une liaison ne suffisait pas — la seconde cause, à connaître avant de
  conclure un relevé.** Les vingt-sept liaisons étaient justes et Crash Team
  Racing ne répondait toujours à **aucun bouton**. La cause était
  `[Pad1] ForceAnalogOnReset`, booléen de défaut `true`
  (`src/core/analog_controller.cpp`) : CTR est un jeu **d'avant l'analogique**
  et ne répond pas en mode analogique forcé. Le passer à `false` a réglé la
  panne. **Avant de conclure qu'un relevé a échoué, vérifier qu'aucun réglage
  de MODE ne rend le jeu sourd à des liaisons pourtant justes.**

---

## Pour les huit autres émulateurs

La procédure est la même ; seuls changent le fichier et le geste dans
l'interface. L'ordre importe : commencer par ceux dont un profil déclare
`mapping = "inconnu"` **et** dont le propriétaire a des jeux.

Après chaque relevé, mettre à jour le `[input]` du profil concerné :

| Ce qui a été constaté | Ce qu'on écrit |
|---|---|
| la manette répond sans rien configurer | `mapping = "auto"` |
| la manette est muette, rien n'est relevé | `mapping = "a-relever"` + `mapping_where` |
| le relevé est fait, imposé, et un bouton a été VU répondre | `mapping = "releve"` + `mapping_where` |
| personne n'a essayé | `mapping = "inconnu"` (le défaut) |

La troisième ligne est née le 2026-08-29, avec la clôture de D3, parce
qu'aucune des trois autres n'était vraie de DuckStation. **Ne jamais écrire
`auto` pour un émulateur dont les liaisons sont imposées** : `auto` dit que
l'émulateur se débrouille, et effacerait la raison pour laquelle `enforced`
existe. La quatrième valeur exige un **témoin humain** — c'est la seule du
vocabulaire dans ce cas.

**« Ça a l'air de marcher » n'est pas une mesure.** Un journal lu deux secondes
après le démarrage ne prouve rien : le 2026-08-28, l'absence d'un message
d'erreur y a été prise pour un succès alors que le fichier en comptait 272
occurrences une minute plus tard. Compter les occurrences sur le fichier
complet, jamais sur ses premières lignes.
