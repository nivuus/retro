# Amorçage des émulateurs — conception

**Objectif :** un émulateur que `retro install` vient de poser doit lancer un
jeu, pas son assistant de première configuration.

**Spec parente :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`
**Sous-projet voisin :** `docs/superpowers/plans/2026-08-28-manettes-sous-projet-e.md`

---

## Ce qui a été mesuré, et qui commande tout le reste

Le 2026-08-28, sur la machine : lancer Crash Team Racing depuis Steam ouvrait
l'assistant de configuration de DuckStation. La chaîne a été suivie maillon par
maillon.

| Maillon | Preuve | État |
|---|---|---|
| Steam → lanceur | le raccourci porte `duckstation.psx "G:\Games\Sony\Playstation\Crash Team Racing-PSX-PAL.cue"` | intact |
| lanceur → ligne de commande | `_launcher\journal.txt`, cinq lancements, tous avec `-batch -nogui -fullscreen` et le bon chemin de ROM | intact |
| ligne de commande → DuckStation | aucun `settings.ini` sous `C:\Users`, aucun `portable.txt` dans `D:\Emulation\DuckStation` | **rompu** |

DuckStation, quand son `settings.ini` n'existe pas, tient
`Main/SetupWizardIncomplete` pour vrai et affiche son assistant **avant**
d'honorer la ligne de commande. Aucun des dix-sept arguments de la révision
v0.1-11609 ne le saute : `-setupwizard` le force, rien ne l'annule. Et comme
personne ne termine un assistant depuis un canapé, rien n'est jamais écrit —
le lancement suivant recommence à l'identique. Une instance restée sur cet
assistant depuis plusieurs heures a d'ailleurs été relevée vivante sur la
machine, n'ayant créé aucun fichier de données.

**La mesure qui tranche :** un `settings.ini` de deux lignes — `[Main]` /
`SetupWizardIncomplete = false` — déposé dans le dossier de données de
DuckStation (`%USERPROFILE%\Documents\DuckStation`), puis la commande exacte
du journal rejouée. DuckStation a cette fois créé toute son arborescence de
données, chargé sa base de jeux et écrit `playtime.dat` contenant
`SCES-02105` — le serial PAL de Crash Team Racing. Il est allé jusqu'à
démarrer le jeu.

**Une seconde cause du même symptôme, découverte le même jour.** L'assistant
désactivé ne suffit pas : DuckStation ouvrait encore, par-dessus tout, une
fenêtre modale « Mise à jour disponible » (71,31 Mo) qu'aucune manette ne
peut fermer — elle bloquait le lancement exactement comme l'assistant.
`[AutoUpdater]` / `CheckAtStartup = false` la ferme. La raison de fond
dépasse le confort : `retro` épingle la version de chaque émulateur dans son
manifeste, avec son empreinte SHA256, et `acquire` écrit un témoin
`.retro-version` à côté de l'installation ; une mise à jour appliquée par
l'émulateur lui-même ferait diverger l'installation de ce que le manifeste
atteste, en silence.

Trois faits en découlent, et ils sont la raison d'être de cette conception :

1. **`retro install` ne produit pas un émulateur utilisable.** Il extrait une
   archive vérifiée, et s'arrête là. Un émulateur extrait est un émulateur qui
   n'a jamais été configuré.
2. **Le défaut n'est pas propre à DuckStation.** L'inventaire des neuf
   émulateurs installés sur la machine ne montre **aucune** configuration
   utilisateur, nulle part — ni dans `Documents`, ni dans `AppData`. PCSX2 a le
   même assistant obligatoire et sera le prochain à s'ouvrir à la place d'un
   jeu.
3. **Le symptôme a déjà été rencontré et pris pour autre chose.**
   `retro-launch.cs` porte, à propos du job object : « Mesuré le 2026-08-27 sur
   un émulateur resté sur son assistant de premier lancement ». Le processus
   orphelin a été corrigé ; ce qui l'avait laissé sur son assistant ne l'a pas
   été.

**Le problème est celui de la résolution d'écran, que ce dépôt a déjà résolu**
— une écriture qui ne peut avoir lieu que sur la machine, dans une chaîne dont
la politique se décide ailleurs. La réponse est la même, et elle n'est pas
négociable : **le lanceur ne décide rien.** Python compose, teste, dépose dans
le plan ; le lanceur exécute.

---

## Ce qui est décidé

| Question | Décision |
|---|---|
| Qui écrit la configuration ? | Le lanceur, seul code du projet qui s'exécute sur Windows au bon moment. `retro` tourne depuis un hôte qui n'atteint ni `C:\Users` ni `%APPDATA%`. |
| Où vit le contenu ? | Dans le profil TOML, jamais dans le code — comme `RenderMode.config`. |
| Quand écrit-on ? | **Uniquement si le fichier cible est absent.** Une installation configurée n'est jamais retouchée. |
| Et pour forcer ? | Un ordre explicite, `retro launcher --reamorcer <profil>`, consommé par le lanceur, qui sauvegarde avant de réécrire. |
| Que contient l'amorçage ? | Ce qui rend l'émulateur utilisable à la manette depuis un canapé — pas le strict minimum. Chaque clé **relevée sur la machine**. |
| Le mode portable ? | **Exclu.** `acquire.acquire` fait `shutil.rmtree` du dossier d'installation à chaque montée de version : une configuration posée à côté de l'exécutable, cartes mémoire et sauvegardes comprises, disparaîtrait à la première mise à jour. |
| Quels émulateurs ? | Les neuf, un par un, chacun mesuré. |
| Nom du bloc | `[bootstrap]` — les clés TOML du dépôt sont en anglais, seuls commentaires et messages sont en français. |

---

## Le contrat, de bout en bout

```
profil TOML            [bootstrap] target + content
      │                (le contenu et sa cible, écrits une fois, relus par un humain)
      ▼
