"""Les données livrées avec le paquet.

Ce test est la seule chose qui empêche une faute de frappe dans un TOML de
n'être découverte que sur la console du propriétaire.
"""
import fnmatch
import importlib.resources
import pathlib
import re
import subprocess
import tomllib

import pytest

from retro import cli, install, manifest, profiles

RACINE = pathlib.Path(__file__).parent.parent

# Les données vivent DANS le paquet, et ce test les atteint comme le code les
# atteint : par importlib.resources. Les localiser depuis la racine du dépôt
# laissait passer le défaut qui rendait « retro scan » inutilisable sur un
# wheel installé — les fichiers étaient bien versionnés, simplement pas là où
# le paquet installé allait les chercher.
DONNEES = pathlib.Path(str(importlib.resources.files("retro"))) / "data"
CORE = DONNEES / "manifests" / "core.toml"
PROFILS = DONNEES / "profiles"

# Aucun fichier versionné ne référence de nom d'émulateur au statut contesté :
# le dépôt est public et sa politique l'exclut. Cette liste est le garde-fou
# automatique. Les forks du projet fermé en 2024 y figurent aussi : le nom
# change, le statut non.
INTERDITS = ("ryujinx", "yuzu", "citron", "sudachi", "switch", "ryubing",
             "suyu", "torzu", "uzuy", "eden", "kefir", "strato", "skyline")

# Les émulateurs QUE LE MANIFESTE CONNAÎT SANS LES ÉPINGLER. Leur empreinte
# est vide, ce qui veut dire « pas encore relevée » : `acquire` les refuse
# avant de télécharger quoi que ce soit, et `retro scan` ignore puis SIGNALE
# leurs systèmes, faute d'émulateur installé.
#
# C'est une réponse, pas un oubli : une empreinte inventée passerait la revue
# et casserait à l'installation, sur la console, sans que rien n'explique
# pourquoi. La liste est gelée par test_le_garde_fou_ne_se_raccourcit_pas —
# en allonger une est un acte explicite, qui se voit en revue.
EMPREINTES_A_RELEVER = frozenset({"vita3k"})

# Les documents qui ÉNONCENT la politique doivent pouvoir nommer ce qu'ils
# excluent : sans cela, la raison de l'exclusion n'est écrite nulle part. Ce
# sont les seules exemptions, nominatives, et gelées par
# test_le_garde_fou_ne_se_raccourcit_pas : en ajouter une se voit en revue,
# contrairement à retirer discrètement un nom d'INTERDITS.
EXEMPTES = frozenset({
    "tests/test_donnees.py",
    "docs/superpowers/specs/2026-08-26-retro-console-design.md",
    "docs/superpowers/plans/2026-08-26-emulateurs-sous-projet-a.md",
})

# Un gabarit launch est une ligne de commande Windows : des jetons séparés par
# des espaces, ceux qui portent un chemin étant guillemetés.
_JETON = re.compile(r'"([^"]*)"|(\S+)')


def _jetons(gabarit: str) -> list[str]:
    return [guillemete or nu for guillemete, nu in _JETON.findall(gabarit)]


def _est_sous(chemin: pathlib.PureWindowsPath,
              dossier: pathlib.PureWindowsPath) -> bool:
    return chemin.parts[:len(dossier.parts)] == dossier.parts


def test_le_manifeste_noyau_se_charge():
    m = manifest.load_manifest(CORE)
    assert m, "le manifeste noyau est vide"


def test_les_profils_se_chargent():
    p = profiles.load_profiles(PROFILS)
    assert p


def test_les_donnees_vivent_dans_le_paquet():
    """Un wheel installé ne voit que ce qui est DANS le paquet.

    Mesuré : avec les données à la racine du dépôt et data-files, un wheel
    installé dans un venv neuf faisait pointer DEFAULT_MANIFEST sur
    site-packages/manifests/core.toml, qui n'existe pas — « retro scan » et
    « retro install » étaient inutilisables. Le mode éditable, où __file__
    reste dans le dépôt, masquait entièrement le défaut.
    """
    paquet = pathlib.Path(str(importlib.resources.files("retro")))
    assert CORE.is_file(), f"manifeste noyau absent du paquet : {CORE}"
    assert sorted(f.name for f in PROFILS.glob("*.toml")), "aucun profil livré"
    # Et le code doit les chercher là, pas ailleurs.
    assert cli.DEFAULT_MANIFEST == CORE
    assert cli.DEFAULT_PROFILES == PROFILS
    assert paquet in cli.DEFAULT_MANIFEST.parents, (
        f"{cli.DEFAULT_MANIFEST} est hors du paquet {paquet}"
    )


def test_chaque_fichier_de_donnees_est_emporte_par_le_wheel():
    """Vivre dans l'arbre ne suffit pas : sans package-data, setuptools laisse
    les .toml derrière lui et l'installation retombe sur le défaut d'origine.
    """
    conf = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    motifs = conf["tool"]["setuptools"]["package-data"]["retro"]
    paquet = RACINE / "retro"
    oublies = [
        str(f.relative_to(paquet))
        for f in sorted((paquet / "data").rglob("*")) if f.is_file()
        if not any(fnmatch.fnmatch(str(f.relative_to(paquet)), m) for m in motifs)
    ]
    assert oublies == [], f"données hors de package-data : {oublies}"


def test_chaque_emulateur_a_son_profil():
    """Un émulateur sans profil s'installe et ne lance jamais rien."""
    m = manifest.load_manifest(CORE)
    p = profiles.load_profiles(PROFILS)
    orphelins = [e.key for e in m.values() if e.profile not in p]
    assert orphelins == [], f"émulateurs sans profil : {orphelins}"


def test_chaque_profil_a_son_emulateur():
    """Un profil sans émulateur déclare des systèmes que rien ne peut lancer."""
    m = manifest.load_manifest(CORE)
    utilises = {e.profile for e in m.values()}
    p = profiles.load_profiles(PROFILS)
    orphelins = sorted(set(p) - utilises)
    assert orphelins == [], f"profils sans émulateur au manifeste : {orphelins}"


def test_les_empreintes_ont_la_bonne_forme():
    """Un sha256 tronqué ou remplacé par un espace réservé ne protège de rien.

    Les archives supplémentaires sont vérifiées de la même façon : celle qui
    porte les cores de RetroArch pèse plus que l'archive principale, et une
    empreinte fantaisiste y serait tout aussi aveugle.
    """
    for e in manifest.load_manifest(CORE).values():
        if e.key in EMPREINTES_A_RELEVER:
            # Non épinglé, et il le DIT : l'empreinte est vide, la version
            # aussi. Les deux se relèvent ensemble, sur la même archive.
            assert e.sha256 == "", (
                f"{e.key} est déclaré à relever mais porte une empreinte : "
                "la retirer de EMPREINTES_A_RELEVER"
            )
            assert e.version == "", (
                f"{e.key} : empreinte à relever mais version épinglée. Les "
                "deux décrivent la MÊME archive et se relèvent ensemble — une "
                "version sans empreinte laisserait croire à un pinning."
            )
            continue
        for quoi, sha in [(e.key, e.sha256)] + [
            (f"{e.key} parts[{i}]", p.sha256) for i, p in enumerate(e.parts)
        ]:
            assert len(sha) == 64, f"{quoi} : sha256 de {len(sha)} caractères"
            assert all(c in "0123456789abcdef" for c in sha.lower()), quoi


