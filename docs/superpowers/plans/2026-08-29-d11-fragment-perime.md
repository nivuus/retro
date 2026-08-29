# D11 — Ce que le dépôt impose n'est pas ce que la console applique — plan

> **EXÉCUTÉ le 2026-08-29 dans `packages/retro`.** Ce plan est écrit *après*
> coup : il consigne ce qui a été fait, ce qui a été **rejeté** et pourquoi, et
> ce qui **reste à mesurer sur la console** — que la session qui l'écrit
> n'atteint pas.

**Dette :** `docs/dettes.md`, D11. Deux défauts distincts, tous deux vérifiés
dans le code avant d'être touchés.

**Suite de référence au départ :** `637 passed, 2 skipped`.
**Suite à l'arrivée :** `653 passed, 2 skipped`.

---

## Ce qui est MESURÉ ici, ce qui est RAPPORTÉ, ce qui reste SUPPOSÉ

**Mesuré dans cette session, sur ce dépôt :**

- `ecrire_plan` (`retro/launcher.py`) est bien le **seul** geste qui dépose
  `<profil>.impose.<n>.<ext>` et `<profil>.bootstrap.<n>.<ext>`, et
  `cli._cmd_scan` son seul appelant.
- `retro/data/launcher/retro-launch.cs` portait **deux** décisions de
  conformité — celle qui écrit et celle de `--explain` — et **les deux**
  comparaient le texte fusionné au texte existant **tel quel**, marques
  comprises.
- `identite.VERSION` vaut `0.1.0+source` **en permanence** sur un arbre source
  jamais construit en roue (`retro/identite.py`, `_lire`). C'est le cas normal
  de l'hôte. Ce fait décide du sort de la piste de l'estampille, plus bas.
- Le garde-fou gelé de l'ensemble imposé de DuckStation est **inchangé** :
  **32 couples, dont 28 en `[Pad1]`**, recomptés après le passage.

**Rapporté, daté, pris pour acquis — pas rejouable ici :** DuckStation réécrit
son `settings.ini` à une fermeture propre depuis son interface et **en efface
tous les commentaires** — 2187 → 985 octets, mesure du 2026-08-29 consignée en
fin de D2. Ni console ni compilateur C# dans cette session (`csc`, `mcs`,
`dotnet`, `mono` : aucun). Cette mesure n'a **pas** été refaite, et rien ici
ne prétend le contraire.

**Supposé :** que `retro status` soit lancé au moins une fois depuis un endroit
qui voit à la fois les profils à jour **et** le disque de la console. C'est déjà
le mode d'emploi documenté du rapport (`build_report` : « `retro status` tourne
sur l'hôte »), mais rien ne l'impose.

---

## Défaut 1 — le fragment n'est écrit que par `retro scan`

### La piste de l'estampille, et pourquoi elle est REJETÉE

La conduite de projet proposait : estampiller le plan de lancement avec
l'identité du paquet qui l'a produit (D6, `retro identite`), puis faire de la
discordance un problème nommé dans `retro status`. Le raisonnement — sur la
console, les profils vivent DANS le paquet, donc un paquet réinstallé avec des
profils neufs mais un scan non rejoué donne un plan d'une autre identité — est
juste. **Il ne tient pas comme mécanisme**, pour trois raisons mesurées :

1. **Il crie à tort dès qu'on croise l'hôte et l'invité.** `identite.VERSION`
   vaut `0.1.0+source` sur l'arbre source, toujours, et une identité gravée
   (`0.1.0+<horodatage>…`) dans la roue installée sur la console. Or `retro
   scan` tourne des deux côtés — la table de D6 le montre — et `retro status`
   aussi. Un plan écrit par l'invité et relu par l'hôte porterait donc une
   identité qui ne peut PAS correspondre, à chaque passage, sans qu'aucun
   fragment ne soit périmé. Ce dépôt écrit déjà, à propos du lanceur périmé,
   qu'« un avertissement qui crie à tort est un avertissement qu'on cesse de
   lire ».
2. **Il crie aussi à chaque reconstruction du paquet**, puisque l'horodatage
   bouge à chaque roue — y compris quand la correction portait sur `scan.py` et
   qu'aucun profil n'a changé. La discordance mesure « le paquet a bougé », pas
   « ce qui est posé est périmé ».
3. **Il se tait sur le cas qui a déjà coûté une bibliothèque.** Les profils du
   propriétaire vivent **hors du paquet**, sur son partage — c'est la troisième
   trouvaille de la mesure de D6. En modifier un ne fait bouger aucune identité
   de paquet : le fragment vieillit, et l'estampille reste muette.

Autrement dit, l'estampille est un **proxy indirect**, à la mauvaise granularité,
faux dans les deux sens. Elle serait défendable s'il n'existait rien de mieux —
mais `retro status` charge déjà les profils (paquet **et** partage du
propriétaire) et lit déjà le disque de la console. La comparaison **directe**
est donc disponible, et elle domine strictement.

### Ce qui a été fait à la place

**Confronter ce que le dépôt impose à ce que la console porte, à l'octet près.**

