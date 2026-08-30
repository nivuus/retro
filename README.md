# retro

Fait remonter une bibliothèque de jeux rétro dans Steam, avec ses jaquettes et
ses catégories, de sorte qu'elle soit indiscernable d'une bibliothèque de vrais
jeux Steam.

Vous déposez une ROM. Elle apparaît dans Steam Big Picture avec son artwork.
Vous la lancez à la manette.

## Ce que ça fait

Neuf commandes. Les quatre premières dans cet ordre, les cinq dernières
quand vous voulez :

- **`retro install`** installe les émulateurs du manifeste sous la racine
  d'émulation. Il les **télécharge depuis Internet** et les extrait — voir
  « Ce qui est téléchargé » plus bas, qui dit d'où et comment c'est vérifié.
  Une montée de version **efface le dossier d'installation** : les
  configurations qui y vivaient partent avec, et la commande les **nomme** au
  lieu de les laisser disparaître en silence. Elles sont reposées au prochain
  lancement d'un jeu ; d'ici là, l'émulateur repart sur ses défauts. C'est
  pourquoi `install` lit les mêmes profils que `scan` (`--profiles`,
  `--user-profiles`) : eux seuls savent quels fichiers vivaient là.
- **`retro launcher`** dépose le lanceur commun sous la racine d'émulation et
  vous donne la commande qui le compile. C'est lui que Steam appelle pour
  chaque jeu : il mesure la session au moment du clic, compose la ligne de
  commande de l'émulateur, et le lance **sans fenêtre de console**. Sa source
  est versionnée (`retro/data/launcher/`) et se compile avec le `csc.exe` que
  tout Windows porte — aucun binaire n'est livré tout fait. C'est lui, aussi,
  qui pose la configuration d'un émulateur qui n'en a aucune : sans elle,
  certains ouvrent leur assistant de première configuration au lieu du jeu.
  `retro launcher --reamorcer <profil>` n'écrit rien lui-même — il ne le peut
  pas, cette configuration vit dans le profil Windows de la console — mais
  laisse un **ordre** que le lanceur exécutera **une fois**, au prochain jeu de
  cet émulateur : sauvegarde de l'existant, puis réécriture.
- **`retro scan`** parcourt votre disque de ROMs et écrit l'inventaire JSON,
  ainsi que le plan de lancement que lit le lanceur.
  Ce sont les profils (`retro/data/profiles/*.toml`) qui disent quel dossier
  appartient à quel système, quelles extensions compter, et quelle ligne de
  commande lance un jeu. **Chaque titre se termine par sa console** — « Chrono
  Trigger (Super Nintendo) » — et l'inventaire porte à côté le titre **nu**,
  qui est celui envoyé à SteamGridDB : la base connaît des jeux, pas des
  rangements, et « Chrono Trigger (Super Nintendo) » n'y trouverait aucune
  jaquette.
- **`retro sync`** lit cet inventaire, écrit les entrées correspondantes dans
  le `shortcuts.vdf` de Steam, et récupère les cinq assets d'artwork depuis
  SteamGridDB. Chaque jeu reçoit deux tags — `Rétro` et le nom de son système —
  qui deviennent des catégories natives, filtrables à la manette. Une catégorie
  ne s'affichant nulle part sur une vignette, la console se lit dans le titre
  lui-même ; les tags servent au filtre, le titre à l'œil.

  **Le passage où les titres ont pris leur console retélécharge tout
  l'artwork**, une seule fois : l'identifiant Steam d'un raccourci dérive de son
  nom, un titre qui change est donc une entrée neuve, et les vignettes de
  l'ancienne sont nommées d'après l'ancien identifiant. Comptez cinq requêtes
  SteamGridDB par jeu pour ce passage-là. Rien n'est perdu : les entrées sont
  recréées dans le même passage, avec leurs catégories et leur réglage de
  manette.
- **`retro render`** lit ou pose le mode de rendu. Trois modes, pour toute la
  console : `native` rend ce que la console d'origine sortait — résolution
  interne 1x, ratio d'époque, et le shader CRT là où l'émulateur en a un ;
  `full` pousse au maximum, à la résolution de la session en cours ; `auto`
  choisit entre les deux, **système par système**, en croisant le coût
  d'émulation déclaré dans le profil avec ce que votre machine offre. Le mode
  vit dans un fichier que le lanceur relit à chaque jeu : en changer ne touche
  aucune entrée Steam, donc aucune vignette n'est à retélécharger.