def test_une_entree_non_epinglee_ne_s_installe_pas():
    """Le refus est mesuré sur le manifeste LIVRÉ, pas sur une fixture.

    C'est la garantie qui rend l'entrée acceptable dans un dépôt public : un
    binaire que rien ne vérifie ne s'installe pas, et rien n'est téléchargé.
    """
    from retro import acquire

    m = manifest.load_manifest(CORE)
    assert EMPREINTES_A_RELEVER <= set(m), (
        f"EMPREINTES_A_RELEVER nomme des clés absentes du manifeste : "
        f"{sorted(EMPREINTES_A_RELEVER - set(m))}"
    )
    for cle in sorted(EMPREINTES_A_RELEVER):
        appels = []
        with pytest.raises(acquire.AcquireError) as exc:
            acquire.acquire(m[cle], pathlib.Path("/nexiste/pas"),
                            fetch=lambda u: appels.append(u) or b"")
        assert appels == [], f"{cle} : l'archive a été téléchargée"
        assert "empreinte" in str(exc.value).lower()


def test_une_entree_non_epinglee_dit_dans_le_manifeste_ce_qui_manque():
    """Une empreinte vide sans un mot se lit comme une faute de frappe.

    Le commentaire qui précède l'entrée doit dire ce qui manque et comment le
    relever — sinon le prochain lecteur la « corrige » en recopiant une
    empreinte trouvée sur une page, ce que ce manifeste s'interdit.
    """
    lignes = CORE.read_text(encoding="utf-8").splitlines()
    for cle in sorted(EMPREINTES_A_RELEVER):
        entete = f"[emulator.{cle}]"
        i = next((n for n, l in enumerate(lignes) if l.strip() == entete), None)
        assert i is not None, f"{entete} absent du manifeste noyau"
        commentaire = []
        n = i - 1
        while n >= 0 and lignes[n].lstrip().startswith("#"):
            commentaire.append(lignes[n])
            n -= 1
        texte = "\n".join(commentaire).lower()
        assert "relev" in texte, (
            f"{entete} : le commentaire qui la précède ne dit pas que "
            "l'empreinte reste à relever, ni comment"
        )


def test_les_url_sont_en_https():
    for e in manifest.load_manifest(CORE).values():
        assert e.url.startswith("https://"), f"{e.key} : {e.url}"
        for i, p in enumerate(e.parts):
            assert p.url.startswith("https://"), f"{e.key} parts[{i}] : {p.url}"


def test_les_gabarits_launch_suivent_la_structure_de_l_archive():
    """Les chemins d'un gabarit sont relatifs au dossier d'installation.

    Rien ne les reliait à l'archive : retirer le préfixe « RetroArch-Win64\\ »
    des neuf gabarits, ou viser un core qui n'en est pas un, laissait les tests
    de données verts — et le raccourci Steam échouait en silence sur la
    console. La règle est déduite du profil lui-même (le dossier racine de son
    exe), donc elle vaut pour tout profil futur, RetroArch ou non ; un profil
    sans « -L », comme Dolphin, n'a simplement rien à vérifier de ce côté.

    Ce que ce test NE prouve pas : que le core existe dans l'archive. Le
    vérifier exigerait de télécharger 200 Mo, et aucun test d'ici ne touche au
    réseau.
    """
    for pid, p in profiles.load_profiles(PROFILS).items():
        dossier = pathlib.PureWindowsPath(p.exe).parent
        for s in p.systems:
            jetons = _jetons(s.launch)
            for j in jetons:
                if "\\" not in j:
                    continue
                assert _est_sous(pathlib.PureWindowsPath(j), dossier), (
                    f"{pid}/{s.id} : « {j} » ne part pas de « {dossier} », le "
                    f"dossier racine de exe = « {p.exe} »"
                )
            for i, j in enumerate(jetons):
                if j != "-L":
                    continue
                assert i + 1 < len(jetons), f"{pid}/{s.id} : -L sans argument"
                core = pathlib.PureWindowsPath(jetons[i + 1])
                assert _est_sous(core, dossier / "cores"), (
                    f"{pid}/{s.id} : le core « {jetons[i + 1]} » n'est pas dans "
                    f"« {dossier / 'cores'} »"
                )
                assert core.name.endswith("_libretro.dll"), (
                    f"{pid}/{s.id} : « {core.name} » n'est pas un core libretro"
                )


def test_le_garde_fou_ne_se_raccourcit_pas():
    """Sans cette assertion, retirer un nom d'INTERDITS — ou ajouter une
    exemption — suffisait à faire taire le garde-fou sans qu'aucun test ne le
    remarque. La liste est donc gelée : la modifier est un acte explicite."""
    assert set(INTERDITS) == {
        "ryujinx", "yuzu", "citron", "sudachi", "switch", "ryubing",
        "suyu", "torzu", "uzuy", "eden", "kefir", "strato", "skyline",
    }
    assert EMPREINTES_A_RELEVER == {"vita3k"}
    assert EXEMPTES == {
        "tests/test_donnees.py",
        "docs/superpowers/specs/2026-08-26-retro-console-design.md",
        "docs/superpowers/plans/2026-08-26-emulateurs-sous-projet-a.md",
    }
    # Dette D10 : cette quatrieme liste exempte un profil de dire ou en est sa
    # vibration. Elle etait la seule des quatre a ne pas etre gelee, et le
    # raisonnement de la docstring ci-dessus valait pourtant mot pour mot :
    # mesure le 2026-08-29, y reinscrire un profil laissait la suite ENTIEREMENT
    # verte. Elle est vide, et le redevenir doit rester un acte explicite.
    assert SANS_NOTE_DE_VIBRATION == frozenset()


def test_aucun_emulateur_au_statut_conteste():
    """Le dépôt est public. Cette politique est écrite dans la spec ; ce test
    est ce qui l'applique, plutôt que la vigilance d'un relecteur.

    La portée est TOUT le versionné : le README, retro/*.py et docs/ sont
    aussi publics que manifests/ et profiles/, et n'étaient vus par rien.
    """
    # La portée est déduite de git, pas d'une liste tenue à la main : un
    # fichier ajouté au dépôt entre d'office dans le champ du garde-fou.
    try:
        sortie = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE,
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        # Échec franc plutôt que skip : un garde-fou qu'on ne remarque pas
        # avoir cessé de tourner ne garde rien.
        raise AssertionError(
            "ce test énumère les fichiers versionnés et exige donc une copie "
            f"de travail git : {exc}"
        ) from exc
    fichiers = [f for f in sortie.split("\0") if f]
    assert len(fichiers) > 20, "git ls-files n'a rien rendu : ce test ne prouve rien"

    trouves = []
    for rel in fichiers:
        chemin = RACINE / rel
        if rel in EXEMPTES or not chemin.is_file():
            continue
        # La fixture .vdf est binaire ; ce qui s'y décode en texte est
        # précisément ce qu'il faut inspecter, le reste est ignoré.
        texte = chemin.read_bytes().decode("utf-8", errors="ignore").lower()
        trouves += [f"{rel} : {mot}" for mot in INTERDITS if mot in texte]
    assert trouves == [], f"références interdites : {trouves}"


def test_les_identifiants_de_systeme_sont_uniques_entre_profils():
    """Deux profils qui revendiquent le même système rendraient le scan
    dépendant de l'ordre de chargement."""
    vus = {}
    for pid, p in profiles.load_profiles(PROFILS).items():
        for s in p.systems:
            assert s.id not in vus, f"{s.id} revendiqué par {vus.get(s.id)} et {pid}"
            vus[s.id] = pid


# --- Le dépôt est public : une promesse fausse est un échec déguisé --------

README = RACINE / "README.md"
NOMBRES = {1: "une", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq",
           6: "six", 7: "sept", 8: "huit"}


def _commandes() -> set[str]:
    """Les sous-commandes réellement offertes, lues de l'analyseur lui-même."""
    import argparse
    sous = next(a for a in cli._build_parser()._actions
                if isinstance(a, argparse._SubParsersAction))
    return set(sous.choices)


def test_le_readme_annonce_toutes_les_commandes():
    """`retro status` était absente du README, et c'est la seule commande
    faite pour un humain. Une commande que rien n'annonce n'existe pour
    personne."""
    texte = README.read_text(encoding="utf-8")
    commandes = _commandes()
    oubliees = sorted(c for c in commandes if f"`retro {c}`" not in texte)
    assert oubliees == [], f"commandes absentes du README : {oubliees}"


