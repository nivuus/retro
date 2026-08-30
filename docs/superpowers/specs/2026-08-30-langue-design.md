# La langue de la console — conception

**Objectif :** un jeu multilingue démarre dans la langue de Steam, et changer
la langue dans Steam la change partout, sans qu'aucune commande soit tapée.

**Spec parente :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`
**Spec voisine :** `docs/superpowers/specs/2026-08-28-amorcage-emulateurs-design.md`
— tout ce qui écrit dans les réglages d'un émulateur passe par le mécanisme
qu'elle décrit, et la langue n'y fait pas exception.

---

## Ce que le propriétaire a tranché

Quatre décisions, prises avant l'écriture de ce document, et qui commandent
tout le reste :

1. **La langue est celle des DEUX axes** — le réglage système que les jeux
   lisent pour choisir leur langue, ET l'interface de l'émulateur — partout où
   l'émulateur expose l'un ou l'autre. Un seul choix côté console.
2. **`auto` suit Steam, et c'est le défaut.** Une valeur explicite fige la
   langue pour qui veut diverger.
3. **Une langue absente d'un émulateur donne un repli DÉCLARÉ et NOMMÉ.** Rien
   n'échoue, rien n'est silencieux : `retro status` écrit quel repli s'applique
   et pourquoi.
4. **`retro` gagne toujours.** La langue rejoint les clés reposées à chaque
   lancement. C'est la seule condition sous laquelle « suivre Steam » veut dire
   quelque chose — un régime `si-absent` ne poserait rien sur une console déjà
   jouée, et le mode `auto` ne suivrait plus rien.

La quatrième mérite d'être posée en clair, parce qu'elle **entame une promesse
du paquet** : « un émulateur que vous avez réglé vous appartient ». Les clés
imposées étaient jusqu'ici réservées à celles sans lesquelles un jeu ne démarre
pas sans clavier. Une langue n'en est pas : un jeu démarre très bien en
anglais. Le propriétaire a choisi de l'y ajouter en connaissance de cause, et
la contrepartie est portée par `status` : la section Langue doit dire, par
émulateur, que ce réglage-là est repris à chaque lancement.

---

## La décision de nommage, et ce qu'elle supprime

**La langue canonique de `retro` est le nom que Steam emploie** — `french`,
`english`, `japanese`, `schinese`, `koreana`, `brazilian`, `latam` — et non un
code ISO.

Steam étant la source par défaut, tout autre choix imposerait une table de
correspondance de plus entre ce que Steam dit et ce que `retro` nomme. Une
table de plus est un endroit de plus où une langue peut se perdre : une entrée
manquante y rendrait « langue inconnue » sur une langue que Steam sait très
bien nommer, et le symptôme serait un émulateur resté en anglais sans qu'aucune
ligne ne dise pourquoi.

Il reste **une** traduction, et elle est irréductible : du nom Steam vers la
valeur que l'émulateur attend. Elle vit dans le profil, avec le reste de ce qui
est propre à un émulateur, et nulle part ailleurs.

**À épingler avant l'implémentation :** la liste exacte des noms, depuis la
liste documentée par Steam, et la **casse** de la valeur réellement écrite dans
le registre. Les deux se relèvent, elles ne se supposent pas — `koreana`,
`brazilian` et `latam` suffisent à montrer que cette liste n'est pas
devinable.

---

## Le mécanisme

### `retro/langue.py` — un module qui ne connaît aucun émulateur

Sœur de `render.py`, et bâtie sur le même principe : elle dit QUELLE langue
s'applique, jamais ce que cela signifie pour tel émulateur.

Elle porte :

- `LANGUES` — les noms de Steam, et `AUTO` qui n'en est pas un ;
- `resoudre(demandee, steam, declarees, repli)` — rend la langue effective
  **et son motif**.

**Le motif n'est pas un ornement.** Comme pour `render`, chaque résolution rend
la raison de son choix, parce que `status` doit pouvoir l'écrire. Une langue
qui se choisirait en silence donnerait un jeu en anglais que le propriétaire
croirait non traduit.

Les motifs sont au nombre de quatre : « posée à la main », « `auto` : Steam dit
X », « `auto` : Steam n'a rien dit », et « repli : X n'est pas déclaré ici ».

### Le profil — un bloc langue par entrée d'amorçage

Chaque entrée `[[bootstrap]]` peut porter un `[bootstrap.langue]` : un repli, et
un fragment de clés par langue déclarée.

```toml
[[bootstrap]]
target = '%USERPROFILE%\Documents\DuckStation\settings.ini'
content = """…"""
enforced = """…"""