- **`retro langue`** lit ou pose la langue de la console — une seule, pour tous
  les systèmes, comme le mode de rendu. Sans `--langue`, elle affiche celle qui
  est en vigueur ; avec, elle la pose et nomme le fichier écrit. C'est `auto`
  par défaut : le lanceur lit alors la langue du client Steam dans le registre,
  par son **nom** — `french`, `koreana`, `brazilian`, et non un code ISO. Un
  nom que `retro` ne connaît pas ne fait rien échouer et ne se perd pas non
  plus : chaque table déclare le **repli** qui s'applique alors, `retro status`
  dit lequel, et le choix a été fait par `retro scan` — le lanceur lit une
  ligne de plan, il ne décide de rien. Comme le mode de rendu, la langue vit à
  côté des plans de lancement et non dans les options d'un raccourci : en
  changer ne crée donc aucune entrée Steam, et rien n'est à retélécharger.

  **Ces clés-là sont reposées à chaque lancement**, par la même fusion que les
  clés imposées, et c'est la seule exception à « un émulateur que vous avez
  réglé vous appartient » : la langue que vous changeriez dans l'émulateur
  lui-même reviendrait au jeu suivant. `retro langue` est l'endroit où elle se
  change. À l'inverse, un émulateur dont le profil **ne déclare aucune table**
  ne reçoit rien du tout — ses jeux restent dans **sa** langue, quoi que la
  console demande. Ce n'est pas « il la suit mal », c'est « il ne la suit pas »,
  et les deux se lisent pareil à l'écran : un jeu en anglais.

  **Le mécanisme est en place et testé, mais aucun profil ne déclare encore de
  table** : la commande accepte les trente et une langues de Steam et n'en pose
  aujourd'hui aucune. C'est l'état réel de la console, et `retro status` est le
  seul endroit où il se lit — « aucune table de langues déclarée », pour les
  dix entrées d'amorçage des six profils qui en portent une ; les quatre autres
  profils n'ont aucune entrée d'amorçage, donc pas même une ligne. Les valeurs
  se relèvent sur chaque émulateur, une par une : voir `docs/dettes.md`, D12.
  Ajouter une table **exige un nouveau `retro scan`** — ce sont les fragments
  qu'il dépose que le lanceur fusionne.
- **`retro bios`** obtient les BIOS manquants depuis une source **que vous
  déclarez** dans votre propre manifeste, et n'écrit que ce qu'elle a vérifié :
  chaque fichier reçu est comparé au **md5 que le profil déclare**, jamais à un
  md5 rendu par la source — qui n'attesterait que d'elle. Ce qui ne correspond
  pas n'est pas écrit, et la commande le dit en nommant le fichier. Sans source
  déclarée, elle ne devine aucune adresse : elle liste ce qui manque et
  s'arrête. Avec `--emulation-root-local`, elle **porte** en plus chaque BIOS
  vérifié dans le dossier où son émulateur le cherche — sans quoi le rapport
  peut être vert sur des BIOS qu'aucun émulateur ne voit.
- **`retro status`** est la seule commande faite pour un humain : elle écrit un
  rapport lisible depuis le canapé. Quels émulateurs sont installés et en
  quelle version, combien de jeux par système, **quels BIOS manquent**, et la
  liste des problèmes — chacun avec le chemin concerné et le geste à faire.
  Elle ne modifie rien.
- **`retro identite`** dit quelle construction du paquet est en train de
  tourner. Sans elle, deux paquets différents portent le même `0.1.0`, et
  `pip install --upgrade` répond « Requirement already satisfied » **sans rien
  installer** : un correctif écrit et testé peut alors rester sans effet sur la
  console, et l'erreur obtenue décrit le symptôme d'origine, exactement comme
  si le correctif était faux. `scan` et `status` citent désormais cette
  identité en tête de leur rapport, pour que l'inventaire dise toujours qui l'a
  produit.

