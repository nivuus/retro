"""Métadonnées : ce que Steam sait afficher, et rien de plus.

shortcuts.vdf n'a aucun champ de description, de date ou d'éditeur. Toute la
richesse passe par les tags — d'où l'extraction de la décennie, du genre et du
nombre de joueurs, qui deviennent des catégories filtrables à la manette.

Aucun test ne touche le réseau.
"""
import json
import pathlib

from retro import metadata
from retro.steam import entry

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
JEU = json.loads((FIXTURES / "screenscraper-jeu.json").read_text(encoding="utf-8"))


def faux_reseau(reponse=None, erreur=None):
    appels = []

    def fetch_json(url, params):
        appels.append((url, params))
        if erreur:
            raise erreur
        return reponse if reponse is not None else JEU

    return fetch_json, appels


def rom(titre="Chrono Trigger"):
    return entry.RomEntry(
        title=titre, rom_path=f"G:\\ROMs\\snes\\{titre}.sfc",
        system_name="Super Nintendo",
        emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
        launch_template='-f "{rom}"', start_dir="D:\\Emulation\\RetroArch",
    )


def test_sans_cle_aucun_appel(tmp_path):
    """Dégradation gracieuse : pas de clé, pas de métadonnées, pas d'erreur."""
    fj, appels = faux_reseau()
    c = metadata.MetadataClient(api_key=None, cache_dir=tmp_path, fetch_json=fj)
    assert c.tags_for("Chrono Trigger.sfc", "snes") == ()
    assert appels == []


def test_les_tags_sont_extraits(tmp_path):
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    tags = c.tags_for("Chrono Trigger.sfc", "snes")
    assert "1990s" in tags
    assert "RPG" in tags


def test_le_cache_evite_un_second_appel(tmp_path):
    """Trois mille ROMs et une API à quota : le cache n'est pas un confort."""
    fj, appels = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    c.tags_for("Chrono Trigger.sfc", "snes")
    c.tags_for("Chrono Trigger.sfc", "snes")
    assert len(appels) == 1


def test_le_cache_survit_a_un_nouveau_client(tmp_path):
    fj, appels = faux_reseau()
    metadata.MetadataClient(api_key="cle", cache_dir=tmp_path,
                            fetch_json=fj).tags_for("Chrono Trigger.sfc", "snes")
    metadata.MetadataClient(api_key="cle", cache_dir=tmp_path,
                            fetch_json=fj).tags_for("Chrono Trigger.sfc", "snes")
    assert len(appels) == 1


def test_une_panne_reseau_ne_leve_pas(tmp_path):
    """Les métadonnées sont un ornement : une panne ne doit jamais empêcher un
    jeu de remonter dans Steam."""
    fj, _ = faux_reseau(erreur=OSError("réseau injoignable"))
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    assert c.tags_for("Chrono Trigger.sfc", "snes") == ()


def test_un_jeu_inconnu_ne_leve_pas(tmp_path):
    fj, _ = faux_reseau(reponse={"response": {}})
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    assert c.tags_for("Inconnu 9999.sfc", "snes") == ()


def test_une_reponse_partielle_rend_ce_qu_elle_peut(tmp_path):
    """L'API rend des fiches très inégales : l'absence d'un champ ne doit pas
    faire perdre les autres."""
    fj, _ = faux_reseau(reponse={"response": {"jeu": {
        "genres": [{"noms": [{"langue": "fr", "text": "Plateforme"}]}]}}})
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    assert c.tags_for("X.sfc", "snes") == ("Plateforme",)


def test_la_cle_ne_fuit_pas_dans_le_cache(tmp_path):
    """Le cache vit sur le volume de jeux, que d'autres outils lisent."""
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="secret-de-l-api", cache_dir=tmp_path,
                                fetch_json=fj)
    c.tags_for("Chrono Trigger.sfc", "snes")
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert "secret-de-l-api" not in f.read_text(encoding="utf-8")


