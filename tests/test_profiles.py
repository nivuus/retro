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


def _deux_sources(tmp_path, pid_utilisateur):
    """Un profil livré et un profil du propriétaire qui servent le MÊME dossier
    de ROMs sous des identifiants de système DIFFÉRENTS."""
    livres, miens = tmp_path / "livres", tmp_path / "miens"
    livres.mkdir(); miens.mkdir()
    (livres / "ra.toml").write_text("""
schema = 1
id = "retroarch"
exe = 'ra.exe'
[[system]]
id = "psx"
name = "PlayStation"
folders = ["Playstation"]
extensions = [".cue"]
launch = '-f "{rom}"'
bios = []
""", encoding="utf-8")
    (miens / "m.toml").write_text(f"""
schema = 1
id = "{pid_utilisateur}"
exe = 'perso.exe'
[[system]]
id = "psx-perso"
name = "PlayStation (le mien)"
folders = ["Playstation"]
extensions = [".cue"]
launch = '-f "{{rom}}"'
bios = []
""", encoding="utf-8")
    return profiles.load_profiles(livres, miens)


@pytest.mark.parametrize("pid", ["duckstation", "zz-le-mien"])
def test_la_preseance_ne_depend_pas_du_nom_du_fichier(tmp_path, pid):
    """« Le vôtre l'emporte » portait sur le seul identifiant de SYSTÈME. Un
    profil du propriétaire servant « Playstation » sous un identifiant à lui
    ne reprenait rien : les deux systèmes survivaient, et le scan tranchait
    par ordre alphabétique des identifiants de PROFIL. Le propriétaire
    gagnait ou perdait selon le nom qu'il avait donné à son fichier."""
    fusionnes = _deux_sources(tmp_path, pid)
    revendiquent = [
        p.id for p in fusionnes.values() for s in p.systems
        if "playstation" in profiles.folder_claims(s)
    ]
    assert revendiquent == [pid], (
        "un seul profil doit revendiquer ce dossier, et ce doit être celui "
        f"du propriétaire — trouvé : {revendiquent}"
    )


def test_le_profil_livre_devenu_vide_disparait(tmp_path):
    """Il ne pourrait plus rien lancer, et `retro status` réclamerait
    l'installation d'un émulateur dont plus aucun jeu ne dépend."""
    assert "retroarch" not in _deux_sources(tmp_path, "duckstation")


# --- les trois modes de rendu -------------------------------------------

def profil_rendu(corps: str, launch: str = '-f {render} "{rom}"') -> str:
    """Un profil minimal dont le seul système porte le bloc donné."""
    return f'''
schema = 1
id = "essai"
exe = "essai.exe"
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '{launch}'
cost = "light"
bios = []
{corps}
'''


RENDU_VALIDE = """
[system.render.native]
args = "-scale=1"
crt = "-shader=crt-geom"
[system.render.full]
args = "-scale={scale} --resolution={width}x{height}"
[system.render]
native_height = 240
max_scale = 8
"""


def test_un_bloc_de_rendu_complet_se_charge(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "e.toml",
                                     profil_rendu(RENDU_VALIDE)))
    systeme = p.systems[0]
    assert systeme.cost == "light"
    assert systeme.render.native.crt == "-shader=crt-geom"
    assert systeme.render.max_scale == 8


def test_un_profil_sans_bloc_de_rendu_reste_valide(tmp_path):
    """Les modes se remplissent émulateur par émulateur, chaque option lue
    dans l'exécutable livré. Un profil qui n'en a pas encore doit continuer de
    lancer ses jeux — c'est `retro status` qui nomme ceux qui n'en ont pas."""
    p = profiles.load_profile(ecrire(tmp_path, "e.toml",
                                     profil_rendu("", launch='-f "{rom}"')))
    assert p.systems[0].render is None


def test_un_bloc_de_rendu_sans_marqueur_dans_launch_est_refuse(tmp_path):
    """Sans {render}, les arguments n'iraient NULLE PART : les trois modes se
    lanceraient à l'identique, et le propriétaire croirait choisir."""
    with pytest.raises(profiles.ProfileError, match=r"ne contient pas \{render\}"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu(
            RENDU_VALIDE, launch='-f "{rom}"')))


def test_un_marqueur_sans_bloc_de_rendu_est_refuse(tmp_path):
    """Le marqueur arriverait littéralement sur la ligne de commande."""
    with pytest.raises(profiles.ProfileError, match="aucun bloc 'render'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("")))


def test_un_seul_mode_declare_est_refuse(tmp_path):
    """L'autre se lancerait avec les réglages par défaut, sans rien changer et
    sans rien dire — et `auto`, qui choisit entre les deux, n'aurait plus le
    choix."""
    with pytest.raises(profiles.ProfileError, match="ne déclare pas full"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
crt_absent = "aucun shader"
""")))


@pytest.mark.parametrize("faute,motif", [
    ("[system.render.natif]\nargs = \"-x\"", "clés inconnues"),
    ("[system.render.native]\nargms = \"-x\"", "clés inconnues"),
])
def test_une_faute_de_frappe_sur_un_nom_de_mode_est_refusee(tmp_path, faute, motif):
    """Une clé mal orthographiée ne serait jamais lue : le réglage qu'elle
    porte n'aurait aucun effet, et rien ne le dirait."""
    corps = faute + '\n[system.render.full]\nargs = "-y"\n'
    with pytest.raises(profiles.ProfileError, match=motif):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu(corps)))


def test_un_mode_sans_args_est_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError, match="pas de champ 'args'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
crt_absent = "aucun shader"
[system.render.full]
args = "-y"
""")))


def test_un_mode_vide_sans_note_est_refuse(tmp_path):
    """Un mode vide est peut-être la vérité — tous les émulateurs n'exposent
    pas leurs réglages en ligne de commande — mais rien ne le distinguerait
    d'un bloc oublié."""
    with pytest.raises(profiles.ProfileError, match="est vide sans 'note'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = ""
crt_absent = "aucun shader"
[system.render.full]
args = "-y"
""")))


def test_un_mode_vide_avec_note_est_accepte(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = ""
note = "cet émulateur n'expose aucun réglage de rendu en ligne de commande"
crt_absent = "ni shader"
[system.render.full]
args = "-y"
""")))
    assert p.systems[0].render.native.note


def test_le_mode_natif_doit_trancher_sur_le_crt(tmp_path):
    """« Ce que la console d'origine fournissait » passait par un tube
    cathodique. Ni crt ni crt_absent rendrait une image propre qu'aucun
    téléviseur de l'époque n'a produite, sans que le rapport puisse le dire."""
    with pytest.raises(profiles.ProfileError, match="SOIT 'crt'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
[system.render.full]
args = "-y"
""")))


def test_le_crt_et_son_absence_a_la_fois_sont_refuses(tmp_path):
    with pytest.raises(profiles.ProfileError, match="SOIT 'crt'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
crt = "-shader=crt"
crt_absent = "aucun shader"
[system.render.full]
args = "-y"
""")))


