# D7 — le jeton de chemin, et les quatre réglages qu'il rend tenables — plan

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — `superpowers:subagent-driven-development`.

**Objectif :** rendre reposables les quatre réglages mesurés le 2026-08-29 et
posés à la main, dont aucun ne survit à quoi que ce soit.

**Spec :** `docs/superpowers/specs/2026-08-28-amorcage-emulateurs-design.md`
**Dette :** `docs/dettes.md`, D7 — et la pièce centrale de ce plan **débloque
aussi D9** : la case « Don't show this warning again » du paquet de polices de
Vita3K est une clé de plus dans le MÊME fichier INI que la modale de
privilèges, et personne ne pourra la reposer tant qu'aucun `target` ne
désignera ce fichier.

## Contraintes globales

- **Python 3.11 minimum.** Aucun test ne touche le réseau ni n'exige Windows.
- **Les chemins Windows sont des `str`**, antislashs internes compris. Les
  écrire en chaîne TOML LITTÉRALE (`'…'`, `'''…'''`), jamais de base.
- **Une valeur fausse se comporte exactement comme l'absence de valeur.**
  Toute valeur posée cite sa source dans le **code source** de l'émulateur —
  pas une page de documentation, pas une chaîne du binaire, qui donne les
  libellés de l'interface et non les valeurs du fichier (leçon D2).
- **Un test qui passe quelle que soit l'implémentation est un défaut.**
- Le lanceur se compile avec le `csc.exe` du .NET Framework. Le dépôt n'a
  aucun cadre de test C# : ce qui s'y écrit se vérifie **à la main, par
  `--explain`**, et la vérification s'écrit dans le rapport de fin.
- **La console Windows n'est pas atteignable depuis la session qui exécute ce
  plan.** Toute mesure est une tâche à part, explicitement nommée.

---

## Ce que ce plan a établi avant d'être écrit

Trois choses lues dans le code, qui précisent l'énoncé de la dette :

1. **La racine d'émulation n'est pas le bon jeton.** Les quatre fichiers
   vivent sous le dossier d'INSTALLATION de leur émulateur, dont le nom est
   décidé par le manifeste (`install_dir`) et **surchargeable** par le
   manifeste du propriétaire — `_install_dirs_pour` documente le jour où
   `install_dir = "DuckStation-v0.1"` a fait pointer tout l'inventaire sur un
   dossier inexistant. Un `{emulation_root}\Vita3K\…` réécrirait ce nom une
   seconde fois, dans le profil, et une surcharge ferait rater la cible **en
   silence**. Le jeton est donc `{install_dir}`.
2. **`plan_systeme` a déjà la valeur sous la main.** Elle s'appelle `workdir`
   et vaut `f"{emulation_root}\\{install_dirs[pid]}"`. La substitution est un
   `str.replace`, au même endroit et pour la même raison que `{render_config}`.
3. **Un profil ne peut porter qu'UNE cible**, et la dette ne le dit pas.
   `Profile.bootstrap` est un `Bootstrap | None` ; `bootstrap_name` nomme un
   seul fichier par profil ; le plan porte quatre lignes `bootstrap_*` au
   singulier ; `InscrireTemoin` déduplique le témoin sur le seul identifiant
   de profil. **RPCS3 a deux fichiers.** Passer à plusieurs entrées est donc
   une pièce obligatoire, pas un confort.

Et une quatrième, qui ferme la question du format : **la fusion n'a pas besoin
d'apprendre le YAML.** Le `Default.yml` de RPCS3 est posé par le régime
`si-absent`, qui copie des octets et ne lit jamais le contenu. Voir la tâche 6.

---

## Tâche 1 : le jeton `{install_dir}`

**Fichiers :**
- Modifier : `retro/profiles.py` (`_lire_bootstrap`), `retro/launcher.py`
  (`plan_systeme`)
- Test : `tests/test_profiles.py`, `tests/test_launcher.py`

**Ce qu'il faut obtenir :**

- dans `profiles.py`, la liste des jetons connus, publique parce que
  `launcher.py` et `install.py` la reliront :

```python
JETON_INSTALL = "{install_dir}"
JETONS_CIBLE = (JETON_INSTALL,)
_JETON_CIBLE = re.compile(r"\{[^}]*\}")
```

