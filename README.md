# retro

Fait remonter une bibliothèque de jeux rétro dans Steam, avec ses jaquettes et
ses catégories, de sorte qu'elle soit indiscernable d'une bibliothèque de vrais
jeux Steam.

Vous déposez une ROM. Elle apparaît dans Steam Big Picture avec son artwork.
Vous la lancez à la manette.

## Ce que ça fait

`retro sync` lit un inventaire de ROMs, écrit les entrées correspondantes dans
le `shortcuts.vdf` de Steam, et récupère les cinq assets d'artwork depuis
SteamGridDB. La bibliothèque se range toute seule par système, par décennie et
par genre — ces catégories sont natives dans Steam et filtrables à la manette.

Ce que Steam ne sait pas afficher pour un jeu non-Steam : description, date de
sortie, éditeur. Le format `shortcuts.vdf` n'a aucun champ pour ça. Toute la
richesse passe donc par l'artwork et les tags.

## Ce que ça ne fait pas

- **Ça ne touche jamais aux jeux que vous avez ajoutés vous-même.** Une entrée
  n'appartient à `retro` que si elle porte le tag `Rétro` **et** que son
  exécutable vit sous la racine d'émulation. Les deux conditions, toujours.
- **Ça ne distribue aucune ROM, aucun BIOS, aucun émulateur.** Vous fournissez
  vos fichiers.
- **Ça n'arrête pas Steam.** `retro sync` refuse de s'exécuter tant que Steam
  tourne — il réécrirait le fichier à sa fermeture et le travail serait perdu,
  sans le moindre message. Fermez Steam d'abord.

## Utilisation

```bash
retro sync --steam-root 'D:\Steam' \
           --emulation-root 'D:\Emulation' \
           --inventory inventaire.json \
           --steamgriddb-key VOTRE_CLE
```

L'inventaire est un JSON, produit par le scanner de votre choix :

```json
[{
  "title": "Chrono Trigger",
  "rom_path": "G:\\ROMs\\snes\\ct.sfc",
  "system_name": "Super Nintendo",
  "emulator_exe": "D:\\Emulation\\RetroArch\\retroarch.exe",
  "launch_template": "-L \"cores\\snes9x_libretro.dll\" -f \"{rom}\"",
  "start_dir": "D:\\Emulation\\RetroArch",
  "extra_tags": ["1995", "RPG"]
}]
```

La clé SteamGridDB est facultative. Sans elle, les jeux remontent normalement,
simplement sans jaquettes.

## Sûreté

Le fichier que ce paquet écrit est celui dont la corruption casse la
bibliothèque Steam de quelqu'un. Trois protections :

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
