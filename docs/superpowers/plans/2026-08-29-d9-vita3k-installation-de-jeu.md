# D9 — Vita3K : faire entrer un jeu — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — `superpowers:subagent-driven-development`.

**Objectif :** qu'un dump PS Vita déposé sur le partage s'installe, se lance, et
ne rejoue ni son installation ni une modale à chaque partie.

**Dette :** `docs/dettes.md`, D9. Ce plan ne modifie PAS ce fichier : la dette
se met à jour par qui la clôt, une fois les mesures faites.

**Specs :** `docs/superpowers/specs/2026-08-26-retro-console-design.md` et
`docs/superpowers/specs/2026-08-28-amorcage-emulateurs-design.md`

**Dépend de D7**, `docs/superpowers/plans/2026-08-29-d7-jeton-de-chemin-et-fusion.md`,
pour **deux** pièces, et ce plan ne spécifie ni l'une ni l'autre à sa place :

1. **le jeton de chemin dans `bootstrap.target`.** La dette D9 l'appelle
   `{emulation_root}` ; D7 a mesuré que ce nom-là est le mauvais — `install_dir`
   est surchargeable par le manifeste du propriétaire, et le réécrire dans le
   profil ferait rater la cible **en silence** — et a retenu **`{install_dir}`**,
   substitué en Python, `{emulation_root}` étant explicitement refusé avec son
   message. Ce plan emploie donc `{install_dir}` ;
2. **plusieurs cibles par profil** (tâche 3 de D7). Vita3K en a **deux**, dans
   deux formats : `gui-configs\CurrentSettings.ini` pour la modale des
   privilèges, que D7 pose, et `config.yml` pour celle des polices, que ce plan
   pose. `Profile.bootstrap` n'en porte qu'une aujourd'hui.

Les tâches 4 et 5 ne peuvent pas être terminées avant ces deux pièces.

---

## Ce que le code source de Vita3K dit déjà, et qui déplace la question

Tout ce qui suit est **lu dans la source**, `master` au 2026-08-29, clonée hors
du dépôt puis effacée. Aucune ligne ne vient d'une documentation ni des chaînes
d'un binaire. Les chemins sont ceux du dépôt Vita3K.

| Fait | Où | Ce que ça change |
|---|---|---|
| Le refus « Vitamin dump » se déclenche sur la présence de `sce_module/steroid.suprx` **dans l'archive**, et n'existe QUE dans `get_archive_contents_path` | `vita3k/interface.cpp` | le refus par archive est bien local à l'archive ; le chemin dossier ne le rejouera jamais |
| `install_content` supprime la destination — `if (exists(dst_path)) fs::remove_all(dst_path);` — **avant** de copier | `vita3k/interface.cpp` | un échec de copie détruit l'installation précédente. Le « dossier vide » de la dette est cohérent avec ça |
| `copy_directory_contents` est un `try { … } catch (const std::exception &) { return false; }` — **l'exception est jetée sans être lue** | `vita3k/util/src/fs_utils.cpp` | 🔴 **le message `Failed to copy directory to:` ne peut PAS nommer sa cause, par construction.** Relancer mille fois n'apprendra rien. Toute enquête doit venir de l'extérieur du binaire |
| Le chemin dossier n'a **aucune** garde de réinstallation, contrairement au chemin archive (`reinstall_callback`) | `vita3k/interface.cpp` | passer un dossier en `content-path` **rase et recopie le jeu à chaque appel**. Le profil le fait à chaque lancement : 3,5 Go rasés puis recopiés par partie |
| `is_nonpdrm` → `decrypt_install_nonpdrm` **déchiffre le PFS** (`execute(zRIF, src, dst_dec, …)`) puis remplace le dossier | `vita3k/packages/src/pkg.cpp` | 🔴 un dump NoNpDrm est **chiffré**. Une copie manuelle en donne une copie chiffrée, que rien ne déchiffrera. Le contournement « robocopy » ne vaut que pour un dump SANS `sce_sys/package/` |
| `copy_license` lit le `content_id` du fichier de licence (offset `0x10`, `0x30` octets), en tire `title_id = content_id.substr(7, 9)`, et **copie le fichier tel quel** vers `ux0/license/<title_id>/<content_id>.rif` | `vita3k/packages/src/license.cpp`, `packages/include/packages/license.h` | la « conversion » n'est **pas** une conversion : c'est une copie renommée. Et le nom ne se devine pas, il se lit dans les octets |
| `main.cpp` : `is_rif = (extension == ".rif") \|\| (filename == "work.bin")` → `copy_license(emuenv, *cfg.content_path)` | `vita3k/main.cpp` | 🔴 **Vita3K sait poser une licence depuis la ligne de commande.** `Vita3K.exe "<…>\sce_sys\package\work.bin"` suffit. Rien à écrire dans `retro` pour le faire |
| `get_license` : licence absente → `LOG_WARN("License file is corrupted or missing…")` puis `sku_flag = 1` si `sce_sys/retail/livearea` existe, `0` sinon | `vita3k/packages/src/license.cpp` | la licence manquante ne bloque rien : elle fausse **un seul champ**. C'est un défaut réel, pas un mur |
| La case « Don't show this warning again » de la modale des polices fait `emuenv.cfg.warn_missing_firmware = false;` puis `config::serialize_config(…)` | `vita3k/gui-qt/src/main_window.cpp` | ⚠ elle n'écrit **pas** dans `gui-configs\CurrentSettings.ini` — c'est l'autre modale, celle de D7 |
| `code(bool, "warn-missing-firmware", true, warn_missing_firmware)` | `vita3k/config/include/config/config.h` | la clé cible est **`warn-missing-firmware`**, défaut `true`, dans **`config.yml`** — un **YAML**, pas un INI. Elle n'est exposée par **aucune** option de ligne de commande (`config.cpp`, `init_config`) |
| `firmware.font_package = has_installed_firmware_content(vita_fs_path / "sa0")`, `main_firmware` = `vs0`, et `has_installed_firmware_content` = « existe, est un dossier, non vide » | `vita3k/app/src/app.cpp` | le paquet de polices s'installe dans `sa0\`. `install_pup` l'extrait de `sa0.img` **du même PUP**, s'il y est : le geste existe déjà, seul le fichier manque |
| `cfg.overwrite_config` vaut vrai par défaut (`add_flag("!--keep-config,!-w", …)`) et `init_config` finit par `serialize_config` | `vita3k/config/src/config.cpp` | ⚠ **Vita3K régénère son `config.yml` à chaque lancement** et en efface tous les commentaires. `--keep-config` / `-w` l'en empêche |
| `--installed-path,-r` est validé par `CLI::IsMember(get_file_set(vita_fs_path / "ux0/app"))`, qui rend les **noms de dossiers** | `vita3k/config/src/config.cpp` | la forme de `-r` est tranchée : c'est le **TITLE ID**, pas un chemin. Le profil dit encore « reste à mesurer » ; ce n'est plus vrai |
| `pref-path` (`config.yml`) remplace la racine du système de fichiers Vita ; si elle est non vide et **n'existe pas**, Vita3K refuse de démarrer (`Cannot find Vita FS path`) | `vita3k/config/src/config.cpp` | le `ux0` peut sortir de `%APPDATA%`. Le dossier doit exister AVANT |