### Les BIOS

Certains systèmes ne jouent rien sans un BIOS que vous devez fournir. Sans lui,
le jeu apparaît dans Steam, se lance, écran noir : rien n'explique pourquoi.
C'est ce que `retro status --bios <dossier>` dit à votre place. Il distingue
trois états, parce qu'ils appellent trois gestes différents : **présent et
valide**, **absent**, et **présent mais corrompu** — un fichier renommé depuis
un autre BIOS, que vous croyez avoir déposé.

Quand plusieurs BIOS sont interchangeables — les trois BIOS PlayStation, un par
région — le rapport le dit : un seul suffit, celui de la région de vos jeux. Il
ne réclame pas les deux autres.

`retro bios` va les chercher pour vous, à une adresse **que vous écrivez dans
votre manifeste** — jamais dans celui livré avec le paquet, dont le dépôt est
public : y pointer un dépôt de BIOS serait un acte de distribution.

```toml
[bios]
base_url = "https://exemple/BIOS"

# Facultatif : ce que VOTRE source range ailleurs que sous le nom du fichier.
# Le nom à gauche est celui que le profil déclare, celui de droite le chemin
# chez la source. Rien n'est deviné : une source qui range autrement rend 404,
# et la commande donne l'URL qu'elle a essayée.
[bios.paths]
"dc_boot.bin" = "dc/dc_boot.bin"
```

**Ce qui rend une source utilisable n'est pas sa réputation, c'est
l'empreinte.** Le md5 vient du profil, pas de la source ; un fichier qui ne
correspond pas n'est pas écrit. C'est la même règle que l'empreinte SHA256 des
émulateurs, et elle vaut davantage ici : un émulateur faux plante, un BIOS faux
démarre.

**Et un BIOS dans votre dossier n'est pas un BIOS que l'émulateur voit.** Les
deux dossiers sont distincts, et le second est celui qu'un jeu interroge. Un
profil déclare `bios_dir` quand on a **mesuré** où son émulateur cherche ;
`retro bios --emulation-root-local` y porte alors les fichiers vérifiés. Un
profil qui ne le déclare pas est **nommé** plutôt que deviné : un dossier
inventé déposerait les fichiers à côté, sans autre symptôme qu'un écran noir.

### Le vrai titre d'un jeu