- `_lire_bootstrap` accepte une `target` qui **commence par** un jeton connu,
  en plus des deux formes actuelles ;
- elle **refuse tout jeton inconnu, en le nommant**, et cite les jetons
  connus. Sans ce refus, `{emulation_roo}\x.ini` tombe dans le message
  « chemin absolu », qui envoie corriger la mauvaise chose ;
- dans `launcher.py`, la substitution, avec le commentaire qui dit pourquoi
  elle est ici et pas dans le lanceur — la convention de nommage ne se décide
  qu'à un endroit :

```python
def resoudre_cible(target: str, install_dir_windows: str) -> str:
    """La cible, jetons substitués — comme {render_config}."""
    return target.replace(profiles_mod.JETON_INSTALL, install_dir_windows)
```

- `plan_systeme` écrit `bootstrap_target=` **substitué**, et continue de
  nommer le fichier déposé d'après la cible **brute** : c'est son extension
  qui compte, et elle ne change pas.

**Les tests, et ce qu'ils doivent échouer à prouver avant l'implémentation :**

- [ ] `test_une_cible_sous_le_dossier_d_installation_est_acceptee` —
  `'{install_dir}\gui-configs\CurrentSettings.ini'` se charge. Échoue
  aujourd'hui sur « doit être un chemin Windows absolu ».
- [ ] `test_un_jeton_de_cible_inconnu_est_refuse` — `'{emulation_root}\x.ini'`
  lève `ProfileError`, et le message contient `{emulation_root}` **et**
  `{install_dir}`. Assertion sur les deux : un message qui refuse sans dire ce
  qui est permis fait relire le validateur.
- [ ] `test_le_plan_substitue_le_dossier_d_installation` — `plan_systeme(...,
  workdir="D:\\Emulation\\Vita3K", ...)` rend
  `bootstrap_target=D:\Emulation\Vita3K\gui-configs\CurrentSettings.ini`.
- [ ] `test_le_nom_du_fichier_depose_suit_la_cible_brute` — la cible à jeton
  donne bien un fichier en `.ini`, pas en `.txt`.
- [ ] Commit.

---

## Tâche 2 : Vita3K — la modale de privilèges

Premier réglage rendu tenable, et il ne demande **aucune** modification du
lanceur : une seule cible, un `enforced` INI, la fusion existante.

**Fichiers :**
- Modifier : `retro/data/profiles/vita3k.toml`
- Test : `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- un bloc d'amorçage visant
  `'{install_dir}\gui-configs\CurrentSettings.ini'` ;
- `enforced` portant exactement `[MainWindow] warnAdminPrivileges=false` —
  clé relevée dans `gui_settings.h` (`gui::mw_warnAdminPrivileges`) et
  gardant `prompt_admin_privileges_warning_if_needed` dans `main_window.cpp` ;
  valeur **vérifiée par l'effet** le 2026-08-29 (la ligne d'avertissement a
  disparu du journal, et la modale de l'écran) ;
- `content` obligatoire, et il porte l'en-tête à **trois catégories** —
  `_valider_regimes` refuse un profil qui impose sans distinguer « imposé,
  reposé à chaque lancement » / « posé une fois » / « à vous ». Y mettre
  une préférence réellement mesurée, ou rien de plus que l'en-tête ;
- le profil DIT que cette cible vit sous le dossier d'installation, donc
  qu'elle **disparaît à chaque `retro install`** et se repose au lancement
  suivant. Ce n'est pas une panne : c'est le comportement que la spec avait
  prévu pour RetroArch et Cemu.

- [ ] `test_vita3k_impose_la_modale_de_privileges` dans `test_donnees.py` :
  `('MainWindow', 'warnAdminPrivileges')` est dans les clés imposées, et
  **nulle part** dans `content`. Sur le modèle de
  `test_duckstation_n_impose_que_ce_que_le_proprietaire_a_approuve`.
- [ ] `test_aucun_profil_livre_ne_porte_de_jeton_inconnu` : pour chaque profil
  livré, chaque `{…}` d'une cible est dans `profiles.JETONS_CIBLE`.
- [ ] Commit.

**⚠ Ce réglage n'est PAS vérifié tant que la tâche 8 n'a pas tourné.** Il est
posé à la main sur la machine : le prouver, c'est le voir reposé par la
console après suppression, pas le lire dans un profil.

---

## Tâche 3 : plusieurs cibles par profil, côté Python

**Fichiers :**
- Modifier : `retro/profiles.py`, `retro/launcher.py`, `retro/status.py`,
  `retro/data/profiles/duckstation.toml`,
  `retro/data/profiles/vita3k.toml`,
  `docs/superpowers/specs/2026-08-28-amorcage-emulateurs-design.md`
- Test : `tests/test_profiles.py`, `tests/test_launcher.py`,
  `tests/test_status.py`, `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- `[bootstrap]` devient `[[bootstrap]]`, un tableau de tables. **Une seule
  forme est acceptée** : garder les deux ferait deux façons d'écrire la même
  chose, et le jour où quelqu'un mélange, rien ne dirait laquelle gagne.
  `Profile.bootstrap` devient `bootstraps: tuple[Bootstrap, ...] = ()` ;