**Ce qui reste supposé, et que ce plan ne présente jamais comme acquis :** la
cause de l'échec de `install_content` ; le fait que le dossier laissé derrière
soit réellement vide plutôt que partiel ; le volume sur lequel les 79,9 Go
libres ont été mesurés.

---

## Contraintes globales

- **Python 3.11 minimum.** Aucun test ne touche le réseau ni n'exige Windows.
- **Aucune ROM, aucun dump, aucun binaire, aucune licence dans le dépôt.** Les
  fixtures de licence de la tâche 5 sont **fabriquées octet par octet en
  Python**, jamais copiées d'un dump.
- **Une valeur fausse se comporte exactement comme l'absence de valeur.** Toute
  clé posée vient du code source de Vita3K cité ci-dessus, ou d'un relevé sur
  la machine. Jamais d'une documentation, jamais d'un libellé d'interface.
- **La console Windows n'est pas accessible depuis la session qui exécute ce
  plan.** Chaque mesure est une étape explicite, avec sa procédure, et son
  résultat s'écrit avant que la tâche suivante démarre.
- **Les chemins Windows sont des `str`** (`install.local_path` les traduit).
- **Un test qui passe quelle que soit l'implémentation est un défaut.**
- Vérifie les mutations avec `PYTHONDONTWRITEBYTECODE=1`.

---

## Tâche 1 : trouver pourquoi `install_content` échoue

**Rien d'autre ne commence avant celle-ci.** Un contournement posé sur une cause
inconnue se rejouera : le même dump, un autre jeu, une autre machine.

Et il faut savoir ceci avant de commencer : **le binaire ne dira rien de plus.**
`copy_directory_contents` avale son exception sans la lire
(`vita3k/util/src/fs_utils.cpp`), donc le journal a déjà tout donné. La cause se
prend de l'extérieur, ou pas du tout.

**Fichiers :** aucun modifié. La sortie est un relevé écrit, repris en tâche 2.

### Étape de mesure — quatre relevés, dans cet ordre

Tout se fait par WinRM depuis l'hôte, sauf ce qui demande la session
interactive (aucun de ces quatre-là ne la demande).

1. **Le journal COMPLET du lancement fautif**, pas la seule ligne d'erreur.
   `Get-Content <racine Vita3K des données>\logs\*.log` — ou le journal à côté
   de l'exécutable si `--archive-log` a été employé. Relever, dans l'ordre :
   la ligne `Installing contents from CLI: <chemin>` (elle donne **ce qui a été
   passé**, séparateurs compris) ; la présence ou l'absence de
   `No found any content compatible on this path` ; **le nombre** de lignes
   `Failed to copy directory to:` — une par contenu détecté par
   `get_contents_path`. Plus d'une ligne veut dire que le dump porte plusieurs
   `param.sfo` (patch, DLC), ce qui est une histoire différente.
