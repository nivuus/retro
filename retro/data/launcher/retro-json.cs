// retro-json — the JSON half of the launcher's merge.
//
// A fragment is a JSON object; every SCALAR leaf of it is imposed on the
// target at the same path. The value is replaced IN PLACE: the file keeps
// every other byte the emulator wrote — order, indentation, number
// spelling. A parse/serialise round trip (JavaScriptSerializer is the only
// serializer csc.exe reaches without a package) would rewrite the whole
// file and could respell numbers, to change one value.
//
// A leaf missing from the target is inserted at the end of the deepest
// object of its path that exists, with the indentation of that object's
// members; missing intermediate objects are written with it. Arrays are
// never merged — retro/dialectes.py (`valider_json`) refuses them in a
// fragment, since replacing one would drop what the emulator keeps in it.
//
// THE KEYS ARE THE ONES OF retro/dialectes.py (`cles_json`): a leaf's
// section is the "/"-joined path of the objects above it.
using System;
using System.Collections.Generic;
using System.Text;

static class FusionJson
{
    sealed class Membre
    {
        public string Cle;
        public int DebutCle;      // index of the key's opening quote
        public int DebutValeur;
        public int FinValeur;     // exclusive
        public Objet Enfant;      // non-null when the value is an object
    }

    sealed class Objet
    {
        public int Ouverture;     // index of '{'
        public int Fermeture;     // index of '}'
        public List<Membre> Membres = new List<Membre>();
    }

    sealed class Feuille
    {
        public string[] Chemin;
        public string Valeur;     // raw JSON text of the scalar
    }

    public static string Fusionner(string existant, string apporte,
                                   out int posees)
    {
        var feuilles = new List<Feuille>();
        Objet source = Analyser(apporte);
        Aplatir(apporte, source, new List<string>(), feuilles);

        string texte = existant.Trim().Length == 0 ? "{}" : existant;
        finDeLigne = texte.Contains("\r\n") ? "\r\n" : "\n";
        Objet racine = Analyser(texte);

        // Edits are collected, then applied from the END of the text, so
        // that no position computed on the original is shifted.
        var remplacements = new SortedDictionary<int, KeyValuePair<int, string>>();
        var insertions = new Dictionary<Objet, Dictionary<string, object>>();
        posees = 0;
        foreach (Feuille f in feuilles)
        {
            Objet courant = racine;
            int profondeur = 0;
            Membre trouve = null;
            while (true)
            {
                Membre m = Chercher(courant, f.Chemin[profondeur]);
                if (m == null) break;
                if (profondeur == f.Chemin.Length - 1) { trouve = m; break; }
                if (m.Enfant == null)
                    throw new Exception(
                        "The target holds \"" + string.Join("/", f.Chemin, 0,
                            profondeur + 1)
                        + "\" as a plain value, and the plan poses a sub-key "
                        + "under it. Replacing it would erase what the "
                        + "emulator keeps there.");
                courant = m.Enfant;
                profondeur++;
            }
            posees++;
            if (trouve != null)
            {
                remplacements[trouve.DebutValeur] = new KeyValuePair<int, string>(
                    trouve.FinValeur, f.Valeur);
                continue;
            }
            Dictionary<string, object> arbre;
            if (!insertions.TryGetValue(courant, out arbre))
                insertions[courant] = arbre = new Dictionary<string, object>();
            for (int i = profondeur; i < f.Chemin.Length - 1; i++)
            {
                object suivant;
                if (!arbre.TryGetValue(f.Chemin[i], out suivant))
                    arbre[f.Chemin[i]] = suivant = new Dictionary<string, object>();
                arbre = (Dictionary<string, object>)suivant;
            }
            arbre[f.Chemin[f.Chemin.Length - 1]] = f.Valeur;
        }

        var edits = new List<KeyValuePair<int, KeyValuePair<int, string>>>();
        foreach (var r in remplacements)
            edits.Add(new KeyValuePair<int, KeyValuePair<int, string>>(r.Key, r.Value));
        foreach (var ins in insertions)
        {
            Objet o = ins.Key;
            string retrait = RetraitDesMembres(texte, o);
            var morceaux = new List<string>();
            foreach (var paire in ins.Value)
                morceaux.Add(Ecrire(paire.Key, paire.Value, retrait));
            string ajout = string.Join(",", morceaux.ToArray());
            // After the last member's value, or right after "{" when the
            // object is empty; the closing brace keeps its own line.
            int apres = o.Membres.Count > 0
                ? o.Membres[o.Membres.Count - 1].FinValeur : o.Ouverture + 1;
            string texteAjout = (o.Membres.Count > 0 ? "," : "") + ajout
                + (o.Membres.Count == 0 && retrait.Length > 0
                   ? finDeLigne + RetraitParent(texte, o) : "");
            edits.Add(new KeyValuePair<int, KeyValuePair<int, string>>(
                apres, new KeyValuePair<int, string>(apres, texteAjout)));
        }
        edits.Sort((a, b) => b.Key.CompareTo(a.Key));
        var sortie = new StringBuilder(texte);
        foreach (var e in edits)
        {
            sortie.Remove(e.Key, e.Value.Key - e.Key);
            sortie.Insert(e.Key, e.Value.Value);
        }
        return sortie.ToString();
    }