def test_un_crt_en_mode_full_est_refuse(tmp_path):
    """Déclaré là, il ne serait jamais appliqué."""
    with pytest.raises(profiles.ProfileError, match="ne prend ni 'crt'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
crt_absent = "aucun"
[system.render.full]
args = "-y"
crt = "-shader=crt"
""")))


def test_une_variable_inconnue_est_refusee(tmp_path):
    """Elle arriverait TELLE QUELLE sur la ligne de commande de l'émulateur,
    qui l'ignorerait ou refuserait de démarrer — et le mode aurait pourtant
    l'air appliqué."""
    with pytest.raises(profiles.ProfileError, match="variables inconnues"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "--res={resolution}"
crt_absent = "aucun"
[system.render.full]
args = "-y"
""")))


def test_l_echelle_exige_ce_qui_permet_de_la_calculer(tmp_path):
    """{scale} se calcule en divisant la hauteur de session par celle de la
    console d'origine : sans ces deux nombres, elle n'est pas calculable."""
    with pytest.raises(profiles.ProfileError, match="native_height"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
crt_absent = "aucun"
[system.render.full]
args = "-scale={scale}"
""")))


def test_un_bloc_de_rendu_sans_cout_est_refuse(tmp_path):
    """C'est ce que `auto` croise avec la machine : sans lui il déciderait sur
    une valeur inventée, et un jeu qui rame ressemblerait à du matériel
    insuffisant."""
    sans_cout = profil_rendu(RENDU_VALIDE).replace('cost = "light"\n', "")
    with pytest.raises(profiles.ProfileError, match="'cost' vaut"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", sans_cout))


def test_un_cout_mal_orthographie_est_refuse(tmp_path):
    mauvais = profil_rendu(RENDU_VALIDE).replace('"light"', '"leger"')
    with pytest.raises(profiles.ProfileError, match="'cost' vaut 'leger'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", mauvais))


def test_un_fichier_de_reglages_sans_reference_est_refuse(tmp_path):
    """Un fichier que rien ne référence ne serait jamais lu par l'émulateur :
    le mode serait déclaré, écrit sur le disque, et sans le moindre effet."""
    with pytest.raises(profiles.ProfileError, match="que rien ne référence"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-f"
crt_absent = "aucun"
config = "video_shader_enable = true"
[system.render.full]
args = "-y"
""")))


def test_une_reference_sans_fichier_de_reglages_est_refusee(tmp_path):
    """Le chemin d'un fichier qui n'existe pas : l'émulateur s'en plaindrait,
    ou l'ignorerait — et le mode aurait l'air appliqué."""
    with pytest.raises(profiles.ProfileError, match=r"\{render_config\} sans 'config'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = '--appendconfig "{render_config}"'
crt_absent = "aucun"
[system.render.full]
args = "-y"
""")))