2. **Ce qui reste RÉELLEMENT dans la destination.**
   `Get-ChildItem -Recurse <ux0>\app\<TITLEID> | Measure-Object -Sum Length` →
   nombre d'objets et octets. « Vide » est aujourd'hui une observation à l'œil ;
   il faut le chiffre. **Zéro fichier** et **quelques fichiers** ne désignent pas
   la même cause.
3. **L'espace libre du volume de DESTINATION**, qui est celui de `%APPDATA%`,
   donc `C:` — et non celui du partage. `Get-PSDrive C`. Les 79,9 Go de la dette
   ne disent rien tant qu'on ne sait pas sur quel volume ils ont été lus.
4. **La longueur du plus long chemin produit.** Sur la source :
   `Get-ChildItem -Recurse -File <source> | ForEach-Object { $_.FullName.Length - <longueur du préfixe source> } | Measure-Object -Maximum`.
   Ajouter la longueur du préfixe de destination
   (`C:\Users\<compte>\AppData\Roaming\Vita3K\Vita3K\ux0\app\<TITLEID>\`).
   **Au-delà de 259, la limite `MAX_PATH` est atteinte** — `boost::filesystem`,
   que Vita3K emploie (`vita3k/util/include/util/fs.h`), n'ajoute pas le préfixe
   `\\?\` ; `robocopy`, lui, gère les chemins longs, ce qui expliquerait
   exactement qu'il ait réussi là où l'émulateur échoue.

### Étape de mesure — deux essais croisés

Ils découpent l'espace des causes en quatre pour dix minutes de machine.

- **Essai A — source locale et courte.** Copier la source sur `C:\s\<TITLEID>`
  avec `robocopy /E`, puis
  `Vita3K.exe --keep-config "C:\s\<TITLEID>"`. Réussit ⇒ ce qui est en cause est
  la source (lettre mappée, partage, longueur côté source), pas la destination.
- **Essai B — destination courte.** Créer `D:\v` (le dossier **doit exister
  avant**, sinon Vita3K refuse de démarrer avec `Cannot find Vita FS path`),
  y déplacer le contenu actuel de `%APPDATA%\Vita3K\Vita3K\` (`os0`, `vs0`,
  `ux0`, la configuration des utilisateurs), poser `pref-path: D:\v` dans
  `<installation>\config.yml`, puis rejouer l'installation d'origine. Réussit
  ⇒ c'est la longueur ou le lieu de la destination.

### Ce qu'il faut obtenir

Un tableau, écrit dans le rapport de tâche, qui relie observation et cause :

| Observation | Cause désignée | Remède, en tâche 2 |
|---|---|---|
| longueur totale > 259, et essai B réussit | `MAX_PATH` sur la destination | remède 1 |
| C: presque plein | volume de destination saturé | remède 1 (il déplace aussi les données) |
| essai A réussit, essai B échoue | la source (lettre mappée, partage) | remède 2 |
| les deux échouent, longueurs courtes, disque libre | écriture refusée à `%APPDATA%` par un filtre | remède 3 |
| plusieurs lignes `Failed to copy…` | le dump porte plusieurs contenus | remède 4 |

Si aucune ligne ne s'applique, **la tâche 2 ne s'exécute pas** : le relevé qui
tranche est alors une capture Process Monitor (Sysinternals) filtrée sur
`Vita3K.exe`, opérations `CreateFile`/`WriteFile`, dernier résultat non-`SUCCESS`
avant l'échec. C'est un outil ponctuel, téléchargé et effacé, **jamais épinglé
au manifeste** : il ne fait pas partie de la console.

---

## Tâche 2 : appliquer le remède que la mesure désigne — un seul

**Fichiers :**
- Modifier : `retro/data/profiles/vita3k.toml` (le constat, en commentaire)
- Test : `tests/test_donnees.py`

**Un seul remède s'exécute**, celui que la tâche 1 désigne. Les autres sont
écrits ici pour que le choix se fasse sur des remèdes lisibles, pas sur une
intuition.

**Remède 1 — sortir le système de fichiers Vita de `%APPDATA%`.** Poser
`pref-path` sur un dossier court, sous la racine d'émulation, créé d'avance ;
déplacer `os0`, `vs0`, `ux0` et les utilisateurs avant de poser la clé.
Deux gains au-delà de la panne : les 3,5 Go par jeu quittent le profil
itinérant Windows, et l'état de la Vita — `vs0` pour le firmware, `sa0` pour les
polices, `ux0/license` — **devient visible depuis l'hôte**, qui atteint déjà la
racine d'émulation. La clé se pose ensuite par la tâche 4, jamais à la main.

**Remède 2 — installer depuis une copie locale.** Le dump est copié par
`robocopy /E` sur un dossier local court, l'installation est faite depuis là, la
copie est effacée. C'est un geste, pas un réglage : il vit dans la tâche 6.

**Remède 3 — l'écriture est refusée.** Relever l'auteur du refus
(`Get-WinEvent -LogName "Microsoft-Windows-Windows Defender/Operational"`, ou le
résultat Process Monitor), puis retomber sur le remède 1, qui change de dossier
de destination et sort du périmètre du filtre.

**Remède 4 — plusieurs contenus.** `get_contents_path` remonte un contenu par
`param.sfo` trouvé récursivement. Un patch (`app_category` contenant `gp`)
exige que l'application soit installée d'abord — `set_content_path` rend
`Install app before patch`. Installer les contenus **un par un**, l'application
avant son patch, chacun avec son propre `content-path`.

**Ce qu'il faut obtenir :**

- le constat écrit **dans le profil**, en commentaire, avec sa date, ce qui a
  été mesuré et ce qui reste supposé — sur le modèle des deux racines de D5 ;
- un test dans `tests/test_donnees.py` qui exige que `vita3k.toml` dise ce qu'il
  sait de l'installation d'un jeu : la garde grossière du dépôt, celle qui
  attrape l'oubli, pas la formulation. Modèle exact :
  `test_chaque_profil_livre_dit_ou_en_est_son_amorcage`.

---

## Tâche 3 : un second dialecte de fusion — le YAML plat de `config.yml`

**D7 conclut que « la fusion n'a pas besoin d'apprendre le YAML », et il a
raison pour son cas — pas pour celui-ci.** Son `Default.yml` de RPCS3 est posé
par le régime `si-absent`, qui copie des octets et ne lit jamais le contenu.
Ici, le fichier visé est créé par Vita3K lui-même au premier lancement
(`init_config` → `serialize_config`, `vita3k/config/src/config.cpp`) : `si-absent`
ne se déclencherait donc **jamais**, et la clé ne serait jamais posée. Le seul
régime qui s'applique est `enforced`, qui lit et fusionne. Les deux plans ne se
contredisent pas : D7 n'en a pas besoin, D9 si.

La modale des polices se ferme par `warn-missing-firmware`, qui vit dans
`config.yml`. C'est un **YAML**. La fusion du projet ne parle qu'INI, et son
défaut serait parfaitement muet : `CleDe` (`retro/data/launcher/retro-launch.cs`)
exige un `=` et rend `null` sans lui, donc une ligne `warn-missing-firmware: false`
apportée à un YAML **ne poserait rien, sans un mot** — zéro clé fusionnée,
aucun message, la modale toujours là.

Deux pièges de forme s'y ajoutent, tous deux mesurés :

1. `MARQUE_FUSION` commence par `;` — un commentaire INI. En YAML, `;` n'est pas
   un commentaire : la marque **corromprait le fichier**. En YAML, c'est `#`.
2. Vita3K **régénère** son `config.yml` à chaque lancement (`serialize_config`,
   appelée par `init_config` puisque `overwrite_config` vaut vrai par défaut),
   et yaml-cpp n'émet aucun commentaire : la marque disparaîtrait à chaque
   partie, la fusion la reposerait, et **chaque lancement produirait une
   sauvegarde de plus** — l'inverse exact de ce que l'idempotence garantit.
   **Décision : en YAML, la fusion ne pose aucune marque de ligne**, et
   l'idempotence se juge sur la seule valeur. La raison s'écrit en commentaire,
   à côté de `MARQUE_FUSION`.

**Fichiers :**
- Modifier : `retro/profiles.py`, `retro/data/launcher/retro-launch.cs`
- Test : `tests/test_profiles.py`, `tests/test_donnees.py`

- [ ] **Étape 1 — écrire le test qui échoue**

```python
def test_les_cles_d_un_fragment_yaml_sont_lues_sans_section():
    fragment = (
        "# posé par retro\n"
        "warn-missing-firmware: false\n"
        "pref-path: D:\\Emulation\\Vita3K\\data\n"
        "lle-modules:\n"
        "  - libscemp4\n"
    )
    assert profiles.cles_yaml(fragment) == [
        ("", "warn-missing-firmware"), ("", "pref-path"), ("", "lle-modules")]


def test_une_ligne_de_sequence_yaml_n_est_pas_une_cle():
    # « - libscemp4 » appartient à la clé du dessus. La compter séparément
    # ferait croire à un réglage que rien ne lit.
    assert profiles.cles_yaml("lle-modules:\n  - libscemp4\n") == [
        ("", "lle-modules")]


def test_le_dialecte_suit_l_extension_de_la_cible():
    assert profiles.cles_de("C:\\x\\a.ini", "[S]\nk = 1\n") == [("S", "k")]
    assert profiles.cles_de("C:\\x\\config.yml", "k: 1\n") == [("", "k")]
```

- [ ] **Étape 2 — lancer les tests, vérifier qu'ils échouent** sur
  `AttributeError: module 'retro.profiles' has no attribute 'cles_yaml'`.

- [ ] **Étape 3 — implémenter dans `retro/profiles.py`**

```python
# Les extensions dont le contenu est un YAML plat. Vita3K est le seul cas
# livré : son config.yml est une map de scalaires au premier niveau, plus
# quelques séquences (CONFIG_VECTOR dans config/include/config/config.h).
_YAML = (".yml", ".yaml")


def cles_yaml(fragment: str) -> list[tuple[str, str]]:
    """Les clés d'un YAML PLAT, sous la section vide.

    Seul le premier niveau compte : une ligne indentée appartient à la clé du
    dessus, et une ligne « - x » est un élément de séquence. Les compter pour
    des réglages ferait dire au rapport qu'une clé est imposée alors qu'aucun
    lecteur YAML ne la verrait — la panne muette que ce dépôt refuse.
    """
    cles = []
    for ligne in fragment.splitlines():
        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        if ligne[:1].isspace() or ligne.lstrip().startswith("-"):
            continue
        if ":" in ligne:
            cles.append(("", ligne.split(":", 1)[0].strip()))
    return cles


def cles_de(target: str, fragment: str) -> list[tuple[str, str]]:
    """Les couples (section, clé) d'un fragment, dans le dialecte de sa CIBLE.

    Le dialecte se déduit de l'extension du fichier visé, pas d'un champ
    déclaré : un champ pourrait contredire ce que le fragment contient, une
    extension non.
    """
    suffixe = pathlib.PureWindowsPath(target).suffix.lower()
    return cles_yaml(fragment) if suffixe in _YAML else cles_ini(fragment)
```

- [ ] **Étape 4 — brancher `_valider_regimes` sur `cles_de`.** Elle prend
  aujourd'hui `content` et `enforced` seuls ; elle prend désormais `target` en
  premier argument et compare avec `cles_de(target, …)`. Sans cela, deux clés
  YAML déclarées dans les deux régimes passeraient sans être vues : `cles_ini`
  ne trouve aucun `=` et rend une liste vide, donc l'intersection est toujours
  vide et la garde ne garde plus rien.

- [ ] **Étape 5 — la marque d'en-tête.** `MARQUE_BOOTSTRAP` est cherchée dans
  `content` en sous-chaîne (`profiles._lire_bootstrap`) : un `#` YAML la porte
  aussi bien qu'un `;` INI, rien à changer. Ajouter un test qui le fige, pour
  qu'un durcissement futur de la garde ne casse pas le seul profil YAML livré.

- [ ] **Étape 6 — le lanceur C#.** `Fusionner` reçoit le dialecte, déduit de
  l'extension de `bootstrap_target` (le plan la porte déjà). En YAML :
  `SectionDe` rend toujours `null` ; `CleDe` coupe sur `:` au lieu de `=`, refuse
  les lignes indentées et les `-` ; la marque n'est pas posée. Le reste de
  l'algorithme — remplacer à sa place, compléter à la fin, ne rien réécrire si
  le résultat est identique — est inchangé.

- [ ] **Étape 7 — lancer la suite, tout doit passer. Commit.**

```bash
git add retro/profiles.py retro/data/launcher/retro-launch.cs tests/
git commit -m "feat(profils): fusionner aussi un YAML plat, pour le config.yml de Vita3K"
```

**Vérification manuelle, sur la machine** — le dépôt n'a pas de tests C# :
recompiler (`compiler.cmd`), lancer un jeu, relire `config.yml` et
`_launcher\journal.txt`. Le journal doit dire `1 cle(s) imposee(s)` au premier
passage, puis `deja conforme` aux suivants. **S'il dit `deja conforme` dès le
premier passage, la fusion n'a rien vu** : c'est exactement le défaut que cette
tâche ferme.

---

## Tâche 4 : le bloc `[bootstrap]` de Vita3K

**Bloquée par les deux pièces de D7 : le jeton `{install_dir}`, et plusieurs
cibles par profil.** La configuration de Vita3K est `<installation>\config.yml`
(`--config-location`, « Default loaded: `<Vita3K>/config.yml` », relevé sur le
binaire au 2026-08-29), et `_lire_bootstrap` exige aujourd'hui un `target`
absolu ou commençant par une variable d'environnement : aucune de ces deux
formes ne désigne un dossier sous la racine d'émulation, qui est un paramètre de
`retro scan`. Et Vita3K a **deux** fichiers à recevoir, quand `Profile.bootstrap`
n'en porte qu'un.

**Fichiers :**
- Modifier : `retro/data/profiles/vita3k.toml`
- Test : `tests/test_donnees.py`

**La cible :** `{install_dir}\config.yml`. Pas `{emulation_root}\Vita3K\…` :
`Vita3K` est l'`install_dir` du manifeste noyau, que le manifeste du
propriétaire peut surcharger, et le réécrire ici ferait rater la cible sans un
mot le jour où il le fera — c'est la mesure de D7.

**La clé imposée, et d'où elle vient :**

```toml
enforced = '''
# Imposé par « retro » et reposé à chaque lancement.
warn-missing-firmware: false
'''
```

`warn-missing-firmware` est le nom exact de la clé YAML, relevé dans
`vita3k/config/include/config/config.h` :
`code(bool, "warn-missing-firmware", true, warn_missing_firmware)`. Sa valeur
par défaut est `true`. C'est celle-là, et pas une autre, que la case
« Don't show this warning again » écrit — `vita3k/gui-qt/src/main_window.cpp`,
`confirm_missing_firmware_warning`, qui fait
`emuenv.cfg.warn_missing_firmware = false;` puis `config::serialize_config(…)`.

⚠ **Ce n'est pas la clé de D7.** La modale des privilèges est un `QSettings`
INI, `[MainWindow] warnAdminPrivileges`, dans `gui-configs\CurrentSettings.ini`.
Les deux modales de Vita3K vivent dans **deux fichiers et deux formats
différents**, et les confondre poserait une clé qu'aucun lecteur ne lit. D7 pose
la première ; celle-ci est la seconde, et elle a besoin du même jeton.

**Ce qu'il faut obtenir :**

- `content` : un `config.yml` minimal portant `MARQUE_BOOTSTRAP` en commentaire
  `#`, et distinguant les **trois** catégories que `_valider_regimes` exige dès
  qu'un profil impose quelque chose — ce que la console impose et repose, ce
  qu'elle a posé une fois, et le reste, qui appartient au propriétaire ;
- `--keep-config` (`-w`) **ajouté à la ligne de lancement**, et sa raison écrite :
  sans lui, `init_config` finit par `serialize_config` et Vita3K régénère son
  `config.yml` à chaque partie, effaçant l'en-tête que ce bloc vient de poser
  (`vita3k/config/src/config.cpp`, `overwrite_config` vrai par défaut via
  `add_flag("!--keep-config,!-w", …)`) ;
- si le remède 1 de la tâche 2 a été retenu, `pref-path` entre dans le même
  `enforced`, avec sa valeur sous la racine d'émulation. **Le dossier doit
  exister avant le premier lancement** : `pref-path` non vide et inexistant fait
  refuser le démarrage (`Cannot find Vita FS path`, `InvalidApplicationPath`) ;
- retirer du profil la mention « `--installed-path` : sa forme exacte reste à
  mesurer ». Elle est mesurée : `CLI::IsMember(get_file_set(vita_fs_path / "ux0/app"))`
  compare la valeur aux **noms de dossiers** de `ux0/app`, donc c'est le TITLE ID ;
- le profil **cesse d'être exempté** de `test_chaque_profil_livre_dit_ou_en_est_son_amorcage`
  — il porte désormais un bloc — et un test nouveau exige que la clé imposée soit
  bien `warn-missing-firmware`, en nommant sa source dans le message d'échec.

**Étape de mesure, après pose :** lancer un jeu, relire le `config.yml` de la
machine. La ligne doit y être **et** la modale ne doit plus sortir. La vérifier
par l'effet, comme la clé de privilèges l'a été : la modale absente à l'écran,
et le lancement qui va jusqu'au jeu.

---

## Tâche 5 : la licence — ce que `retro` en sait, et ce qu'il n'a pas à faire

La dette demande où vivrait la conversion. **La réponse est : nulle part dans
`retro`**, et c'est le code source qui la donne.

- Il n'y a **pas de conversion** : `copy_license` (`vita3k/packages/src/license.cpp`)
  **copie le fichier tel quel** vers `ux0/license/<title_id>/<content_id>.rif`.
  Seul le nom change.
- Vita3K le fait **de lui-même** à l'installation (`is_nonpdrm` →
  `decrypt_install_nonpdrm` → `copy_license`), et **sur ordre** depuis la ligne
  de commande : `main.cpp` traite tout `content-path` nommé `work.bin` ou en
  `.rif` comme une licence à poser. `Vita3K.exe "<…>\sce_sys\package\work.bin"`
  est donc le geste, et il est natif.