def test_le_readme_compte_juste_ses_commandes():
    """« Trois commandes » alors qu'il y en a quatre : le compte lui-même
    doit suivre l'analyseur."""
    texte = README.read_text(encoding="utf-8").lower()
    n = len(_commandes())
    assert f"{NOMBRES[n]} commandes" in texte, (
        f"le README doit annoncer « {NOMBRES[n]} commandes »"
    )
    faux = [m for k, m in NOMBRES.items() if k != n and f"{m} commandes" in texte]
    assert faux == [], f"compte faux dans le README : {faux}"


def test_le_readme_dit_a_quoi_sert_la_verification_des_bios():
    """Le cœur de ce sous-projet n'était mentionné nulle part."""
    texte = README.read_text(encoding="utf-8").lower()
    assert "bios" in texte.split("## ce que ça fait")[1].split("##")[0], (
        "la vérification des BIOS n'est pas décrite avec les commandes"
    )


def test_le_readme_ne_promet_pas_un_classement_que_rien_ne_produit():
    """`retro/metadata.py` n'est importé par aucun module de production, et
    `scan` écrit `extra_tags=()` en dur : les seuls tags écrits sont « Rétro »
    et le système. Le README promettait pourtant un classement « par décennie
    et par genre ». Sur un dépôt public, la promesse elle-même est un échec
    déguisé en réussite.

    Ce test se désarme tout seul le jour où le module est câblé.
    """
    production = [f for f in sorted((RACINE / "retro").rglob("*.py"))
                  if f.name != "metadata.py"]
    cable = any("metadata" in f.read_text(encoding="utf-8") for f in production)
    if cable:
        return
    lignes = README.read_text(encoding="utf-8").splitlines()
    for i, ligne in enumerate(lignes):
        if "décennie" not in ligne.lower() and "genre" not in ligne.lower():
            continue
        contexte = " ".join(lignes[max(0, i - 3):i + 4]).lower()
        assert "pas encore actif" in contexte or "n'est pas actif" in contexte, (
            f"README ligne {i + 1} : promesse de classement sans mention que "
            f"ce n'est pas encore actif — « {ligne.strip()} »"
        )


def test_le_depot_porte_le_texte_de_sa_licence():
    """pyproject déclare MIT et le README dit « MIT. », mais le dépôt n'en
    contenait aucun texte. La licence MIT exige la distribution de sa notice :
    sans elle, la licence annoncée n'est pas concédée."""
    licence = RACINE / "LICENSE"
    assert licence.is_file(), "aucun fichier LICENSE à la racine du dépôt"
    texte = licence.read_text(encoding="utf-8")
    for attendu in ("MIT", "Maxime Allanic", "2026", "WITHOUT WARRANTY"):
        assert attendu in texte, f"LICENSE : « {attendu} » absent"
    conf = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
    assert conf["project"]["license"]["text"] == "MIT"


def test_la_licence_est_versionnee():
    """Un LICENSE non versionné ne protège que la copie de travail."""
    sortie = subprocess.run(["git", "ls-files", "-z", "LICENSE"], cwd=RACINE,
                            capture_output=True, text=True, check=True).stdout
    assert [f for f in sortie.split("\0") if f] == ["LICENSE"]


def test_les_bios_playstation_sont_interchangeables():
    """Un des trois suffit, celui de la région des jeux — c'est ce que dit le
    commentaire du profil depuis toujours. Déclarés `required = true` un par
    un, le rapport disait « MANQUANT : scph5500.bin » et « MANQUANT :
    scph5502.bin » à quelqu'un qui venait de déposer scph5501.bin, le bon.

    Le système « psx » a quitté RetroArch pour DuckStation ; le groupe l'a
    suivi. Ce test est écrit pour SUIVRE le système, pas le profil : c'est le
    besoin PlayStation qui doit rester groupé, quel que soit l'émulateur qui
    le sert un jour.
    """
    psx = next(s for p in profiles.load_profiles(PROFILS).values()
               for s in p.systems if s.id == "psx")
    groupes = {b.get("group") for b in psx.bios}
    assert groupes == {"psx-region"}, (
        f"les trois BIOS PlayStation ne forment pas un groupe : {groupes}"
    )
    assert all(b.get("region") for b in psx.bios), (
        "sans region, le rapport ne peut pas dire lequel des trois déposer"
    )


def test_toute_region_declaree_appartient_a_un_groupe():
    """`region` n'a de sens que pour départager les membres d'un groupe :
    ailleurs, c'est une clé que personne ne lit."""
    orphelines = [
        f"{pid}/{s.id}/{b['file']}"
        for pid, p in profiles.load_profiles(PROFILS).items()
        for s in p.systems for b in s.bios
        if b.get("region") and not b.get("group")
    ]
    assert orphelines == [], f"region sans group : {orphelines}"


def test_les_profils_livres_resolvent_en_chemin_local():
    """Le pont qui manquait entre les données livrées et le code qui les lit.

    Rien ne reliait `exe` — tel qu'il est écrit dans les profils du dépôt — à
    la fonction qui le traduit en chemin local. La correspondance tenait par
    convention, et c'est exactement ce qui a laissé passer le défaut : les
    fixtures portaient « retroarch.exe », les profils livrés
    « RetroArch-Win64\\retroarch.exe », et sous Linux le second ne se résout
    pas comme le premier. Aucun test n'aurait vu la différence.
    """
    charges = profiles.load_profiles(PROFILS)
    assert charges, "aucun profil livré : ce test ne prouve rien"
    composes = 0
    for pid, profil in charges.items():
        chemin = install.emulator_exe(pathlib.Path("/Emulation"), "Dir", profil.exe)
        assert "\\" not in str(chemin), \
            f"{pid} : séparateur Windows non traduit dans {chemin}"
        assert chemin.name.lower().endswith(".exe"), f"{pid} : {chemin}"
        composes += len(pathlib.PurePosixPath(str(chemin)).parts) > 4
    # Les archives officielles ont un dossier racine : au moins un profil livré
    # porte donc un exe en PLUSIEURS composants. Si ce compte tombe à zéro, les
    # fixtures plates redeviennent représentatives — et le trou se rouvre.
    assert composes, "aucun profil livré n'exerce la traduction des séparateurs"


def test_chaque_gabarit_livre_guillemete_la_rom():
    """Un chemin de ROM porte des espaces : « Halo 2 (USA).iso ».

    Non guillemeté dans le gabarit, il arrive à l'émulateur découpé en
    plusieurs arguments — l'émulateur ne trouve pas le fichier, ou pire,
    s'ouvre sur son propre menu et la console a l'air de fonctionner. Rien
    d'autre ici ne le verrait : `load_profile` n'exige que la PRÉSENCE de
    {rom}, pas ses guillemets, et les fixtures des autres tests n'ont pas
    d'espace dans leurs noms.
    """
    nus = [
        f"{pid}/{s.id}"
        for pid, p in profiles.load_profiles(PROFILS).items()
        for s in p.systems if '"{rom}"' not in s.launch
    ]
    assert nus == [], f"gabarits dont {{rom}} n'est pas guillemeté : {nus}"


def test_chaque_profil_livre_lance_en_plein_ecran():
    """Un émulateur qui s'ouvre en fenêtre sur un écran de télévision est une
    panne silencieuse : le jeu tourne, personne ne le voit en entier, et rien
    ne dit qu'une option manque.

    Le vocabulaire diffère d'un émulateur à l'autre — -fullscreen, -f,
    -full-screen, --fullscreen, ou une valeur de configuration transitoire
    chez Flycast — donc la garde est délibérément large : elle exige que le
    mot apparaisse, pas qu'il prenne une forme précise. Elle attrape le seul
    défaut qui compte, l'oubli pur et simple.
    """
    sans = [
        f"{pid}/{s.id}"
        for pid, p in profiles.load_profiles(PROFILS).items()
        for s in p.systems
        if "fullscreen" not in s.launch.replace("-", "").lower()
        and " -f " not in f" {s.launch} "
    ]
    assert sans == [], f"gabarits sans plein écran : {sans}"