« mslug2 » est un nom de romset, pas un nom de jeu : dans Steam il ne dit rien,
et envoyé à SteamGridDB il ne trouve **aucune jaquette**. Donnez `--databases`
à `retro scan` — le dossier `database\rdb\` que RetroArch livre — et chaque
jeu reconnu porte son vrai titre.

**Trois clés, essayées dans cet ordre, et aucune n'est floue :**

1. **le nom du fichier**, comparé à celui que la base porte. Pour l'arcade
   c'est l'identité même : `mslug2.zip` **est** Metal Slug 2 ;
2. **l'empreinte MD5** du fichier, qui ne dépend d'aucun nom. Réservée à ce
   qui est assez petit pour se hacher — une cartouche, jamais un disque ;
3. **le numéro de série gravé dans l'image**, pour les disques. C'est ce qui
   rattrape `Crash Team Racing-PSX-PAL.cue`, qu'aucun nom ne reconnaît : ses
   octets disent SCES-02105, et la base répond « CTR - Crash Team Racing ».

**Ça ne devine jamais.** Aucune comparaison approximative, aucun score de
similarité, aucun « le plus proche ». Un jeu qu'aucune clé ne reconnaît garde
son nom de fichier, et `retro scan` le **nomme** — un titre faux se lit
exactement comme un titre juste, et personne ne le vérifierait.

Quelle base décrit quel système se déclare dans `retro/data/databases.toml` :
c'est une correspondance entre nos identifiants et les noms de fichiers que
RetroArch livre, dont ni l'un ni l'autre ne nous appartient.

### Ce que Steam ne sait pas afficher

Pour un jeu non-Steam : description, date de sortie, éditeur. Le format
`shortcuts.vdf` n'a aucun champ pour ça. Toute la richesse passe donc par
l'artwork et les tags.

Le classement automatique en catégories de décennie et de genre est **prévu et
pas encore actif** : le module qui interroge une base de métadonnées existe
(`retro/metadata.py`), mais rien ne l'appelle et aucune option ne permet de
fournir une clé d'API. Aujourd'hui, les seuls tags écrits sont `Rétro` et le
nom du système.

## Ce que ça ne fait pas

- **Ça ne touche jamais aux jeux que vous avez ajoutés vous-même.** Une entrée
  n'appartient à `retro` que si elle porte le tag `Rétro` **et** que son
  exécutable vit sous la racine d'émulation. Les deux conditions, toujours.
- **Ça ne distribue aucune ROM, aucun BIOS, aucun émulateur.** Vous fournissez
  vos ROMs et vos BIOS. `retro install` ne redistribue pas les émulateurs non
  plus : il télécharge chacun depuis le site de son propre projet, à l'URL et
  sous l'empreinte que porte le manifeste.
- **Ça ne retouche la configuration d'un émulateur que si vous l'avez
  autorisé.** Par défaut — la stratégie `si-absent` — le fichier n'est posé
  que s'il est **absent** : un émulateur que vous avez réglé vous appartient,
  et le seul chemin qui écrase est `retro launcher --reamorcer`, qui
  sauvegarde d'abord.
  Un profil peut en outre déclarer un petit nombre de clés **imposées**,
  reposées à chaque lancement : celles sans lesquelles un jeu ne démarre pas
  sans clavier — un assistant de première configuration qui s'ouvre
  par-dessus, une fenêtre de mise à jour, un plein écran manquant. Pour
  DuckStation, c'est **trois clés**, et le reste de son fichier suit le
  régime ordinaire : ce que vous changez dans l'émulateur tient.
  **Modifier n'y est jamais écraser** : seules ces clés-là sont réécrites,
  tout le reste — vos clés, vos commentaires, l'ordre du fichier — est
  préservé, une sauvegarde horodatée est faite avant chaque écriture, et un
  fichier déjà conforme n'est **pas** réécrit du tout. Les lignes posées par
  `retro` sont marquées comme telles, `retro status` dit combien de clés
  chaque profil impose, et l'en-tête du fichier doit distinguer les trois
  catégories — le chargement refuse un profil qui imposerait des clés en
  promettant le contraire.
- **Ça n'arrête pas Steam.** `retro sync` refuse de s'exécuter tant que Steam
  tourne — il réécrirait le fichier à sa fermeture et le travail serait perdu,
  sans le moindre message. Fermez Steam d'abord.

### Ce qui manque, et qui est écrit quelque part

**Treize** manques constatés sont consignés dans `docs/dettes.md`, chacun avec
ce qu'il coûte vu du canapé et où il se joue dans le code : aucune vibration
nulle part, rien qui garantisse une image maximale sans déformation, ni capteur
de mouvement ni manette PlayStation, la console qui tourne sur un paquet périmé
sans que rien ne le dise, **quatre réglages critiques que le mécanisme
d'amorçage ne sait pas tenir**, une PS4 dont l'émulateur ne peut recevoir aucun
jeu, une PS Vita où installer un jeu échoue par les deux voies prévues, et
**une langue que le mécanisme sait poser et qu'aucun profil ne déclare
encore** — dont l'hôte et la console ne lisent d'ailleurs pas le réglage de la
même façon. Ceux qui touchent la manette débordent sur l'invité Windows, qui a
son propre fichier dans `nivuus/installer` : `docs/console-dettes.md`.

**Quatre ont bougé le 2026-08-29, et deux sont nées le même jour.** La
**manette muette dans DuckStation** est réglée : Crash Team Racing répond,
confirmé par le propriétaire. Il a fallu deux clés, pas une — les vingt-sept
liaisons relevées, **et** `ForceAnalogOnReset = false`, sans laquelle les
liaisons étaient justes et le jeu restait muet. **Le cadrage de DuckStation**
est réglé lui aussi (`CropMode = Borders`) ; le reste de cette dette-là est
ouvert. **La PS Vita est close** : l'émulateur est installé depuis le manifeste
du propriétaire, son firmware 3.74 posé, et un jeu répertorié puis lancé.

Les deux nouvelles sont nées de cette clôture, et elles portent plus loin
qu'elle : **la console faisait tourner un paquet périmé** — neuf profils au
lieu de dix, même numéro de version, aucun signal — de sorte qu'un correctif
écrit ici pouvait rester sans effet sur la machine ; et **deux réglages
mesurés, indispensables, ne sont tenus par rien**, faute d'un mécanisme
d'amorçage capable de viser leurs fichiers.

Les entrées gardent l'histoire complète, y compris les tentatives qui ont
échoué — c'est souvent l'échec qui porte la leçon.

## Utilisation

```bash
# 1. installer les émulateurs (télécharge depuis Internet)
retro install --emulation-root 'D:\Emulation' \
              --user-manifest 'G:\retro\emulators.toml' \
              --user-profiles 'G:\retro\profiles'