- **Ni `retro install` ni `retro scan` ne peuvent le faire** : le premier
  installe des émulateurs, pas des jeux ; le second tourne sur l'hôte, qui
  n'atteint pas le système de fichiers Vita.

Ce que `retro` peut faire, en revanche, c'est **dire** si la licence est là —
ce qu'aucune commande ne sait aujourd'hui, et ce que le message de Vita3K
n'annonce qu'en jeu, dans un journal que personne ne lit depuis un canapé.

**La forme du nom est MESURÉE, pas observée sur un cas.** Le `EP9000-` du cas
de la dette est le préfixe régional de ce jeu-là, rien de plus. La règle est :

- `content_id` : `SceNpDrmLicense.content_id`, **offset `0x10`, `0x30` octets**,
  chaîne C (`packages/include/packages/license.h`) ;
- `title_id` = `content_id.substr(7, 9)` — neuf caractères à partir du septième
  (`license.cpp`) ;
- destination : `ux0/license/<title_id>/<content_id>.rif` ;
- un fichier de licence fait `0x200` octets — la structure s'arrête à
  `rsa_signature[0x100]` posé en `0x100`.

**Fichiers :**
- Créer : `retro/licence.py`
- Test : `tests/test_licence.py`

- [ ] **Étape 1 — écrire les tests qui échouent**

