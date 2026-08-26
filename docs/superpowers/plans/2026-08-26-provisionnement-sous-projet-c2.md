# Provisionnement de la console (sous-projet C2) — plan d'implémentation

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development`.

**Objectif :** rendre la console réellement fonctionnelle sur la VM — installer
le paquet `retro` au provisionnement, et corriger deux trous du provisionnement
existant qui rendent la manette et la synchronisation muettes.

**Dépôt :** `packages/installer`, **distinct** de celui où vivent les
sous-projets précédents. Il a ses propres conventions, en particulier pour les
tests.

**Spec :** `packages/retro/docs/superpowers/specs/2026-08-26-retro-console-design.md`

## Contraintes globales

- **Le retrogaming est OPTIONNEL.** C'est la contrainte qui structure tout ce
  plan. Rien ne s'installe si la case n'est pas cochée dans l'assistant, au même
  titre que `docker` ou `wifi-ap`.
- **Une étape non concernée s'exécute et le dit.** Elle ne disparaît pas de la
  liste. Une étape absente ne laisse aucune trace, et six mois plus tard
  personne ne sait si elle a échoué ou n'a jamais tourné.
- **Deux correctifs de ce plan ne dépendent PAS de l'option**, parce qu'ils
  réparent des trous du provisionnement existant : la vérification de ViGEmBus
  et la sentinelle `steam.hold`. Les conditionner reviendrait à laisser une VM
  sans manette à qui ne veut pas de retrogaming.
- **Style du dépôt hôte.** Les tests y sont des scripts Python autonomes qui
  accumulent des échecs dans une liste et sortent en code 1, pas des tests
  pytest. Suivre la convention locale, pas celle du paquet `retro`.
- **Aucun test n'exige Windows.** Les étapes PowerShell sont vérifiées par
  lecture de leur texte, comme le fait déjà `test_windows_guest_provision.py`.
- **Ne jamais toucher aux fichiers hors périmètre.** Ce dépôt porte le travail
  de son propriétaire.

---

## Tâche 1 : ViGEmBus, le driver dont l'absence est muette

`25-apollo.ps1` vérifie scrupuleusement le driver d'écran virtuel par son
identifiant matériel, et **ne vérifie pas** le driver de manette virtuelle.
L'installateur d'Apollo l'embarque normalement — mais sans lecture de contrôle,
son absence ne produit aucun signe : l'image arrive, le son arrive, et la
manette ne fait rien. Pour une console de jeu, c'est le seul driver qui ne peut
pas manquer.

**Ce correctif est inconditionnel** : il ne concerne pas le retrogaming mais
toute manette passée par Moonlight.

**Fichiers :**
- Modifier : `installer/windows-guest/provision/25-apollo.ps1`
- Modifier : `scripts/tests/test_windows_guest_provision.py`

- [ ] **Étape 1 : écrire la vérification, sur le modèle de celle qui existe**

Juste après le bloc SudoVDA, ajouter une vérification de même forme, fondée sur
l'identifiant matériel déclaré par le driver — pas sur un nom de service, qui
change entre versions. ViGEmBus s'enregistre sous `Root\ViGEmBus`.

L'échec doit **nommer la conséquence**, pas seulement le symptôme : le message
doit dire qu'aucune manette ne fonctionnera. Suivre le ton des messages
existants du fichier, qui expliquent tous *pourquoi* la chose compte.

Contrairement à SudoVDA, dont l'absence est fatale, réfléchis à la gravité :
une console sans manette est inutilisable, mais l'installation peut-elle
continuer pour être diagnostiquée ? Tranche, et écris la raison dans le
commentaire.

- [ ] **Étape 2 : le test**

Dans `scripts/tests/test_windows_guest_provision.py`, suivre exactement la
forme des vérifications existantes (`check(...)` accumulant dans `failures`).
Vérifier que l'étape mentionne l'identifiant matériel et qu'elle lève.

- [ ] **Étape 3 : lancer les tests du dépôt**

```bash
python3 scripts/tests/test_windows_guest_provision.py
python3 scripts/tests/test_windows_guest_apollo.py
```

- [ ] **Étape 4 : commit**

---

## Tâche 2 : la sentinelle `steam.hold`

`steam-shell.ps1` relance Steam dès qu'il quitte la table des processus, toutes
les trois secondes. Or la synchronisation de la bibliothèque **exige que Steam
soit arrêté** : il réécrit `shortcuts.vdf` à sa fermeture, et écraserait le
travail. Sans sentinelle, la synchronisation réussit sans rien produire, par
intermittence — un échec qui ressemble à une réussite.

**Ce correctif est inconditionnel** : la garde est inerte tant que personne ne
pose la sentinelle, et elle coûte une comparaison toutes les trois secondes.

**Fichiers :**
- Modifier : `installer/windows-guest/provision/assets/steam-shell.ps1`
- Modifier : `scripts/tests/test_windows_guest_provision.py`

- [ ] **Étape 1 : la garde**

Le shell teste `C:\nivuus\state\steam.hold` avant de relancer Steam. Deux
exigences qui comptent autant l'une que l'autre :

- **La sentinelle expire d'elle-même au bout de cinq minutes.** Une
  synchronisation qui plante ne doit pas immobiliser la console sur un écran
  sans Steam, indéfiniment, sans personne pour s'en apercevoir. L'expiration se
  lit sur l'horodatage du fichier, pas sur une minuterie interne : le shell peut
  redémarrer entre-temps.
- **Le propriétaire doit voir ce qui se passe.** Le fond d'écran affiche déjà
  quelque chose pendant le démarrage ; pendant la retenue, il doit dire que la
  bibliothèque se met à jour. Un écran figé sans explication se lit comme un
  plantage, et quelqu'un finira par redémarrer la machine au milieu d'une
  écriture.

- [ ] **Étape 2 : le test**

Vérifier que le shell mentionne la sentinelle, l'expiration, et qu'il continue
de relancer Steam en son absence — c'est cette dernière propriété qui garantit
que la garde n'a pas cassé le comportement normal.

- [ ] **Étape 3 : lancer les tests, puis commit**

---

## Tâche 3 : la fonctionnalité optionnelle, côté hôte

**Fichiers :**
- Modifier : `installer/install-engine/steps/features.py`
- Modifier : les tests correspondants du dépôt

- [ ] **Étape 1 : déclarer la fonctionnalité**

Ajouter `retro` à la liste des fonctionnalités que l'assistant peut cocher, sur
le modèle exact de celles qui existent (`docker`, `wifi-ap`, `home-assistant`).
Elle **dépend de la VM Windows** : cocher le retrogaming sans la machine
virtuelle n'a aucun sens, et le dire au moment du choix vaut mieux que de
laisser une étape échouer plus tard.

- [ ] **Étape 2 : transmettre l'interrupteur au provisionnement**

La configuration voyage vers la VM par le dossier `config/` du payload, aux
côtés de `sunshine.conf`, `apps.json` et `secrets.psd1`. Ajouter un
`config/retro.psd1` qui porte l'état de l'option et les chemins que l'étape
utilisera.

Le fichier doit être **présent dans tous les cas**, portant `Enabled = $false`
quand la case n'est pas cochée. Un fichier absent est ambigu — option
désactivée, ou payload construit par une version antérieure ? Un fichier qui
dit explicitement non ne se confond avec rien.

- [ ] **Étape 3 : les tests**

Suivre la convention du dépôt. Vérifier les deux cas : coché et non coché.

---

## Tâche 4 : l'étape de provisionnement

**Fichiers :**
- Créer : `installer/windows-guest/provision/32-retro.ps1`
- Modifier : `installer/windows-guest/provision/run-all.ps1`
- Modifier : `installer/windows-guest/payload.py` et `fetch_payload.py`
- Modifier : les tests correspondants

- [ ] **Étape 1 : l'étape elle-même**

`32-retro.ps1`, entre `30-steam.ps1` et `35-shares.ps1`. Elle :

1. lit `config/retro.psd1` ; si le retrogaming n'est pas coché, **écrit
   pourquoi elle s'arrête** et sort en succès ;
2. installe Python sur la VM ;
3. dépose `7zr.exe` — **sans lui, RetroArch ne s'installe pas** : ses archives
   utilisent un filtre de compression que la bibliothèque Python ne sait pas
   lire, et il n'existe aucune variante dans un autre format. C'est une
   exigence, pas une commodité ;
4. installe le paquet `retro` ;
5. exécute `retro install`.

Elle **n'exécute pas** `retro sync` : les partages ne sont montés qu'à l'étape
35, donc le dossier des ROMs n'existe pas encore. La première synchronisation
a lieu au premier déclenchement depuis l'hôte.

Deux prérequis mesurés, tous deux dans la spec, qui doivent être **vérifiés par
l'étape et non supposés** :

- `%TEMP%` doit disposer d'au moins 1,5 Gio libre. L'installation y fait
  transiter environ 1,3 Gio, sur la partition système qui n'est pas celle des
  jeux. Une VM au disque système étroit échoue au milieu du provisionnement, et
  le message doit dire exactement cela plutôt que de laisser lire un manque
  d'espace générique.
- Le volume persistant doit exister — c'est là que les émulateurs s'installent.

- [ ] **Étape 2 : le payload**

`7zr.exe` et le paquet `retro` doivent arriver sur la VM. Suivre la mécanique
existante de `fetch_payload.py`, qui récupère déjà Steam, Apollo et les pilotes
avec leurs empreintes.

**Ces téléchargements ne doivent avoir lieu que si l'option est cochée** : le
payload d'une installation sans retrogaming n'a pas à grossir de plusieurs
centaines de mégaoctets.

- [ ] **Étape 3 : les tests**

Vérifier, dans le style du dépôt : que l'étape figure dans la liste de
`run-all.ps1` ; qu'elle sort proprement quand l'option est absente ; qu'elle
vérifie l'espace temporaire ; qu'elle dépose `7zr.exe`.

---

## Tâche 5 : le déclenchement depuis l'hôte

**Fichiers :**
- Créer : le script hôte qui synchronise la bibliothèque
- Modifier : les tests correspondants

- [ ] **Étape 1 : la séquence**

Sur le modèle de `testdomain.py`, qui parle déjà à la VM :

1. `retro install` — reprend le manifeste du propriétaire, désormais lisible
   sur le partage. Steam tourne encore, cette étape ne le touche pas ;
2. poser `C:\nivuus\state\steam.hold` ;
3. arrêter Steam ;
4. `retro sync` ;
5. **retirer la sentinelle — quoi qu'il arrive**, y compris si l'étape 4
   échoue ;
6. relayer le rapport.

L'étape 5 dans un `finally`, et l'expiration de cinq minutes couvre le cas où
l'hôte lui-même disparaît en cours de route.

- [ ] **Étape 2 : refuser proprement quand le retrogaming n'est pas installé**

Le script doit dire que la fonctionnalité n'est pas activée, plutôt que
d'échouer sur une commande introuvable.

---

## Vérification finale

- [ ] **Les tests du dépôt hôte passent**

```bash
for t in scripts/tests/test_windows_guest_*.py; do python3 "$t" || echo "ÉCHEC: $t"; done
```

- [ ] **Une installation sans retrogaming reste identique à aujourd'hui**

C'est la vérification qui compte le plus, et elle découle directement de la
contrainte : rien de ce plan ne doit changer le comportement d'une machine dont
le propriétaire n'a pas coché la case — hormis les deux correctifs
inconditionnels, qui réparent des trous existants.

- [ ] **Aucun fichier hors périmètre modifié**

```bash
git diff --stat main..HEAD
```

## Ce que ce sous-projet ne fait pas

- **Les configurations Steam Input** — le point à mesurer en premier sur la
  vraie machine : rien ne prouve hors ligne qu'une configuration déposée dans
  le dossier des contrôleurs soit reprise telle quelle. À traiter quand la
  console tournera, avec une manette en main.
- **Les huit profils standalone** — sous-projet D.
