"""Les profils : comment on parle à un émulateur.

C'est l'abstraction qui doit permettre au sous-projet D d'ajouter dix
émulateurs sans rouvrir une ligne de code. Tout ce qui est propre à un
émulateur vit dans son TOML.
"""
import pathlib

import pytest

from retro import profiles

RETROARCH = """
schema = 1
id = "retroarch"
exe = "retroarch.exe"

[input]
steam_input = "required"

[exit]
native = "Select+Start"
fallback = "alt+f4"

[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue", ".chd", ".m3u"]
launch = '-L "cores\\\\swanstation_libretro.dll" -f "{rom}"'
bios = [{ file = "scph5501.bin", md5 = "abc", required = true }]

[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc", ".smc"]
launch = '-L "cores\\\\snes9x_libretro.dll" -f "{rom}"'
bios = []
"""


def ecrire(tmp_path, nom, contenu):
    p = tmp_path / nom
    p.write_text(contenu, encoding="utf-8")
    return p


def test_charge_un_profil(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "retroarch.toml", RETROARCH))
    assert p.id == "retroarch"
    assert p.exe == "retroarch.exe"
    assert len(p.systems) == 2


def test_les_systemes_portent_leurs_extensions(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    psx = next(s for s in p.systems if s.id == "psx")
    assert psx.extensions == (".cue", ".chd", ".m3u")
    assert psx.name == "PlayStation"


def test_les_bios_sont_declares(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    psx = next(s for s in p.systems if s.id == "psx")
    assert psx.bios[0]["file"] == "scph5501.bin"
    snes = next(s for s in p.systems if s.id == "snes")
    assert snes.bios == ()


def test_bios_sans_md5_refuse(tmp_path):
    """Une faute de frappe sur la clé désactiverait la vérification en silence.

    « md5s » au lieu de « md5 » se charge sans un mot : le BIOS n'est plus
    vérifié, et le propriétaire croit ses BIOS validés. Le message doit nommer
    le profil ET le système, sinon il faut relire tout le TOML pour trouver la
    ligne.
    """
    mauvais = RETROARCH.replace('md5 = "abc"', 'md5s = "abc"')
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    message = str(exc.value)
    assert "md5" in message and "psx" in message and "retroarch" in message


def test_bios_sans_file_refuse(tmp_path):
    """Une empreinte sans nom de fichier ne désigne rien à vérifier."""
    mauvais = RETROARCH.replace('file = "scph5501.bin", ', "")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "file" in str(exc.value) and "psx" in str(exc.value)


def test_bios_md5_non_textuel_refuse(tmp_path):
    """Ces fichiers sont écrits à la main : un md5 sans guillemets se parse en
    entier TOML. Sans validation de TYPE (pas seulement de présence),
    l'entier traverse le chargement du profil et bios.check_bios explose sur
    l'appel .lower() d'un entier — une trace Python sur la commande faite
    pour expliquer les pannes. Le message doit nommer le profil, le système
    et le champ.
    """
    mauvais = RETROARCH.replace('md5 = "abc"', "md5 = 5501")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    message = str(exc.value)
    assert "md5" in message and "psx" in message and "retroarch" in message


def test_bios_file_non_textuel_refuse(tmp_path):
    """Même défaut, même remède, pour 'file' : un nom de fichier numérique
    sans guillemets (ex. un modèle de console) se parse aussi en entier."""
    mauvais = RETROARCH.replace('file = "scph5501.bin"', "file = 5501")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    message = str(exc.value)
    assert "file" in message and "psx" in message and "retroarch" in message


def test_la_sortie_est_declaree(tmp_path):
    """Sans hotkey de sortie, un émulateur lancé à la manette immobilise la
    console jusqu'au redémarrage de la VM."""
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", RETROARCH))
    assert p.exit_native == "Select+Start"
    assert p.exit_fallback == "alt+f4"


def test_launch_sans_rom_est_refuse(tmp_path):
    """Un gabarit sans {rom} lance l'émulateur sans jeu : il s'ouvre sur son
    propre menu, la console a l'air de marcher, et rien ne le signale."""
    mauvais = RETROARCH.replace('-f "{rom}"', "-f")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "{rom}" in str(exc.value) and "psx" in str(exc.value)


def test_extensions_vides_refusees(tmp_path):
    """Un système sans extension ne peut rien matcher : il serait absent de la
    bibliothèque sans que rien ne le dise."""
    mauvais = RETROARCH.replace('extensions = [".sfc", ".smc"]', "extensions = []")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "snes" in str(exc.value)


def test_extension_sans_point_refusee(tmp_path):
    """Le scan compare à Path.suffix, qui porte toujours son point."""
    mauvais = RETROARCH.replace('[".sfc", ".smc"]', '["sfc"]')
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))
    assert "sfc" in str(exc.value)


