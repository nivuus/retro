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
[bootstrap]
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
    assert profil.bootstrap is not None
    assert profil.bootstrap.target == (
        "%USERPROFILE%\\Documents\\DuckStation\\settings.ini")
    assert "SetupWizardIncomplete = false" in profil.bootstrap.content


def test_un_profil_sans_bootstrap_reste_valide(tmp_path):
    """Un émulateur qui démarre nu n'a pas de bloc, et son profil doit
    continuer de se charger."""
    sans = BOOTSTRAP_VALIDE[:BOOTSTRAP_VALIDE.index("[bootstrap]")] + \
        BOOTSTRAP_VALIDE[BOOTSTRAP_VALIDE.index("[[system]]"):]
    assert profiles.load_profile(ecrire(tmp_path, "duckstation.toml", sans)).bootstrap is None


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
