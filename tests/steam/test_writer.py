"""Écriture de shortcuts.vdf : atomicité, sauvegarde, garde Steam."""
import os
import pathlib
import types

import pytest

from retro.steam import vdf_io, writer

ENTREE = {
    "appid": -1, "appname": "Jeu", "exe": '"D:\\x.exe"', "StartDir": '"D:\\"',
    "icon": "", "ShortcutPath": "", "LaunchOptions": "", "IsHidden": 0,
    "AllowDesktopConfig": 1, "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0,
    "DevkitGameID": "", "DevkitOverrideAppID": 0, "LastPlayTime": 0,
    "tags": {"0": "Rétro"},
}


def test_ecrit_un_fichier_relisible(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    writer.write_shortcuts(p, [ENTREE])
    assert vdf_io.load_shortcuts(p) == [ENTREE]


def test_sauvegarde_l_ancien_fichier(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    ancien = dict(ENTREE, appname="Ancien")
    p.write_bytes(vdf_io.dumps_shortcuts([ancien]))
    bak = writer.write_shortcuts(p, [ENTREE])
    assert bak is not None and bak.exists()
    assert vdf_io.load_shortcuts(bak) == [ancien]


def test_pas_de_sauvegarde_si_rien_a_sauver(tmp_path):
    assert writer.write_shortcuts(tmp_path / "shortcuts.vdf", [ENTREE]) is None


def test_aucun_fichier_temporaire_ne_subsiste(tmp_path):
    p = tmp_path / "shortcuts.vdf"
    writer.write_shortcuts(p, [ENTREE])
    assert [f.name for f in tmp_path.iterdir()] == ["shortcuts.vdf"]


def test_l_ancien_fichier_survit_a_un_echec(tmp_path, monkeypatch):
    """Écriture atomique : si le rendu échoue, l'ancien fichier est intact."""
    p = tmp_path / "shortcuts.vdf"
    p.write_bytes(vdf_io.dumps_shortcuts([ENTREE]))
    original = p.read_bytes()

    def explose(_entries):
        raise RuntimeError("rendu impossible")

    monkeypatch.setattr(writer.vdf_io, "dumps_shortcuts", explose)
    with pytest.raises(RuntimeError):
        writer.write_shortcuts(p, [ENTREE])
    assert p.read_bytes() == original


def test_l_ecriture_passe_par_un_fichier_temporaire(tmp_path, monkeypatch):
    """L'atomicité elle-même, pas seulement l'ordre des opérations.

    Le test d'échec ci-dessus simule la panne dans dumps_shortcuts, donc avant
    tout contact avec le disque : mesuré, il reste vert même si l'on remplace
    temp+os.replace par une écriture directe. Il atteste « rendre avant
    d'écrire », pas « écrire ailleurs puis basculer ». Celui-ci pin le motif.
    """
    p = tmp_path / "shortcuts.vdf"
    ecrits, bascules = [], []
    vrai_write = pathlib.Path.write_bytes
    monkeypatch.setattr(pathlib.Path, "write_bytes",
                        lambda self, d: (ecrits.append(self.name), vrai_write(self, d))[1])
    vrai_replace = os.replace
    monkeypatch.setattr(os, "replace",
                        lambda a, b: (bascules.append((str(a), str(b))), vrai_replace(a, b))[1])
    writer.write_shortcuts(p, [ENTREE])
    assert "shortcuts.vdf" not in ecrits, f"écriture directe sur la cible : {ecrits}"
    assert len(bascules) == 1 and bascules[0][1].endswith("shortcuts.vdf")


def test_le_parsing_de_tasklist_extrait_les_noms(monkeypatch):
    """La branche Windows, testée sans Windows.

    Son mode de panne va dans le mauvais sens : un découpage cassé rend une
    liste vide, donc steam_is_running renvoie False pendant que Steam tourne et
    la garde devient silencieusement inactive.
    """
    sortie = '"steam.exe","4028","Console","1","89 340 K"\n"explorer.exe","912","Console","1","42 000 K"\n'
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(writer.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(stdout=sortie))
    assert writer._running_processes() == ["steam.exe", "explorer.exe"]
    assert writer.steam_is_running()


def test_steam_detecte_comme_actif():
    assert writer.steam_is_running(["explorer.exe", "steam.exe"])


def test_steam_detecte_comme_inactif():
    assert not writer.steam_is_running(["explorer.exe", "retroarch.exe"])


def test_steamwebhelper_ne_compte_pas():
    """steamwebhelper survit brièvement à la fermeture de Steam. Le prendre
    pour Steam bloquerait toute synchronisation sans raison."""
    assert not writer.steam_is_running(["steamwebhelper.exe"])


def test_detection_insensible_a_la_casse():
    assert writer.steam_is_running(["STEAM.EXE"])


def test_la_garde_leve_une_erreur_explicite(monkeypatch):
    monkeypatch.setattr(writer, "_running_processes", lambda: ["steam.exe"])
    with pytest.raises(writer.SteamRunningError) as exc:
        writer.assert_steam_not_running()
    assert "steam" in str(exc.value).lower()


def test_deux_ecritures_dans_la_meme_seconde_gardent_deux_sauvegardes(tmp_path, monkeypatch):
    """L'horodatage a une résolution d'une seconde. Deux synchronisations
    rapprochées visaient le même chemin de sauvegarde, et la seconde détruisait
    la première en rendant un chemin qui avait l'air d'une sauvegarde fraîche.
    """
    monkeypatch.setattr(writer, "_horodatage", lambda: "20260826-120000")
    p = tmp_path / "shortcuts.vdf"
    p.write_bytes(vdf_io.dumps_shortcuts([dict(ENTREE, appname="Un")]))

    bak1 = writer.write_shortcuts(p, [dict(ENTREE, appname="Deux")])
    bak2 = writer.write_shortcuts(p, [dict(ENTREE, appname="Trois")])

    assert bak1 != bak2, "les deux sauvegardes visent le même chemin"
    assert vdf_io.load_shortcuts(bak1)[0]["appname"] == "Un"
    assert vdf_io.load_shortcuts(bak2)[0]["appname"] == "Deux"


def test_ecriture_identique_ne_sauvegarde_ni_n_ecrit(tmp_path):
    """Sans cette garde, chaque synchronisation sans changement laissait un
    .bak de plus, indéfiniment, et réécrivait le fichier pour rien."""
    p = tmp_path / "shortcuts.vdf"
    writer.write_shortcuts(p, [ENTREE])
    avant = p.stat().st_mtime_ns

    assert writer.write_shortcuts(p, [ENTREE]) is None
    assert [f.name for f in tmp_path.iterdir()] == ["shortcuts.vdf"]
    assert p.stat().st_mtime_ns == avant, "le fichier a été réécrit à l'identique"