# --- enrichissement d'un inventaire ---

def test_enrich_remplit_les_extra_tags(tmp_path):
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    enrichies = metadata.enrich([rom()], c)
    assert "RPG" in enrichies[0].extra_tags


def test_enrich_ne_touche_pas_aux_autres_champs(tmp_path):
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    avant = rom()
    apres = metadata.enrich([avant], c)[0]
    for champ in ("title", "rom_path", "system_name", "emulator_exe",
                  "launch_template", "start_dir"):
        assert getattr(apres, champ) == getattr(avant, champ)


def test_enrich_sans_cle_rend_l_inventaire_intact(tmp_path):
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key=None, cache_dir=tmp_path, fetch_json=fj)
    assert metadata.enrich([rom()], c) == [rom()]


def test_les_dimensions_sont_configurables(tmp_path):
    """Trois mille jeux et huit tags chacun rendent Big Picture illisible."""
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    seul_genre = metadata.enrich([rom()], c, dimensions=("genre",))[0]
    assert seul_genre.extra_tags == ("RPG",)


# --- aucune erreur ne remonte : les chemins hors du filet ---

def test_un_nom_de_rom_non_encodable_ne_leve_pas(tmp_path):
    """Un demi-substitut dans un nom de ROM ne doit pas coûter le jeu.

    C'est ce que produit couramment `surrogateescape` en listant un disque
    sous POSIX : un octet non décodable devient « \\udce9 », et
    `str.encode()` lève alors UnicodeEncodeError. Le hachage du cache est
    la première chose que fait `metadata_for`, hors de tout filet.
    """
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    tags = c.tags_for("Pok\udce9mon.sfc", "snes")
    assert "1990s" in tags and "RPG" in tags


def test_deux_noms_de_rom_non_encodables_ne_partagent_pas_leur_cache(tmp_path):
    """Le hachage doit rester injectif : remplacer les substituts par un
    caractère de repli ferait rendre la fiche du premier jeu pour le second."""
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    assert (c._chemin_cache("A\udce9.sfc", "snes")
            != c._chemin_cache("A\udcea.sfc", "snes"))


def test_un_cache_illisible_ne_leve_pas(tmp_path, monkeypatch):
    """`Path.is_file()` avale ENOENT et ENOTDIR, PAS EACCES.

    Sur un dossier de cache sans droit de traversée — un cache posé par un
    autre utilisateur sur le volume de jeux — il lève donc PermissionError,
    et l'appel vit hors du try/except de `metadata_for`. L'erreur est
    injectée à l'endroit exact où le système la lèverait plutôt que
    provoquée par un chmod : la suite tourne aussi sous root, qui ignore les
    permissions et ferait passer ce test quelle que soit l'implémentation.
    """
    def is_file_interdit(self):
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(pathlib.Path, "is_file", is_file_interdit)
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    tags = c.tags_for("Chrono Trigger.sfc", "snes")
    assert "1990s" in tags and "RPG" in tags


def test_enrich_survit_a_un_nom_de_rom_non_encodable(tmp_path):
    """La promesse du module vaut pour l'inventaire entier : un seul nom
    exotique ne doit pas faire perdre les 2999 autres jeux."""
    fj, _ = faux_reseau()
    c = metadata.MetadataClient(api_key="cle", cache_dir=tmp_path, fetch_json=fj)
    exotique = entry.RomEntry(
        title="Pok\udce9mon", rom_path="G:\\ROMs\\snes\\Pok\udce9mon.sfc",
        system_name="Super Nintendo",
        emulator_exe="D:\\Emulation\\RetroArch\\retroarch.exe",
        launch_template='-f "{rom}"', start_dir="D:\\Emulation\\RetroArch",
    )
    enrichies = metadata.enrich([exotique, rom()], c)
    assert len(enrichies) == 2
    assert "RPG" in enrichies[1].extra_tags