```python
import pytest
from retro import licence


def _work_bin(content_id: str) -> bytes:
    """Un fichier de licence FABRIQUÉ, jamais copié d'un dump.

    La structure vient de packages/include/packages/license.h : content_id
    est un char[0x30] à l'offset 0x10, et la structure fait 0x200 octets.
    """
    octets = bytearray(0x200)
    octets[0x10:0x10 + len(content_id)] = content_id.encode("ascii")
    return bytes(octets)


def test_le_content_id_se_lit_a_l_offset_attendu():
    brut = _work_bin("EP9000-PCSF00012_00-0000000000000000")
    assert licence.content_id(brut) == "EP9000-PCSF00012_00-0000000000000000"


def test_le_title_id_est_le_septieme_caractere_sur_neuf():
    # substr(7, 9) dans copy_license : ce n'est PAS « ce qui suit le tiret »,
    # et les deux coïncident seulement pour un préfixe de six caractères.
    assert licence.title_id("EP9000-PCSF00012_00-0000000000000000") == "PCSF00012"
    assert licence.title_id("UP0001-PCSA00001_00-0000000000000000") == "PCSA00001"


def test_le_chemin_de_licence_est_celui_que_vita3k_cherche():
    brut = _work_bin("EP9000-PCSF00012_00-0000000000000000")
    assert licence.chemin_relatif(brut) == (
        "ux0\\license\\PCSF00012\\EP9000-PCSF00012_00-0000000000000000.rif")


def test_un_fichier_trop_court_est_refuse_en_le_nommant():
    with pytest.raises(licence.LicenceError) as exc:
        licence.content_id(b"\x00" * 0x40)
    assert "0x200" in str(exc.value)


def test_un_content_id_vide_est_refuse():
    # Un work.bin dont les octets 0x10..0x40 sont nuls donnerait un title_id
    # vide, donc un dossier « ux0\license\\ » — un chemin d'apparence normale
    # que Vita3K ne lirait jamais.
    with pytest.raises(licence.LicenceError):
        licence.content_id(bytes(0x200))
```

