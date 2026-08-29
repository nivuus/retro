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

**5. Ce qui n'a PAS pu être relevé : les valeurs.**

Aucune manette n'était connectée. Le pad d'Apollo
(`USB\VID_045E&PID_028E`) et une DualShock 4 (`VID_054C&PID_05C4`) figurent
tous deux dans les périphériques de l'invité, mais avec l'état `Unknown` —
c'est-à-dire **absents**. Le pad n'existe que pendant une session Moonlight, et
DuckStation aurait répondu mot pour mot « Automatic mapping failed, no devices
are available ».

C'est exactement ce que la procédure ci-dessous va chercher, et c'est la seule
partie qui exige le propriétaire, une manette et un canapé.

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

- **Ne pas figer l'identifiant relevé dans le profil livré.** Le pad d'Apollo
  n'existe que pendant une session. Ce que le relevé établit, c'est la
  **forme** — et un exemplaire réel de ce que DuckStation écrit, qui devient le
  gabarit à jetons substitué au lancement par le lanceur (le patron de
  `{render_config}`, tâche 3 du plan des manettes).
- **Basculer le profil** : `retro/data/profiles/duckstation.toml`, bloc
  `[input]`, de `mapping = "a-relever"` vers ce que la mesure dit. Si la
  manette répond sans qu'on ait rien eu à écrire, c'est `auto`. `retro status`
  cessera alors de le signaler.
- **La configuration écrite par DuckStation reste en place** : l'amorçage ne
  repose son fichier que s'il est absent. Une manette relevée le reste tant que
  personne n'ordonne un ré-amorçage — et un ré-amorçage la perdrait, ce que
  `retro launcher --reamorcer` fait précédé d'une sauvegarde.

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
| personne n'a essayé | `mapping = "inconnu"` (le défaut) |

**« Ça a l'air de marcher » n'est pas une mesure.** Un journal lu deux secondes
après le démarrage ne prouve rien : le 2026-08-28, l'absence d'un message
d'erreur y a été prise pour un succès alors que le fichier en comptait 272
occurrences une minute plus tard. Compter les occurrences sur le fichier
complet, jamais sur ses premières lignes.