retro scan             _launcher\systems\<profil>.bootstrap.<ext>   ← le contenu
      │                + trois lignes dans chaque plan du profil     ← la consigne
      ▼
retro-launch.exe       si la cible est absente : la poser, puis lancer le jeu
      │                si elle est présente : ne rien toucher
      ▼
_launcher\bootstrap.txt   ce qui a été posé, où, quand   ← lisible depuis l'hôte
      │
      ▼
retro status           le dit
```

Chaque étage a une seule responsabilité, et aucune n'est rejouée à l'étage
suivant : le profil porte le contenu, `scan` porte la décision, le lanceur
porte l'écriture, le témoin porte la trace.

---

## Le bloc `[bootstrap]` d'un profil

Par **profil**, pas par système : la configuration d'un émulateur ne change pas
selon la console qu'il émule. Même raison que pour le gabarit d'entrée de la
tâche 3 du sous-projet E.

```toml
[bootstrap]
# Pourquoi ce bloc existe, et ce que chaque clé fait là — en commentaire, comme
# partout ailleurs dans ce dépôt.
target = '%USERPROFILE%\Documents\DuckStation\settings.ini'
content = '''
; Écrit par « retro ». Ce fichier n'est posé que s'il est absent.
[Main]
SetupWizardIncomplete = false
'''
```

- `target` — chemin **Windows**, avec ses variables d'environnement. C'est le
  seul moyen d'atteindre un dossier de profil utilisateur depuis un TOML lu sur
  un hôte Linux. Le lanceur les développe avec
  `Environment.ExpandEnvironmentVariables`.
- `content` — le fichier, en entier, dans la syntaxe de l'émulateur. Il porte
  en tête, **dans la syntaxe de commentaire de son propre format**, la phrase
  qui dit qui l'a écrit — la même exigence que les plans et que les
  configurations d'entrée du sous-projet E.
- Le bloc est **facultatif**. Un profil sans bloc reste valide : c'est le cas
  d'un émulateur qui démarre nu, et le profil doit alors **dire pourquoi** il
  n'en a pas besoin. Un bloc absent sans explication ne se distingue pas d'un
  bloc oublié.

**Validation à la lecture du profil** (`profiles.py`) :

- `target` non vide dès que `content` l'est, et réciproquement — la moitié d'un
  amorçage n'amorce rien ;
- `target` est un chemin absolu ou commence par une variable d'environnement ;
  un chemin relatif s'écrirait dans le dossier de travail de l'émulateur, qui
  n'est pas le sien ;
- `content` porte la phrase d'en-tête. Une configuration écrite par un outil et
  qui ne le dit pas est un piège pour le prochain lecteur.

---

## Le plan

`retro scan` dépose le contenu dans
`_launcher\systems\<profil>.bootstrap.<ext>` — à côté des plans de système et
des `.cfg` de rendu, dont il suit la convention de nommage et **la purge** : un
amorçage resté là après qu'un profil a disparu réécrirait la configuration d'un
émulateur que plus rien ne décrit.

Chaque plan de système du profil gagne trois lignes :

```
bootstrap_target=%USERPROFILE%\Documents\DuckStation\settings.ini
bootstrap_source=D:\Emulation\_launcher\systems\duckstation.bootstrap.ini
bootstrap_when=si-absent
```

Toujours écrites, **vides** quand le profil n'a pas de bloc : `Valeur()` traite
une clé manquante comme une faute du plan, et c'est une propriété qu'on garde —
elle a déjà attrapé des plans écrits par une version antérieure. Le patron est
celui de `native=` et `full=`, vides chez DuckStation sans que cela signifie
« oublié ».

`bootstrap_when` n'a aujourd'hui qu'une seule valeur, `si-absent`, et **c'est
volontaire**. La tâche 2 du sous-projet E doit écrire des configurations
d'entrée dans les mêmes fichiers, avec une autre stratégie — réécrites à chaque
lancement, jetons de manettes substitués. Deux mécanismes distincts pour « un
fichier de configuration que `retro` pose sur la machine » divergeraient au
premier changement. Le champ existe donc dès maintenant pour que cette tâche
ajoute sa stratégie plutôt qu'un second contrat. Le lanceur **refuse** toute
valeur qu'il ne connaît pas : une stratégie inconnue est une faute bruyante,
jamais un fichier écrit au hasard.

---

## Le lanceur

Avant `Process.Start`, et après la lecture du plan :

1. `bootstrap_target` vide → rien à faire, aucune ligne au journal.
2. Développer les variables d'environnement de la cible.
3. La cible existe → ne rien toucher. Le journal ne le dit pas : ce serait une
   ligne à chaque lancement de chaque jeu, pour un non-événement.
4. La cible est absente → créer les dossiers parents, copier la source, noter
   au journal ce qui a été posé et où, et mettre à jour le témoin.
5. Une écriture qui échoue **n'empêche pas le jeu de démarrer** : le message
   part à l'écran et au journal, puis l'émulateur est lancé. Il ouvrira son
   assistant, mais le propriétaire aura lu pourquoi — un lanceur qui abandonne
   ici rendrait la main à Steam, ce qui ressemble exactement à un jeu qu'on
   vient de quitter.

L'amorçage précède le lancement dans tous les cas, `--explain` excepté :
`--explain` rend compte sans rien lancer, et doit rester sans effet de bord.
Il **dit** en revanche ce qu'il aurait posé.

---

## Le ré-amorçage

`retro` ne peut pas écrire dans `C:\Users` : « forcer » n'est donc pas une
écriture, c'est un **ordre**.

`retro launcher --reamorcer <profil>` écrit une ligne dans
`_launcher\reamorcer.txt`. Au prochain jeu de ce profil, le lanceur :

1. sauvegarde la cible en `<nom>.bak-<horodatage>` — la convention de
   `shortcuts.vdf.bak-*`, déjà en usage ;
2. réécrit la cible depuis la source ;
3. retire la ligne consommée, pour que l'ordre ne vaille qu'une fois.

Un ordre qui nomme un profil inconnu est rapporté par `retro`, pas laissé au
lanceur : la liste des profils est connue en Python.

---

## Le témoin, et ce que `retro status` en dit

`retro status` tourne sur l'hôte et ne voit ni `C:\Users` ni `%APPDATA%`. Il ne
peut donc pas **constater** qu'un émulateur est amorcé — il ne peut que lire ce
que le lanceur a écrit là où l'hôte regarde.

`_launcher\bootstrap.txt`, une ligne par profil amorcé :

```
duckstation	2026-08-28 10:27:26	C:\Users\<compte>\Documents\DuckStation\settings.ini
```

Le rapport en fait, par émulateur installé et porteur d'un bloc `[bootstrap]` :

- **amorcé** — la date et la cible ;
- **pas encore amorcé** — « aucun jeu de cet émulateur n'a encore été lancé ;
  sa configuration sera posée au premier lancement » ;
- **jamais amorçable** — le profil n'a pas de bloc, et le rapport répète la
  raison que le profil en donne.

Le témoin est une trace, **pas une source de vérité** : c'est le disque de la
console qui décide, et le lanceur consulte la cible, jamais le témoin. Un
témoin effacé fait dire au rapport « pas encore amorcé » sur un émulateur qui
l'est — le lanceur, lui, ne réécrira rien. Le rapport le dit dans ces termes.

---

## Le contenu se mesure

**Aucune clé n'entre dans un gabarit sans avoir été relevée sur la machine.**
C'est la contrainte du sous-projet E, et elle vaut ici pour la même raison : un
identifiant ou une clé écrits d'après un souvenir de forum sont faux en
silence, et un émulateur ignore sans un mot une clé qu'il ne connaît pas.

La manœuvre, pour chaque émulateur :

1. le lancer **dans la session interactive** — `schtasks /create … /IT` puis
   `/run`. Lancé par WinRM, donc en session 0, il ne voit ni écran ni manette ;
2. régler dans son interface ce que l'amorçage doit porter, à la souris
   distante (`SetCursorPos` + `mouse_event`, captures d'écran déposées sur le
   partage) ;
3. l'arrêter proprement, pour qu'il **persiste lui-même** son fichier ;
4. lire ce fichier, et n'en garder que les clés qu'on fixe — chacune avec sa
   raison en commentaire dans le profil ;
5. vérifier l'amorçage en repartant de zéro : cible supprimée, jeu lancé depuis
   Steam, le jeu démarre.

Ce que l'amorçage porte, quand l'émulateur l'expose : ne pas ouvrir
d'assistant, démarrer en plein écran, ne pas demander confirmation à l'arrêt,
ne pas se mettre en pause à la perte du focus, masquer le curseur, empêcher la
mise en veille, et le chemin des BIOS.

**Le chemin des BIOS n'est pas un détail de confort.** `retro status --bios`
vérifie le dossier que le propriétaire a choisi — tandis qu'un émulateur cherche dans le sien. Sans ce réglage, le
rapport annonce « BIOS présent » pendant que l'émulateur ne le voit pas : c'est
un mensonge du rapport, et le pire des états. Chaque profil dont les systèmes
déclarent des `bios` doit donc porter le réglage correspondant, ou dire
pourquoi il ne le peut pas.

### Les neuf émulateurs

Chaque ligne est **à mesurer**. Les emplacements ci-dessous sont des points de
départ pour la mesure, pas des faits établis — sauf DuckStation, relevé le
2026-08-28.

| Émulateur | Cible présumée | Assistant au premier lancement ? | Mesuré |
|---|---|---|---|
| DuckStation | `%USERPROFILE%\Documents\DuckStation\settings.ini` | **oui — deux causes mesurées : l'assistant, et un vérificateur de mise à jour** | 2026-08-28 |
| PCSX2 | `%USERPROFILE%\Documents\PCSX2\inis\PCSX2.ini` | à établir | non |
| RetroArch | `retroarch.cfg`, sous l'installation | à établir | non |
| Dolphin | `User\Config\Dolphin.ini` | à établir | non |
| Cemu | `settings.xml` | à établir | non |
| PPSSPP | `memstick\PSP\SYSTEM\ppsspp.ini` | à établir | non |
| RPCS3 | `config\config.yml` | à établir | non |
| Flycast | `emu.cfg` | à établir | non |
| Xemu | `xemu.toml` | à établir | non |

Le profil de l'émulateur personnel — celui que le propriétaire déclare dans
`G:\retro\profiles`, hors dépôt — suit la même règle : il n'est pas livré
ici, mais il s'amorce par le même contrat, et sa mesure lui revient.

RetroArch et Cemu posent une question de plus : leur configuration vit, selon
la version, **sous le dossier d'installation** — que
`acquire.acquire` supprime à chaque montée de version. Pour ceux-là, la mesure
doit établir s'ils exposent un dossier de données hors de l'installation. Si
aucun ne l'expose, le profil le dit et l'amorçage se rejoue après chaque mise à
jour — ce que le lanceur fait naturellement, la cible ayant disparu avec le
dossier.

---

## Ce que ça ne fait pas

- **Ça ne touche jamais une configuration existante.** Ni fusion, ni clé
  ajoutée, ni valeur corrigée. Un émulateur configuré appartient au
  propriétaire. Le seul chemin qui écrase est un ordre explicite, et il
  sauvegarde d'abord.
- **Ça ne fournit aucun BIOS.** L'amorçage dit à l'émulateur où les chercher ;
  les y déposer reste au propriétaire, et `retro status --bios` dit lesquels
  manquent. Sur la machine de mesure, ce dossier est vide : Crash Team Racing
  ne démarrera pas du tout tant qu'un `scph5502.bin` n'y sera pas —
  mesuré le 2026-08-28 : l'émulateur reconnaît le jeu, cherche un BIOS PAL,
  n'en trouve aucun et quitte.
- **Ça ne configure pas les manettes.** C'est le sous-projet E, qui écrira dans
  les mêmes fichiers avec une autre stratégie, par le même contrat.
- **Ça ne rend pas le mode portable disponible.** Voir la décision plus haut :
  `acquire` supprime le dossier d'installation à chaque mise à jour.

---

## Tests

Aucun test ne touche le réseau, aucun n'exige Windows.

**`tests/test_profiles.py`**
- un bloc `[bootstrap]` complet est lu et typographié ;
- un profil sans bloc reste valide ;
- `target` sans `content` — et l'inverse — est refusé, avec le chemin du
  fichier fautif dans le message ;
- une `target` relative est refusée ;
- un `content` sans phrase d'en-tête est refusé.

**`tests/test_launcher.py`**
- les trois lignes `bootstrap_*` figurent dans **chaque** plan de système du
  profil, et sont vides pour un profil sans bloc ;
- le fichier d'amorçage est déposé sous le nom attendu, avec le contenu du
  profil ;
- il est **purgé** quand le profil disparaît, comme les `.ini` et les `.cfg` ;
- `--reamorcer` écrit l'ordre, et refuse un profil inconnu en le nommant.

**`tests/test_status.py`**
- les trois états du rapport — amorcé, pas encore, sans bloc — depuis un témoin
  fabriqué ;
- un témoin absent ne fait pas échouer le rapport.

**Le lanceur (C#)** — le dépôt n'a pas de tests C#, et en introduire un cadre
dépasse ce travail. La vérification est **manuelle et écrite** dans le rapport
de fin, sur la machine : cible supprimée, Crash Team Racing lancé depuis Steam,
le jeu démarre sans assistant, `journal.txt` et `bootstrap.txt` le disent.
`--explain` sert de contrôle intermédiaire, lisible par WinRM sans rien lancer.

**Un test qui passerait quelle que soit l'implémentation est un défaut.**

---

## Ordre de travail

1. le contrat de bout en bout, avec DuckStation pour seul porteur — c'est ce
   qui ferme le défaut mesuré ;
2. `retro status` et le témoin ;
3. les huit autres émulateurs, un par un, chacun avec sa mesure et sa
   vérification sur la machine. Un émulateur non mesuré n'a pas de bloc, et son
   profil dit qu'il reste à mesurer — jamais un gabarit écrit d'après une
   documentation.