def test_deux_systemes_de_meme_id_refuses(tmp_path):
    mauvais = RETROARCH.replace('id = "snes"', 'id = "psx"')
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "r.toml", mauvais))


def test_schema_inconnu_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "r.toml", "schema = 99\nid = 'x'\n"))


def test_charge_un_dossier(tmp_path):
    d = tmp_path / "profiles"
    d.mkdir()
    (d / "retroarch.toml").write_text(RETROARCH, encoding="utf-8")
    (d / "notes.txt").write_text("ignoré", encoding="utf-8")
    tous = profiles.load_profiles(d)
    assert set(tous) == {"retroarch"}


def test_dossier_vide_leve(tmp_path):
    """Aucun profil = aucun jeu ne peut être lancé. Ce n'est pas un état
    normal, c'est un paquet cassé."""
    d = tmp_path / "vide"
    d.mkdir()
    with pytest.raises(profiles.ProfileError):
        profiles.load_profiles(d)


def test_systeme_sans_id_refuse(tmp_path):
    """Un système sans 'id' recevait l'identifiant littéral « ? ».

    Le profil se chargeait sans un mot, mais aucun dossier de ROMs ne s'appelle
    « ? » : le système entier n'apparaissait jamais dans Steam et le scan
    rendait zéro. Même famille que la faute de frappe sur une clé de BIOS.
    """
    sans_id = RETROARCH.replace('id = "snes"\n', "")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profile(ecrire(tmp_path, "r.toml", sans_id))
    assert "id" in str(exc.value)
    assert "?" not in str(exc.value)


def test_deux_profils_de_meme_id_refuses(tmp_path):
    """Deux profils de même 'id' s'effaçaient l'un l'autre en silence.

    Le dernier chargé gagnait et l'autre disparaissait entièrement : un profil
    copié sans changer son 'id' a remplacé les neuf systèmes de RetroArch par
    deux, le scan a rendu 0, et la synchronisation a supprimé les entrées
    devenues orphelines. Ajouter des profils par copie est le chemin nominal.
    """
    d = tmp_path / "profiles"
    d.mkdir()
    (d / "retroarch.toml").write_text(RETROARCH, encoding="utf-8")
    copie = RETROARCH.replace('id = "psx"', 'id = "ps2"').replace(
        'id = "snes"', 'id = "gc"')
    (d / "zz-copie.toml").write_text(copie, encoding="utf-8")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profiles(d)
    message = str(exc.value)
    assert "retroarch" in message
    assert "retroarch.toml" in message and "zz-copie.toml" in message


# --- Groupes de BIOS : « un parmi ceux-ci suffit » ------------------------
#
# Les trois BIOS PlayStation sont interchangeables : celui de la région des
# jeux suffit. Déclarés `required = true` un par un, le rapport accusait de
# deux fichiers manquants quelqu'un qui avait déposé le bon.

GROUPE = """
schema = 1
id = "retroarch"
exe = "retroarch.exe"

[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-f "{rom}"'
bios = [
  { file = "a.bin", md5 = "aa", required = true, group = "region", region = "Japon" },
  { file = "b.bin", md5 = "bb", required = true, group = "region", region = "Europe" },
]
"""


def test_un_groupe_de_bios_est_charge(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "r.toml", GROUPE))
    psx = p.systems[0]
    assert [b.get("group") for b in psx.bios] == ["region", "region"]
    assert [b.get("region") for b in psx.bios] == ["Japon", "Europe"]


