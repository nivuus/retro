"""Récupération de l'artwork. Aucun test ne touche le réseau."""
import json
import pathlib

from retro.steam import artwork

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"
RECHERCHE = json.loads((FIXTURES / "sgdb-search.json").read_text())
GRILLES = json.loads((FIXTURES / "sgdb-grids.json").read_text())


def faux_reseau(reponses=None):
    appels = []

    def fetch_json(url, headers):
        appels.append(url)
        if "search" in url:
            return RECHERCHE
        return (reponses or {}).get(url, GRILLES)

    def fetch_bytes(url):
        appels.append(url)
        return b"\xff\xd8\xff-image-factice"

    return fetch_json, fetch_bytes, appels


def test_sans_cle_ne_telecharge_rien(tmp_path):
    """Dégradation gracieuse : pas de clé, pas d'artwork, pas d'erreur."""
    fj, fb, appels = faux_reseau()
    client = artwork.ArtworkClient(api_key=None, fetch_json=fj, fetch_bytes=fb)
    assert client.fetch_for("Chrono Trigger", 2398962978, tmp_path) == []
    assert appels == []


def test_ecrit_les_assets_sous_les_bons_noms(tmp_path):
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    ecrits = client.fetch_for("Chrono Trigger", 2398962978, tmp_path)
    assert "2398962978p.jpg" in ecrits
    assert (tmp_path / "2398962978p.jpg").read_bytes().startswith(b"\xff\xd8\xff")


def test_les_cinq_assets_sont_demandes(tmp_path):
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    assert len(client.fetch_for("Chrono Trigger", 2398962978, tmp_path)) == 5


def test_asset_present_sous_une_autre_extension_non_retelecharge(tmp_path):
    """Le piège que la mesure a révélé : coder .jpg en dur ferait retélécharger
    à chaque synchronisation un portrait déjà présent en .png."""
    (tmp_path / "2398962978p.png").write_bytes(b"deja-la")
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    assert "2398962978p.jpg" not in client.fetch_for("Chrono Trigger", 2398962978, tmp_path)
    assert (tmp_path / "2398962978p.png").read_bytes() == b"deja-la"


def test_un_asset_deja_present_n_est_pas_retelecharge(tmp_path):
    """Chaque asset se décide INDIVIDUELLEMENT.

    Un portrait déjà présent ne doit ni être écrasé, ni empêcher la
    récupération des quatre autres. Sauter globalement dès qu'un seul asset
    existe laisserait à jamais incomplète toute bibliothèque dont une
    synchronisation s'est interrompue en cours de boucle.

    N'assertionne PAS « aucun appel ne contient telle URL » : le faux réseau
    rend la même URL pour tous les endpoints, et le client la redemande
    légitimement pour les assets manquants — l'assertion serait insatisfiable
    quel que soit le code.
    """
    (tmp_path / "2398962978p.jpg").write_bytes(b"deja-la")
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    ecrits = client.fetch_for("Chrono Trigger", 2398962978, tmp_path)
    assert (tmp_path / "2398962978p.jpg").read_bytes() == b"deja-la"
    assert not any(n.startswith("2398962978p.") for n in ecrits)
    assert len(ecrits) == 4, f"les quatre autres assets doivent être récupérés : {ecrits}"


def test_jeu_introuvable_ne_leve_pas(tmp_path):
    def fetch_json(url, headers):
        return {"success": True, "data": []}
    client = artwork.ArtworkClient(
        api_key="cle", fetch_json=fetch_json, fetch_bytes=lambda u: b"")
    assert client.fetch_for("Jeu Inconnu 9999", 123, tmp_path) == []


def test_erreur_reseau_ne_leve_pas(tmp_path):
    """L'artwork est un ornement. Une panne SteamGridDB ne doit pas faire
    échouer une synchronisation par ailleurs valide."""
    def fetch_json(url, headers):
        raise OSError("réseau injoignable")
    client = artwork.ArtworkClient(
        api_key="cle", fetch_json=fetch_json, fetch_bytes=lambda u: b"")
    assert client.fetch_for("Chrono Trigger", 2398962978, tmp_path) == []


def test_dossier_grid_cree_si_absent(tmp_path):
    cible = tmp_path / "grid"
    fj, fb, _ = faux_reseau()
    client = artwork.ArtworkClient(api_key="cle", fetch_json=fj, fetch_bytes=fb)
    client.fetch_for("Chrono Trigger", 2398962978, cible)
    assert cible.is_dir()


def test_la_cle_part_dans_l_en_tete(tmp_path):
    vus = []

    def fetch_json(url, headers):
        vus.append(headers)
        return {"success": True, "data": []}

    client = artwork.ArtworkClient(
        api_key="secret", fetch_json=fetch_json, fetch_bytes=lambda u: b"")
    client.fetch_for("X", 1, tmp_path)
    assert vus[0]["Authorization"] == "Bearer secret"


def test_purge_des_orphelins(tmp_path):
    for nom in ["111p.jpg", "111_hero.png", "111_icon.ico", "222p.jpg"]:
        (tmp_path / nom).write_bytes(b"x")
    supprimes = artwork.prune_orphans(tmp_path, [111])
    assert sorted(supprimes) == ["111_hero.png", "111_icon.ico", "111p.jpg"]
    assert (tmp_path / "222p.jpg").exists()


def test_la_purge_ne_deborde_pas_sur_un_appid_voisin(tmp_path):
    """111 préfixe la chaîne 1112 : une purge par préfixe de chaîne détruirait
    l'artwork d'un jeu parfaitement valide."""
    (tmp_path / "1112p.jpg").write_bytes(b"x")
    (tmp_path / "111p.jpg").write_bytes(b"x")
    assert artwork.prune_orphans(tmp_path, [111]) == ["111p.jpg"]
    assert (tmp_path / "1112p.jpg").exists()


def test_purge_sans_orphelin_ne_touche_a_rien(tmp_path):
    (tmp_path / "222p.jpg").write_bytes(b"x")
    assert artwork.prune_orphans(tmp_path, []) == []
    assert (tmp_path / "222p.jpg").exists()


def test_purge_sur_dossier_absent(tmp_path):
    assert artwork.prune_orphans(tmp_path / "jamais", [111]) == []


def test_une_vignette_verrouillee_n_emporte_pas_la_synchronisation(
        tmp_path, monkeypatch):
    """Même motif que le nettoyage du temporaire de `acquire` : un ménage qui
    échoue ne doit pas emporter le travail utile. La purge précède l'écriture
    des raccourcis ; sous Windows, le client Steam tient ses vignettes
    ouvertes et leur suppression lève [WinError 32]. Une bibliothèque entière
    qui ne remonte pas pour un ornement orphelin serait un mauvais échange."""
    import os

    (tmp_path / "111p.jpg").write_bytes(b"x")
    (tmp_path / "111_hero.png").write_bytes(b"x")

    vrai_unlink = os.unlink

    def unlink_refuse(chemin, *args, **kwargs):
        if os.path.basename(os.fspath(chemin)) == "111p.jpg":
            raise PermissionError(
                32, "The process cannot access the file because it is being "
                    "used by another process")
        return vrai_unlink(chemin, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink_refuse)

    # Ne lève pas, et ne compte que ce qui a réellement disparu.
    assert artwork.prune_orphans(tmp_path, [111]) == ["111_hero.png"]
    assert (tmp_path / "111p.jpg").exists()
    assert not (tmp_path / "111_hero.png").exists()