- migrer `duckstation.toml` et le profil de la tâche 2, **sans toucher à leur
  contenu** : seul l'en-tête de bloc change ;
- migrer l'exemple TOML de la spec — `test_l_exemple_de_bootstrap_de_la_
  specification_se_charge` l'extrait du document et le passe au validateur ;
  cet exemple doit rester chargeable ;
- les fichiers déposés portent l'**indice de l'entrée**, 1-based, dans l'ordre
  du profil : `bootstrap_name(pid, i, target)` →
  `f"{pid}.bootstrap.{i}{suffixe}"`, `enforced_name` →
  `f"{pid}.impose.{i}{suffixe}"`. `profils_amorcables`, qui coupe le nom sur
  `.bootstrap`, continue de rendre le bon identifiant — le vérifier par un
  test plutôt que par lecture ;
- le plan porte le **compte** puis des lignes indicées :

```
bootstrap_count=2
bootstrap_target.1=D:\Emulation\RPCS3\GuiConfigs\CurrentSettings.ini
bootstrap_source.1=D:\Emulation\_launcher\systems\rpcs3.bootstrap.1.ini
bootstrap_when.1=si-absent
bootstrap_enforced.1=D:\Emulation\_launcher\systems\rpcs3.impose.1.ini
bootstrap_target.2=D:\Emulation\RPCS3\config\input_configs\global\Default.yml
bootstrap_source.2=D:\Emulation\_launcher\systems\rpcs3.bootstrap.2.yml
bootstrap_when.2=si-absent
bootstrap_enforced.2=
```

  `bootstrap_count=0` pour un profil sans bloc, et **aucune ligne indicée** :
  `Valeur()` traite une clé absente comme une faute du plan, et `count` suffit
  désormais à porter cette propriété ;
- `status.etat_amorcage` rend **une `Amorcage` par entrée**, pas par profil —
  sinon deux cibles se disputent une ligne et la seconde disparaît du rapport.
  `lire_amorcages` rend `dict[str, list[tuple[str, str]]]` : profil → liste de
  (date, cible), parce que le témoin porte désormais plusieurs lignes par
  profil. Un profil sans bloc garde son unique ligne « aucune configuration à
  poser (voir son profil) ».

- [ ] `test_un_profil_declare_plusieurs_amorcages` — deux `[[bootstrap]]`
  donnent deux entrées, dans l'ordre du fichier.
- [ ] `test_le_plan_porte_une_ligne_par_amorcage` — `bootstrap_count=2` et les
  huit lignes indicées, valeurs exactes.
- [ ] `test_un_profil_sans_amorcage_porte_un_compte_nul` — `bootstrap_count=0`,
  et `bootstrap_target.1` **absent** du plan.
- [ ] `test_les_deux_amorcages_d_un_profil_ne_se_confondent_pas` — les quatre
  noms de fichiers déposés sont deux à deux distincts.
- [ ] `test_un_amorcage_perime_est_retire` étendu à la forme indicée : passer
  de deux entrées à une doit **supprimer** `…bootstrap.2.yml` et
  `…impose.2.ini`.
- [ ] `test_le_rapport_nomme_les_deux_cibles_d_un_profil` dans
  `test_status.py`, depuis un témoin fabriqué à deux lignes.
- [ ] Commit.

---

## Tâche 4 : le lanceur C#, une boucle au lieu d'un cas

**Fichiers :**
- Modifier : `retro/data/launcher/retro-launch.cs`
- Test : aucun (pas de cadre C# dans ce dépôt) — vérification en tâche 8.

**Ce qu'il faut obtenir :**

- `Amorcer` lit `bootstrap_count`, boucle de 1 à N et applique à **chaque**
  entrée les deux régimes dans l'ordre inchangé : poser si absent, puis
  refondre les clés imposées. L'ordre reste celui du commentaire existant, et
  la raison ne change pas ;
- l'ordre de ré-amorçage vaut **pour toutes les entrées du profil** et n'est
  consommé **qu'une fois**, après la boucle. Le consommer dans la boucle ne
  reposerait que la première cible ;
- un `count` nul consomme quand même un ordre devenu sans objet — c'est le
  garde existant, à conserver mot pour mot ;
- **un garde nouveau** : si une `bootstrap_target.N` contient encore `{`, le
  lanceur lève, en nommant la cible et en disant de relancer `retro scan`.
  Sans lui, Windows créerait un dossier littéralement nommé `{install_dir}`
  et l'émulateur ne lirait jamais rien — panne muette exemplaire ;
- `InscrireTemoin(profil, cible)` déduplique désormais sur **profil ET
  cible** : la ligne remplacée est celle qui porte les deux, pas la première
  du profil. Le format de ligne — `profil \t date \t cible` — ne change pas,
  `lire_amorcages` le relit tel quel ;
- `--explain` rend une ligne par entrée, indicée comme le plan
  (`amorcage_cible.1=`, `amorcage_impose.1=`, `amorcage_a_poser.1=`), plus
  `amorcage_count=`. L'ordre de ré-amorçage reste rendu une fois, avec son
  rattrapage d'exception intact : c'est le seul contrôle lisible par WinRM, et
  il ne doit jamais ouvrir de boîte modale en session 0.

**⚠ Une conséquence à écrire dans le rapport, pas à découvrir sur la
console :** un lanceur d'AVANT cette tâche, lisant un plan d'APRÈS, échoue sur
`Valeur(p, "bootstrap_target")` — bruyamment, à chaque jeu. C'est le bon
comportement, et `lanceur_perime` le signale déjà, mais l'ordre des gestes sur
la machine devient obligatoire : `retro launcher` (dépose la source), puis
`compiler.cmd` sur Windows, **puis** `retro scan`.

- [ ] Commit.

---

## Tâche 5 : RPCS3 — les modales du dossier de dialogue

**Fichiers :**
- Modifier : `retro/data/profiles/rpcs3.toml`
- Test : `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- une entrée visant `'{install_dir}\GuiConfigs\CurrentSettings.ini'`, avec les
  modales dans `enforced` — INI de QSettings, donc la fusion existante ;
- **la liste des clés se relève dans `rpcs3qt/gui_settings.h`, elle ne se
  recopie pas de la dette.** D7 écrit « sept » et en énumère huit : le compte
  n'est donc pas un fait. Prendre le nom du groupe, le nom de chaque clé et sa
  valeur par défaut dans l'en-tête, et n'imposer que celles qui sont
  **vraies par défaut** — imposer `false` sur une clé déjà fausse est du
  bruit qui se lit comme un réglage ;
- la valeur s'écrit comme **QSettings l'écrit**, pas comme on la lit en C++ :
  la relire dans un `CurrentSettings.ini` que RPCS3 a lui-même produit après
  que les cases ont été décochées. C'est la règle de la spec, et c'est la
  seule protection contre un `False` majuscule ignoré en silence ;
- le profil nomme `confirmationBoxBootGame` à part : c'est celle qui
  s'interpose **à chaque lancement de jeu**, et `infoBoxEnabledInstallPUP`
  celle qui laissait RPCS3 ouvert après l'installation du firmware.

- [ ] `test_rpcs3_impose_ses_modales` : chaque couple (section, clé) relevé
  est dans `enforced` et dans aucun `content`, et la liste est **gelée** dans
  le test — l'allonger ou la raccourcir devient un acte qui se voit en revue,
  comme pour DuckStation.
- [ ] Commit.

---

## Tâche 6 : RPCS3 — la manette, et le format qui n'est pas de l'INI

`config\input_configs\global\Default.yml` est du **YAML**. La question posée
par la dette — la fusion doit-elle l'apprendre ? — a une réponse **non**, et
c'est la tâche la moins chère du plan.

**Pourquoi le fichier est posé en bloc, régime `si-absent` :**

- le régime `si-absent` **copie des octets** et ne lit jamais le contenu :
  le lanceur ne connaît le format d'aucun fichier qu'il pose. Le seul format
  que la fusion connaisse reste l'INI, et rien n'a besoin de changer ;
- la cible vit sous le dossier d'installation, que `retro install` efface à
  chaque montée de version : la cible disparaît, donc `si-absent` **repose**.
  C'est exactement l'auto-réparation que la spec avait prévue pour RetroArch
  et Cemu, et elle joue ici en notre faveur ;
- **réécrire ce fichier en entier à chaque lancement serait ÉCRASER**, pas
  modifier. Le propriétaire a autorisé « seulement les clés que la console
  doit imposer » dans un INI qu'on fusionne ; un remplacement intégral d'un
  fichier que RPCS3 réécrit lui-même quand on configure un pad dans son
  interface effacerait sans un mot toute liaison qu'il y aurait faite. Ce
  serait une autorisation nouvelle, à demander — voir les arbitrages.

**Ce que ça laisse ouvert, et il faut l'écrire dans le profil :** si le fichier
existe avec `Handler: Null` — ce que produit un passage malheureux par la
configuration de pad de RPCS3 —, `si-absent` ne le répare pas. Le seul
remède aujourd'hui est la montée de version de RPCS3.

**Fichiers :**
- Modifier : `retro/data/profiles/rpcs3.toml`, `tests/test_donnees.py`

**Ce qu'il faut obtenir :**

- une seconde entrée visant
  `'{install_dir}\config\input_configs\global\Default.yml'`, avec **tout** le
  fichier dans `content` et un `enforced` vide ;
- le contenu, et ses deux pièges de forme, chacun avec sa source :

```yaml
# Écrit par « retro ».
Player 1 Input:
  Handler: XInput
  Device: "XInput Pad #1"
```

  - `Handler` vaut `XInput`, **avec ses deux majuscules** —
    `pad_config_types.cpp`, `case pad_handler::xinput: return "XInput";` ;
  - `Device` **doit être cité** : en YAML `#` ouvre un commentaire, donc
    `XInput Pad #1` non quoté devient `XInput Pad`, qui ne désigne rien. Le
    nom vient de `xinput_pad_handler.cpp`, `m_name_string = "XInput Pad #"` ;
  - trois lignes suffisent parce que `xinput_pad_handler::init_config()`
    renseigne les vingt-quatre `.def` puis appelle `from_default()`. Sans le
    fichier, `cfg_player` vaut `pad_handler::null` (`Emu/Io/pad_config.h`) :
    ce n'est pas une liaison fausse, c'est l'absence de manette ;
- la marque `Écrit par « retro »` est en commentaire **YAML** (`#`), et
  `_lire_bootstrap` l'exige déjà — c'est ce qui rend la garde vraie pour un
  format qu'elle ne connaît pas.

- [ ] `test_rpcs3_pose_son_gestionnaire_de_manette_en_bloc` : l'entrée qui
  vise `Default.yml` a un `enforced` **vide**, et son `content` contient
  `Handler: XInput` et `Device: "XInput Pad #1"` **avec les guillemets**.
  Assertion sur la chaîne guillemetée exacte : sans elle, le test passerait
  sur le fichier cassé que ce plan existe pour éviter.
- [ ] `test_aucun_profil_livre_ne_pose_de_liaison_de_manette` : ajouter
  l'exception **nommée** de RPCS3, comme celle de DuckStation. `Handler` et
  `Device` ne sont pas des liaisons — ils choisissent le gestionnaire — et la
  garde doit le dire plutôt que de se taire par accident de forme.
- [ ] Commit.

---

## Tâche 7 : l'aggravant — ce que `retro install` vient d'effacer

Trois des quatre réglages vivent sous un dossier que `retro install` supprime
(`acquire`, `shutil.rmtree`). Le mécanisme les repose au lancement suivant —
mais **rien ne fait le lien**, et c'est la moitié de la dette : une manette
muette après une mise à jour ne ressemble pas à une mise à jour.

**Fichiers :**
- Modifier : `retro/install.py`, `retro/cli.py`
- Test : `tests/test_install.py`, `tests/test_cli_install.py`

**Ce qu'il faut obtenir :**

- dans `install.py` :

```python
def configurations_effacees(resultats, emulateurs, profils):
    """(profil, cible) des amorçages disparus avec le dossier d'installation.

    Seuls ceux dont la cible commence par le jeton du dossier d'installation :
    un %USERPROFILE% survit à toutes les montées de version.
    """
```

  Ne retenir que les émulateurs dont l'état rendu par `acquire` est
  `« installé »` ou `« réinstallé »` — « à jour » n'a rien effacé. Le lien
  manifeste → profil est `emu.profile`, celui qu'`_install_dirs_pour` emploie
  déjà ;
- `_cmd_install` charge les profils (`--profiles`, `--user-profiles`, mêmes
  options et même aide que `scan`) et imprime, après le rapport :

```
  · rpcs3 : sa configuration a été effacée avec son dossier
    ({install_dir}\config\input_configs\global\Default.yml). Elle sera
    reposée au prochain lancement d'un de ses jeux — d'ici là, la manette ne
    répond pas.
```

- **le dossier de profils du propriétaire absent reste normal** : il vit sur
  un partage qui n'est pas toujours monté, `_dossier(None)` le dit déjà.

- [ ] `test_une_reinstallation_nomme_la_configuration_effacee` — un profil à
  cible `{install_dir}\…` et un résultat « réinstallé » rendent le couple ;
  « à jour » ne rend rien.
- [ ] `test_une_cible_hors_du_dossier_d_installation_n_est_pas_nommee` — une
  cible en `%USERPROFILE%\…` ne figure jamais dans le résultat, même
  réinstallée. Sans ce test, la fonction pourrait tout rendre et passer.
- [ ] `test_retro_install_dit_ce_qu_il_a_efface` — la sortie de la commande
  porte l'identifiant du profil et la cible.
- [ ] Commit.

---

## Tâche 8 : les mesures, sur la console — et rien avant

**Aucune de ces étapes n'est faisable depuis l'hôte.** Elles s'exécutent sur
la console, dans la session interactive (`schtasks /it`, jamais WinRM en
session 0), et leur résultat s'écrit dans le rapport de fin.

- [ ] **M1 — l'ordre des gestes.** `retro launcher`, puis `compiler.cmd` sur
  Windows, puis `retro scan`. Un plan neuf lu par un lanceur ancien échoue à
  chaque jeu (tâche 4) : c'est bruyant, mais il ne faut pas le découvrir en
  jouant.
- [ ] **M2 — le relevé RPCS3.** Ouvrir `GuiConfigs\CurrentSettings.ini` tel
  que RPCS3 l'a écrit après que les cases ont été décochées, et **recopier de
  là** le nom de groupe et la forme exacte des valeurs dans le profil de la
  tâche 5. Croiser avec `rpcs3qt/gui_settings.h` pour les noms et les défauts.
- [ ] **M3 — `--explain` à blanc.** Sur un jeu de chaque profil touché, lire
  `amorcage_count`, `amorcage_cible.N` et `amorcage_a_poser.N`. Aucune ligne
  ne doit contenir `{`. C'est le seul contrôle lisible sans rien lancer.
- [ ] **M4 — l'auto-réparation, prouvée.** Renommer la cible Vita3K, lancer un
  jeu, vérifier qu'elle est reposée, que la modale de privilèges ne sort plus,
  et que `journal.txt` et `bootstrap.txt` le disent. Recommencer en la
  laissant en place et en changeant `warnAdminPrivileges` à `true` : la fusion
  doit la remettre à `false` **sans toucher au reste du fichier**, et un
  second lancement doit rendre « déjà conforme, rien ne sera réécrit ».
- [ ] **M5 — la manette RPCS3 après une montée de version.** Supprimer le
  dossier d'installation, réinstaller, vérifier que `retro install` nomme la
  configuration effacée (tâche 7), lancer un jeu, et **voir un bouton
  répondre**. C'est le seul oracle : un fichier posé ne prouve pas une
  manette. Sans ce pas, D7 reste ouverte pour RPCS3.

---

## Deux arbitrages — à porter au propriétaire, pas à exécuter

**1. Le dialecte JSON, pour l'émulateur du propriétaire — recommandation :
NON, pas dans ce plan.** Le tactile n'est alimenté que si `EnableMouse` est
faux (`if (_viewModel.IsActive && !ConfigurationState.Instance.Hid.EnableMouse.Value)`),
la valeur est bonne aujourd'hui, et le libellé de l'interface — « Direct Mouse
Access » — donne envie de l'activer. Reposer cette clé demanderait un second
dialecte de fusion, côté validation Python **et** côté lanceur C#. Le prix
n'est pas celui des trois autres cas :

- une fusion JSON qui préserve l'ordre, la mise en forme et les clés inconnues
  est un analyseur, pas un `str.replace`. Le .NET Framework n'offre rien qui
  le fasse sans réordonner, et le dépôt n'a **aucun cadre de test C#** : le
  seul code non testé du projet doublerait de surface ;
- un JSON mal réécrit n'est pas une clé fausse, c'est un fichier illisible —
  l'émulateur repart sur ses défauts, **sans un mot**. La règle du dépôt joue
  ici contre nous, pas pour nous ;
- le profil concerné vit **hors dépôt**, sur le partage du propriétaire :
  le code voyagerait dans le dépôt public pour un profil que personne ici ne
  peut charger.

Ce qui est écrit à la place, et qui ne coûte rien : la note existe déjà dans
le profil du propriétaire, et D7 en porte la cause. La question à trancher :
**une clé unique, dans un JSON, vaut-elle un second format de fusion non
testable — ou accepte-t-on de la reposer à la main le jour où le tactile
meurt ?** Si la réponse est « il faut le mécanisme », c'est un plan à part,
avec sa propre conception.

**2. Le garde-fou `test_aucun_emulateur_au_statut_conteste` — à relâcher ou
non, en revue.** Il cherche ses mots interdits en **sous-chaîne**, sur le
texte en minuscules. L'un d'eux est une sous-chaîne du nom anglais du compte
super-utilisateur de Windows — le compte sous lequel toute la console tourne,
et qui apparaît dans les messages des émulateurs comme dans n'importe quel
chemin `C:\Users\…`. Le garde-fou refuse donc des textes parfaitement
légitimes, **en nommant un émulateur qui n'est pas là**, ce qui envoie
chercher au mauvais endroit. La dette D7 en fait elle-même la démonstration :
sa première rédaction a été refusée, et la périphrase qui la remplace restera
laide tant que la correspondance se fera en sous-chaîne.

**Ce plan ne le corrige pas, délibérément.** C'est un garde-fou de conformité
d'un dépôt public ; le relâcher — même vers une frontière de mot, qui serait
la bonne réponse — se décide en revue, avec la liste gelée sous les yeux, pas
au détour d'une tâche. Le noter, le poser, et attendre la réponse.

---

## Vérification finale

- [ ] Suite complète, arbre frais, sous `-W error`
- [ ] Aucun test ne touche le réseau, aucun n'exige Windows
- [ ] `retro status` rend une ligne par cible d'amorçage, et le témoin à
      plusieurs lignes par profil se relit
- [ ] Aucun profil livré ne porte de jeton absent de `profiles.JETONS_CIBLE`
- [ ] Aucun plan écrit ne contient `{` dans une ligne `bootstrap_target.N`
- [ ] Chaque valeur posée par ce plan cite sa source dans le code source de
      son émulateur, dans le profil, à côté de la clé
- [ ] Les cinq mesures M1–M5 sont jouées et **écrites** dans le rapport de fin

## Ce que ce plan ne fait pas

- **Il ne pose aucune valeur qu'il n'a pas relevée.** La liste des modales de
  RPCS3 est à relire dans `gui_settings.h` et dans un fichier que RPCS3 a
  écrit lui-même : la dette en annonce sept et en énumère huit.
- **Il n'apprend pas le JSON à la fusion**, et donc ne repose pas le réglage
  du tactile de l'émulateur du propriétaire. C'est un arbitrage, ci-dessus.
- **Il ne réécrit pas `Default.yml` à chaque lancement.** Un fichier existant
  avec un mauvais gestionnaire n'est réparé que par une montée de version de
  RPCS3. Le rendre imposé demanderait une autorisation d'ÉCRASER que le
  propriétaire n'a pas donnée.
- **Il ne touche pas au garde-fou des émulateurs au statut contesté.**
- **Il ne ferme pas D9.** Il lui donne la pièce qui lui manquait — un `target`
  qui désigne le fichier INI de Vita3K — mais la licence NoNpDrm à convertir,
  la copie manuelle de `ux0/app/<TITLEID>/` et la modale du paquet de polices
  restent entières.
- **Il ne mesure pas les huit autres émulateurs.** L'amorçage de PCSX2,
  RetroArch, Dolphin, Cemu, PPSSPP, Flycast et Xemu reste la tâche 3 de
  l'ordre de travail de la spec.
- **Il n'ajoute pas `{emulation_root}`** comme jeton. Aucune des quatre cibles
  n'en a besoin, et un second jeton est un second moyen de se tromper. Le jour
  où un chemin sous la racine mais hors d'un dossier d'installation sera
  nécessaire, la table des jetons est un unique tuple.


---

## ⚖ Arbitrage rendu le 2026-08-29 par la conduite de projet — RPCS3, `Handler:`

**Les plans D4 et D7, écrits séparément, se contredisent sur une ligne.** D7
prescrit de poser `Handler: XInput` (mesuré : le propriétaire a confirmé que
les contrôles répondent). D4 a relevé dans la source que `b_has_motion` reste
`false` sous XInput, quel que soit le pad — donc que ce choix **interdit le
mouvement pour toujours**, et qu'il faudrait `Handler: SDL`.

**Décision : `Handler: XInput` est posé, et D4 ne le change pas sans mesure.**

Trois raisons, dans cet ordre :

1. **XInput est la seule des deux valeurs qui ait été vue fonctionner.** SDL
   n'a jamais été essayé sur cette machine. La règle du dépôt est de ne jamais
   troquer une valeur mesurée contre une valeur supposée — une valeur fausse se
   comporte exactement comme l'absence de valeur, et ici l'absence de valeur
   signifie `pad_handler::null`, c'est-à-dire pas de manette du tout.
2. **Le coût du choix est borné, et il ne touche qu'une dette.**
   `xinput_pad_handler.cpp` pose `b_has_rumble = true` : XInput ne bloque donc
   **pas D1**. Il ne coûte que le mouvement, c'est-à-dire D4 — une dette qui,
   elle, attend de toute façon un changement de type de pad dans
   `nivuus/installer` (C2) qu'aucun des deux plans ne contrôle.
3. **Basculer maintenant, ce serait déboguer deux inconnues à la fois** — le
   défaut nommé que D4 s'interdit elle-même dans sa section « Ordre ».

**Ce que cette décision impose aux deux plans, et c'est la partie qui coûte :**

- **D7 ne doit pas poser `Default.yml` en `si-absent` sans dire comment on en
  sort.** `si-absent` copie des octets et ne réécrit jamais : le jour où D4
  voudra `Handler: SDL`, le fichier existera déjà et **rien ne le remplacera**.
  Le geste de sortie — supprimer le fichier, ou une option qui le force — doit
  être écrit dans le profil, sans quoi la bascule de D4 échouera en silence,
  ce qui est très exactement le défaut que ces deux plans existent pour éviter.
- **D4 ne planifie pas la bascule à l'aveugle.** Elle devient une tâche à deux
  temps : (a) mesurer que `Handler: SDL` + son `Device:` rendent une manette
  qui répond — un bouton vu répondre, rien de moins ; (b) alors seulement
  relever les valeurs d'`Axis`, qui viennent de l'override SDL de
  `get_motion_axis_list()` et **ne sont pas relevées à ce jour**.
- **Aucun des deux plans ne fige `Handler` dans une liste gelée** sans y écrire
  que la valeur est un arbitrage réversible, daté d'aujourd'hui, et non un fait
  mesuré sur l'émulateur.

**Ce que cet arbitrage ne tranche pas :** si le mouvement vaut, à l'usage, le
risque de reperdre une manette qui marche. C'est une question de valeur, pas de
fait, et elle appartient au propriétaire — le jour où D4 arrivera à cette
tâche, pas aujourd'hui.
