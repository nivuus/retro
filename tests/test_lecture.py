"""Lire un fichier en entier, ou echouer — jamais rendre un fragment.

Le defaut d'origine se mesure sur un partage SMB, que ces tests ne peuvent
pas fabriquer. Ce qu'ils epinglent, c'est la GARDE : un total qui ne
correspond pas a `stat()` doit lever, et non se faire passer pour du contenu.
"""
import hashlib
import io
import pathlib

import pytest

from retro import lecture


def test_un_fichier_entier_est_rendu_entier(tmp_path):
    f = tmp_path / "gros.bin"
    contenu = bytes(range(256)) * 20000          # ~5 Mo, plus d'une tranche
    f.write_bytes(contenu)
    assert lecture.octets(f) == contenu
    assert lecture.md5(f) == hashlib.md5(contenu).hexdigest()


def test_une_lecture_courte_leve_au_lieu_de_rendre_du_vide(tmp_path, monkeypatch):
    """LE DEFAUT MESURE : sur le partage de la console, un fichier de deux
    mebioctets rendait ZERO octet, `stat()` donnant la bonne taille. Hache
    tel quel, ce vide faisait conclure « corrompu » sur un fichier valide —
    le rapport accusait, et `retro bios` retelechargeait a chaque passage."""
    f = tmp_path / "tronque.bin"
    f.write_bytes(b"x" * 1000)

    vrai_open = pathlib.Path.open

    def open_muet(self, *a, **kw):
        if self.name == "tronque.bin":
            return io.BytesIO(b"")               # le partage rend du vide
        return vrai_open(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "open", open_muet)
    with pytest.raises(lecture.LectureCourte, match="1000"):
        lecture.octets(f)
    with pytest.raises(lecture.LectureCourte):
        lecture.md5(f)


def test_une_lecture_courte_est_une_OSError(tmp_path):
    """Les appelants de ce paquet traitent deja l'illisible comme un ETAT —
    « present et inutilisable » — et non comme un plantage. En faire une
    OSError les laisse fonctionner sans les rouvrir."""
    assert issubclass(lecture.LectureCourte, OSError)


def test_un_fichier_vide_est_rendu_vide(tmp_path):
    """Zero octet ATTENDU n'est pas une lecture courte : la garde compare a
    `stat()`, pas a zero. Confondre les deux ferait lever sur un fichier
    legitimement vide."""
    f = tmp_path / "vide.bin"
    f.write_bytes(b"")
    assert lecture.octets(f) == b""
    assert lecture.md5(f) == hashlib.md5(b"").hexdigest()