# 2. inventorier les ROMs
retro scan --roms /mnt/roms \
           --roms-windows 'G:\ROMs' \
           --emulation-root 'D:\Emulation' \
           --emulation-root-local /mnt/emulation \
           --user-manifest 'G:\retro\emulators.toml' \
           --user-profiles 'G:\retro\profiles' \
           --output inventaire.json

# 3. faire remonter le tout dans Steam
retro sync --steam-root /mnt/steam \
           --steam-root-windows 'D:\Steam' \
           --emulation-root 'D:\Emulation' \
           --inventory inventaire.json \
           --steamgriddb-key VOTRE_CLE

# 4. lire ce qui va et ce qui manque (dans la machine virtuelle : les deux
#    chemins de la paire --roms/--roms-windows s'y confondent)
retro status --roms 'G:\ROMs' \
             --roms-windows 'G:\ROMs' \
             --emulation-root 'D:\Emulation' \
             --user-manifest 'G:\retro\emulators.toml' \
             --user-profiles 'G:\retro\profiles' \
             --bios 'G:\ROMs\bios'
```

`--roms` est le chemin par lequel la machine qui scanne atteint les ROMs ;
`--roms-windows` celui par lequel la console les verra. `--steam-root` et
`--steam-root-windows` sont la même distinction pour l'installation Steam : le
premier sert à lire et écrire `shortcuts.vdf`, le second est ce que **Steam**
relira — notamment le chemin des icônes. Dans chaque paire, les deux ne se
confondent que lorsque la commande tourne sur la console elle-même.

`--emulation-root-local` est la même distinction pour les émulateurs :
`--emulation-root` est ce que la **console** lira dans `shortcuts.vdf`,
`--emulation-root-local` le chemin par lequel la machine qui scanne atteint les
mêmes fichiers — un chemin POSIX là où l'autre est un chemin Windows. Donné,
`scan` vérifie que chaque émulateur est réellement installé, ignore les systèmes
dont il manque, et **le dit** — sur la sortie d'erreur et sur la sortie
standard. Sans lui, rien n'est vérifié : une installation ratée peuple alors
Steam de raccourcis vers des programmes absents, et la bibliothèque ne se
contente pas d'être vide, elle est morte.

« Installé » veut dire deux choses à la fois, et `scan`, `status` et `install`
l'entendent de la même façon : l'exécutable du profil existe, **et** le témoin
de version `.retro-version` est là. Le témoin n'est déposé qu'après vérification
de toutes les archives — RetroArch sans ses cores ne lance rien tout en
paraissant installé. Un émulateur déposé à la main est donc signalé, pas
inventorié. `retro status` fait la même vérification, avec le chemin qu'il
reçoit déjà.

`--manifest` et `--user-manifest` sont passés à `install` **et** à `scan`, avec
les mêmes valeurs : c'est le manifeste qui décide où chaque émulateur
s'installe, donc lui seul sait où l'inventaire doit pointer. Les donner à l'un
et pas à l'autre produit des raccourcis qui ne lancent rien.

`--user-profiles` est le pendant de `--user-manifest` pour les profils, et va
avec lui : `scan` et `status` le prennent tous les deux, avec les mêmes
valeurs.

### Vos propres émulateurs

Le dépôt est public et ne référence que des émulateurs au statut juridique
clair. Rien ne vous limite : vous déclarez les vôtres dans **votre** manifeste
(`--user-manifest`) et **votre** dossier de profils (`--user-profiles`), tous
deux hors dépôt.

Vos profils **complètent** ceux du paquet, ils ne les remplacent pas : ajouter
le vôtre ne vous fait perdre aucun des systèmes livrés. L'absence du dossier
n'est pas une erreur — il vit souvent sur un partage qui n'est pas monté quand
la machine se provisionne.

Deux règles de préséance, et c'est tout :

- **À identifiant de profil égal, le vôtre l'emporte**, entièrement, systèmes
  compris — exactement comme une entrée de votre manifeste remplace celle du
  noyau.
- **Un système que vous revendiquez vous revient**, et quitte le profil livré :
  écrire un profil qui déclare `psx` suffit à faire passer vos jeux
  PlayStation par votre émulateur plutôt que par le DuckStation livré.

En revanche, **deux profils du même dossier ne peuvent pas revendiquer le même
système** : un seul dossier de ROMs porte ce nom, et le scan trancherait par
ordre alphabétique — renommer un fichier changerait alors l'émulateur qui lance
vos jeux, sans un mot. Ce cas-là est refusé en nommant les deux fichiers.

### Déclarer les modes de rendu d'un système

Chaque système peut déclarer ce que `native` et `full` ajoutent à sa ligne de
commande. `{render}` dit **où** ces arguments s'insèrent — certains émulateurs
exigent le fichier en dernier, et personne ne peut deviner la place juste :

```toml
[[system]]
id     = "gamecube"
launch = '-b {render} -e "{rom}"'
cost   = "medium"          # light | medium | heavy — ce sur quoi `auto` décide