def test_le_dossier_racine_de_cemu_suit_la_version_du_manifeste():
    """Cemu est le seul émulateur livré dont le dossier racine d'archive porte
    le numéro de version : `Cemu_2.6\\`.

    Faire monter le manifeste à la version suivante sans toucher au profil
    ferait pointer Steam sur `Cemu_2.6\\Cemu.exe`, qui n'existerait plus — et
    le seul symptôme serait un raccourci qui ne démarre pas. Retirer le
    préfixe entier aurait le même effet.

    Rien d'autre ne le verrait : `test_les_profils_livres_resolvent_en_chemin_
    local` se contente qu'UN profil livré ait un exe en plusieurs composants,
    et RetroArch et Dolphin le lui donnent déjà — un Cemu redevenu plat y
    passerait inaperçu. Mesuré : la mutation `exe = 'Cemu.exe'` laissait tout
    le fichier vert.
    """
    version = manifest.load_manifest(CORE)["cemu"].version
    exe = profiles.load_profiles(PROFILS)["cemu"].exe
    racine = pathlib.PureWindowsPath(exe).parts[0]
    assert racine == f"Cemu_{version}", (
        f"le profil Cemu part de « {racine} » alors que le manifeste déclare "
        f"la version {version} : l'archive dépose ses fichiers dans "
        f"« Cemu_{version}\\ ». Corriger exe = « {exe} »."
    )


# --- le script de compilation du lanceur --------------------------------

def test_le_script_de_compilation_n_est_pas_en_utf8():
    r"""cmd.exe coupe une ligne sur un caractère UTF-8, y compris en commentaire.

    Mesuré sur la VM le 2026-08-27 : le script a compilé le lanceur
    CORRECTEMENT tout en crachant huit « 'ucun' is not recognized as an
    internal or external command » venus de ses propres `rem`. Une réussite qui
    a l'air d'un échec est aussi mauvaise que l'inverse — et personne n'aurait
    lu la seule ligne qui comptait au milieu des huit autres.

    En page de code 8 bits, chaque caractère tient sur un octet : le parsing
    est sûr. Le test porte sur l'ENCODAGE et non sur l'absence d'accents, pour
    que le script reste écrit en français correct.
    """
    from retro import launcher
    octets = (launcher.SOURCES / "compiler.cmd").read_bytes()
    # Décodable en cp850 : c'est la condition qui rend le parsing sûr.
    texte = octets.decode("cp850")
    assert "csc.exe" in texte
    # Et surtout PAS de séquence multi-octets UTF-8, qui serait le défaut
    # mesuré : un « é » y vaut deux octets, dont cmd coupe la ligne.
    accentues = [o for o in octets if o > 127]
    assert b"\xc3" not in octets and b"\xe2" not in octets, (
        "le script semble encodé en UTF-8 : cmd.exe couperait ses lignes")
    assert accentues, ("le script a perdu ses accents — l'encodage cp850 les "
                       "porte, il n'y a pas à les remplacer")


def test_la_source_du_lanceur_est_en_utf8_avec_bom():
    """csc.exe lit un .cs dans la page de code locale SANS BOM : les messages
    d'erreur que le lanceur affiche au propriétaire y perdraient leurs accents,
    sur sa télévision et dans son journal."""
    from retro import launcher
    octets = (launcher.SOURCES / launcher.SOURCE).read_bytes()
    assert octets.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 absent"
    octets.decode("utf-8-sig")


def test_le_lanceur_n_envoie_jamais_vers_retro_sync():
    """C'est `retro scan` qui écrit les plans de lancement — `cli._cmd_scan`
    est le seul appelant de `launcher.ecrire_plan`. Trois diagnostics du
    lanceur disaient pourtant « relancer retro sync », dont celui qu'un
    lanceur neuf produit sur un plan écrit par une version antérieure : le
    propriétaire lançait `retro sync`, rien ne changeait, et le message
    revenait à l'identique au lancement suivant.

    Le contrôle porte sur TOUT le fichier, commentaires compris : la
    correction ne tient que si personne ne réintroduit la formule.
    """
    from retro import launcher
    texte = (launcher.SOURCES / launcher.SOURCE).read_text(encoding="utf-8-sig")
    fautives = [f"ligne {n + 1} : {l.strip()}"
                for n, l in enumerate(texte.splitlines()) if "retro sync" in l]
    assert fautives == [], (
        "retro-launch.cs envoie vers « retro sync » alors que c'est "
        "« retro scan » qui écrit les plans : " + " | ".join(fautives)
    )


def test_chaque_profil_livre_dit_ou_en_est_son_amorcage():
    """« Un bloc absent sans explication ne se distingue pas d'un bloc
    oublié » (la conception de l'amorçage), et `retro status` renvoie
    justement au profil : « aucune configuration à poser (voir son profil) ».
    Un profil muet envoie donc le propriétaire lire une page qui ne dit rien —
    neuf fois de suite, ce qui était l'état livré.

    Le test se désarme profil par profil : celui qui PORTE un bloc n'a plus
    rien à expliquer.
    """
    for f in sorted(PROFILS.glob("*.toml")):
        if profiles.load_profile(f).bootstraps:
            continue
        commentaires = "\n".join(l for l in f.read_text(encoding="utf-8").splitlines()
                                 if l.lstrip().startswith("#"))
        assert "[bootstrap]" in commentaires, (
            f"{f.name} : aucun commentaire ne dit pourquoi ce profil n'a pas "
            "de bloc [[bootstrap]]"
        )
        assert "mesur" in commentaires.lower(), (
            f"{f.name} : le commentaire ne dit pas que l'amorçage reste à "
            "mesurer sur la machine — sans quoi rien ne distingue « pas "
            "encore regardé » de « cet émulateur se débrouille »"
        )


# Les valeurs de ratio qui ÉTIRENT l'image, lues dans les révisions épinglées
# au manifeste. Ce sont les seules déformations que ces deux émulateurs
# savent produire, et aucune n'est sur l'axe du remplissage : les nommer ici
# ferme la porte à celui qui, cherchant à « remplir davantage », les prendrait
# pour la solution.
#   - RetroArch 1.22.2 : ASPECT_RATIO_FULL, dernière valeur de l'enum
#     aspect_ratio de gfx/video_defines.h, soit l'indice 24 ;
#   - Dolphin 2606a : AspectMode::Stretch = 3 et AspectMode::CustomStretch = 5
#     dans Source/Core/VideoCommon/VideoConfig.h.
ETIREMENTS = (
    'aspect_ratio_index = "24"',
    "AspectRatio=3",
    "AspectRatio=5",
)


def _modes_livres():
    """Chaque mode de rendu déclaré par un profil livré, nommé."""
    for pid, p in sorted(profiles.load_profiles(PROFILS).items()):
        for s in p.systems:
            if s.render is None:
                continue
            yield f"{pid}/{s.id}/native", s.render.native
            yield f"{pid}/{s.id}/full", s.render.full


def test_aucun_reglage_livre_n_etire_l_image():
    """L'objectif de la console est « le plus possible de l'écran SANS étirer
    l'image ». Les deux émulateurs qui pilotent leur rendu savent étirer ;
    aucun réglage livré ne doit le demander, et un jour où quelqu'un
    confondrait « remplir » et « étirer », c'est ici que ça se verrait — pas
    sur la télévision."""
    fautifs = [
        f"{nom} : {mauvais}"
        for nom, mode in _modes_livres()
        for mauvais in ETIREMENTS
        if mauvais in mode.args + mode.crt + mode.config
    ]
    assert fautifs == [], f"réglages qui déforment l'image : {fautifs}"