    // The file's own line ending: a CRLF file stays CRLF.
    static string finDeLigne = "\n";

    static string Ecrire(string cle, object valeur, string retrait)
    {
        string entete = (retrait.Length > 0 ? finDeLigne + retrait : "")
                      + "\"" + cle + "\": ";
        string simple = valeur as string;
        if (simple != null) return entete + simple;
        var sous = (Dictionary<string, object>)valeur;
        var parties = new List<string>();
        foreach (var p in sous) parties.Add(Ecrire(p.Key, p.Value, ""));
        return entete + "{" + string.Join(", ", parties.ToArray()) + "}";
    }

    static Membre Chercher(Objet o, string cle)
    {
        foreach (Membre m in o.Membres) if (m.Cle == cle) return m;
        return null;
    }

    static void Aplatir(string texte, Objet o, List<string> chemin,
                        List<Feuille> sortie)
    {
        foreach (Membre m in o.Membres)
        {
            chemin.Add(m.Cle);
            if (m.Enfant != null) Aplatir(texte, m.Enfant, chemin, sortie);
            else sortie.Add(new Feuille {
                Chemin = chemin.ToArray(),
                Valeur = texte.Substring(m.DebutValeur,
                                         m.FinValeur - m.DebutValeur) });
            chemin.RemoveAt(chemin.Count - 1);
        }
    }

    // The whitespace before the first member's key, on its own line; "" for
    // an object written on one line.
    static string RetraitDesMembres(string texte, Objet o)
    {
        if (o.Membres.Count == 0)
        {
            string parent = RetraitParent(texte, o);
            int fin = o.Fermeture;
            // "{\n  }" : a multi-line empty object — indent one step deeper.
            return texte.IndexOf('\n', o.Ouverture, fin - o.Ouverture) >= 0
                ? parent + "  " : "";
        }
        int debutCle = o.Membres[0].DebutCle;
        int ligne = texte.LastIndexOf('\n', debutCle);
        if (ligne < o.Ouverture) return "";
        return texte.Substring(ligne + 1, debutCle - ligne - 1);
    }

    static string RetraitParent(string texte, Objet o)
    {
        int ligne = texte.LastIndexOf('\n', o.Fermeture);
        if (ligne < 0) return "";
        string avant = texte.Substring(ligne + 1, o.Fermeture - ligne - 1);
        return avant.Trim().Length == 0 ? avant : "";
    }

    // ---- a minimal JSON reader: positions, not values ------------------