def test_groupe_non_textuel_refuse(tmp_path):
    contenu = GROUPE.replace('group = "region", region = "Japon"',
                             "group = 1, region = \"Japon\"")
    # match resserré sur « non textuel » : avec seulement match="group", ce
    # test restait vert même sans la vérification de type de 'group' — le
    # groupe à un seul membre que produit group = 1 (b.bin reste seul dans
    # le groupe "region") lève un ProfileError dont le message, « le groupe
    # de BIOS '1' [...] », contient "group" comme sous-chaîne de « groupe ».
    with pytest.raises(profiles.ProfileError, match="non textuel"):
        profiles.load_profile(ecrire(tmp_path, "r.toml", contenu))


def test_region_non_textuelle_refusee(tmp_path):
    contenu = GROUPE.replace('region = "Japon"', "region = 1")
    with pytest.raises(profiles.ProfileError, match="region"):
        profiles.load_profile(ecrire(tmp_path, "r.toml", contenu))


def test_groupe_a_un_seul_membre_refuse(tmp_path):
    """Une faute de frappe sur le nom du groupe le scinde en silence, et le
    membre resté seul redevient exigé à lui tout seul — exactement le défaut
    que les groupes corrigent. Un groupe d'un seul membre n'a aucun sens :
    il est refusé plutôt que toléré."""
    contenu = GROUPE.replace('group = "region", region = "Europe"',
                             'group = "regionn", region = "Europe"')
    with pytest.raises(profiles.ProfileError, match="seul"):
        profiles.load_profile(ecrire(tmp_path, "r.toml", contenu))


def test_groupe_aux_exigences_contradictoires_refuse(tmp_path):
    """« un parmi ceux-ci » n'a pas de sens si les membres ne s'accordent pas
    sur le fait d'être exigés."""
    contenu = GROUPE.replace('md5 = "bb", required = true',
                             'md5 = "bb", required = false')
    with pytest.raises(profiles.ProfileError, match="required"):
        profiles.load_profile(ecrire(tmp_path, "r.toml", contenu))


# --- Les profils du propriétaire ------------------------------------------
#
# Le manifeste accepte déjà une surcharge utilisateur : c'est l'échappatoire
# qui permet au dépôt public de ne référencer aucun émulateur contesté sans
# brider personne. Déclarer un émulateur au manifeste ne suffit pourtant pas à
# s'en servir — il lui faut un profil. Les profils du propriétaire vivent donc
# hors dépôt, et se FUSIONNENT avec ceux du paquet.

# La forme RÉELLE de `exe` : les archives officielles ont un dossier racine, et
# l'antislash n'est pas un séparateur sous Linux. Une fixture au nom plat a
# déjà laissé passer un défaut qui ignorait TOUS les systèmes avec les profils
# livrés ; on ne la reproduit pas ici.
DUCKSTATION = """
schema = 1
id = "duckstation"
exe = 'DuckStation-x64\\duckstation-qt-x64-ReleaseLTCG.exe'

[[system]]
id = "psx"
name = "PlayStation"
extensions = [".chd", ".cue"]
launch = '-fullscreen "{rom}"'
bios = []
"""


PPSSPP = """
schema = 1
id = "ppsspp"
exe = 'PPSSPPWindows64\\PPSSPPWindows64.exe'

[[system]]
id = "psp"
name = "PlayStation Portable"
extensions = [".iso", ".cso"]
launch = '--fullscreen "{rom}"'
bios = []
"""


def _sources(tmp_path, livres: dict, miens: dict | None = None):
    """Un dossier de profils livrés, un dossier de profils du propriétaire."""
    paquet = tmp_path / "paquet"
    paquet.mkdir()
    for nom, contenu in livres.items():
        (paquet / nom).write_text(contenu, encoding="utf-8")
    if miens is None:
        return paquet, tmp_path / "jamais-monte"
    sien = tmp_path / "sien"
    sien.mkdir()
    for nom, contenu in miens.items():
        (sien / nom).write_text(contenu, encoding="utf-8")
    return paquet, sien


