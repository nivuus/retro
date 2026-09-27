"""The XML dialect: a fragment is an XML document, and every element that
holds text and no child element is a key, its section the "/"-joined path
of the elements above it, root included ("content" for
<content><console_language>2</console_language></content>).

Cemu keeps the language games read in settings.xml, under <content>.
"""
import pytest

from retro import dialectes, profiles


def test_les_feuilles_d_un_fragment_xml_sont_ses_cles():
    fragment = ("<content><console_language>2</console_language>"
                "<a><b>1</b></a></content>")
    assert dialectes.cles_xml(fragment) == [
        ("content", "console_language"), ("content/a", "b")]


def test_un_commentaire_et_une_declaration_ne_sont_pas_des_cles():
    fragment = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                "<!-- Écrit par « retro » -->\n<content></content>\n")
    assert dialectes.cles_xml(fragment) == []


def test_le_dialecte_d_une_cible_xml_est_xml():
    assert profiles.dialecte("C:\\x\\settings.xml") == "xml"
    assert profiles.cles_de("C:\\x\\settings.xml",
                            "<content><k>1</k></content>") == [("content", "k")]


@pytest.mark.parametrize("fragment", ["<content><k>1</k>", "texte", ""])
def test_un_fragment_xml_illisible_est_refuse(fragment):
    with pytest.raises(ValueError):
        dialectes.valider_xml(fragment)


def test_un_fragment_xml_valide_passe():
    dialectes.valider_xml("<content><check_update>false</check_update></content>")