    static Objet Analyser(string texte)
    {
        int i = Blancs(texte, 0);
        if (i >= texte.Length || texte[i] != '{')
            throw new Exception("The JSON file does not start with an "
                                + "object: the merge would pose nothing.");
        Objet o;
        int fin = LireObjet(texte, i, out o);
        if (Blancs(texte, fin) != texte.Length)
            throw new Exception("The JSON file carries text after its root "
                                + "object.");
        return o;
    }

    static int Blancs(string t, int i)
    {
        while (i < t.Length && char.IsWhiteSpace(t[i])) i++;
        return i;
    }

    static int LireObjet(string t, int i, out Objet o)
    {
        o = new Objet { Ouverture = i };
        i = Blancs(t, i + 1);
        if (i < t.Length && t[i] == '}') { o.Fermeture = i; return i + 1; }
        while (true)
        {
            if (i >= t.Length || t[i] != '"') throw Erreur(t, i, "a key");
            int debutCle = i;
            int finCle = LireChaine(t, i);
            string cle = Decoder(t.Substring(i + 1, finCle - i - 2));
            i = Blancs(t, finCle);
            if (i >= t.Length || t[i] != ':') throw Erreur(t, i, "\":\"");
            i = Blancs(t, i + 1);
            var m = new Membre { Cle = cle, DebutCle = debutCle,
                                 DebutValeur = i };
            if (t[i] == '{')
            {
                Objet enfant;
                i = LireObjet(t, i, out enfant);
                m.Enfant = enfant;
            }
            else i = LireValeur(t, i);
            m.FinValeur = i;
            if (Chercher(o, cle) == null) o.Membres.Add(m);
            i = Blancs(t, i);
            if (i < t.Length && t[i] == ',') { i = Blancs(t, i + 1); continue; }
            if (i < t.Length && t[i] == '}') { o.Fermeture = i; return i + 1; }
            throw Erreur(t, i, "\",\" or \"}\"");
        }
    }

    static int LireValeur(string t, int i)
    {
        if (i >= t.Length) throw Erreur(t, i, "a value");
        char c = t[i];
        if (c == '"') return LireChaine(t, i);
        if (c == '{') { Objet ignore; return LireObjet(t, i, out ignore); }
        if (c == '[')
        {
            i = Blancs(t, i + 1);
            if (i < t.Length && t[i] == ']') return i + 1;
            while (true)
            {
                i = Blancs(t, LireValeur(t, i));
                if (i < t.Length && t[i] == ',') { i = Blancs(t, i + 1); continue; }
                if (i < t.Length && t[i] == ']') return i + 1;
                throw Erreur(t, i, "\",\" or \"]\"");
            }
        }
        int debut = i;
        while (i < t.Length && "-+.0123456789eEtruefalsn".IndexOf(t[i]) >= 0) i++;
        if (i == debut) throw Erreur(t, i, "a value");
        return i;
    }

    // Index just past the closing quote.
    static int LireChaine(string t, int i)
    {
        for (int j = i + 1; j < t.Length; j++)
        {
            if (t[j] == '\\') { j++; continue; }
            if (t[j] == '"') return j + 1;
        }
        throw Erreur(t, i, "the end of a string");
    }

    static string Decoder(string brut)
    {
        if (brut.IndexOf('\\') < 0) return brut;
        var s = new StringBuilder();
        for (int i = 0; i < brut.Length; i++)
        {
            if (brut[i] != '\\' || i + 1 >= brut.Length) { s.Append(brut[i]); continue; }
            char c = brut[++i];
            if (c == 'u' && i + 4 < brut.Length)
            {
                s.Append((char)Convert.ToInt32(brut.Substring(i + 1, 4), 16));
                i += 4;
            }
            else s.Append(c == 'n' ? '\n' : c == 't' ? '\t' : c == 'r' ? '\r'
                        : c == 'b' ? '\b' : c == 'f' ? '\f' : c);
        }
        return s.ToString();
    }

    static Exception Erreur(string t, int i, string attendu)
    {
        return new Exception("Unreadable JSON at position " + i
                             + ": expected " + attendu + ".");
    }
}
