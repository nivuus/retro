// retro-yaml — the YAML half of the launcher's merge, on TWO levels.
//
// Level one is what the flat dialect always merged: a top-level
// "key: value" (Vita3K's config.yml). Level two is a top-level mapping of
// mappings — RPCS3's config.yml, "System:" then "  Language: French" —
// where the key is (System, Language) and must be written back under
// "System:", at that section's own indentation. Written at the top level,
// no YAML reader would attach it to System, and RPCS3 would keep English
// without a word.
//
// THE RULE IS THE ONE OF retro/dialectes.py (`lignes_yaml`), line for line:
//   - a top-level "name:" with nothing after the colon opens a SECTION only
//     when the next meaningful line is indented and is "key: ..." rather
//     than "- item"; otherwise it stays a flat key ("lle-modules:" followed
//     by a sequence);
//   - inside a section, only lines at the section's FIRST child indentation
//     are keys; deeper lines belong to the key above them and are never
//     touched;
//   - "#" is the only comment; keys are case-sensitive, as yaml-cpp compares
//     them byte for byte.
//
// No YAML library is used, on purpose: csc.exe from the .NET Framework has
// no package manager, and a parse/serialise round trip would rewrite the
// owner's whole file — order, comments, quoting — to change one value.
using System;
using System.Collections.Generic;

static class FusionYaml
{
    const string RETRAIT_PAR_DEFAUT = "  ";

    sealed class Cle
    {
        public string Section;
        public string Nom;
        public int Ligne;
    }

    sealed class Section
    {
        public int Entete;
        public int Derniere;
        public string Retrait;
    }

    public static string Fusionner(string existant, string apporte,
                                   out int posees)
    {
        string[] source = Lignes(apporte);
        var ordre = new List<string>();
        var apportees = new Dictionary<string, Cle>();
        foreach (Cle c in Cles(source, null))
        {
            string id = Id(c.Section, c.Nom);
            if (!apportees.ContainsKey(id)) ordre.Add(id);
            apportees[id] = c;
        }

        string[] lignes = Lignes(existant);
        var sections = new Dictionary<string, Section>();
        List<Cle> presentes = Cles(lignes, sections);

        posees = 0;
        var remplacees = new Dictionary<int, string>();
        var reste = new List<string>(ordre);
        foreach (Cle c in presentes)
        {
            string id = Id(c.Section, c.Nom);
            if (!reste.Contains(id)) continue;
            string retrait = lignes[c.Ligne].Substring(
                0, lignes[c.Ligne].Length - lignes[c.Ligne].TrimStart().Length);
            remplacees[c.Ligne] = retrait + source[apportees[id].Ligne].Trim();
            reste.Remove(id);
            posees++;
        }

        // Keys of an existing section go right after its last line, at its
        // own indentation. Keys of the top level, and whole sections the
        // file lacks, go at the end: YAML accepts a top-level key anywhere.
        var apres = new Dictionary<int, List<string>>();
        var enFin = new List<string>();
        var nouvelles = new List<string>();
        foreach (string id in reste)
        {
            Cle c = apportees[id];
            string texte = source[c.Ligne].Trim();
            Section s;
            if (c.Section.Length == 0)
            {
                enFin.Add(texte);
            }
            else if (sections.TryGetValue(c.Section, out s))
            {
                if (!apres.ContainsKey(s.Derniere))
                    apres[s.Derniere] = new List<string>();
                apres[s.Derniere].Add(s.Retrait + texte);
            }
            else
            {
                if (!nouvelles.Contains(c.Section)) nouvelles.Add(c.Section);
                continue;
            }
            posees++;
        }
        foreach (string nom in nouvelles)
        {
            // A flat key of the same name would make a duplicate top-level
            // key, which yaml-cpp rejects: refuse loudly instead.
            foreach (Cle c in presentes)
                if (c.Section.Length == 0 && c.Nom == nom)
                    throw new Exception(
                        "The file already holds a top-level key \"" + nom
                        + "\" with no sub-keys, and the plan asks to pose a "
                        + "section of the same name there. Writing it would "
                        + "make a duplicate key the emulator would reject.");
            enFin.Add(nom + ":");
            foreach (string id in reste)
            {
                Cle c = apportees[id];
                if (c.Section != nom) continue;
                enFin.Add(RETRAIT_PAR_DEFAUT + source[c.Ligne].Trim());
                posees++;
            }
        }

        var sortie = new List<string>();
        for (int i = 0; i < lignes.Length; i++)
        {
            string remplacee;
            sortie.Add(remplacees.TryGetValue(i, out remplacee)
                       ? remplacee : lignes[i]);
            List<string> ajouts;
            if (apres.TryGetValue(i, out ajouts)) sortie.AddRange(ajouts);
        }
        if (enFin.Count > 0)
        {
            int fin = sortie.Count;
            while (fin > 0 && sortie[fin - 1].Trim().Length == 0) fin--;
            sortie.InsertRange(fin, enFin);
        }
        return string.Join("\r\n", sortie.ToArray());
    }

