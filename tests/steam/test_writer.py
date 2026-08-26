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


def test_l_ecriture_passe_reellement_par_un_fichier_temporaire(tmp_path, monkeypatch):
    """Ne teste pas seulement « rendre avant d'écrire » (déjà couvert par
    test_l_ancien_fichier_survit_a_un_echec) mais l'atomicité elle-même :
    le nouveau contenu doit être écrit intégralement AILLEURS, et le fichier
    final ne doit changer qu'au moment d'un unique os.replace(). Une
    implémentation qui écrirait directement dans path (perdant l'atomicité)
    ferait passer les autres tests mais pas celui-ci."""
    p = tmp_path / "shortcuts.vdf"
    p.write_bytes(vdf_io.dumps_shortcuts([ENTREE]))
    original = p.read_bytes()

    os_replace_reel = os.replace
    appels = []

    def replace_espion(src, dst):
        src, dst = pathlib.Path(src), pathlib.Path(dst)
        # Au moment du remplacement : la nouvelle version est déjà écrite en
        # entier ailleurs, et le fichier final n'a pas encore été touché.
        assert src != dst, "le remplacement doit basculer depuis un autre fichier"
        assert src.exists() and src.read_bytes() == vdf_io.dumps_shortcuts(
            [dict(ENTREE, appname="Nouveau")]
        )
        assert dst.read_bytes() == original, "le fichier final a été modifié avant le replace"
        appels.append((src, dst))
        os_replace_reel(src, dst)

    monkeypatch.setattr(writer.os, "replace", replace_espion)
    writer.write_shortcuts(p, [dict(ENTREE, appname="Nouveau")])

    assert appels, "os.replace n'a jamais été appelé : l'écriture n'est pas atomique"


def test_running_processes_parse_la_sortie_de_tasklist_sous_windows(monkeypatch):
    """La branche Windows de _running_processes() doit être exercée sans
    Windows : son mode de panne va dans le mauvais sens (une liste vide fait
    croire que Steam ne tourne jamais), donc une régression y serait un échec
    muet — précisément ce que ce module existe pour empêcher."""
    monkeypatch.setattr(writer.os, "name", "nt")
    sortie_tasklist = (
        '"steam.exe","1234","Console","1","50 000 Ko"\r\n'
        '"explorer.exe","5678","Console","1","30 000 Ko"\r\n'
    )

    def faux_run(*args, **kwargs):
        return types.SimpleNamespace(stdout=sortie_tasklist)

    monkeypatch.setattr(writer.subprocess, "run", faux_run)
    assert writer._running_processes() == ["steam.exe", "explorer.exe"]


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
