// retro-xml — the XML half of the launcher's merge.
//
// A fragment is an XML document; every element that holds text and no
// child element is a LEAF, imposed on the target at the same path of
// element names, root included. The leaf's text is set in place; a leaf
// missing from the target is appended to the deepest element of its path
// that exists, at the indentation of that element's children, with any
// missing parent elements. Everything else in the document — comments,
// order, whitespace — is kept, through XmlDocument.PreserveWhitespace:
// System.Xml ships with the .NET Framework csc.exe compiles against, so no
// package is needed and nothing is re-serialised by hand.
//
// THE KEYS ARE THE ONES OF retro/dialectes.py (`cles_xml`): a leaf's section
// is the "/"-joined path of the elements above it.
using System;
using System.Collections.Generic;
using System.Text;
using System.Xml;

static class FusionXml
{
    public static string Fusionner(string existant, string apporte,
                                   out int posees)
    {
        var source = new XmlDocument();
        source.LoadXml(apporte);
        var feuilles = new List<KeyValuePair<List<string>, string>>();
        Aplatir(source.DocumentElement, new List<string>(), feuilles);

        var cible = new XmlDocument { PreserveWhitespace = true };
        if (existant.Trim().Length == 0)
            cible.LoadXml("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<"
                          + source.DocumentElement.Name + "/>");
        else
            cible.LoadXml(existant);
        if (cible.DocumentElement.Name != source.DocumentElement.Name)
            throw new Exception(
                "The XML target's root is <" + cible.DocumentElement.Name
                + "> and the plan's fragment is <"
                + source.DocumentElement.Name + ">: merging one into the "
                + "other would pose nothing the emulator reads.");
        string finDeLigne = existant.Contains("\r\n") ? "\r\n" : "\n";

        posees = 0;
        foreach (var f in feuilles)
        {
            XmlElement courant = cible.DocumentElement;
            List<string> chemin = f.Key;
            for (int i = 0; i < chemin.Count; i++)
            {
                XmlElement suivant = null;
                foreach (XmlNode n in courant.ChildNodes)
                    if (n.NodeType == XmlNodeType.Element && n.Name == chemin[i])
                    { suivant = (XmlElement)n; break; }
                if (suivant == null)
                {
                    suivant = cible.CreateElement(chemin[i]);
                    Ajouter(courant, suivant);
                }
                courant = suivant;
            }
            courant.InnerText = f.Value;
            posees++;
        }

        // OuterXml, not an XmlWriter: the writer rebuilds the declaration
        // (encoding="utf-8" in lower case), OuterXml keeps it as read. The
        // whitespace nodes keep the file's CRLF while the nodes inserted
        // here carry LF: normalise, then give a CRLF file its CRLF back.
        string texte = cible.OuterXml.Replace("\r\n", "\n");
        return finDeLigne == "\r\n" ? texte.Replace("\n", "\r\n") : texte;
    }

    // Appended after the parent's last child, indented like its siblings
    // (or one step deeper than the parent), the closing tag kept on its own
    // line when the parent was written that way.
    static void Ajouter(XmlElement parent, XmlElement enfant)
    {
        string retraitEnfants = null;
        foreach (XmlNode n in parent.ChildNodes)
            if (n.NodeType == XmlNodeType.Element && n.PreviousSibling != null
                && n.PreviousSibling.NodeType == XmlNodeType.Whitespace)
            {
                string blanc = n.PreviousSibling.Value;
                retraitEnfants = blanc.Substring(blanc.LastIndexOf('\n') + 1);
                break;
            }
        XmlNode dernier = parent.LastChild;
        bool finIndentee = dernier != null
            && dernier.NodeType == XmlNodeType.Whitespace
            && dernier.Value.Contains("\n");
        string retraitParent = finIndentee
            ? dernier.Value.Substring(dernier.Value.LastIndexOf('\n') + 1) : "";
        // No sibling to copy: one step deeper than the parent, four spaces,
        // the step tinyxml2 (Cemu's writer) uses.
        if (retraitEnfants == null)
            retraitEnfants = finIndentee ? retraitParent + "    " : "";

        XmlDocument doc = parent.OwnerDocument;
        if (finIndentee)
        {
            parent.InsertBefore(doc.CreateWhitespace("\n" + retraitEnfants),
                                dernier);
            parent.InsertBefore(enfant, dernier);
        }
        else
        {
            if (retraitEnfants.Length > 0)
                parent.AppendChild(doc.CreateWhitespace("\n" + retraitEnfants));
            parent.AppendChild(enfant);
        }
    }

    static void Aplatir(XmlElement e, List<string> chemin,
                        List<KeyValuePair<List<string>, string>> sortie)
    {
        foreach (XmlNode n in e.ChildNodes)
        {
            if (n.NodeType != XmlNodeType.Element) continue;
            var el = (XmlElement)n;
            var ici = new List<string>(chemin) { el.Name };
            bool aDesEnfants = false;
            foreach (XmlNode c in el.ChildNodes)
                if (c.NodeType == XmlNodeType.Element) { aDesEnfants = true; break; }
            if (aDesEnfants) Aplatir(el, ici, sortie);
            else sortie.Add(new KeyValuePair<List<string>, string>(ici, el.InnerText));
        }
    }
}