def test_chaque_mode_livre_tranche_sur_le_remplissage():
    """Le troisième axe de la dette D2. Un mode qui ne le tranche pas laisse
    l'émulateur décider seul du cadrage : sur neuf émulateurs configurés par
    neuf équipes, ce n'est pas une console, c'est neuf comportements.

    Le test se désarme mode par mode, comme celui de l'amorçage : un mode
    déclaré VIDE ne passe rien à l'émulateur — il n'a pas de remplissage à
    régler, et sa 'note' dit déjà pourquoi.
    """
    from retro import render

    muets = [nom for nom, mode in _modes_livres()
             if render.resoudre_remplissage(nom.rsplit("/", 1)[1],
                                            mode).remplissage
             == render.NON_MESURE]
    assert muets == [], (
        "modes de rendu livrés qui ne disent rien du remplissage : "
        f"{muets}. Déclarer 'fill' — les arguments qui le règlent existent — "
        "ou 'fill_absent', qui dit que cet émulateur n'en expose aucun."
    )


# Ce que la console IMPOSE dans le settings.ini de DuckStation, arbitré par le
# propriétaire le 2026-08-29 : ces clés, et pas une de plus. Sans elles, un jeu
# ne démarre pas sans clavier — l'assistant de première configuration ou la
# fenêtre de mise à jour s'ouvrent par-dessus, et le plein écran manque — ou il
# démarre sans qu'aucun bouton ne réponde. Tout le reste du bloc est une
# PRÉFÉRENCE, posée une fois puis laissée au propriétaire : la liste est ici
# pour qu'un ajout se voie en revue.
# L'ordre est celui du FICHIER, pas celui dans lequel ils ont été énoncés :
# regrouper les deux clés de [Main] évite de déclarer la section deux fois.
#
# [Pad1] A REJOINT L'ENSEMBLE IMPOSÉ le 2026-08-29, et cet élargissement a été
# décidé, pas subi. Deux raisons, et elles sont mesurées :
#
#   1. Sous « -batch -nogui » — le seul mode que la console emploie —
#      DuckStation ne rouvre jamais son settings.ini. Un régime « si-absent »
#      ne poserait donc ces liaisons sur AUCUNE console déjà jouée, où le
#      fichier existe déjà. Ce que la console doit garantir, c'est qu'un jeu
#      répond à la manette ; « si-absent » ne le garantit pas.
#   2. Ce n'est PAS une préférence reprise au propriétaire par mégarde : sans
#      ces vingt-sept lignes, la manette est muette — c'est la dette D3,
#      constatée le 2026-08-28 sur Crash Team Racing. Le prix, lui, est réel
#      et il est écrit dans le profil : le propriétaire ne peut plus remapper
#      sa manette depuis l'interface de DuckStation, puisque le lancement
#      suivant repose ces liaisons.
#
# Les vingt-sept LIAISONS sont celles que l'assistant de DuckStation a ÉCRITES
# lui-même le 2026-08-29 — ni plus, ni moins. Aucune clé « Type » : DuckStation
# n'en écrit pas, et la liste ne prétend pas mieux savoir.
#
# DEUX CLÉS ONT REJOINT L'ENSEMBLE IMPOSÉ le 2026-08-29 au soir, et cette garde
# a échoué avant d'être mise à jour — c'est son rôle. Ni l'une ni l'autre n'est
# une liaison, et ni l'une ni l'autre n'est une préférence :
#
#   · [Display] CropMode = Borders — sans elle, l'image porte des bandes que
#     personne ne peut retirer du canapé. Confirmé par le propriétaire.
#   · [Pad1] ForceAnalogOnReset = false — sans elle, Crash Team Racing ne
#     répond à AUCUN bouton, les vingt-sept liaisons fussent-elles justes.
#     Confirmé par le propriétaire : la manette répond dès le lancement.
#
# Le prix de la seconde est écrit dans le profil et il est réel : le réglage
# est GLOBAL, donc les jeux qui veulent l'analogique (Gran Turismo, Ape Escape,
# Metal Gear Solid) démarreront en mode numérique. La bascule reste mappée sur
# `Analog = SDL-0/Guide`.
DUCKSTATION_IMPOSE = (
    ("Main", "SetupWizardIncomplete"),
    ("Main", "StartFullscreen"),
    ("AutoUpdater", "CheckAtStartup"),
    # Ajoutée le 2026-08-29, dette D2 : le cadrage. `Borders` vient de la
    # SOURCE de DuckStation (src/core/settings.cpp, s_display_crop_mode_names)
    # et non des chaînes du binaire, qui ne donnent que les libellés de
    # l'interface — deux tentatives ont échoué là-dessus avant celle-ci.
    ("Display", "CropMode"),
    ("Pad1", "Analog"),
    ("Pad1", "Circle"),
    ("Pad1", "Cross"),
    ("Pad1", "Down"),
    # Ajoutée le 2026-08-29, dette D3, et ce n'est PAS une liaison : booléen,
    # défaut `true` dans src/core/analog_controller.cpp. Crash Team Racing est
    # un jeu d'avant l'analogique ; forcé en analogique il ne répond pas, les
    # vingt-sept liaisons ci-dessous fussent-elles justes.
    ("Pad1", "ForceAnalogOnReset"),
    ("Pad1", "L1"),
    ("Pad1", "L2"),
    ("Pad1", "L3"),
    ("Pad1", "LDown"),
    ("Pad1", "LLeft"),
    ("Pad1", "LRight"),
    ("Pad1", "LUp"),
    ("Pad1", "LargeMotor"),
    ("Pad1", "Left"),
    ("Pad1", "R1"),
    ("Pad1", "R2"),
    ("Pad1", "R3"),
    ("Pad1", "RDown"),
    ("Pad1", "RLeft"),
    ("Pad1", "RRight"),
    ("Pad1", "RUp"),
    ("Pad1", "Right"),
    ("Pad1", "Select"),
    ("Pad1", "SmallMotor"),
    ("Pad1", "Square"),
    ("Pad1", "Start"),
    ("Pad1", "Triangle"),
    ("Pad1", "Up"),
)


def _cles_ini(texte: str) -> list[tuple[str, str]]:
    """Les couples (section, clé) d'un fragment INI, dans l'ordre."""
    section, cles = "", []
    for ligne in texte.splitlines():
        nu = ligne.strip()
        if not nu or nu[0] in ";#":
            continue
        if nu.startswith("[") and nu.endswith("]"):
            section = nu[1:-1].strip()
        elif "=" in nu:
            cles.append((section, nu.split("=", 1)[0].strip()))
    return cles


def test_duckstation_n_impose_que_ce_que_le_proprietaire_a_approuve():
    """Élargir ce que la console impose, c'est reprendre au propriétaire un
    réglage qu'il croyait sien — et il ne s'en apercevrait qu'en le voyant
    revenir après l'avoir changé. L'ajout doit se voir en revue."""
    b, = profiles.load_profiles(PROFILS)["duckstation"].bootstraps
    assert tuple(_cles_ini(b.enforced)) == DUCKSTATION_IMPOSE


def test_aucune_preference_livree_n_est_reposee_a_chaque_lancement():
    """La règle générale dont la liste ci-dessus est le cas particulier :
    aucune clé ne doit être à la fois posée une fois et imposée."""
    fautifs = []
    for pid, p in sorted(profiles.load_profiles(PROFILS).items()):
        for b in p.bootstraps:
            if not b.enforced:
                continue
            deux = set(_cles_ini(b.content)) & set(_cles_ini(b.enforced))
            if deux:
                fautifs.append((pid, b.target, sorted(deux)))
    assert fautifs == [], f"clés dans les deux régimes : {fautifs}"


# --- Manettes livrées : ce qu'aucun profil n'a le droit d'inventer --------