- [ ] **Étape 2 — lancer, vérifier l'échec** (`ModuleNotFoundError: retro.licence`).

- [ ] **Étape 3 — implémenter `retro/licence.py`**, minimal : `LicenceError`,
  `content_id(octets)`, `title_id(cid)`, `chemin_relatif(octets)`. Les trois
  constantes — `0x10`, `0x30`, `0x200`, `(7, 9)` — portent chacune en commentaire
  le fichier source Vita3K d'où elles viennent. Un commentaire qui ne dit pas
  d'où vient une constante rend cette constante indistinguable d'une invention.

- [ ] **Étape 4 — lancer les tests, ils passent.**

- [ ] **Étape 5 — brancher `retro status`.** Pour chaque jeu Vita inventorié
  dont le dossier porte `sce_sys\package\work.bin`, dire si le `.rif` attendu
  existe sous la racine du système de fichiers Vita. **Cela n'est possible que
  si le remède 1 de la tâche 2 a été appliqué** : tant que le `ux0` vit dans
  `%APPDATA%`, l'hôte ne le voit pas, et le rapport doit alors dire cela — « la
  console range son système de fichiers Vita dans le profil Windows, que cet
  hôte n'atteint pas » — plutôt que de conclure à une licence absente. Un
  rapport qui annonce un manque qu'il ne peut pas constater est le pire des
  états ; c'est le raisonnement déjà écrit pour le témoin d'amorçage.