- `retro/launcher.py` — `fragments_attendus(profile_id, index, amorcage)` rend
  la liste `(nom de fichier, texte)` qu'une entrée d'amorçage fait déposer.
  **`ecrire_plan` s'en sert pour écrire**, et le contrôle pour comparer : une
  seule définition, jamais deux — deux divergeraient au premier changement de
  convention, et le contrôle finirait par bénir un fragment périmé.
- `retro/launcher.py` — `lire_fragments(emulation_root_local)` rend le contenu
  réel du dossier des plans, `nom → texte`. **`None` quand le dossier n'existe
  pas**, et c'est la distinction qui compte : `None` veut dire « `retro scan`
  n'a jamais tourné ici », `{}` veut dire « il a tourné et n'a rien eu à
  déposer ». Les confondre aurait accusé dix profils sur une machine où il n'y
  a rien à reprocher.
- `retro/status.py` — `etat_fragments` (trois états : conforme, écart, jamais
  déposé) et `_probleme_fragments`, **un seul problème groupé** : la cause est
  unique — un scan à rejouer — et dix lignes disant la même chose se lisent
  comme dix pannes. L'action nomme le geste : `retro scan`, le seul qui
  redépose ces fichiers, ce que rien dans le rapport ne disait.
- `retro/cli.py` — `_cmd_status` passe `lire_fragments(...)`.

**Pourquoi à l'octet près, et pas sur les clés.** Le cas le plus courant d'un
`enforced` corrigé est une **valeur** changée, pas une clé ajoutée. Comparer les
seuls couples section/clé — ce que `profiles.cles_ini` sait faire — aurait laissé
passer exactement le correctif qu'on vient d'écrire.

**Le `content` est contrôlé aussi**, pas seulement le `enforced`. Il vieillit de
la même façon et sera posé tel quel sur la prochaine console neuve, avec le
contenu d'un autre âge. Le coût était nul : c'est la même boucle.

### Ce que cette solution laisse passer, et il faut le dire

- **Un `retro status` lancé DANS l'invité sur un paquet périmé se tait.** Il
  compare des profils périmés à un fragment déposé par ces mêmes profils
  périmés : tout concorde. C'est **le domaine de D6**, pas celui-ci — le témoin
  et le refus en code 8 existent pour ça — et D11 dit elle-même que les deux
  causes « se diagnostiqueront l'une pour l'autre ». Le contrôle mord quand le
  rapport est lu depuis un endroit qui voit les profils à jour.
- **Le plan de lancement lui-même n'est pas contrôlé** : `<profil>.<système>.ini`
  et les `.cfg` de mode dépendent de la racine d'émulation et des dossiers
  d'installation, pas seulement du profil. Un arbitrage de rendu périmé dans un
  plan resterait invisible. La ligne tracée est nette — sont contrôlés les
  fragments **dérivés d'un bloc `[[bootstrap]]`** — mais elle est arbitraire.
- **L'action est unilatérale.** Si c'est le dépôt de l'hôte qui est en retard
  sur la console, « lancer `retro scan` » écraserait le neuf par l'ancien. Le
  rapport nomme la discordance correctement ; il ne sait pas dire de quel côté
  est le retard.
- Un fragment **illisible** (encodage cassé) est compté comme un écart, pas
  comme une panne distincte. C'est délibéré : il n'est de toute façon pas
  conforme.

---

## Défaut 2 — la marque de fusion est un commentaire

`Fusionner` retire les marques à la lecture et les repose à l'écriture : c'est
ce qui la rendait idempotente. L'appelant décidait « déjà conforme » en
comparant `fusionne` à `existant` **tel quel**. Les commentaires effacés par
l'interface, les deux textes diffèrent **toujours** — sauvegarde horodatée et
réécriture complète **à chaque lancement**, alors que pas une clé n'a bougé.

### Ce qui a été fait

`retro/data/launcher/retro-launch.cs` : `SansMarques(texte)` retire les lignes
égales à `MARQUE_FUSION` (et normalise les fins de ligne), et **les deux** juges
de conformité — celui qui écrit, celui de `--explain` — passent par lui. La
conformité se juge donc **sur les clés**, jamais sur les marques qui les
commentent.

Trois gardes Python, faute de mieux (voir plus bas) : plus aucune comparaison
`fusionne == existant` dans la source ; **exactement deux** juges, tous deux
`SansMarques(fusionne) == SansMarques(existant)` — les laisser diverger rendrait
« rien ne sera réécrit » à un propriétaire dont le fichier est réécrit à chaque
clic, c'est-à-dire un oracle qui ment ; et `SansMarques` se réfère à
`MARQUE_FUSION`, jamais à un littéral recopié qui s'en désaccorderait.

### Ce que ce choix concède, explicitement

- **Les marques ne reviennent pas d'elles-mêmes.** Elles sont reposées quand une
  clé est réellement (re)posée, et pas avant. Les rendre permanentes demanderait
  de réécrire le fichier à chaque cycle — la panne même qu'on ferme. Une marque
  est un **confort de lecture** ; l'idempotence est une **promesse** faite au
  propriétaire.