[system.render]
native_height = 480        # la hauteur que sortait la console d'origine
max_scale     = 12         # au-delà, l'émulateur refuse ou rame

[system.render.native]
args = '--config GFX.Settings.InternalResolution=1'
crt  = '...'               # OU crt_absent = "pourquoi il n'y en a pas"
fill = "entier"            # OU fill_absent = "cet émulateur n'en expose aucun"

[system.render.full]
args = '--config GFX.Settings.InternalResolution={scale}'
fill = "ajuste"
```

**Trois axes, et ils ne se remplacent pas.** La *résolution interne* dit
combien de pixels l'émulateur calcule ; le *ratio d'époque* dit la forme de
l'image — un 4:3 correctement rendu sur un 16:9 laisse des bandes noires sur
les côtés, **c'est voulu, ce n'est pas de la déformation** ; le *remplissage*
dit comment l'image produite est posée sur l'écran. C'est ce troisième axe, et
lui seul, qui répond à « occuper le plus possible de l'écran **sans étirer
l'image** ». Il n'a que deux valeurs, parce que ce sont les deux seules façons
d'agrandir sans déformer :

| `fill` | ce que ça fait |
|---|---|
| `entier` | multiple **entier** seulement : chaque pixel d'origine reste un carré de pixels identiques, le reste est de la bande noire |
| `ajuste` | le plus grand agrandissement qui **tienne**, ratio conservé, au prix d'un facteur non entier |

L'étirement n'est pas une troisième valeur qu'on n'aurait pas retenue : il
n'est pas sur cet axe. La **politique** — `native` remplit `entier`, `full`
remplit `ajuste` — est écrite dans `retro/render.py`, et `retro status` la
cite. Un profil qui la contredit est refusé au chargement : la contradiction
ne se verrait sinon que sur l'écran, sur une image floue qu'on croirait
normale.

Trois variables sont disponibles, substituées **au lancement** : `{width}` et
`{height}`, la résolution de la session en cours, et `{scale}`, combien de fois
la résolution d'origine y tient.

Le bloc est **facultatif**, mais tout ce qu'il contient est vérifié au
chargement, parce que chacune de ces fautes est muette : un `{render}` oublié
laisserait les arguments nulle part, un seul mode déclaré ferait que l'autre se
lance en réglages par défaut, une variable mal orthographiée arriverait
littéralement sur la ligne de commande. Un `args` vide est accepté — beaucoup
d'émulateurs n'exposent aucun réglage de rendu en ligne de commande — mais
**exige alors une `note` qui dit pourquoi**, que `retro status` affiche : sans
elle, rien ne distinguerait « vérifié impossible » de « bloc oublié ».

`retro status` nomme les systèmes qui n'ont encore aucun mode déclaré. Ceux-là
lancent la même commande dans les trois modes, et il vaut mieux le lire que le
découvrir.

`retro scan` produit ce JSON, que `retro sync` relit tel quel :

```json
[{
  "title": "Chrono Trigger",
  "rom_path": "G:\\ROMs\\snes\\Chrono Trigger (USA).sfc",
  "system_name": "Super Nintendo",
  "emulator_exe": "D:\\Emulation\\_launcher\\retro-launch.exe",
  "launch_template": "retroarch.snes \"{rom}\"",
  "start_dir": "D:\\Emulation\\RetroArch",
  "extra_tags": []
}]
```

`emulator_exe` vient du manifeste (`install_dir`) et du profil (`exe`) : c'est
la raison pour laquelle `scan` doit recevoir les mêmes manifestes qu'`install`.
`launch_template` porte `{rom}`, que `sync` remplace par `rom_path` ; un profil
dont le gabarit ne le contient pas est refusé au chargement, parce qu'un
émulateur lancé sans jeu s'ouvre sur son propre menu et la console a l'air de
fonctionner.

La clé SteamGridDB est facultative. Sans elle, les jeux remontent normalement,
simplement sans jaquettes.

## Ce qui est téléchargé, et comment c'est vérifié

**`retro install` télécharge et extrait du contenu venu d'Internet.** Il faut
le savoir avant de le lancer.

Ce qu'il télécharge est décrit par un manifeste TOML, et rien d'autre :

- **Le manifeste noyau**, `retro/data/manifests/core.toml`, livré avec le
  paquet. Il ne référence que des émulateurs au statut juridique clair — ce
  dépôt est public, et pointer vers un émulateur contesté est un acte de
  distribution. Aujourd'hui : RetroArch (buildbot.libretro.com), Dolphin
  (dl.dolphin-emu.org), puis DuckStation, PCSX2, PPSSPP, Flycast, xemu, RPCS3
  et Cemu, chacun depuis la publication versionnée de son propre projet.
  RetroArch couvre le rétro ; les sept autres couvrent ce qu'il sert mal —
  PlayStation, PlayStation 2, PSP, Dreamcast, Xbox, PlayStation 3 et Wii U.
- **Votre manifeste**, hors dépôt, passé par `--user-manifest`. Même schéma,
  sans cette limite : c'est là que vous déclarez vos propres émulateurs. Son
  absence est normale et n'est pas une erreur.

Déclarer un émulateur au manifeste ne suffit pas à s'en servir : il lui faut
aussi un **profil**, qui dit quels systèmes il couvre, quelles extensions il
accepte et comment on le lance. Vos profils vivent eux aussi hors dépôt, dans
le dossier que `--user-profiles` désigne — voir « Vos propres émulateurs ».

Chaque archive porte au manifeste une **empreinte SHA-256 épinglée**, et elle
est **vérifiée avant toute extraction**. Une empreinte qui ne correspond pas
fait échouer l'installation de cet émulateur en le nommant, et ne laisse rien
derrière elle. Les empreintes du noyau ont été calculées en téléchargeant les
archives, jamais recopiées d'une page tierce : une empreinte recopiée n'atteste
que de la page.

L'extraction **n'écrit jamais hors du dossier de destination** : une archive
qui contiendrait « ../ » ou un chemin absolu est rejetée en le nommant, et le
secours 7-Zip, lui, maintient l'extraction sous son `-o`.

Un émulateur peut être livré en plusieurs archives qui se déversent dans le
même dossier. Toutes sont téléchargées et vérifiées **avant** que la moindre
écriture ne touche à l'installation existante — un émulateur amputé est pire
qu'un émulateur absent, parce qu'il paraît installé et ne lance rien. Parmi
les émulateurs livrés, RetroArch est le seul dans ce cas : son archive
principale ne contient aucun core.

L'installation est idempotente. Un témoin `.retro-version` évite de
retélécharger des gigaoctets déjà présents à chaque reconstruction de la
machine.

### Prérequis : un binaire 7-Zip

**En pratique, ni RetroArch ni RPCS3 ne s'installent sans un binaire 7-Zip sur
le `PATH`.** `py7zr`, la bibliothèque Python, ne sait pas lire le filtre
**BCJ2** — elle le marque « Unsupported » dans son propre code — et c'est
précisément celui qu'emploient les archives du buildbot libretro et celles de
RPCS3. Les 7z de PCSX2, eux, se lisent sans ce secours.

`retro install` essaie `py7zr` d'abord, puis se rabat sur le premier binaire
trouvé parmi `7zz`, `7z`, `7za`, `7zr`, `7zr.exe`, `7z.exe`. S'il n'en trouve
aucun, il le dit et nomme l'archive en cause — il ne fait pas semblant
d'installer.

`7zr` suffit : ~600 Ko, redistribuable, il lit tous les filtres
(<https://www.7-zip.org/a/7zr.exe>). Sous Linux, `p7zip-full` ou `7zip` selon
la distribution.

## Sûreté

Le fichier que ce paquet écrit est celui dont la corruption casse la
bibliothèque Steam de quelqu'un. Quatre protections :

- **Écriture atomique** — le rendu est complet en mémoire avant que le disque
  soit touché, puis un fichier temporaire est basculé d'un coup. Une écriture
  interrompue ne laisse pas de bibliothèque tronquée.
- **Sauvegarde horodatée** de l'ancien fichier avant chaque écriture qui change
  quelque chose. Une sauvegarde n'en écrase jamais une autre, même à la seconde
  près ; et une synchronisation sans changement n'écrit ni ne sauvegarde rien,
  donc les `.bak` ne s'accumulent pas.
- **Refus si Steam tourne**, parce qu'écrire alors perdrait le travail sans
  rien signaler.
- **Refus si `--emulation-root` ne contient pas les émulateurs de
  l'inventaire**, parce qu'alors le paquet ne reconnaît plus ses propres
  entrées et recrée les mêmes raccourcis à chaque passage en rapportant des
  ajouts réussis.

`shortcuts.vdf` n'est plus le seul fichier écrit hors de la racine
d'émulation. Pour qu'un émulateur fraîchement installé lance un jeu plutôt que
son assistant de première configuration, le **lanceur** pose sa configuration
là où cet émulateur la lit — dans le profil Windows du propriétaire
(`%USERPROFILE%\Documents\...`), le seul endroit qui survive à une mise à
jour. Trois règles l'encadrent, et ce sont les mêmes que ci-dessus :

- **seulement si le fichier est absent.** Une configuration existante n'est ni
  lue, ni fusionnée, ni corrigée ;
- **le seul chemin qui écrase est un ordre explicite** — `retro launcher
  --reamorcer <profil>` — et il **sauvegarde** l'existant en
  `<nom>.bak-<horodatage>` avant de réécrire, puis ne vaut qu'une fois ;
- **écriture atomique**, comme celle de `shortcuts.vdf` : une écriture
  interrompue ne laisse pas une configuration à moitié posée — qui, elle, ne
  serait plus jamais réparée, puisqu'elle *existerait*.

C'est le lanceur qui écrit, sur la console, parce que `retro` tourne depuis un
hôte qui n'atteint ni `C:\Users` ni `%APPDATA%`. Ce qu'il pose vient du profil
de l'émulateur, et `retro status` dit, par émulateur, ce qui a été posé, quand
et où.

## Développement

```bash
pip install -e '.[dev]'
python3 -m pytest
```

Les tests ne touchent ni au réseau, ni à Steam, ni à Windows : tout tourne sous
Linux. La fixture `shortcuts-reel.vdf` vient d'une installation Steam
réelle ; seuls ses `appid` et sa forme en subsistent, tout le reste — titres,
chemins, tags — a été réécrit — voir `tests/fixtures/README.md`. Elle ne doit
pas être régénérée par ce dépôt : sa valeur tient précisément à ce qu'elle n'en
provient pas.

## Licence

MIT — le texte complet est dans [LICENSE](LICENSE).