def test_chaque_profil_livre_dit_ce_qu_il_sait_de_sa_manette():
    """Le défaut du code — « inconnu » — est le bon état d'un profil du
    propriétaire qui se tait. Il n'est PAS acceptable d'un profil livré : le
    lecteur de `retroarch.toml` doit pouvoir y lire si sa manette a été
    mesurée, sans aller déduire un silence d'une valeur par défaut écrite
    ailleurs. C'est la même exigence que le bloc [bootstrap] absent, qui doit
    dire pourquoi il est absent.
    """
    for f in sorted(PROFILS.glob("*.toml")):
        with f.open("rb") as fh:
            brut = tomllib.load(fh)
        assert "mapping" in brut.get("input", {}), (
            f"{f.name} : [input] ne déclare pas 'mapping'. Rien n'y distingue "
            "« cet émulateur trouve sa manette seul » de « personne n'a "
            "jamais regardé » — et c'est cette confusion qui a laissé "
            "DuckStation muet sur Crash Team Racing."
        )


def test_duckstation_declare_son_releve_clos_sans_pretendre_a_l_automatique():
    """Dette D3, close le 2026-08-29 — et le champ doit dire COMMENT.

    L'histoire tient en trois dates. Le 2026-08-28 : le jeu démarre, la manette
    ne répond pas, alors que le plan des manettes rangeait DuckStation parmi
    les émulateurs qui « détectent bien tout seuls ». Le 2026-08-29 au matin :
    les vingt-sept liaisons sont relevées, écrites par l'assistant de
    DuckStation lui-même, mais personne n'a encore vu un bouton agir. Le
    2026-08-29 : le propriétaire confirme que Crash Team Racing répond à la
    manette. Les trois conditions de la procédure sont remplies.

    LE CHAMP NE PEUT PAS VALOIR « auto », ET C'EST LE CŒUR DE CE TEST.
    « auto » veut dire « cet émulateur trouve sa manette seul » — c'est très
    exactement ce que D3 a réfuté. DuckStation ne la trouve que parce que la
    console lui impose vingt-huit clés de [Pad1]. Le jour où quelqu'un
    « simplifierait » ce champ en `auto`, plus rien dans le dépôt ne dirait
    que retirer `enforced` rend la console muette.

    Il ne peut pas valoir « a-relever » non plus : `retro status` annoncerait
    une manette muette sur le seul émulateur dont un bouton ait été VU agir.
    Ni « inconnu », qui effacerait la mesure. D'où le quatrième état.
    """
    profil = profiles.load_profile(PROFILS / "duckstation.toml")
    assert profil.input_mapping == profiles.MAPPING_RELEVE
    assert profil.input_mapping != profiles.MAPPING_AUTO
    assert "Pad1" in profil.input_mapping_where


def test_aucun_profil_livre_ne_pose_de_liaison_de_manette():
    """La garde de D3, et la seule mécanisable.

    Un relevé n'est valide que fait par l'émulateur lui-même, dans sa propre
    configuration, une fois le pad choisi dans son interface (plan des
    manettes, tâche 1 — quatre identifiants relevés pour une seule manette
    physique, un seul bon). Une liaison écrite d'après une recette est donc
    fausse, et son échec est INDISCERNABLE de l'absence de liaison :
    l'émulateur l'ignore sans un mot. Huit des neuf profils livrés n'ont
    toujours aucun relevé.

    DuckStation fait exception depuis le 2026-08-29, et l'exception est
    NOMMÉE : ses vingt-sept liaisons ont été écrites par son propre assistant,
    et elles vivent dans `enforced` — pas ici. `content` reste, pour les neuf
    profils, un endroit où aucune liaison de manette n'a le droit d'être : ce
    qu'on y poserait ne serait posé que sur une console qui n'a jamais joué.
    """
    for f in sorted(PROFILS.glob("*.toml")):
        profil = profiles.load_profile(f)
        if profil.input_mapping == profiles.MAPPING_AUTO:
            continue
        for b in profil.bootstraps:
            actives = [l.strip() for l in b.content.splitlines()
                       if l.strip() and not l.lstrip().startswith((";", "#"))]
            fautives = [l for l in actives if l.lower().startswith("bindings/")]
            assert fautives == [], (
                f"{f.name} : le bloc [[bootstrap]] visant {b.target} pose des "
                "liaisons de manette alors que son [input] mapping vaut "
                f"« {profil.input_mapping} » : " + " | ".join(fautives)
            )


def test_les_liaisons_de_duckstation_sont_imposees_et_non_posees_une_fois():
    """Le régime de [Pad1], et il n'est pas interchangeable.

    Le squelette entièrement commenté que ce test gardait jusqu'au 2026-08-29
    n'a plus lieu d'être : les liaisons ont été relevées, elles sont réelles,
    et elles vivent désormais dans `enforced`.

    `content` ne les poserait JAMAIS sur une console déjà jouée : le fichier y
    existe, et le régime « si-absent » passe son chemin. Or DuckStation ne
    rouvre jamais ce fichier sous « -batch -nogui » (mesuré le 2026-08-29 :
    cinq heures et demie de jeu sans une écriture), donc rien ne viendrait
    jamais réparer la manette. Les deux moitiés de ce test disent la même
    chose : [Pad1] est dans `enforced`, et NULLE PART dans `content`.
    """
    b, = profiles.load_profile(PROFILS / "duckstation.toml").bootstraps
    pad_impose = [c for s, c in _cles_ini(b.enforced) if s == "Pad1"]
    liaisons = [c for c in pad_impose if c != "ForceAnalogOnReset"]
    assert len(liaisons) == 27, (
        "duckstation.toml : `enforced` ne porte plus les vingt-sept liaisons "
        f"relevées le 2026-08-29, mais {len(liaisons)}. Elles ont été "
        "écrites par DuckStation lui-même ; en retirer une, c'est rendre un "
        "bouton muet sans qu'aucun message ne le dise."
    )
    # La vingt-huitième clé de [Pad1] n'est PAS une liaison, et elle est
    # exigée à part : sans elle, les vingt-sept ci-dessus sont justes et Crash
    # Team Racing ne répond à rien. Deux causes, un seul symptôme.
    assert "ForceAnalogOnReset" in pad_impose, (
        "duckstation.toml : [Pad1] n'impose plus ForceAnalogOnReset. Son "
        "défaut est `true` (src/core/analog_controller.cpp) et un jeu d'avant "
        "l'analogique ne répond alors à aucun bouton — la manette est muette "
        "exactement comme si les liaisons manquaient."
    )
    pad_pose = [c for s, c in _cles_ini(b.content) if s == "Pad1"]
    assert pad_pose == [], (
        "duckstation.toml : des liaisons de manette sont passées dans "
        "`content`, qui n'est posé que si le fichier est ABSENT. Sur une "
        f"console déjà jouée elles ne seraient jamais écrites : {pad_pose}"
    )


def test_la_procedure_de_releve_existe_et_est_atteignable():
    """`retro status` renvoie le propriétaire vers cette page : un renvoi qui
    ne mène nulle part est pire que pas de renvoi — il se lit comme une
    procédure existante que le lecteur n'arriverait pas à trouver."""
    from retro import status
    procedure = RACINE / "docs" / "releve-manettes.md"
    assert procedure.is_file(), f"{procedure} n'existe pas"
    assert status.PROCEDURE_RELEVE.endswith("releve-manettes.md")
    assert (RACINE / status.PROCEDURE_RELEVE).is_file()