    static string[] Lignes(string texte)
    {
        return texte.Replace("\r\n", "\n").Split('\n');
    }

    static string Id(string section, string cle)
    {
        return section + "\n" + cle;
    }

    static int Profondeur(string ligne)
    {
        return ligne.Length - ligne.TrimStart().Length;
    }

    static bool Significative(string ligne)
    {
        string nu = ligne.Trim();
        return nu.Length > 0 && nu[0] != '#';
    }

    static string NomDe(string nu)
    {
        int deuxPoints = nu.IndexOf(':');
        if (deuxPoints <= 0 || nu[0] == '-') return null;
        string nom = nu.Substring(0, deuxPoints).Trim();
        return nom.Length > 0 ? nom : null;
    }

    static bool OuvreUneSection(string[] lignes, int n)
    {
        for (int i = n + 1; i < lignes.Length; i++)
        {
            if (!Significative(lignes[i])) continue;
            string nu = lignes[i].Trim();
            return Profondeur(lignes[i]) > 0 && nu[0] != '-'
                && nu.IndexOf(':') > 0;
        }
        return false;
    }

    // Every key line, in order. When `sections` is given, it is filled with
    // each section's header, last line and child indentation.
    static List<Cle> Cles(string[] lignes, Dictionary<string, Section> sections)
    {
        var cles = new List<Cle>();
        string section = "";
        Section courante = null;
        int retrait = -1;
        for (int n = 0; n < lignes.Length; n++)
        {
            string ligne = lignes[n];
            if (!Significative(ligne)) continue;
            string nu = ligne.Trim();
            int profondeur = Profondeur(ligne);
            if (profondeur == 0)
            {
                section = "";
                courante = null;
                retrait = -1;
                string nom = NomDe(nu);
                if (nom == null) continue;
                string valeur = nu.Substring(nu.IndexOf(':') + 1).Trim();
                if (valeur.Length == 0 && OuvreUneSection(lignes, n))
                {
                    section = nom;
                    if (sections != null && !sections.ContainsKey(nom))
                    {
                        courante = new Section();
                        courante.Entete = n;
                        courante.Derniere = n;
                        courante.Retrait = RETRAIT_PAR_DEFAUT;
                        sections[nom] = courante;
                    }
                    continue;
                }
                cles.Add(new Cle { Section = "", Nom = nom, Ligne = n });
                continue;
            }
            if (section.Length == 0) continue;
            if (courante != null) courante.Derniere = n;
            if (retrait < 0)
            {
                retrait = profondeur;
                if (courante != null)
                    courante.Retrait = ligne.Substring(0, profondeur);
            }
            if (profondeur != retrait) continue;
            string cle = NomDe(nu);
            if (cle == null) continue;
            cles.Add(new Cle { Section = section, Nom = cle, Ligne = n });
        }
        return cles;
    }
}
