"""Découverte des comptes Steam locaux."""
import pytest

from retro.steam import accounts


def _faire_compte(racine, account_id):
    d = racine / "userdata" / account_id / "config"
    d.mkdir(parents=True)
    return d


def test_un_seul_compte(tmp_path):
    _faire_compte(tmp_path, "123456789")
    trouves = accounts.discover_accounts(tmp_path)
    assert [c.account_id for c in trouves] == ["123456789"]


def test_plusieurs_comptes_sont_tous_rendus(tmp_path):
    """On ne devine pas lequel est le bon : on les synchronise tous."""
    _faire_compte(tmp_path, "111")
    _faire_compte(tmp_path, "222")
    assert sorted(c.account_id for c in accounts.discover_accounts(tmp_path)) == ["111", "222"]


def test_aucun_compte_leve_une_erreur_explicite(tmp_path):
    (tmp_path / "userdata").mkdir()
    with pytest.raises(accounts.NoSteamAccountError) as exc:
        accounts.discover_accounts(tmp_path)
    assert "connect" in str(exc.value).lower()


def test_userdata_absent_leve_la_meme_erreur(tmp_path):
    with pytest.raises(accounts.NoSteamAccountError):
        accounts.discover_accounts(tmp_path)


def test_dossier_anonymous_ignore(tmp_path):
    """Steam crée userdata/0 pour la session anonyme : ce n'est pas un compte."""
    _faire_compte(tmp_path, "0")
    _faire_compte(tmp_path, "123456789")
    assert [c.account_id for c in accounts.discover_accounts(tmp_path)] == ["123456789"]


def test_entree_non_numerique_ignoree(tmp_path):
    (tmp_path / "userdata" / "ac_backup" / "config").mkdir(parents=True)
    _faire_compte(tmp_path, "123456789")
    assert [c.account_id for c in accounts.discover_accounts(tmp_path)] == ["123456789"]


def test_chemins_derives(tmp_path):
    _faire_compte(tmp_path, "123456789")
    compte = accounts.discover_accounts(tmp_path)[0]
    assert compte.shortcuts_path.name == "shortcuts.vdf"
    assert compte.grid_dir.name == "grid"
    assert compte.grid_dir.parent == compte.config_dir
