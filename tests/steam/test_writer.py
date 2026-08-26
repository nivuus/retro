"""Écriture de shortcuts.vdf : atomicité, sauvegarde, garde Steam."""
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
