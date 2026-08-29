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
        for quoi, sha in [(e.key, e.sha256)] + [
            (f"{e.key} parts[{i}]", p.sha256) for i, p in enumerate(e.parts)
        ]:
            assert len(sha) == 64, f"{quoi} : sha256 de {len(sha)} caractères"
            assert all(c in "0123456789abcdef" for c in sha.lower()), quoi


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
    assert EXEMPTES == {
        "tests/test_donnees.py",
        "docs/superpowers/specs/2026-08-26-retro-console-design.md",
        "docs/superpowers/plans/2026-08-26-emulateurs-sous-projet-a.md",
    }


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
NOMBRES = {1: "une", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six"}


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
        if profiles.load_profile(f).bootstrap is not None:
            continue
        commentaires = "\n".join(l for l in f.read_text(encoding="utf-8").splitlines()
                                 if l.lstrip().startswith("#"))
        assert "[bootstrap]" in commentaires, (
            f"{f.name} : aucun commentaire ne dit pourquoi ce profil n'a pas "
            "de bloc [bootstrap]"
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