[bootstrap.langue]
# La langue posée quand celle de Steam n'est pas déclarée ci-dessous.
repli = "english"
english  = """
[Main]
Language = en
"""
french = """
[Main]
Language = fr
"""
```

*(Les clés et valeurs ci-dessus sont un GABARIT DE FORME, pas un relevé. Voir
« Ce qui n'est pas livré ».)*

**Attaché à l'entrée, et non au profil.** RetroArch le démontre : sa langue
d'interface vit dans `retroarch.cfg`, la langue système que les jeux lisent est
une option de cœur, dans `melonDS.opt`. Deux fichiers, deux entrées
`[[bootstrap]]`, deux tables. Un bloc langue au niveau du profil aurait forcé à
choisir un des deux fichiers, et l'autre axe serait resté muet.

**Une entrée sans bloc langue ne pose aucune langue.** C'est un état légitime et
**nommé** par `status`, jamais un silence — exactement comme `crt_absent` et
`fill_absent` le font pour le rendu.

### Quatre refus au chargement du profil

Ils rejoignent les gardes de `profiles.py`. Chacun attrape une panne qui serait
autrement muette :

1. **Une langue déclarée qui n'est pas un nom de Steam.** Une coquille — `frensh`
   — ne serait jamais demandée par personne, donc ne poserait jamais rien, sans
   un mot.
2. **Un repli qui n'est pas lui-même déclaré.** La ligne de repli du plan
   pointerait vers un fragment qui n'existe pas, et le lanceur crierait au
   lancement d'un jeu — au pire moment, sur la console, loin des tests.
3. **Deux langues d'une même entrée qui ne posent pas LES MÊMES clés.**
   Découvert en écrivant le plan, et c'est le plus vicieux des quatre : la
   fusion n'écrit que les clés que le fragment apporte. Si `french` pose
   `[Main] Language` et `japanese` pose `[Main] Langue`, passer du premier au
   second **laisse la clé du premier en place** — l'émulateur lit alors deux
   réglages dont l'ancien gagne, et le symptôme est une langue qui refuse de
   changer sans que rien n'ait échoué. L'ensemble des couples
   « (section, clé) » doit donc être **identique** dans toutes les langues
   déclarées d'une entrée.
4. **Un bloc langue sur un profil dont l'en-tête ne prévient pas qu'il impose
   des clés.** `profiles.py` fait déjà ce contrôle pour `enforced` ; les clés de
   langue sont des clés imposées et doivent y être soumises. Sans quoi le
   fichier promettrait au propriétaire un régime qu'il n'applique pas.

### `retro scan` — un fragment par langue déclarée

À côté des fragments actuels, `scan` dépose un fichier par langue déclarée :

```
duckstation.1.langue.english.ini
duckstation.1.langue.french.ini
```

La convention de nommage suit celle de `enforced_name` — même profil, même
rang, même extension tirée de la cible brute — et **une seule définition sert à
l'écriture et au contrôle**, comme `fragments_attendus` le fait déjà. Deux
définitions divergeraient au premier changement, et le contrôle finirait par
bénir un fragment périmé : c'est précisément la panne que ce contrôle existe
pour attraper.

Ces fragments **rejoignent le contrôle de conformité** (`lire_fragments`,
comparaison à l'octet près, saut de ligne final compris).

### Le plan — la décision est prise ici, pas dans le lanceur

Pour chaque entrée d'amorçage, **une ligne par langue de Steam**, toutes,
pointant vers le fragment de cette langue *ou vers celui du repli* :

```
bootstrap_langue.1.french=…\duckstation.1.langue.french.ini
bootstrap_langue.1.english=…\duckstation.1.langue.english.ini
bootstrap_langue.1.dutch=…\duckstation.1.langue.english.ini    ← repli, résolu ici
…
bootstrap_langue.1.defaut=…\duckstation.1.langue.english.ini   ← Steam n'a rien dit
```

C'est la transposition exacte des lignes `auto_<classe>` que le plan porte déjà
pour le rendu : **Python résout, le lanceur lit une ligne.** Le lanceur ne
calcule aucun repli, donc il ne peut pas en appliquer un autre que celui que
`status` a annoncé — les deux ne peuvent pas diverger, parce qu'il n'y a qu'un
seul juge.

La ligne `defaut` couvre le seul cas que Python ne peut pas pré-résoudre :
Steam muet — jamais lancé, valeur absente, lecture impossible. Le lanceur y
trouve un chemin plutôt qu'une clé manquante, et `Valeur()` garde sa propriété :
une clé absente reste une faute du plan.

Une entrée **sans** bloc langue n'écrit **aucune** de ces lignes. Le lanceur le
constate à la première et n'en cherche pas d'autres — sur le modèle de
`bootstrap_count=0`, qui dit « rien à recevoir » sans faire boucler sur du vide.

### Le lanceur — `langue.txt`, voisin de `mode.txt`

Sous la racine locale, à côté de `mode.txt`, et pour la raison qui a mis le mode
de rendu dans un fichier : **l'identifiant d'un raccourci Steam dérive de ses
options.** Écrire la langue dans les options de lancement ferait changer
d'identifiant à toute la bibliothèque à chaque changement de langue, et tout
l'artwork serait à retélécharger pour un réglage.

À chaque jeu, le lanceur :

1. lit `langue.txt` — absent ou illisible vaut `auto`, comme `lire_mode` ;
2. sur une valeur explicite, l'emploie ; sur `auto`, lit la langue de Steam ;
3. cherche `bootstrap_langue.<rang>.<langue>` dans le plan, ou
   `bootstrap_langue.<rang>.defaut` si Steam n'a rien dit ;
4. fusionne le fragment trouvé **par le chemin de fusion existant** — marques,
   sauvegarde horodatée, comparaison avant réécriture, tout est déjà là.

**Deux fragments sont donc refondus par cible, dans cet ordre :** l'imposé
ordinaire, puis celui de la langue. L'ordre est sans effet sur le résultat — ils
ne partagent aucune clé — mais il est fixé pour que le journal soit lisible et
que deux exécutions rendent le même fichier à l'octet près.

Le témoin par cible et la sortie `--explain` gagnent la langue appliquée et le
fragment employé, et le lanceur écrit le témoin de langue décrit plus bas. Sans quoi le seul moyen de savoir quelle langue la console a
posée serait d'ouvrir le settings.ini de l'émulateur.

---

## Où le lanceur lit la langue de Steam — ET CE N'EST PAS MESURÉ

**Le candidat retenu :** `HKCU\Software\Valve\Steam\Language`, valeur `REG_SZ`,
accessible en C# via `Microsoft.Win32.Registry` sans référence supplémentaire
au-delà de ce que `csc.exe` fournit par défaut.

**L'autre voie, écartée :** le `localconfig.vdf` que `retro` ouvre déjà pour
Steam Input. Il est **par compte**, et la console synchronise *tous* les comptes
locaux — deux comptes peuvent donc porter deux langues, et il n'existe aucune
règle honnête pour départager. Le registre, lui, porte la valeur du client qui
tourne : une seule valeur, celle que le propriétaire voit à l'écran.

**Ce que ce document ne prouve pas :** ni l'existence de cette clé sur l'invité,
ni la casse de sa valeur, ni son rafraîchissement au changement de langue sans
redémarrage de Steam. **La première tâche du plan d'implémentation est ce
relevé**, sur la machine, avant qu'une ligne de C# soit écrite.

Trois issues, et le design tient dans les trois :

- la clé existe et suit → rien à changer ;
- la clé existe mais ne suit qu'au redémarrage de Steam → le design tient, et
  `status` doit le dire, sinon le propriétaire changera sa langue et croira le
  mécanisme cassé ;
- la clé n'existe pas → on bascule sur `localconfig.vdf` avec une règle de
  départage écrite, et **cette règle passe en revue** — ce n'est pas un détail
  d'implémentation.

### Le témoin, et pourquoi `status` ne lit pas le registre lui-même

`retro status` **tourne aussi sur l'hôte**, sans voir le disque de la console —
c'est une propriété assumée, que `lire_fragments` porte déjà en distinguant
« le dossier n'existe pas » de « il est vide ». Un `status` qui lirait le
registre ne pourrait donc rendre la langue de Steam **que sur Windows**, et
rendrait autre chose ailleurs : deux rapports contradictoires sur la même
console, sans que rien ne dise lequel croire.

**Le lanceur écrit donc ce qu'il a lu.** À chaque jeu, dans un témoin sous la
racine locale, à côté du journal : la valeur brute obtenue de Steam, la langue
effective, le motif, et l'horodatage du lancement. `status` lit ce témoin.

C'est ce qui rend le relevé du registre vérifiable depuis le canapé, et ce qui
distingue trois états qu'aucun autre moyen ne sépare : « Steam dit `french` »,
« on n'a rien pu lire chez Steam », et **« aucun jeu n'a encore été lancé depuis
que ce mécanisme existe »** — ce dernier étant le seul état sous lequel
l'absence de témoin n'accuse personne.

---

## La commande

Calquée sur `render`, jusqu'aux codes de retour :

```
retro langue --emulation-root-local D:\Emulation
retro langue --emulation-root-local D:\Emulation --langue french
retro langue --emulation-root-local D:\Emulation --langue auto
```

Sans `--langue`, elle lit et affiche. Avec, elle pose, confirme le fichier
écrit, et — comme `render` — **avertit sur stderr et rend 1 si le lanceur n'est
pas installé** : la langue serait bien posée, mais personne ne la lirait, et le
taire ferait croire au propriétaire que son choix s'applique.

Une langue inconnue est refusée par `argparse` sur la liste des noms de Steam,
`auto` compris.

**Changer de langue ne demande aucune resynchronisation.** Les fragments de
toutes les langues déclarées sont déjà sur le disque, posés par `scan` ;
`langue.txt` ne fait que désigner lequel. Aucune entrée Steam n'est touchée,
donc aucun identifiant ne bouge, donc aucune vignette n'est à retélécharger.

**Ce qui, en revanche, exige un `retro scan` :** l'ajout d'une table de langues
à un profil, ou la modification d'un fragment. Le contrôle de conformité le
signale — c'est son rôle.

---

## Ce que `retro status` doit dire

Une section « Langue », qui porte trois choses qu'aucune autre section ne
porte :

1. **la langue effective et son motif** — « `auto` : Steam dit `french` », ou
   « `japanese`, posée à la main » ;
2. **la valeur brute lue chez Steam au dernier lancement**, telle que le témoin
   la porte, même quand elle ne sert pas — et « aucun jeu lancé depuis » quand
   le témoin est absent (voir « Le témoin ») ;
3. **par émulateur, l'un de trois états** :
   - langue posée, et laquelle ;
   - **repli nommé** — « PPSSPP ne déclare pas `dutch`, repli sur `english` » ;
   - **aucune table déclarée** — cet émulateur ne suit pas la langue du tout.

Le troisième état est celui qui compte. Sans lui, un émulateur qui ne suit pas
la langue serait indiscernable d'un émulateur qui la suit mal, et les deux se
lisent à l'écran de la même façon : un jeu en anglais.

Le rapport doit aussi rappeler que ces clés sont **reposées à chaque
lancement** — c'est la contrepartie de la décision 4, et un propriétaire qui
change sa langue dans DuckStation doit pouvoir lire pourquoi son choix n'a pas
tenu.

---

## Les tests

- **`tests/test_langue.py`** — la résolution et ses quatre motifs, le repli, une
  langue non déclarée, Steam muet.
- **`tests/test_launcher.py`** — les lignes du plan (une par langue, celle du
  repli résolue, `defaut`), les fragments déposés, leur nom, leur saut de ligne
  final, et une entrée sans bloc langue qui n'écrit aucune ligne.
- **`tests/test_profiles.py`** — les quatre refus.
- **`tests/test_status.py`** — les trois états par émulateur, la valeur brute du
  témoin affichée même inutilisée, et un témoin absent qui rend « aucun jeu
  lancé depuis » plutôt qu'une langue supposée.
- **`tests/test_cli.py`** — lecture, écriture, langue inconnue, avertissement
  lanceur absent (code 1).
- **Le lanceur C#** — il n'existe **aucun compilateur C# sur l'hôte** (D7). Le
  `.cs` ne peut être validé que par des tests Python qui exigent qu'il **lise**
  chacune des nouvelles clés du plan, sur le modèle de ceux qui existent déjà.
  **La boucle réelle, la lecture du registre et la double fusion restent à
  mesurer sur la console** — ce document ne prétend pas le contraire.

---

## Ce qui n'est PAS livré, et pourquoi

**Livré et testé :** tout le mécanisme ci-dessus, de bout en bout.

**Non livré, parce que non mesuré : les tables de langues elles-mêmes.**

Aucune clé ne sera écrite dans un profil sans avoir été relevée sur l'invité.
C'est la leçon de D3, et elle est plus dure ici qu'ailleurs : une valeur de
langue fausse est **ignorée en silence** par l'émulateur, donc indiscernable de
l'absence de valeur, à l'œil comme au journal. Le symptôme serait « le jeu est
en anglais » — exactement le symptôme d'avant la fonctionnalité.

Deux conséquences concrètes :

- **Les 6 profils qui ont déjà un `[[bootstrap]]`**, soit **dix entrées** —
  DuckStation (1), PCSX2 (1), Dolphin (×2), RetroArch (×2), RPCS3 (×2),
  Vita3K (×2) — recevront leur table quand la clé aura été relevée, profil par
  profil, chacun étant sa propre tâche. La table se déclare **par entrée**, et
  non par profil : les quatre profils à deux cibles en ont donc deux à relever
  chacun, et l'omission de leurs `×2` faisait compter six tables là où il en
  faut dix.
- **`cemu`, `flycast`, `ppsspp` et `xemu` n'ont aucun `[[bootstrap]]`.** Chez
  eux, il faut d'abord établir **où vit le fichier de réglages** avant de parler
  de langue. C'est un travail par émulateur, hors du mécanisme, et il n'est pas
  dans ce spec.

Un mécanisme livré sans aucune table est **utile et honnête** : `retro status`
dira « aucune table déclarée » pour les dix profils, ce qui est exactement
l'état réel de la console. C'est le contraire d'une fonctionnalité qui aurait
l'air de marcher.

---

## Ce que ce spec ne traite pas

- **La région d'une ROM.** Sur SNES, Mega Drive et l'essentiel de la 16 bits, la
  langue est **dans la cartouche** : aucun réglage ne la change. Ces
  systèmes-là ne suivront jamais la langue de Steam, et `status` le dira par
  « aucune table déclarée » — ce qui est vrai, et suffisant.
- **La langue de `retro` lui-même.** Ses messages sont en français et le
  restent ; ce spec parle de la langue des jeux et des émulateurs.
- **L'écriture dans les réglages de Steam.** `retro` lit la langue de Steam, il
  ne l'écrit jamais. `sync` refuse déjà de tourner Steam ouvert ; écrire dans un
  fichier de Steam serait le seul geste à risque du paquet, et rien ici ne le
  demande.
