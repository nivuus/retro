# retro

Fait remonter une bibliothèque de jeux rétro dans Steam, avec ses jaquettes et
ses catégories, de sorte qu'elle soit indiscernable d'une bibliothèque de vrais
jeux Steam.

Vous déposez une ROM. Elle apparaît dans Steam Big Picture avec son artwork.
Vous la lancez à la manette.

## Ce que ça fait

Trois commandes, dans cet ordre :

- **`retro install`** installe les émulateurs du manifeste sous la racine
  d'émulation. Il les **télécharge depuis Internet** et les extrait — voir
  « Ce qui est téléchargé » plus bas, qui dit d'où et comment c'est vérifié.
- **`retro scan`** parcourt votre disque de ROMs et écrit l'inventaire JSON.
  Ce sont les profils (`retro/data/profiles/*.toml`) qui disent quel dossier
  appartient à quel système, quelles extensions compter, et quelle ligne de
  commande lance un jeu.
- **`retro sync`** lit cet inventaire, écrit les entrées correspondantes dans
  le `shortcuts.vdf` de Steam, et récupère les cinq assets d'artwork depuis
  SteamGridDB. La bibliothèque se range toute seule par système, par décennie
  et par genre — ces catégories sont natives dans Steam et filtrables à la
  manette.

Ce que Steam ne sait pas afficher pour un jeu non-Steam : description, date de
sortie, éditeur. Le format `shortcuts.vdf` n'a aucun champ pour ça. Toute la
richesse passe donc par l'artwork et les tags.

## Ce que ça ne fait pas

- **Ça ne touche jamais aux jeux que vous avez ajoutés vous-même.** Une entrée
  n'appartient à `retro` que si elle porte le tag `Rétro` **et** que son
  exécutable vit sous la racine d'émulation. Les deux conditions, toujours.
- **Ça ne distribue aucune ROM, aucun BIOS, aucun émulateur.** Vous fournissez
  vos ROMs et vos BIOS. `retro install` ne redistribue pas les émulateurs non
  plus : il télécharge chacun depuis le site de son propre projet, à l'URL et
  sous l'empreinte que porte le manifeste.
- **Ça n'arrête pas Steam.** `retro sync` refuse de s'exécuter tant que Steam
  tourne — il réécrirait le fichier à sa fermeture et le travail serait perdu,
  sans le moindre message. Fermez Steam d'abord.

## Utilisation

```bash
# 1. installer les émulateurs (télécharge depuis Internet)
retro install --emulation-root 'D:\Emulation' \
              --user-manifest 'G:\retro\emulators.toml'

# 2. inventorier les ROMs
retro scan --roms /mnt/roms \
           --roms-windows 'G:\ROMs' \
           --emulation-root 'D:\Emulation' \
           --user-manifest 'G:\retro\emulators.toml' \
           --output inventaire.json

# 3. faire remonter le tout dans Steam
retro sync --steam-root 'D:\Steam' \
           --emulation-root 'D:\Emulation' \
           --inventory inventaire.json \
           --steamgriddb-key VOTRE_CLE
```

`--roms` est le chemin par lequel la machine qui scanne atteint les ROMs ;
`--roms-windows` celui par lequel la console les verra. Les deux diffèrent dès
que le scan ne tourne pas sur la console elle-même.

`--manifest` et `--user-manifest` sont passés à `install` **et** à `scan`, avec
les mêmes valeurs : c'est le manifeste qui décide où chaque émulateur
s'installe, donc lui seul sait où l'inventaire doit pointer. Les donner à l'un
et pas à l'autre produit des raccourcis qui ne lancent rien.

`retro scan` produit ce JSON, que `retro sync` relit tel quel :

```json
[{
  "title": "Chrono Trigger",
  "rom_path": "G:\\ROMs\\snes\\Chrono Trigger (USA).sfc",
  "system_name": "Super Nintendo",
  "emulator_exe": "D:\\Emulation\\RetroArch\\RetroArch-Win64\\retroarch.exe",
  "launch_template": "-L \"RetroArch-Win64\\cores\\snes9x_libretro.dll\" -f \"{rom}\"",
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
  distribution. Aujourd'hui : RetroArch (buildbot.libretro.com) et Dolphin
  (dl.dolphin-emu.org).
- **Votre manifeste**, hors dépôt, passé par `--user-manifest`. Même schéma,
  sans cette limite : c'est là que vous déclarez vos propres émulateurs. Son
  absence est normale et n'est pas une erreur.

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
qu'un émulateur absent, parce qu'il paraît installé et ne lance rien. RetroArch
est dans ce cas : son archive principale ne contient aucun core.

L'installation est idempotente. Un témoin `.retro-version` évite de
retélécharger des gigaoctets déjà présents à chaque reconstruction de la
machine.

### Prérequis : un binaire 7-Zip

**En pratique, RetroArch ne s'installe pas sans un binaire 7-Zip sur le
`PATH`.** `py7zr`, la bibliothèque Python, ne sait pas lire le filtre **BCJ2**
— elle le marque « Unsupported » dans son propre code — et c'est précisément
celui qu'emploient les archives du buildbot libretro.

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

MIT.