- **L'en-tête explicatif du `content` ne revient pas davantage.** C'est
  l'arbitrage encore ouvert en fin de D2, et **ce plan ne le tranche pas** : il
  appartient au propriétaire.
- Une cible aux fins de ligne `\n` n'est plus convertie en `\r\n` au passage.
  Cohérent avec « modifier, jamais écraser » ; c'est néanmoins un changement de
  comportement, et il est noté ici plutôt que découvert.

### La piste qui a été écartée : marquer par une CLÉ

DuckStation **préserve ce qu'il ne comprend pas** — `DisplayCropMode`, clé
inventée, a survécu à la réécriture (fin de D2). Une clé de comptabilité
(`[Retro] Impose = …`) survivrait donc là où un commentaire meurt. Écartée :
le propriétaire a autorisé à écrire « **seulement les clés que la console doit
imposer** », et une clé que son émulateur ne reconnaît pas sort de cette
autorisation. Le même paragraphe de D2 rappelle d'ailleurs que « la clé a
survécu » ne prouve jamais « la clé est reconnue ».

---

## Ce qui n'a PAS pu être prouvé ici

**Aucun compilateur C#, aucun cadre de test C# dans cette session** — vérifié :
`csc`, `mcs`, `dotnet`, `mono` sont tous absents. La correction du défaut 2 est
donc gardée par des tests qui lisent la **source** `.cs`, jamais par son
exécution. C'est le plafond que ce dépôt s'est déjà donné, et il l'écrit :
« Ce dépôt n'a AUCUN cadre de test C#. La seule chose vérifiable depuis ici est
donc mécanique. » Une réimplémentation Python de `Fusionner` servant d'oracle a
été écartée : ce dépôt s'interdit deux implémentations d'un même arbitrage, et
elle aurait divergé du C# au premier changement en prétendant le valider.

Ce qui n'est **pas** prouvé, en clair :

- que la source modifiée **compile** avec le `csc.exe` du .NET Framework ;
- que `SansMarques` fait, à l'exécution, ce que sa lecture promet ;
- que le cycle « ouvrir l'interface, la fermer proprement, relancer » ne
  produit plus de sauvegarde.

---

## Ce qui reste à mesurer sur la console

Dans cet ordre. Aucune de ces étapes n'a été faite.

1. **Recompiler le lanceur** — `D:\Emulation\_launcher\compiler.cmd` — après un
   `retro scan` qui redépose la source. `retro status` doit cesser de dire que
   le lanceur est plus ancien que sa source. **Si la compilation échoue, tout le
   reste du défaut 2 est faux** : c'est la première chose à voir.
2. **Le cycle qui prouve le défaut 2.** Lancer un jeu (fusion faite) →
   `--explain` doit rendre « déjà conforme, rien ne sera réécrit » → ouvrir
   DuckStation par son **interface**, le fermer proprement (c'est ce passage,
   et lui seul, qui efface les commentaires ; `-batch -nogui` ne le fait pas) →
   `--explain` doit rendre **la même chose**. Avant ce correctif, il rendait
   « oui, N clés imposées ». Compter les fichiers `settings.ini.bak-*` avant et
   après : **aucun nouveau** est le résultat attendu.
3. **Le défaut 1, de bout en bout.** Changer une valeur d'un `enforced` sur
   l'hôte, réinstaller la roue sur la console **sans** rejouer `retro scan`,
   puis lancer `retro status` depuis l'hôte : il doit nommer
   `duckstation.impose.1.ini — ne correspond plus au profil` et renvoyer à
   `retro scan`. Rejouer le scan, relancer `status` : **silence**.
4. **Le contre-essai qui compte autant.** Sur une console à jour et fraîchement
   scannée, `retro status` ne doit produire **aucun** problème d'amorçage — ni
   depuis l'invité, ni depuis l'hôte. Un contrôle qui crie à tort vaut moins
   que pas de contrôle du tout.
5. **Constater que les clés sont toujours appliquées.** Après le cycle 2, relire
   `settings.ini` : `SetupWizardIncomplete`, `StartFullscreen`, `CropMode` et
   les 28 liaisons de `[Pad1]` doivent y être aux valeurs du profil. Rappel de
   D2 : **« la clé a survécu » ne prouve pas « la clé est reconnue »** — la
   seule preuve reste l'effet observé, manette en main et image sans bandes.

---

## Fichiers touchés

- `retro/launcher.py` — `fragments_attendus`, `lire_fragments` ; `ecrire_plan`
  passe par la première.
- `retro/status.py` — `Fragment`, `etat_fragments`, `_probleme_fragments` ;
  `build_report` accepte `fragments`.
- `retro/cli.py` — `_cmd_status` lit les fragments déposés.
- `retro/data/launcher/retro-launch.cs` — `SansMarques`, et les deux juges de
  conformité qui y passent.
- `tests/test_launcher.py`, `tests/test_status.py`, `tests/test_cli.py`,
  `tests/test_donnees.py`.

Rien dans `packages/installer`. Rien dans `docs/dettes.md`.