- [ ] **Étape 6 — commit.**

```bash
git add retro/licence.py tests/test_licence.py retro/status.py tests/test_status.py
git commit -m "feat(vita): lire le content id d'un work.bin et dire si la licence est posée"
```

---

## Tâche 6 : installer une fois, lancer sans réinstaller

C'est le geste que la dette dit qu'aucune commande ne porte. Deux faits mesurés
le cadrent, et ils vont dans des sens opposés :

- **la copie manuelle ne suffit pas** pour un dump NoNpDrm. `install_content`
  n'a pas seulement copié : il a appelé `is_nonpdrm`, qui **déchiffre le PFS**
  (`decrypt_install_nonpdrm`, `vita3k/packages/src/pkg.cpp`) avant de remplacer
  le dossier. Un `robocopy` rend une copie **chiffrée**, que rien dans la chaîne
  ne déchiffrera. Le contournement de la dette ne vaut donc que pour un dump
  **sans** `sce_sys/package/` — ce qui se vérifie en une commande, et doit être
  vérifié avant d'y compter ;
- **le lancement actuel réinstalle.** `launch = '--fullscreen "{rom}"'` passe le
  dossier du jeu en `content-path`, donc `install_contents` à chaque partie ;
  et `install_content` fait `fs::remove_all(dst_path)` **avant** de copier. Un
  échec de copie détruit donc l'installation précédente — ce qui explique le
  dossier vide de la dette bien mieux qu'un disque plein.

**Fichiers :**
- Modifier : `retro/data/profiles/vita3k.toml`
- Test : `tests/test_donnees.py`, `tests/test_scan.py`

**La question à trancher, et il faut l'écrire, pas la deviner :** le profil n'a
qu'un `launch` par système, et une bibliothèque Vita a deux formes — le `.vpk`,
qu'il faut installer, et le dossier `ux0/app/<TITLEID>`, qui peut déjà l'être.
`-r <TITLEID>` lance sans réinstaller, mais **échoue au parsing** sur un titre
absent de `ux0/app` (`CLI::IsMember`), donc il ne peut pas servir les deux.