def test_les_profils_du_proprietaire_s_ajoutent_a_ceux_du_paquet(tmp_path):
    """Le besoin d'origine : ajouter un émulateur que le dépôt public ne peut
    pas référencer. Pointer --profiles ailleurs perdait ceux du paquet ; la
    seconde source les COMPLÈTE."""
    paquet, sien = _sources(tmp_path, {"retroarch.toml": RETROARCH},
                            {"ppsspp.toml": PPSSPP})
    tous = profiles.load_profiles(paquet, sien)
    assert set(tous) == {"retroarch", "ppsspp"}
    assert tous["ppsspp"].exe == "PPSSPPWindows64\\PPSSPPWindows64.exe"
    # Les systèmes du paquet que personne ne revendique restent servis.
    assert {s.id for s in tous["retroarch"].systems} == {"psx", "snes"}


def test_le_profil_du_proprietaire_l_emporte_a_identifiant_egal(tmp_path):
    """La MÊME règle que le manifeste : à clé égale, la version du
    propriétaire remplace celle du paquet, entièrement."""
    sien = RETROARCH.replace('exe = "retroarch.exe"',
                             "exe = 'RetroArch-nightly\\retroarch.exe'")
    sien = sien.replace('id = "snes"', 'id = "megadrive"')
    paquet, dossier = _sources(tmp_path, {"retroarch.toml": RETROARCH},
                               {"retroarch.toml": sien})
    tous = profiles.load_profiles(paquet, dossier)
    assert set(tous) == {"retroarch"}
    assert tous["retroarch"].exe == "RetroArch-nightly\\retroarch.exe"
    # Remplacé, pas fusionné système par système : « snes » ne survit pas.
    assert {s.id for s in tous["retroarch"].systems} == {"psx", "megadrive"}


def test_le_dossier_du_proprietaire_absent_est_normal(tmp_path):
    """Il vit sur un partage qui n'est pas monté au moment du
    provisionnement — exactement comme le manifeste utilisateur. Une erreur
    ici casserait l'installation d'une machine neuve."""
    paquet, jamais = _sources(tmp_path, {"retroarch.toml": RETROARCH})
    assert not jamais.exists()
    assert set(profiles.load_profiles(paquet, jamais)) == {"retroarch"}


def test_le_dossier_du_proprietaire_vide_est_normal(tmp_path):
    paquet, sien = _sources(tmp_path, {"retroarch.toml": RETROARCH}, {})
    assert set(profiles.load_profiles(paquet, sien)) == {"retroarch"}


def test_sans_second_dossier_le_chargement_est_celui_d_avant(tmp_path):
    paquet, _ = _sources(tmp_path, {"retroarch.toml": RETROARCH})
    assert set(profiles.load_profiles(paquet)) == {"retroarch"}


def test_un_systeme_revendique_par_le_proprietaire_lui_revient(tmp_path):
    """Le cas qui décide : Duckstation revendique « psx », que le RetroArch
    livré sert déjà. Le profil du propriétaire l'emporte, et le système
    QUITTE le profil livré — sans quoi deux profils se disputeraient le même
    dossier de ROMs et le scan trancherait par ordre alphabétique.
    """
    paquet, sien = _sources(tmp_path, {"retroarch.toml": RETROARCH},
                            {"duckstation.toml": DUCKSTATION})
    tous = profiles.load_profiles(paquet, sien)
    assert {s.id for s in tous["duckstation"].systems} == {"psx"}
    assert {s.id for s in tous["retroarch"].systems} == {"snes"}
    # Un seul profil sert « psx » : le scan n'a plus rien à arbitrer.
    servants = [pid for pid, p in tous.items()
                if any(s.id == "psx" for s in p.systems)]
    assert servants == ["duckstation"]


