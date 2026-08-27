# Profils standalone et extension utilisateur (sous-projet D) — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — `superpowers:subagent-driven-development`.

**Objectif :** couvrir les consoles que RetroArch ne sert pas bien, et permettre
au propriétaire d'ajouter ses propres émulateurs — y compris ceux que le dépôt
public ne peut pas référencer.

**Spec :** `docs/superpowers/specs/2026-08-26-retro-console-design.md`

## Contraintes globales

- **Python 3.11 minimum.** Aucun test ne touche le réseau ni n'exige Windows.
- **Les chemins Windows sont des `str`.** Un chemin d'exécutable de profil peut
  contenir des antislashs *à l'intérieur* — `RetroArch-Win64\retroarch.exe` — et
  la résolution locale doit les traduire. **Ce défaut a déjà coûté une
  bibliothèque entière** : sous Linux, tous les systèmes étaient ignorés parce
  que la fixture de test utilisait un nom plat. Utilise la forme réelle partout.
- **Aucune ROM, aucun BIOS, aucun binaire dans le dépôt.**
- **Le manifeste versionné ne référence aucun émulateur au statut contesté.** Un
  test l'automatise sur tous les fichiers suivis, et la liste est gelée.
- **Un `sha256` inventé est pire qu'un émulateur absent** : il passe les tests
  ici et échoue sur la console, où personne ne peut le diagnostiquer.
- **Un test qui passe quelle que soit l'implémentation est un défaut.**
- Vérifie les mutations avec `PYTHONDONTWRITEBYTECODE=1` : une mutation de même
  longueur restaurée dans la même seconde laisse le bytecode compilé valide.

---

## Tâche 1 : les profils du propriétaire

Le manifeste accepte déjà une surcharge utilisateur — c'est l'échappatoire qui
permet au dépôt public de ne rien référencer de contesté sans brider personne.
**Les profils, eux, ne l'acceptent pas** : l'option qui les désigne prend un
seul dossier, et y pointer ailleurs perd ceux que le paquet livre.

Or déclarer un émulateur au manifeste ne suffit pas à s'en servir : il lui faut
un profil, qui dit quels systèmes il couvre, quelles extensions il accepte et
comment on le lance. **L'extension utilisateur est donc incomplète**, et cela se
voit dès qu'on essaie de l'utiliser.

**Fichiers :**
- Modifier : `retro/profiles.py`, `retro/cli.py`
- Test : `tests/test_profiles.py`, `tests/test_cli_install.py`

**Ce qu'il faut obtenir :**

- une option supplémentaire désignant un dossier de profils **du propriétaire**,
  hors dépôt, **fusionné** avec ceux du paquet plutôt que les remplaçant ;
- **la même règle de préséance que le manifeste** : à identifiant égal, le
  profil du propriétaire l'emporte. Va lire comment la fusion du manifeste est
  écrite et suis-la — deux mécanismes différents pour la même idée seraient
  une source de bugs ;
- **l'absence du dossier est normale**, jamais une erreur : il vit sur un
  partage qui n'est pas monté au moment du provisionnement ;
- le refus des identifiants de système en double doit **continuer de valoir
  entre les deux sources** — un profil utilisateur qui revendique un système
  déjà servi doit être rejeté ou l'emporter, mais jamais laisser deux profils
  se disputer silencieusement le même dossier de ROMs.

Décide de la dernière question toi-même et **écris la raison** : c'est le genre
de choix qu'un lecteur futur ne devinera pas.

---

## Tâche 2 : les profils standalone

RetroArch couvre le rétro. Ces émulateurs couvrent ce qu'il sert mal.

**Fichiers :**
- Créer : `retro/data/profiles/*.toml` (un par émulateur)
- Modifier : `retro/data/manifests/core.toml`
- Test : `tests/test_donnees.py`

**Les émulateurs à couvrir**, par ordre de valeur pour une console de salon :

| Émulateur | Systèmes |
|---|---|
| Duckstation | PlayStation |
| PCSX2 | PlayStation 2 |
| PPSSPP | PlayStation Portable |
| Flycast | Dreamcast |
| Xemu | Xbox |
| RPCS3 | PlayStation 3 |
| Cemu | Wii U |

**La règle qui prime : chaque URL et chaque empreinte doivent être RÉELLES.**
Va les chercher, télécharge l'archive dans un dossier temporaire hors du dépôt,
calcule l'empreinte toi-même, et efface. **Si tu ne peux pas obtenir une
empreinte pour un émulateur — source instable, redirection, archive
introuvable — retire-le et dis-le dans ton rapport.** Un manifeste à quatre
émulateurs vérifiés vaut mieux qu'un manifeste à sept dont trois sont faux.

**Pour chaque profil**, tu dois établir en lisant l'archive téléchargée, pas en
supposant :
- le chemin réel de l'exécutable **dans** l'archive — beaucoup ont un dossier
  racine, et c'est précisément ce qui a cassé la résolution de chemin ;
- les extensions réellement acceptées ;
- la ligne de commande qui lance un jeu **en plein écran** et se ferme
  proprement — un émulateur qui s'ouvre sur son propre menu donne l'illusion
  que tout va bien ;
- les BIOS exigés, avec leurs empreintes `md5`, et **le groupe** quand
  plusieurs fichiers sont interchangeables — le mécanisme existe déjà, il
  évite d'accuser à tort quelqu'un qui a déposé le bon fichier ;
- de quoi sortir du jeu **à la manette**, sans clavier.

**Le champ `parts`** existe pour les émulateurs livrés en plusieurs archives.
RetroArch en a besoin — son archive principale ne contient aucun core. Vérifie
si l'un des tiens est dans ce cas.

**Un test doit relier chaque profil livré à la résolution de chemin locale**,
comme celui qui existe déjà : c'est ce qui empêche une fixture simplifiée de
masquer un exécutable dans un sous-dossier.

---

## Vérification finale

- [ ] Suite complète, arbre frais, sous `-W error`
- [ ] Aucun test ne touche le réseau
- [ ] Aucun émulateur au statut contesté dans les données versionnées
- [ ] Aucun binaire, aucune archive, aucune ROM dans le dépôt
- [ ] Chaque empreinte du manifeste a été calculée sur l'archive réelle

## Ce que ce sous-projet ne fait pas

- **Les configurations de manette par jeu** — à mesurer sur la vraie machine.
- **Le branchement des métadonnées**, qui attend un identifiant de système
  numérique dans le schéma de profil.