def test_un_mode_avec_fichier_de_reglages_se_charge(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = '--appendconfig "{render_config}"'
crt_absent = "aucun"
config = 'video_shader_enable = "true"'
[system.render.full]
args = "-y"
""")))
    assert 'video_shader_enable' in p.systems[0].render.native.config


# --- le bloc [bootstrap] ------------------------------------------------

# `content` est déclaré avec les guillemets simples triples de TOML : la
# chaîne LITTÉRALE, qui n'interprète aucun échappement. C'est le format à
# employer dans les profils livrés — un fichier de configuration Windows est
# plein d'antislashs, et une chaîne TOML de base les mangerait.
BOOTSTRAP_VALIDE = """
schema = 1
id = "duckstation"
exe = 'duckstation-qt.exe'
[[bootstrap]]
target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[Main]
SetupWizardIncomplete = false
'''
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{rom}"'
"""


def test_le_bloc_bootstrap_est_lu(tmp_path):
    """Le contenu vit dans le profil, jamais dans le code : c'est lui que le
    lanceur posera tel quel."""
    profil = profiles.load_profile(ecrire(tmp_path, "duckstation.toml", BOOTSTRAP_VALIDE))
    assert len(profil.bootstraps) == 1
    assert profil.bootstraps[0].target == (
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini")
    assert "SetupWizardIncomplete = false" in profil.bootstraps[0].content


def test_un_profil_sans_bootstrap_reste_valide(tmp_path):
    """Un émulateur qui démarre nu n'a pas de bloc, et son profil doit
    continuer de se charger."""
    sans = BOOTSTRAP_VALIDE[:BOOTSTRAP_VALIDE.index("[[bootstrap]]")] + \
        BOOTSTRAP_VALIDE[BOOTSTRAP_VALIDE.index("[[system]]"):]
    assert profiles.load_profile(
        ecrire(tmp_path, "duckstation.toml", sans)).bootstraps == ()


def test_une_cible_sans_contenu_est_refusee(tmp_path):
    """La moitié d'un amorçage n'amorce rien, et se lirait pourtant comme un
    profil complet."""
    texte = BOOTSTRAP_VALIDE.replace(
        BOOTSTRAP_VALIDE[BOOTSTRAP_VALIDE.index("content ="):
                         BOOTSTRAP_VALIDE.index("[[system]]")], "")
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "duckstation.toml", texte))
    assert "content" in str(e.value) and "duckstation.toml" in str(e.value)


def test_un_contenu_sans_cible_est_refuse(tmp_path):
    """Un contenu sans cible n'a nulle part où aller."""
    texte = BOOTSTRAP_VALIDE.replace(
        "target = '%USERPROFILE%\\Documents\\DuckStation\\settings.ini'\n", "")
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "duckstation.toml", texte))
    assert "target" in str(e.value)


def test_une_cible_relative_est_refusee(tmp_path):
    """Un chemin relatif s'écrirait dans le dossier de travail de l'émulateur,
    qui n'est pas celui de sa configuration — et le fichier posé ne serait lu
    par personne."""
    texte = BOOTSTRAP_VALIDE.replace(
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini",
        "settings.ini")
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "duckstation.toml", texte))
    assert "absolu" in str(e.value)


def test_un_contenu_sans_marque_est_refuse(tmp_path):
    """Une configuration écrite par un outil et qui ne le dit pas est un piège
    pour le prochain lecteur — et pour le propriétaire qui la modifierait."""
    texte = BOOTSTRAP_VALIDE.replace(
        "; Écrit par « retro » au premier lancement, parce que ce fichier "
        "était absent.\n", "")
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "duckstation.toml", texte))
    assert profiles.MARQUE_BOOTSTRAP in str(e.value)


def test_le_profil_duckstation_livre_ferme_les_deux_causes_mesurees():
    """Le profil livré n'est pas un exemple : c'est lui que `retro scan` lira.

    Mesuré le 2026-08-28 : DEUX causes distinctes ouvraient l'assistant de
    DuckStation à la place d'un jeu — l'assistant de première configuration
    lui-même, et une fenêtre de mise à jour qui bloquait le lancement même
    l'assistant désactivé. Un profil qui n'en fermerait qu'une laisserait le
    symptôme intact pour la moitié des propriétaires qui l'installent.

    Ces deux clés sont désormais IMPOSÉES et non plus seulement posées : le
    propriétaire l'a arbitré le 2026-08-29. La différence n'est pas
    théorique — une seule case recochée par curiosité dans l'interface de
    DuckStation rendait auparavant toute la bibliothèque injouable, sans
    aucun moyen de le deviner."""
    chemin = (pathlib.Path(__file__).parent.parent / "retro" / "data"
              / "profiles" / "duckstation.toml")
    profil = profiles.load_profile(chemin)
    assert len(profil.bootstraps) == 1
    assert profil.bootstraps[0].target == (
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini")
    # La première cause mesurée : sans elle, l'assistant de première
    # configuration s'ouvre avant tout jeu et rien n'est jamais écrit.
    assert "SetupWizardIncomplete = false" in profil.bootstraps[0].enforced
    # La seconde, découverte le même jour : sans elle, une fenêtre « Mise à
    # jour disponible » bloque le lancement aussi sûrement que l'assistant.
    assert "CheckAtStartup = false" in profil.bootstraps[0].enforced
    # Et elles ne sont plus dans le fichier « posé une fois » : les y laisser
    # aurait fait décider le même réglage à deux endroits.
    assert "SetupWizardIncomplete" not in profil.bootstraps[0].content


# --- l'identifiant d'un profil se découpe et nomme un fichier --------------

def _avec_id(identifiant: str) -> str:
    return BOOTSTRAP_VALIDE.replace('id = "duckstation"',
                                    f'id = "{identifiant}"', 1)


def test_un_identifiant_de_profil_avec_un_espace_est_refuse(tmp_path):
    """`ordonner_reamorcage` relit reamorcer.txt avec `split()`, qui découpe
    sur les BLANCS : « duck station » y devient deux ordres, dont aucun ne
    désigne un profil. L'ordre serait écrit, rapporté comme posé, et le
    lanceur ne le verrait jamais."""
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "x.toml", _avec_id("duck station")))
    assert "duckstation.toml" not in str(e.value)
    assert "x.toml" in str(e.value) and "espace" in str(e.value)
    # Et ce que la correction COÛTE : renommer un profil déjà synchronisé
    # change la clé de système, donc les options du raccourci, donc
    # l'identifiant Steam de chaque jeu. Obéir sans le savoir, c'est perdre
    # ses entrées et tout son artwork.
    assert "artwork" in str(e.value) and "Steam fermé" in str(e.value)


def test_un_identifiant_de_profil_avec_un_point_est_refuse(tmp_path):
    """Le lanceur retrouve le profil dans « <profil>.<système> » en coupant au
    premier point : un identifiant qui en porte un désignerait un autre
    profil, et l'amorçage viserait la configuration d'un autre émulateur."""
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "x.toml", _avec_id("duck.station")))
    assert "point" in str(e.value)


def test_un_identifiant_qui_porte_bootstrap_est_refuse(tmp_path):
    """`profils_amorcables` retrouve l'identifiant en coupant le nom de
    fichier sur « .bootstrap » : un identifiant qui porte cette chaîne se
    couperait au mauvais endroit, et « retro launcher --reamorcer » refuserait
    un profil pourtant amorçable."""
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(
            ecrire(tmp_path, "x.toml", _avec_id("duck.bootstrap")))


def test_un_identifiant_ordinaire_reste_accepte(tmp_path):
    """La règle ne doit pas fermer la porte aux identifiants normaux — tiret
    et souligné compris, que les profils du propriétaire emploient."""
    profil = profiles.load_profile(
        ecrire(tmp_path, "x.toml", _avec_id("duck-station_2")))
    assert profil.id == "duck-station_2"


def test_l_exemple_de_bootstrap_de_la_specification_se_charge(tmp_path):
    """La spec est le point de départ de la tâche qui mesurera les huit autres
    émulateurs : un exemple que le validateur refuse ferait démarrer cette
    tâche sur un ProfileError, et son auteur corrigerait le validateur.

    L'exemple est extrait du document, pas recopié ici : recopié, il aurait
    cessé de dire quoi que ce soit du document le jour où celui-ci change.
    """
    import tomllib
    spec = (pathlib.Path(__file__).parent.parent / "docs" / "superpowers"
            / "specs" / "2026-08-28-amorcage-emulateurs-design.md")
    # [1:] : le premier morceau est la PROSE qui précède la première clôture,
    # et elle nomme le bloc sans le montrer.
    blocs = [b.split("```")[0] for b in
             spec.read_text(encoding="utf-8").split("```toml\n")[1:]]
    exemple = [b for b in blocs if "[[bootstrap]]" in b]
    assert exemple, "la spec ne montre plus d'exemple de bloc [[bootstrap]]"
    for bloc in exemple:
        assert profiles._lire_bootstraps(
            spec, tomllib.loads(bloc)["bootstrap"])


# --- le troisième axe : le remplissage -----------------------------------

REMPLI = """
[system.render.native]
args = "-scale=1 -integer=yes"
crt_absent = "aucun shader"
fill = "entier"
[system.render.full]
args = "-scale=4 -integer=no"
fill = "ajuste"
"""


def test_un_remplissage_declare_se_charge(tmp_path):
    from retro import render
    p = profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu(REMPLI)))
    assert p.systems[0].render.native.fill == render.ENTIER
    assert p.systems[0].render.full.fill == render.AJUSTE


def test_un_emulateur_sans_reglage_de_remplissage_le_declare(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
crt_absent = "aucun shader"
fill_absent = "aucune clé de mise à l'échelle entière dans cette révision"
[system.render.full]
args = "-scale=4"
fill_absent = "aucune clé de mise à l'échelle entière dans cette révision"
""")))
    assert "entière" in p.systems[0].render.full.fill_absent


def test_un_remplissage_inconnu_est_refuse(tmp_path):
    """« integer », « ajusté », « fit » : une valeur qu'aucune politique ne
    connaît ne serait comparée à rien, et le mode partirait sans son
    troisième axe sans qu'un mot le dise."""
    with pytest.raises(profiles.ProfileError, match="remplissage inconnu"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
crt_absent = "aucun"
fill = "integer"
[system.render.full]
args = "-y"
fill = "ajuste"
""")))


def test_un_remplissage_contraire_a_la_politique_est_refuse(tmp_path):
    """Un mode natif qui remplirait « au plus grand » rééchantillonnerait la
    trame que le mode natif existe pour préserver — et la contradiction ne se
    verrait que sur l'écran, sur une image floue qu'on croirait normale."""
    with pytest.raises(profiles.ProfileError, match="la politique de remplissage"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
crt_absent = "aucun"
fill = "ajuste"
[system.render.full]
args = "-y"
fill = "ajuste"
""")))


def test_le_remplissage_et_son_absence_a_la_fois_sont_refuses(tmp_path):
    with pytest.raises(profiles.ProfileError, match="SOIT 'fill'"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = "-scale=1"
crt_absent = "aucun"
fill = "entier"
fill_absent = "rien à régler"
[system.render.full]
args = "-y"
""")))


def test_un_remplissage_declare_sur_un_mode_vide_est_refuse(tmp_path):
    """Un mode sans le moindre argument ne passe RIEN à l'émulateur : y
    déclarer un remplissage serait un réglage que rien n'appliquerait."""
    with pytest.raises(profiles.ProfileError, match="Rien ne l'appliquerait"):
        profiles.load_profile(ecrire(tmp_path, "e.toml", profil_rendu("""
[system.render.native]
args = ""
note = "aucun réglage en ligne de commande"
crt_absent = "aucun"
fill = "entier"
[system.render.full]
args = "-y"
""")))


def test_un_profil_qui_ne_tranche_pas_sur_le_remplissage_reste_valide(tmp_path):
    """Le troisième axe se remplit émulateur par émulateur, comme les deux
    autres. Ce qui est interdit, c'est qu'un profil muet ait l'air tranché :
    c'est `retro status` qui nomme ceux qui ne le sont pas."""
    p = profiles.load_profile(ecrire(tmp_path, "e.toml",
                                     profil_rendu(RENDU_VALIDE)))
    assert p.systems[0].render.native.fill == ""
    assert p.systems[0].render.native.fill_absent == ""


# --- les deux régimes d'un amorçage ---------------------------------------
#
# Un même fichier cible porte deux choses qui ne se gouvernent pas pareil :
# ce que la console IMPOSE (sans quoi un jeu ne démarre pas sans clavier) et
# ce qu'elle a POSÉ UNE FOIS parce que le fichier n'existait pas (des
# préférences, qui appartiennent au propriétaire dès la seconde suivante).
#
# Le régime est STRUCTUREL : deux champs distincts, `content` et `enforced`.
# Il ne se déclare pas dans un mode qu'on pourrait mettre en contradiction
# avec ce que le bloc contient — et il se lit d'un coup d'œil dans le profil.

ENTETE_TROIS = """; Écrit par « retro », qui distingue trois choses ici : ce qu'il IMPOSE et
; repose à chaque lancement, ce qu'il a posé UNE FOIS et ne retouche plus, et
; tout le reste, qui vous appartient."""


def _amorcage(content_keys: str, enforced: str = "",
              entete: str = ENTETE_TROIS) -> str:
    bloc = f"""
schema = 1
id = "duckstation"
exe = 'duckstation-qt.exe'
[[bootstrap]]
target = '%USERPROFILE%\\\\Documents\\\\DuckStation\\\\settings.ini'
content = '''
{entete}
{content_keys}
'''
"""
    if enforced:
        bloc += f"enforced = '''\n{enforced}\n'''\n"
    return bloc + """
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{rom}"'
"""


# --- [input] mapping : ce que le profil SAIT de sa manette ---------------
#
# Dette D3 : la manette reste muette dans DuckStation, et rien ne le disait.
# Le champ ne porte JAMAIS un identifiant : il porte l'état du RELEVÉ, seule
# chose qu'on puisse écrire sans mesurer. Un identifiant recopié d'ailleurs
# est un défaut muet — l'émulateur ignore une liaison qui ne correspond à rien
# sans un mot, et la manette reste muette comme si le fichier était vide.

_SANS_INPUT = """
schema = 1
id = "duckstation"
exe = "duckstation.exe"

[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch "{rom}"'
"""


def test_un_amorcage_sans_cles_imposees_reste_valide(tmp_path):
    """Huit profils livrés n'imposent rien : ne rien déclarer doit continuer
    de vouloir dire « posé une fois, jamais retouché »."""
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _amorcage(
        "[Main]\nConfirmPowerOff = false")))
    assert p.bootstraps[0].enforced == ""


def test_les_cles_imposees_se_declarent_a_part(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _amorcage(
        "[Main]\nConfirmPowerOff = false",
        enforced="[Main]\nSetupWizardIncomplete = false")))
    assert "SetupWizardIncomplete" in p.bootstraps[0].enforced
    assert "ConfirmPowerOff" not in p.bootstraps[0].enforced


def test_une_cle_dans_les_deux_regimes_est_refusee(tmp_path):
    """Le même réglage décidé à deux endroits : l'un des deux perdrait
    toujours — le fusionné écrase le posé — et personne, en lisant le profil,
    ne pourrait dire lequel gagne. C'est la faute que ce dépôt refuse partout
    ailleurs, et elle serait ici parfaitement muette."""
    with pytest.raises(profiles.ProfileError, match="DEUX régimes"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _amorcage(
            "[Main]\nStartFullscreen = true",
            enforced="[Main]\nStartFullscreen = true")))


def test_la_meme_cle_dans_deux_sections_differentes_est_permise(tmp_path):
    """« Enabled » sous [Pad1] et sous [Display] ne sont pas le même réglage :
    la comparaison porte sur le couple section/clé, pas sur le nom seul."""
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _amorcage(
        "[Display]\nEnabled = true",
        enforced="[Pad1]\nEnabled = true")))
    assert p.bootstraps[0].enforced


def test_un_amorcage_qui_impose_doit_distinguer_les_trois_categories(tmp_path):
    """L'en-tête PROMET quelque chose. « Vos réglages ne sont jamais
    retouchés » était vrai quand rien n'était imposé ; il devient faux pour
    les clés reposées. Mais dire « tout est reposé » serait faux aussi, pour
    les préférences. Les trois catégories doivent se lire."""
    with pytest.raises(profiles.ProfileError, match="TROIS"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _amorcage(
            "[Main]\nConfirmPowerOff = false",
            enforced="[Main]\nSetupWizardIncomplete = false",
            entete="; Écrit par « retro ». Vos réglages ne sont jamais "
                   "retouchés.")))


def test_un_amorcage_qui_n_impose_rien_garde_l_ancienne_promesse(tmp_path):
    """La garde ne se déclenche QUE s'il y a des clés imposées : les profils
    qui n'en ont pas gardent leur en-tête, qui reste vrai."""
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _amorcage(
        "[Main]\nConfirmPowerOff = false",
        entete="; Écrit par « retro » : ce fichier n'est posé que s'il est "
               "absent, vos réglages ne sont jamais retouchés.")))
    assert p.bootstraps


def _avec_input(bloc: str) -> str:
    return _SANS_INPUT.replace("[[system]]", bloc + "\n[[system]]", 1)


def test_un_profil_muet_sur_sa_manette_vaut_inconnu(tmp_path):
    """Le défaut ne peut être ni « auto » ni « à relever ».

    « auto » ferait dire au rapport que neuf émulateurs trouvent leur manette
    seuls, ce que personne n'a mesuré — c'est exactement le mensonge de
    `steam_input = "required"`, que le code lisait sans jamais l'appliquer.
    « à relever » accuserait de la même façon huit émulateurs d'une panne que
    personne n'a constatée. « inconnu » est le seul état vrai d'un profil qui
    se tait.
    """
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _SANS_INPUT))
    assert p.input_mapping == profiles.MAPPING_INCONNU


def test_un_profil_declare_que_sa_manette_reste_a_relever(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
        '[input]\nmapping = "a-relever"\n'
        "mapping_where = '%USERPROFILE%\\\\Documents\\\\D\\\\settings.ini, "
        "section [Pad1]'\n")))
    assert p.input_mapping == profiles.MAPPING_A_RELEVER
    assert "[Pad1]" in p.input_mapping_where


def test_un_profil_declare_un_releve_clos_sans_dire_que_l_emulateur_trouve_seul(tmp_path):
    """Le quatrième état, né le 2026-08-29 avec la clôture de D3.

    Il dit une chose qu'aucun des trois autres ne pouvait dire : le relevé est
    fait, les liaisons sont IMPOSÉES par la console, et un bouton a été VU
    répondre dans un jeu. C'est le seul état de ce vocabulaire qui exige un
    témoin humain.

    Ce qu'il ne dit PAS, et c'est pour cela qu'il n'est pas « auto » :
    l'émulateur ne trouve toujours pas sa manette seul. Confondre les deux
    ferait disparaître du dépôt la raison pour laquelle `enforced` existe.
    """
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
        '[input]\nmapping = "releve"\n'
        "mapping_where = '%USERPROFILE%\\\\Documents\\\\D\\\\settings.ini, "
        "section [Pad1]'\n")))
    assert p.input_mapping == profiles.MAPPING_RELEVE
    assert p.input_mapping != profiles.MAPPING_AUTO
    assert "[Pad1]" in p.input_mapping_where


def test_un_releve_clos_sans_ou_est_refuse(tmp_path):
    """Même exigence que « a-relever », pour la raison INVERSE.

    « a-relever » nomme le fichier où le relevé se fera. « releve » nomme celui
    où les liaisons sont reposées à chaque lancement — le seul endroit où
    vérifier qu'elles y sont encore. Une console dont un pad de plus s'énumère
    avant celui d'Apollo redevient muette en silence : sans ce chemin, le
    rapport dirait « ça marche » et n'offrirait rien à regarder.
    """
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nmapping = "releve"\n')))


def test_un_profil_peut_declarer_que_l_emulateur_trouve_seul(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
        '[input]\nmapping = "auto"\n')))
    assert p.input_mapping == profiles.MAPPING_AUTO


def test_un_etat_de_mapping_inconnu_du_code_est_refuse(tmp_path):
    """Une faute de frappe — « arelever » — retomberait sinon sur le défaut et
    ferait taire le rapport sur l'émulateur précisément concerné."""
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nmapping = "arelever"\n')))


def test_un_mapping_a_relever_sans_ou_est_refuse(tmp_path):
    """« un constat sans chemin ni action n'aide personne » : c'est la règle
    de `retro status`, et un profil qui déclare sa manette à relever sans dire
    OÙ produirait exactement l'accusation sans diagnostic qu'elle interdit."""
    with pytest.raises(profiles.ProfileError):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nmapping = "a-relever"\n')))


def test_mapping_where_reste_facultatif_quand_rien_n_est_a_relever(tmp_path):
    """Un émulateur qui trouve sa manette seul n'a aucun fichier à nommer, et
    un profil qui n'a jamais été mesuré ne sait pas où regarder."""
    for etat in ("auto", "inconnu"):
        p = profiles.load_profile(ecrire(tmp_path, f"{etat}.toml", _avec_input(
            f'[input]\nmapping = "{etat}"\n')))
        assert p.input_mapping_where == ""


def test_une_cle_inconnue_du_bloc_input_est_refusee(tmp_path):
    """La fragilité que le plan D1 exige de fermer AVANT d'ajouter un champ.

    `render` et `render.<mode>` refusent leurs clés inconnues depuis toujours ;
    `[input]` ne refusait rien. Un « rumbl » mal orthographié retombait donc
    en silence sur le défaut, et le rapport se taisait sur l'émulateur
    précisément concerné — une valeur fausse se comportant exactement comme
    l'absence de valeur, la règle de fond de ce dépôt.
    """
    with pytest.raises(profiles.ProfileError, match="inconnues"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nrumbl = "vu"\n')))



# --- [input] rumble : où en est la VIBRATION de cet émulateur --------------
#
# Dette D1 : la manette ne vibre nulle part, et l'aveu vivait dans des
# commentaires TOML qu'aucun code ne lit. Le champ suit le chemin déjà tracé
# par `mapping` — un vocabulaire fermé qui dit où en est la MESURE, jamais un
# nom de clé deviné. Cinq états, et il en faut cinq : chacun affirme une chose
# que les quatre autres ne disent pas.


def test_un_profil_muet_sur_sa_vibration_vaut_inconnu(tmp_path):
    """Le défaut ne peut être aucun des quatre autres.

    `vu` affirmerait qu'un témoin humain a senti la manette vibrer sur dix
    émulateurs — la seule affirmation de ce vocabulaire qui ne se déduise
    d'aucun fichier. `pose` affirmerait un réglage que personne n'a écrit.
    `absent` affirmerait une lecture de la source que personne n'a faite.
    `a-relever` accuserait dix émulateurs d'une panne constatée sur aucun.
    """
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _SANS_INPUT))
    assert p.input_rumble == profiles.RUMBLE_INCONNU


def test_un_profil_declare_un_reglage_de_vibration_pose_mais_jamais_vu_agir(tmp_path):
    """C'est l'état de DuckStation le 2026-08-29, et aucun autre ne le décrit.

    Ses deux liaisons `LargeMotor` et `SmallMotor` ont été écrites par son
    propre assistant, elles sont reposées à chaque lancement — et personne ne
    les a vues faire vibrer quoi que ce soit. `vu` mentirait, `a-relever`
    effacerait un relevé fait, `absent` serait faux, `inconnu` effacerait la
    mesure.
    """
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
        '[input]\nrumble = "pose"\n'
        "rumble_where = '%USERPROFILE%\\\\Documents\\\\D\\\\settings.ini, "
        "section [Pad1]'\n")))
    assert p.input_rumble == profiles.RUMBLE_POSE
    assert "[Pad1]" in p.input_rumble_where


def test_un_etat_de_vibration_inconnu_du_code_est_refuse(tmp_path):
    """« posé » pour « pose » retomberait sinon sur le défaut, et le rapport
    dirait « jamais mesuré » du seul émulateur qui porte un réglage."""
    with pytest.raises(profiles.ProfileError, match="attendu l'un de"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nrumble = "posé"\n')))


def test_une_vibration_posee_sans_ou_est_refusee(tmp_path):
    """Même exigence que `mapping_where`, et pour la même raison : un réglage
    posé peut cesser d'agir sans un mot, et le rapport n'offrirait alors rien
    à ouvrir."""
    with pytest.raises(profiles.ProfileError, match="rumble_where"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nrumble = "pose"\n')))


def test_une_vibration_a_relever_sans_ou_est_refusee(tmp_path):
    """« un constat sans chemin ni action n'aide personne » : `retro status`
    lèvera un problème pour cet état, et un problème sans fichier à ouvrir est
    une accusation."""
    with pytest.raises(profiles.ProfileError, match="rumble_where"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nrumble = "a-relever"\n')))


def test_une_vibration_mesuree_absente_ne_nomme_aucun_fichier(tmp_path):
    """`absent` existe pour la raison qui a fait naître `fill_absent` : « il
    n'y a rien à régler, et c'est mesuré » n'est pas « personne n'a regardé ».
    Un émulateur sans réglage de rumble n'a aucun fichier à faire ouvrir."""
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
        '[input]\nrumble = "absent"\n')))
    assert p.input_rumble == profiles.RUMBLE_ABSENT
    assert p.input_rumble_where == ""



def test_une_vibration_vue_sans_temoin_est_refusee(tmp_path):
    """« Un témoin humain, ou rien. »

    `vu` est le seul état de ce vocabulaire qui ne se déduise d'AUCUN fichier :
    aucune clé survivante, aucune ligne de journal ne prouve qu'une manette a
    vibré. Sans témoin, cet état serait une affirmation que rien ne soutient —
    et il ferait disparaître du rapport le seul émulateur qui resterait à
    mesurer. Le profil est donc refusé au chargement, pas seulement signalé.
    """
    with pytest.raises(profiles.ProfileError, match="rumble_witness"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nrumble = "vu"\n'
            "rumble_where = 'settings.ini, section [Pad1]'\n")))


def test_un_temoin_de_vibration_sans_date_est_refuse(tmp_path):
    """Un témoignage sans date ne se vérifie contre rien — ni contre une
    révision d'émulateur épinglée au manifeste, ni contre un changement de type
    de pad qui casserait la liaison le lendemain (dette D4)."""
    with pytest.raises(profiles.ProfileError, match="date"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nrumble = "vu"\n'
            "rumble_where = 'settings.ini, section [Pad1]'\n"
            "rumble_witness = 'le propriétaire, sur Crash Team Racing'\n")))


def test_un_temoin_date_qui_nomme_un_jeu_est_accepte(tmp_path):
    """La forme exigée, et rien de plus : une date, et une formule libre. Ce
    qui se vérifie mécaniquement se vérifie ; le reste se lit."""
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
        '[input]\nrumble = "vu"\n'
        "rumble_where = 'settings.ini, section [Pad1]'\n"
        "rumble_witness = 'le propriétaire, 2026-08-29, sur Crash Team "
        "Racing'\n")))
    assert p.input_rumble == profiles.RUMBLE_VU
    assert "2026-08-29" in p.input_rumble_witness


def test_un_temoin_sur_un_etat_autre_que_vu_est_refuse(tmp_path):
    """Les deux se contredisent : un témoin dit que quelqu'un a SENTI la
    manette vibrer, ce qui EST l'état `vu`. Le rapport suivrait le champ et
    tairait le témoignage — ou l'inverse, et personne ne saurait lequel."""
    with pytest.raises(profiles.ProfileError, match="contredisent"):
        profiles.load_profile(ecrire(tmp_path, "d.toml", _avec_input(
            '[input]\nrumble = "pose"\n'
            "rumble_where = 'settings.ini, section [Pad1]'\n"
            "rumble_witness = 'le propriétaire, 2026-08-29, sur CTR'\n")))


# --- un jeu qui est un DOSSIER ---------------------------------------------
#
# `extensions` dit ce qu'est un jeu quand un jeu est un fichier. Une
# bibliothèque PS Vita est faite d'applications INSTALLÉES, qui sont des
# dossiers. Le scan ne peut pas le deviner — deviner ferait une entrée Steam
# de chaque dossier de sauvegardes — donc le profil le DÉCLARE, comme il
# déclare déjà ses `folders` et ses extensions.

APPS = """
schema = 1
id = "vita3k"
exe = "Vita3K.exe"
[[system]]
id = "vita"
name = "PS Vita"
extensions = [".vpk"]
app_dir_marker = "eboot.bin"
launch = '--fullscreen "{rom}"'
bios = []
"""


def test_le_marqueur_de_dossier_est_charge(tmp_path):
    p = profiles.load_profile(ecrire(tmp_path, "vita3k.toml", APPS))
    assert p.systems[0].app_dir_marker == "eboot.bin"


def test_sans_marqueur_le_systeme_n_en_a_pas(tmp_path):
    """Les neuf profils livrés n'en déclarent aucun : leur comportement ne
    change pas, et l'absence se lit comme une absence."""
    p = profiles.load_profile(ecrire(tmp_path, "retroarch.toml", RETROARCH))
    assert all(s.app_dir_marker == "" for s in p.systems)


def test_un_marqueur_de_dossier_vide_refuse(tmp_path):
    """Déclaré vide, il ne reconnaîtrait aucun dossier : le système aurait
    l'air de couvrir une bibliothèque en dossiers et rendrait zéro jeu."""
    with pytest.raises(profiles.ProfileError, match="app_dir_marker"):
        profiles.load_profile(ecrire(
            tmp_path, "v.toml", APPS.replace('"eboot.bin"', '""')))


def test_un_marqueur_de_dossier_non_textuel_refuse(tmp_path):
    with pytest.raises(profiles.ProfileError, match="app_dir_marker"):
        profiles.load_profile(ecrire(
            tmp_path, "v.toml", APPS.replace('"eboot.bin"', "true")))


def test_un_marqueur_de_dossier_qui_est_un_chemin_refuse(tmp_path):
    """Le marqueur est cherché à la RACINE du dossier d'application. Un chemin
    n'y serait comparé à rien, et le système rendrait zéro jeu sans un mot —
    la même faute muette que `folders` avec un séparateur."""
    with pytest.raises(profiles.ProfileError, match="app_dir_marker"):
        profiles.load_profile(ecrire(
            tmp_path, "v.toml",
            APPS.replace('"eboot.bin"', '"sce_sys/param.sfo"')))


# --- le jeton de chemin d'une cible d'amorçage ----------------------------

def _cible(target: str) -> str:
    """Le profil d'amorçage valide, avec une autre cible."""
    return BOOTSTRAP_VALIDE.replace(
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini", target)


def test_une_cible_sous_le_dossier_d_installation_est_acceptee(tmp_path):
    """La configuration de Vita3K, de RPCS3 et de Cemu vit sous le dossier
    d'INSTALLATION de l'émulateur, dont le nom se surcharge au manifeste du
    propriétaire. Sans jeton, ces cibles ne sont pas écrivables — le validateur
    les refusait comme des chemins relatifs."""
    p = profiles.load_profile(ecrire(tmp_path, "vita3k.toml", _cible(
        "{install_dir}\\gui-configs\\CurrentSettings.ini")))
    assert p.bootstraps[0].target == "{install_dir}\\gui-configs\\CurrentSettings.ini"


def test_un_jeton_de_cible_inconnu_est_refuse(tmp_path):
    """Un jeton mal orthographié tombait dans le message « chemin absolu »,
    qui envoie corriger la mauvaise chose. Le refus NOMME le jeton reçu et
    cite ceux qui existent : un refus qui ne dit pas ce qui est permis fait
    relire le validateur au lieu du profil."""
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "x.toml",
                                     _cible("{emulation_root}\\x.ini")))
    assert "{emulation_root}" in str(e.value)
    assert profiles.JETON_INSTALL in str(e.value)


# --- plusieurs cibles par profil ------------------------------------------

DEUX_AMORCAGES = """
schema = 1
id = "rpcs3"
exe = 'rpcs3.exe'
[[bootstrap]]
target = '{install_dir}\\GuiConfigs\\CurrentSettings.ini'
content = '''
; Écrit par « retro » au premier lancement, parce que ce fichier était absent.
[main_window]
confirmationBoxBootGame=false
'''
[[bootstrap]]
target = '{install_dir}\\config\\input_configs\\global\\Default.yml'
content = '''
# Écrit par « retro » au premier lancement, parce que ce fichier était absent.
Player 1 Input:
  Handler: XInput
'''
[[system]]
id = "ps3"
name = "PlayStation 3"
extensions = [".iso"]
launch = '--no-gui "{rom}"'
"""


def test_un_profil_declare_plusieurs_amorcages(tmp_path):
    """RPCS3 a DEUX fichiers à recevoir — ses modales et sa manette — et rien
    ne permettait de le dire : un profil ne portait qu'une cible. L'ordre est
    celui du fichier, parce que c'est le seul que le lecteur du profil voit."""
    p = profiles.load_profile(ecrire(tmp_path, "rpcs3.toml", DEUX_AMORCAGES))
    assert [b.target for b in p.bootstraps] == [
        "{install_dir}\\GuiConfigs\\CurrentSettings.ini",
        "{install_dir}\\config\\input_configs\\global\\Default.yml",
    ]


def test_un_bloc_d_amorcage_au_singulier_est_refuse(tmp_path):
    """Une seule forme est acceptée. Garder les deux ferait deux façons
    d'écrire la même chose, et le jour où quelqu'un mélange, rien ne dirait
    laquelle gagne — le profil se chargerait, à moitié appliqué."""
    texte = DEUX_AMORCAGES.replace("[[bootstrap]]", "[bootstrap]", 1)
    texte = texte[:texte.index("[[bootstrap]]")] + \
        texte[texte.index("[[system]]"):]
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "rpcs3.toml", texte))
    assert "[[bootstrap]]" in str(e.value)


# --- le remplissage IMPOSÉ PAR L'AMORÇAGE, et ses cinq refus -------------
#
# Deux champs sur [system.render] — donc pour LES DEUX modes, parce que le
# fragment `enforced` est posé une fois par lancement, avant que le mode ne
# soit résolu. Chaque refus ci-dessous porte sur une faute MUETTE : le profil
# se chargerait, `retro status` annoncerait un remplissage, et rien ne serait
# posé sur la machine.

def _profil_impose(render_extra: str, enforced: str,
                   modes: str = '''[system.render.native]
args = ""
note = "rien en ligne de commande"
crt_absent = "aucun shader en ligne de commande"
[system.render.full]
args = ""
note = "rien en ligne de commande"
''') -> str:
    """Un profil DuckStation-comme : deux modes vides, un fragment imposé."""
    return f'''
schema = 1
id = "duckstation"
exe = "duckstation-qt.exe"
[[bootstrap]]
target = '%USERPROFILE%\\\\Documents\\\\DuckStation\\\\settings.ini'
content = """
{ENTETE_TROIS}
[Main]
ConfirmPowerOff = false
"""
enforced = """
{enforced}
"""
[[system]]
id = "psx"
name = "PlayStation"
extensions = [".cue"]
launch = '-batch {{render}} "{{rom}}"'
cost = "light"
{modes}[system.render]
{render_extra}
'''


_OU_VALIDE = "[Display] Scaling = ValeurRelevee — relevé le 2026-01-01"
_ENFORCED_SCALING = "[Display]\nScaling = ValeurRelevee"


def test_un_remplissage_impose_se_declare_sur_le_bloc_render(tmp_path):
    """Le chaînon qui manquait : DuckStation ne passe rien en ligne de
    commande, mais la console pose son remplissage dans son settings.ini."""
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
        f'fill_enforced = "entier"\nfill_enforced_where = "{_OU_VALIDE}"',
        _ENFORCED_SCALING)))
    rendu = p.systems[0].render
    assert rendu.fill_enforced == "entier"
    assert rendu.fill_enforced_where == _OU_VALIDE


def test_un_remplissage_impose_inconnu_est_refuse(tmp_path):
    """Une valeur hors de l'axe ne serait comparée à rien, et le rapport
    l'imprimerait telle quelle comme si elle voulait dire quelque chose."""
    with pytest.raises(profiles.ProfileError, match="d.toml") as e:
        profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
            f'fill_enforced = "etire"\nfill_enforced_where = "{_OU_VALIDE}"',
            _ENFORCED_SCALING)))
    assert "etire" in str(e.value)


def test_un_remplissage_impose_sans_son_where_est_refuse(tmp_path):
    """Sans le `where`, personne ne peut vérifier que la clé est bien posée —
    ni la garde de cohérence, ni un relecteur, ni le propriétaire."""
    with pytest.raises(profiles.ProfileError,
                       match="fill_enforced_where") as e:
        profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
            'fill_enforced = "entier"', _ENFORCED_SCALING)))
    assert "d.toml" in str(e.value)


def test_un_where_sans_remplissage_impose_est_refuse(tmp_path):
    """L'autre sens de la même paire : un `where` seul décrit un réglage que
    rien ne déclare, et le rapport n'en dirait pas un mot."""
    with pytest.raises(profiles.ProfileError,
                       match="vont ensemble") as e:
        profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
            f'fill_enforced_where = "{_OU_VALIDE}"', _ENFORCED_SCALING)))
    assert "d.toml" in str(e.value)


def test_un_where_qui_ne_commence_pas_par_section_cle_est_refuse(tmp_path):
    """Le préfixe « [Section] Clé » n'est pas décoratif : c'est ce que la
    garde de cohérence analyse pour vérifier que la clé est bien imposée."""
    with pytest.raises(profiles.ProfileError, match=r"\[Section\] Clé") as e:
        profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
            'fill_enforced = "entier"\n'
            'fill_enforced_where = "posé dans son settings.ini"',
            _ENFORCED_SCALING)))
    assert "d.toml" in str(e.value)


def test_un_remplissage_impose_qui_coexiste_avec_un_fill_de_mode_est_refuse(
        tmp_path):
    """Deux endroits décideraient du même réglage — la faute que
    `_valider_regimes` refuse déjà pour les deux régimes de l'amorçage."""
    modes = '''[system.render.native]
args = "-scale=1"
fill = "entier"
crt_absent = "aucun shader en ligne de commande"
[system.render.full]
args = "-scale=2"
'''
    with pytest.raises(profiles.ProfileError, match="deux endroits") as e:
        profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
            f'fill_enforced = "entier"\nfill_enforced_where = "{_OU_VALIDE}"',
            _ENFORCED_SCALING, modes=modes)))
    assert "d.toml" in str(e.value)


def test_un_remplissage_impose_qui_coexiste_avec_un_fill_absent_est_refuse(
        tmp_path):
    """Même faute dans l'autre sens : « cet émulateur n'expose rien » et
    « la console lui impose ceci » ne peuvent pas être vrais ensemble."""
    modes = '''[system.render.native]
args = ""
note = "rien en ligne de commande"
fill_absent = "aucune clé de cet axe"
crt_absent = "aucun shader en ligne de commande"
[system.render.full]
args = ""
note = "rien en ligne de commande"
'''
    with pytest.raises(profiles.ProfileError, match="deux endroits") as e:
        profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
            f'fill_enforced = "entier"\nfill_enforced_where = "{_OU_VALIDE}"',
            _ENFORCED_SCALING, modes=modes)))
    assert "d.toml" in str(e.value)


def test_un_remplissage_impose_sur_une_cle_que_rien_ne_pose_est_refuse(
        tmp_path):
    """LA GARDE DE COHÉRENCE. Sans elle, un profil annoncerait un remplissage
    que rien ne pose : la clé nommée par le `where` doit figurer dans le
    fragment `enforced`, sinon le rapport ment et la machine ne bouge pas."""
    with pytest.raises(profiles.ProfileError, match=r"\[Display\] Scaling") as e:
        profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
            f'fill_enforced = "entier"\nfill_enforced_where = "{_OU_VALIDE}"',
            "[Main]\nSetupWizardIncomplete = false")))
    assert "d.toml" in str(e.value)


def test_la_garde_de_coherence_regarde_tous_les_amorcages(tmp_path):
    """La clé peut être posée par n'importe lequel des blocs [[bootstrap]] du
    profil : RPCS3 en a deux, et exiger le premier serait arbitraire."""
    p = profiles.load_profile(ecrire(tmp_path, "d.toml", _profil_impose(
        f'fill_enforced = "entier"\nfill_enforced_where = "{_OU_VALIDE}"',
        _ENFORCED_SCALING).replace(
            '[[system]]',
            "[[bootstrap]]\ntarget = 'C:\\\\autre.ini'\n"
            f'content = """\n{ENTETE_TROIS}\n[X]\nY = 1\n"""\n'
            'enforced = """\n[Z]\nW = 2\n"""\n\n[[system]]', 1)))
    assert p.systems[0].render.fill_enforced == "entier"

# --- le second dialecte de fusion : le YAML plat --------------------------
#
# La fusion du projet ne parlait qu'INI, et son défaut aurait été muet : la
# modale des polices de Vita3K se ferme par une clé qui vit dans un
# `config.yml`, et `cles_ini` — comme `CleDe` dans le lanceur — exige un « = ».
# Une ligne « warn-missing-firmware: false » n'aurait donc posé RIEN, sans un
# mot, et les deux gardes bâties sur `cles_ini` auraient gardé le vide.

_YAML_AMORCAGE = """
schema = 1
id = "vita3k"
exe = 'Vita3K.exe'
[[bootstrap]]
target = '{install_dir}\\config.yml'
content = '''
# Écrit par « retro », qui distingue trois choses : ce qu'il IMPOSE et repose
# à chaque lancement, ce qu'il a posé UNE FOIS et ne retouche plus, et tout le
# reste, qui vous appartient.
__CONTENU__
'''
enforced = '''
__IMPOSE__
'''
[[system]]
id = "vita"
name = "PS Vita"
extensions = [".vpk"]
launch = '--fullscreen "{rom}"'
"""


def _yaml_amorcage(contenu: str = "", impose: str = "") -> str:
    return (_YAML_AMORCAGE.replace("__CONTENU__", contenu)
            .replace("__IMPOSE__", impose))


def test_les_cles_d_un_fragment_yaml_sont_lues_sans_section():
    """Un YAML plat n'a pas de sections : la clé se lit seule, sous « »."""
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
    """« - libscemp4 » appartient à la clé du dessus. La compter séparément
    ferait croire à un réglage que rien ne lit."""
    assert profiles.cles_yaml("lle-modules:\n  - libscemp4\n") == [
        ("", "lle-modules")]


def test_le_dialecte_suit_l_extension_de_la_cible():
    """Le dialecte se déduit de l'extension du fichier VISÉ, pas d'un champ
    déclaré : un champ pourrait contredire ce que le fragment contient, une
    extension non."""
    assert profiles.cles_de("C:\\x\\a.ini", "[S]\nk = 1\n") == [("S", "k")]
    assert profiles.cles_de("C:\\x\\config.yml", "k: 1\n") == [("", "k")]


def test_deux_cles_yaml_dans_les_deux_regimes_sont_refusees(tmp_path):
    """La garde des deux régimes est bâtie sur l'analyse des clés. Branchée
    sur `cles_ini` seule, elle ne trouvait aucun « = » dans un YAML, rendait
    une liste vide, et l'intersection était TOUJOURS vide : la garde ne
    gardait plus rien, précisément sur le seul profil qui en avait besoin."""
    with pytest.raises(profiles.ProfileError, match="DEUX régimes"):
        profiles.load_profile(ecrire(tmp_path, "v.toml", _yaml_amorcage(
            contenu="warn-missing-firmware: true",
            impose="warn-missing-firmware: false")))


def test_deux_cles_yaml_distinctes_dans_les_deux_regimes_passent(tmp_path):
    """Le pendant du refus : deux clés différentes ne se recouvrent pas, et
    une garde qui refuserait tout serait aussi inutile qu'une qui accepte
    tout."""
    p = profiles.load_profile(ecrire(tmp_path, "v.toml", _yaml_amorcage(
        contenu="pref-path: D:\\v",
        impose="warn-missing-firmware: false")))
    assert profiles.cles_de(p.bootstraps[0].target, p.bootstraps[0].enforced) \
        == [("", "warn-missing-firmware")]


def test_la_marque_d_amorcage_se_porte_en_commentaire_yaml(tmp_path):
    """`MARQUE_BOOTSTRAP` est cherchée en SOUS-CHAÎNE : un « # » YAML la porte
    aussi bien qu'un « ; » INI. Ce test le fige, pour qu'un durcissement futur
    de la garde ne casse pas le seul profil YAML livré."""
    p = profiles.load_profile(ecrire(tmp_path, "v.toml", _yaml_amorcage(
        impose="warn-missing-firmware: false")))
    assert profiles.MARQUE_BOOTSTRAP in p.bootstraps[0].content
    assert p.bootstraps[0].content.lstrip().startswith("#")


def test_le_refus_des_deux_regimes_nomme_une_cle_yaml_lisiblement(tmp_path):
    """Un YAML plat n'a pas de section. Le message la rendait quand même —
    « [] warn-missing-firmware » — et le lecteur serait parti chercher une
    section inexistante dans un fichier qui n'en porte aucune."""
    with pytest.raises(profiles.ProfileError) as e:
        profiles.load_profile(ecrire(tmp_path, "v.toml", _yaml_amorcage(
            contenu="warn-missing-firmware: true",
            impose="warn-missing-firmware: false")))
    assert "[]" not in str(e.value)
    assert "warn-missing-firmware" in str(e.value)