Deux rangements possibles, à départager par une mesure et non par goût :

**A — la bibliothèque du propriétaire est la source, l'installation est un
geste séparé.** `retro` gagne un ordre, sur le modèle exact de
`launcher.ordonner_reamorcage` : une ligne écrite dans `_launcher\`, consommée
une fois par le lanceur, qui appelle `Vita3K.exe "<dossier>"` puis
`Vita3K.exe "<dossier>\sce_sys\package\work.bin"`. Le lancement, lui, devient
`-r`. Coût : un jeton de plus dans le plan de système pour porter le TITLE ID,
et le scan qui décide lequel des deux gabarits s'applique — **le scan décide,
le lanceur exécute**, comme partout ailleurs.

**B — la bibliothèque EST le `ux0/app` de Vita3K.** `pref-path` place le système
de fichiers Vita là où le propriétaire range ses jeux ; il n'y a plus rien à
installer, et `-r <TITLEID>` lance directement. Coût : le rangement du
propriétaire cesse d'être « un dossier par système sous `G:\Games` », et
`retro scan` doit reconnaître `ux0\app` comme dossier de système — ce que
`folders` sait déjà déclarer.

**Le critère qui tranche, et il est mesurable :** l'option B ne tient que si les
jeux du propriétaire sont **déjà déchiffrés**. Un dump portant
`sce_sys\package\work.bin` doit passer par `install_content` au moins une fois.
Relever, sur la bibliothèque réelle :
`Get-ChildItem -Recurse -Filter work.bin <bibliothèque> | Measure-Object`.
Aucun résultat ⇒ B est ouverte. Un seul ⇒ A, et la question est close.

**Ce qu'il faut obtenir :**

- la décision, **écrite dans le profil avec sa raison** — c'est le genre de
  choix qu'un lecteur futur ne devinera pas ;
- la ligne de lancement qui en découle, et un test qui exige que le gabarit
  livré ne réinstalle pas un jeu déjà installé. Le test se lit sur le gabarit,
  pas sur la machine : `--fullscreen "{rom}"` avec `{rom}` sur un dossier **est**
  une réinstallation, et le message d'échec doit citer `install_content` et son
  `remove_all` ;
- `--keep-config` conservé, quel que soit le rangement (tâche 4).

---

## Vérification finale

- [ ] Suite complète, arbre frais, sous `-W error`
- [ ] Aucun test ne touche le réseau, aucun n'exige Windows
- [ ] Aucun dump, aucune licence, aucun binaire ajouté au dépôt — les fixtures
      de licence sont fabriquées en Python
- [ ] Chaque valeur posée dans `vita3k.toml` nomme, en commentaire, le fichier
      source Vita3K d'où elle vient
- [ ] `docs/dettes.md` **n'a pas été modifié** par ce plan
- [ ] Sur la machine : un jeu installé, lancé depuis Steam, qui démarre sans
      modale et **sans recopier ses 3,5 Go**, journal du lanceur à l'appui
- [ ] Sur la machine : un second lancement du même jeu dit `deja conforme` dans
      `journal.txt` — la fusion YAML est idempotente

## Ce que ce plan ne fait pas

- **Il n'installe pas le paquet de polices.** Vita3K écrit lui-même qu'il n'en
  publie pas l'URL, et rien n'a été pris ailleurs. Le geste, lui, existe déjà :
  `install_pup` extrait `sa0.img` du PUP qu'on lui donne s'il en contient un
  (`vita3k/packages/src/pup.cpp`), donc `--firmware` suffira le jour où le
  fichier sera là. Ce plan **désarme la modale**, il ne comble pas le manque —
  et la conséquence, du texte absent en jeu, reste **non mesurée**.
- **Il ne corrige pas Vita3K.** `copy_directory_contents` avale son exception
  sans la lire ; c'est un défaut amont, qui se signale au projet et ne se
  contourne pas dans ce dépôt.
- **Il ne déchiffre aucun dump.** Le PFS se déchiffre par Vita3K, ou pas.
- **Il ne range pas le PUP du firmware.** Ce point reste ouvert depuis D5 :
  le PUP est dans `G:\retro\bios\` alors que les firmwares vont hors de `bios\`,
  et rien ne sait encore constater qu'un firmware est déjà installé. La
  tâche 5 en donne la moitié — `vs0` non vide, mesuré dans
  `vita3k/app/src/app.cpp` — mais seulement si le remède 1 rend ce dossier
  visible depuis l'hôte.
- **Il n'écrit ni le jeton de cible ni le passage à plusieurs cibles par
  profil** : ce sont les deux pièces de D7, et les tâches 4 et 5 les attendent.
- **Il ne règle ni le mouvement, ni le tactile, ni la vibration** de la
  PS Vita — D4 et D1, qui vivent ailleurs.
- **Il ne lit pas `param.sfo`** pour donner à un jeu son vrai nom dans Steam :
  la bibliothèque affichera les identifiants de titre. C'est la limite connue du
  profil, et elle ne bouge pas ici.