def test_les_liaisons_de_duckstation_portent_la_forme_qu_il_a_ecrite():
    """La forme de `[Pad1]` n'est pas supposée : elle est RELEVÉE.

    Le 2026-08-29, sur l'invité NIVUUS-WIN (`provision_version` B1,
    DuckStation v0.1-11609), l'assistant de DuckStation a écrit lui-même ces
    lignes après un appariement automatique, pad virtuel d'Apollo branché. Ce
    test garde ce que ce relevé a TRANCHÉ, et refuse chacune des formes qui
    avaient été envisagées puis mesurées fausses ou non retenues :

      - des clés `Bindings/…` — c'est la forme de PCSX2, absente du binaire de
        DuckStation, et `docs/dettes.md` la supposait à tort ;
      - `XInput-0/…` — les deux gabarits existent dans le binaire, mais
        DuckStation a écrit `SDL-0`. Ne pas choisir était honnête tant que rien
        n'était relevé ; choisir AUTRE CHOSE que ce qu'il a écrit ne l'est
        plus ;
      - une clé `Type` — DuckStation n'en écrit AUCUNE. En ajouter une serait
        prétendre en savoir plus que l'émulateur sur son propre fichier, et
        c'est exactement la faute que ce dépôt refuse.

    Le silence est le danger de fond : une liaison qui ne correspond à rien est
    ignorée sans un mot, et la manette reste muette comme si la section était
    vide. Aucune de ces fautes ne se verrait autrement qu'ici.
    """
    b, = profiles.load_profile(PROFILS / "duckstation.toml").bootstraps
    impose = dict(_cles_ini(b.enforced))
    pad = [(s, c) for s, c in _cles_ini(b.enforced) if s == "Pad1"]

    fautives = [c for _, c in pad if c.lower().startswith("bindings/")]
    assert fautives == [], (
        "duckstation.toml : [Pad1] porte des clés « Bindings/ », forme "
        "relevée ABSENTE de l'exécutable de DuckStation le 2026-08-29. C'est "
        "la forme de PCSX2 : " + " | ".join(fautives)
    )
    assert "Type" not in impose, (
        "duckstation.toml : [Pad1] porte une clé « Type » que DuckStation n'a "
        "PAS écrite. Le fragment imposé est ce que l'émulateur a produit, pas "
        "ce qu'on aurait cru bon d'y ajouter."
    )

    # Les valeurs, relues dans le fragment : toutes SDL-0, aucune XInput.
    #
    # ForceAnalogOnReset est exclue NOMMÉMENT, et il faut que ce soit nommé :
    # c'est la seule clé de [Pad1] qui ne soit pas une liaison — un booléen,
    # pas un périphérique. L'exclure par un test de forme (« ce qui ne
    # ressemble pas à une liaison ») rouvrirait la porte qu'on ferme ici : une
    # liaison mal écrite s'exclurait elle-même du contrôle.
    liaisons = {c for _, c in pad} - {"ForceAnalogOnReset"}
    valeurs = [l.split("=", 1)[1].strip()
               for l in b.enforced.splitlines()
               if "=" in l and l.split("=", 1)[0].strip() in liaisons]
    hors = [v for v in valeurs if not v.startswith("SDL-0/")]
    assert hors == [], (
        "duckstation.toml : des liaisons de [Pad1] ne portent pas "
        "l'identifiant « SDL-0 » relevé le 2026-08-29 : " + " | ".join(hors)
    )
    assert any(v.endswith(("LargeMotor", "SmallMotor")) for v in valeurs), (
        "duckstation.toml : les deux liaisons de vibration (LargeMotor, "
        "SmallMotor) ont disparu de [Pad1]. Elles font partie de ce que "
        "DuckStation a écrit, et elles sont un maillon de la dette D1."
    )


def test_le_systeme_vita_couvre_les_deux_formes_de_bibliotheque():
    """Une bibliothèque PS Vita a DEUX formes, et il en faut les deux.

    Les .vpk sont des fichiers, les applications installées sont des dossiers
    (« ux0:app\\PCSE00123\\ »). N'en déclarer qu'une moitié ne se voit pas :
    le scan rend simplement moins de jeux qu'il n'y en a, ce qui ressemble à
    une bibliothèque plus petite.

    Ce test suit le SYSTÈME, pas le profil : c'est la forme de la
    bibliothèque Vita qui est en jeu, quel que soit l'émulateur qui la sert.
    """
    vita = next((s for p in profiles.load_profiles(PROFILS).values()
                 for s in p.systems if s.id == "vita"), None)
    assert vita is not None, "aucun profil livré ne couvre la PS Vita"
    assert vita.app_dir_marker, (
        "le système Vita ne déclare pas à quoi se reconnaît une application "
        "installée : ses dossiers de jeux resteraient invisibles au scan"
    )
    assert ".vpk" in vita.extensions, (
        "le système Vita ne déclare pas .vpk : les jeux non installés "
        "resteraient invisibles"
    )


# L'EXEMPTION EST VIDE DEPUIS LE 2026-08-29, et c'est le rappel qui a joué.
#
# duckstation.toml y figurait, ICI et nulle part ailleurs : sa manette entière
# était muette — aucun bouton ne répondait, mesuré le 2026-08-28 sur Crash Team
# Racing, dette D3 — et sur un émulateur qui ne voit pas sa manette, la
# vibration n'est pas mesurable. L'exemption disait de retirer ce nom le jour
# où D3 se clôt. D3 s'est close le 2026-08-29 (le propriétaire a vu la manette
# répondre dans CTR), le nom est retiré, et le profil doit donc dire où en est
# sa vibration comme les neuf autres.
#
# Ce qu'il en dit, et c'est tout ce qu'on en sait : LargeMotor et SmallMotor
# ont été écrits par l'assistant de DuckStation, ils ont la bonne forme, et
# PERSONNE NE LES A VUS FAIRE VIBRER quoi que ce soit. La garde n'exige pas
# une vibration qui marche — elle exige que le profil ne laisse pas croire
# qu'elle marche.
SANS_NOTE_DE_VIBRATION: frozenset[str] = frozenset()


def test_chaque_profil_livre_dit_ou_en_est_sa_vibration():
    """Même raison que pour l'amorçage : un réglage absent sans explication ne
    se distingue pas d'un réglage oublié.

    La dette D1 constate que la manette ne vibre NULLE PART, et qu'aucun profil
    ne pose de réglage de rumble. Tant que ce réglage n'est pas mesuré, le
    profil doit au moins dire qu'il manque, où il ira, et pourquoi rien n'y est
    écrit — sans quoi le prochain lecteur conclura que ces émulateurs vibrent
    tout seuls, exactement l'erreur que le plan des manettes a payée sur
    `steam_input`.
    """
    for f in sorted(PROFILS.glob("*.toml")):
        if f.name in SANS_NOTE_DE_VIBRATION:
            continue
        if profiles.load_profile(f).input_rumble in profiles.RUMBLES_MESURES:
            continue
        commentaires = "\n".join(l for l in f.read_text(encoding="utf-8").splitlines()
                                 if l.lstrip().startswith("#")).lower()
        assert "vibration" in commentaires, (
            f"{f.name} : aucun commentaire ne dit où en est la vibration "
            "sur cet émulateur (dette D1)"
        )
        assert "d1" in commentaires, (
            f"{f.name} : la note de vibration ne renvoie pas à la dette D1, "
            "seul endroit où les trois maillons sont écrits"
        )
        assert "mesur" in commentaires, (
            f"{f.name} : la note de vibration ne dit pas que le réglage reste "
            "à mesurer — une clé de rumble recopiée d'une documentation est "
            "ignorée en silence, et la manette reste muette exactement comme "
            "si rien n'avait été écrit"
        )


# À quoi se reconnaît un réglage de vibration DANS un fragment de
# configuration. Les quatre marques couvrent les formes qu'un émulateur emploie
# pour nommer la chose — DuckStation écrit « LargeMotor » et « SmallMotor »,
# d'autres écrivent « rumble » ou « vibration ».
#
# C'est délibérément une reconnaissance LARGE : son rôle n'est pas de valider
# le nom d'une clé — ce nom, seul un relevé sur la machine peut le donner —
# mais d'empêcher qu'un profil déclare un état posé sans rien poser du tout.
MARQUES_DE_RUMBLE = ("motor", "rumble", "vibrat", "haptic")


def _reglages_de_vibration(profil) -> list[str]:
    """Les lignes d'amorçage de ce profil qui posent effectivement un rumble."""
    return [l.strip()
            for b in profil.bootstraps
            for l in (b.content + "\n" + b.enforced).splitlines()
            if any(m in l.lower() for m in MARQUES_DE_RUMBLE)]


