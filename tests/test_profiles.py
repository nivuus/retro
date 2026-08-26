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