def test_un_profil_livre_entierement_repris_disparait(tmp_path):
    """Un profil sans système ne peut rien lancer, et `load_profile` refuse
    déjà d'en produire un. Rendre celui-là amputé de TOUS ses systèmes
    ferait mentir `retro status`, qui réclamerait l'installation d'un
    émulateur dont plus aucun jeu ne dépend."""
    tout = DUCKSTATION.replace('id = "duckstation"', 'id = "monretroarch"')
    tout += """
[[system]]
id = "snes"
name = "Super Nintendo"
extensions = [".sfc"]
launch = '-fullscreen "{rom}"'
bios = []
"""
    paquet, sien = _sources(tmp_path, {"retroarch.toml": RETROARCH},
                            {"mien.toml": tout})
    tous = profiles.load_profiles(paquet, sien)
    assert set(tous) == {"monretroarch"}


def test_deux_profils_livres_ne_se_disputent_pas_un_systeme(tmp_path):
    """Le refus des identifiants de système en double vaut ENTRE profils
    d'une même source : deux profils qui revendiquent « psx » se disputent le
    même dossier de ROMs, et rien dans le résultat ne le dirait — le scan
    retient le premier par ordre alphabétique. Le message doit nommer le
    système et les deux fichiers, sinon il faut relire tous les TOML."""
    autre = DUCKSTATION
    paquet, _ = _sources(tmp_path, {"retroarch.toml": RETROARCH,
                                    "duckstation.toml": autre})
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profiles(paquet)
    message = str(exc.value)
    assert "psx" in message
    assert "retroarch.toml" in message and "duckstation.toml" in message


def test_deux_profils_du_proprietaire_ne_se_disputent_pas_un_systeme(tmp_path):
    """La même garde dans le dossier du propriétaire : la préséance ne
    départage QUE les deux sources, jamais deux fichiers de la même."""
    copie = DUCKSTATION.replace('id = "duckstation"', 'id = "duckstation-nightly"')
    paquet, sien = _sources(tmp_path, {"retroarch.toml": RETROARCH},
                            {"a-duck.toml": DUCKSTATION, "z-duck.toml": copie})
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profiles(paquet, sien)
    message = str(exc.value)
    assert "psx" in message
    assert "a-duck.toml" in message and "z-duck.toml" in message


def test_deux_profils_de_meme_id_dans_le_dossier_du_proprietaire_refuses(tmp_path):
    """La garde qui existait sur le dossier livré vaut aussi sur le sien : le
    second effacerait le premier en silence."""
    copie = DUCKSTATION.replace('id = "psx"', 'id = "ps2"')
    paquet, sien = _sources(tmp_path, {"retroarch.toml": RETROARCH},
                            {"a.toml": DUCKSTATION, "z.toml": copie})
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profiles(paquet, sien)
    assert "duckstation" in str(exc.value)
    assert "a.toml" in str(exc.value) and "z.toml" in str(exc.value)


def test_le_dossier_livre_reste_obligatoire(tmp_path):
    """L'absence du dossier du propriétaire est normale ; celle du dossier
    livré ne l'est pas. Sans cette asymétrie, un --profiles mal orthographié
    rendrait silencieusement les seuls profils du propriétaire, et les
    systèmes livrés disparaîtraient de Steam sans un mot."""
    _, sien = _sources(tmp_path, {}, {"duckstation.toml": DUCKSTATION})
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profiles(tmp_path / "jamais-livre", sien)
    assert "jamais-livre" in str(exc.value)


def test_un_dossier_du_proprietaire_qui_est_un_fichier_refuse(tmp_path):
    """« Pas monté » et « mal orthographié » ne se ressemblent que de loin.

    Donner le profil lui-même au lieu de son dossier est la faute de frappe
    naturelle. Traitée comme une absence, elle rendrait silencieusement les
    seuls profils du paquet : l'émulateur du propriétaire manquerait, et
    aucun message ne dirait pourquoi.
    """
    paquet, _ = _sources(tmp_path, {"retroarch.toml": RETROARCH})
    fichier = tmp_path / "duckstation.toml"
    fichier.write_text(DUCKSTATION, encoding="utf-8")
    with pytest.raises(profiles.ProfileError) as exc:
        profiles.load_profiles(paquet, fichier)
    assert "duckstation.toml" in str(exc.value)
    assert "dossier" in str(exc.value)