def profils_qui_declarent_un_rumble_sans_le_poser(profils: dict) -> list[str]:
    """Ceux qui annoncent un réglage posé et n'en portent aucun.

    C'est la garde structurelle que la tâche 4 du plan D1 exige, et celle qui
    empêche `test_chaque_profil_livre_dit_ou_en_est_sa_vibration` de devenir
    tautologique : sans elle, il suffirait d'écrire `rumble = "pose"` dans un
    profil pour le dispenser de sa note d'aveu SANS avoir rien posé — le
    rapport annoncerait alors un réglage là où il n'y en a pas, et le symptôme
    au canapé serait rigoureusement le même qu'aujourd'hui.

    `vu` y est soumis au même titre que `pose` : on ne peut pas avoir senti
    vibrer ce que rien ne règle.
    """
    return [pid for pid, p in sorted(profils.items())
            if p.input_rumble in (profiles.RUMBLE_POSE, profiles.RUMBLE_VU)
            and not _reglages_de_vibration(p)]


def test_un_profil_qui_declare_un_rumble_pose_en_porte_effectivement_un():
    """La preuve MATÉRIELLE de l'état déclaré.

    Pour DuckStation, ce sont ses deux liaisons `LargeMotor` et `SmallMotor`,
    écrites par son propre assistant le 2026-08-29 et reposées à chaque
    lancement. La garde des deux liaisons qui existait déjà cesse d'être une
    vérification isolée : elle devient ce qui soutient le champ.
    """
    assert profils_qui_declarent_un_rumble_sans_le_poser(
        profiles.load_profiles(PROFILS)) == []


def test_declarer_un_rumble_pose_sans_rien_poser_rend_la_garde_rouge(tmp_path):
    """Le désarmement vérifié par MUTATION, comme le plan D1 l'exige.

    Un test qui ne casse pas sous cette mutation n'a rien gardé. On prend un
    profil livré qui n'a rien posé, on le fait mentir dans son champ, et la
    garde doit le nommer.
    """
    source = PROFILS / "cemu.toml"
    assert profiles.load_profile(source).input_rumble != profiles.RUMBLE_POSE
    menteur = tmp_path / "cemu.toml"
    menteur.write_text(
        source.read_text(encoding="utf-8").replace(
            'rumble      = "inconnu"',
            'rumble       = "pose"\n'
            "rumble_where = 'controllerProfiles, un fichier par manette'"),
        encoding="utf-8")
    assert profils_qui_declarent_un_rumble_sans_le_poser(
        {"cemu": profiles.load_profile(menteur)}) == ["cemu"], (
        "un profil peut déclarer un réglage de vibration posé sans en porter "
        "aucun : la garde ne garde rien"
    )


def test_aucun_profil_livre_ne_declare_une_vibration_vue_sans_temoin():
    """« Un témoin humain, ou rien. » Le chargement le refuse déjà ; ce test
    le dit sur les profils LIVRÉS, qui sont ce que la console reçoit.

    Ce qui se vérifie mécaniquement se vérifie — un état, une date. Que le
    témoignage nomme un jeu se lit : la formule est libre, l'absence ne l'est
    pas.
    """
    for pid, p in sorted(profiles.load_profiles(PROFILS).items()):
        if p.input_rumble != profiles.RUMBLE_VU:
            continue
        assert p.input_rumble_witness, (
            f"{pid} : déclare avoir été VU vibrer sans nommer de témoin"
        )


# --- Vita3K : la modale de privilèges, et le jeton qui la rend reposable ---

def test_vita3k_impose_la_modale_de_privileges():
    """Mesuré le 2026-08-29 : Vita3K ouvre à CHAQUE lancement un avertissement
    de privilèges élevés qu'aucune manette ne ferme, et toute la console tourne
    sous le compte super-utilisateur — la modale revient donc à chaque partie.

    IMPOSÉE et non posée une fois : la cible vit sous le dossier
    d'installation, que « retro install » efface à chaque montée de version, et
    la case se recoche d'un clic dans l'interface. Une préférence « posée une
    fois » ne la reposerait jamais sur une console déjà jouée.
    """
    b, = profiles.load_profiles(PROFILS)["vita3k"].bootstraps
    assert b.target.startswith(profiles.JETON_INSTALL), b.target
    assert b.target.endswith("gui-configs\\CurrentSettings.ini"), b.target
    assert ("MainWindow", "warnAdminPrivileges") in _cles_ini(b.enforced)
    # Et NULLE PART dans le régime « posé une fois » : le réglage serait
    # décidé à deux endroits, et rien ne dirait lequel gagne.
    assert ("MainWindow", "warnAdminPrivileges") not in _cles_ini(b.content)


def test_aucun_profil_livre_ne_porte_de_jeton_inconnu():
    """Un jeton non reconnu n'est pas substitué : il arrive TEL QUEL dans un
    chemin Windows, où il crée un dossier littéralement nommé « {…} ».
    L'émulateur n'y lit jamais rien, et rien ne le dit — la panne muette
    exemplaire. Le validateur refuse un jeton inconnu en tête de cible ; ce
    test regarde la cible ENTIÈRE, où le validateur ne va pas."""
    fautifs = []
    for pid, p in sorted(profiles.load_profiles(PROFILS).items()):
        for b in p.bootstraps:
            for jeton in re.findall(r"\{[^}]*\}", b.target):
                if jeton not in profiles.JETONS_CIBLE:
                    fautifs.append((pid, jeton, b.target))
    assert fautifs == [], (
        "jetons de cible inconnus (les jetons connus sont "
        f"{', '.join(profiles.JETONS_CIBLE)}) : {fautifs}")


# --- le lanceur C# lit-il ce que le plan écrit ? ---------------------------
#
# Ce dépôt n'a AUCUN cadre de test C#. La seule chose vérifiable depuis ici est
# donc mécanique — mais c'est la vérification qui compte : un lanceur qui ne
# lit pas une clé du plan ne PROTESTE PAS, il l'ignore. Les lignes d'amorçage
# d'un plan tout neuf ne produisent alors aucun amorçage, aucune erreur, et
# `retro status` annonce « pas encore amorcé » après cinquante lancements.
# C'est très exactement l'état du jour de la livraison.

def _cles_de_plan(bootstraps) -> list[str]:
    """Les noms de clé qu'un plan porte, l'indice réduit à son préfixe."""
    from retro import launcher
    profil = profiles.load_profiles(PROFILS)["duckstation"]
    texte = launcher.plan_systeme(
        "duckstation", profil.systems[0], "D:\\E\\d.exe", "D:\\E",
        "D:\\E\\_launcher\\systems", bootstraps=bootstraps)
    noms = []
    for ligne in texte.splitlines():
        if ligne.startswith("#") or "=" not in ligne:
            continue
        cle = ligne.split("=", 1)[0]
        noms.append(cle[:cle.rindex(".") + 1] if re.search(r"\.\d+$", cle)
                    else cle)
    return sorted(set(noms))


def test_le_lanceur_lit_chaque_cle_d_amorcage_que_le_plan_ecrit():
    """Une clé écrite et jamais lue est une fonctionnalité inerte, SANS UN MOT.
    Le contrat entre `plan_systeme` et `retro-launch.cs` n'a pas d'autre
    gardien : les deux moitiés vivent dans deux langages, et seule celle-ci est
    testable."""
    from retro import launcher
    source = (launcher.SOURCES / launcher.SOURCE).read_text(
        encoding="utf-8-sig")
    deux = profiles.load_profiles(PROFILS)["duckstation"].bootstraps * 2
    manquantes = [c for c in _cles_de_plan(deux)
                  if c.startswith("bootstrap") and f'"{c}' not in source]
    assert manquantes == [], (
        "retro-launch.cs ne lit pas ces clés que le plan écrit — elles seraient "
        f"ignorées en silence, à chaque lancement : {manquantes}"
    )
