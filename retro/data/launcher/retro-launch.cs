// retro-launch — le lanceur commun de la console rétro.
//
// Steam fige les options de lancement au moment de la synchronisation. Ce
// qu'il faut savoir pour rendre un jeu — la résolution de la session, ce que
// la machine offre — n'est connu qu'ICI, au lancement : un flux Apollo change
// de résolution selon le client qui se connecte.
//
// Ce programme NE DÉCIDE RIEN. Tout l'arbitrage est calculé par `retro sync`,
// en Python, où il est testé, et écrit dans le plan que ce fichier se contente
// de lire. Le classement de la machine se fait ici parce que la machine est
// ici, mais avec les seuils que le plan porte.
//
// Compilé en /target:winexe — sans console. C'est aussi ce qui supprime la
// fenêtre noire qu'un émulateur au sous-système CONSOLE fait apparaître.
//
// Aucune panne muette : toute erreur s'affiche à l'écran, sur la télévision du
// propriétaire, et s'écrit au journal. Un lanceur qui échoue en silence rend
// la main à Steam instantanément — ce qui ressemble à un jeu qu'on a quitté.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

static class RetroLaunch
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int MessageBoxW(IntPtr h, string texte, string titre, uint type);
    [DllImport("user32.dll")]
    static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll")]
    static extern bool SetProcessDPIAware();

    const int SM_CXSCREEN = 0, SM_CYSCREEN = 1;

    static string dossier;
    static string journal;

    static int Main()
    {
        try
        {
            // Assembly.Location plutôt que MainModule : celui-ci ouvre le
            // process courant et peut lever avant même que le journal existe,
            // c'est-à-dire au seul endroit où l'on ne pourrait rien noter.
            dossier = Path.GetDirectoryName(
                System.Reflection.Assembly.GetExecutingAssembly().Location);
            journal = Path.Combine(dossier, "journal.txt");
            return Lancer();
        }
        catch (Exception e)
        {
            Echouer(e.Message);
            return 1;
        }
    }

    // Le message va À L'ÉCRAN et au journal. Rendre la main à Steam sans rien
    // dire ressemblerait à un jeu qu'on vient de quitter.
    static void Echouer(string message)
    {
        Noter("ÉCHEC : " + message);
        MessageBoxW(IntPtr.Zero, message, "Console rétro — le jeu n'a pas pu démarrer", 0x10);
    }

    static void Noter(string ligne)
    {
        try
        {
            File.AppendAllText(journal,
                DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + ligne
                + Environment.NewLine, new UTF8Encoding(false));
        }
        catch (Exception) { /* un journal illisible ne doit pas tuer le jeu */ }
    }

    static int Lancer()
    {
        // La ligne de commande est lue BRUTE : découpée par le runtime, un
        // chemin de ROM contenant des espaces reviendrait en morceaux.
        string brut = Environment.CommandLine;
        string reste = ApresExecutable(brut).Trim();
        int espace = reste.IndexOf(' ');
        if (espace < 0)
            throw new Exception(
                "Le raccourci Steam ne porte pas de jeu à lancer.\n\n"
                + "Attendu : <système> \"<chemin de la ROM>\"\n"
                + "Reçu : " + (reste.Length == 0 ? "(rien)" : reste));

        string cle = reste.Substring(0, espace);
        string rom = reste.Substring(espace + 1).Trim().Trim('"');

        string plan = Path.Combine(Path.Combine(dossier, "systems"), cle + ".ini");
        if (!File.Exists(plan))
            throw new Exception(
                "Aucun plan de lancement pour « " + cle + " ».\n\n"
                + "Attendu ici : " + plan + "\n\n"
                + "Relancer « retro sync » depuis l'hôte : c'est lui qui écrit "
                + "les plans.");

        var p = LirePlan(plan);
        if (!File.Exists(rom))
            throw new Exception("La ROM est introuvable :\n\n" + rom
                + "\n\nLe partage des ROMs est-il monté ?");
        string emulateur = Valeur(p, "emulator");
        if (!File.Exists(emulateur))
            throw new Exception("L'émulateur est introuvable :\n\n" + emulateur
                + "\n\nRelancer « retro install ».");

        SetProcessDPIAware();
        int largeur = GetSystemMetrics(SM_CXSCREEN);
        int hauteur = GetSystemMetrics(SM_CYSCREEN);
        int vram = VramMo();
        int coeurs = Environment.ProcessorCount;

        string demande = ModeChoisi();
        string classe = ClasserMachine(p, vram, coeurs);
        string effectif = demande;
        string motif = "choisi explicitement";
        if (demande == "auto")
        {
            // Le plan porte déjà la réponse pour chaque classe : rien n'est
            // rejoué ici, donc rien ne peut diverger de la politique testée.
            effectif = Valeur(p, "auto_" + classe);
            motif = "auto → machine " + classe + " (" + vram + " Mo de VRAM, "
                + coeurs + " cœurs)";
        }

        string gabarit = Valeur(p, effectif);
        string rendu = Substituer(gabarit, p, largeur, hauteur);
        // Les espaces se resserrent AVANT que la ROM entre dans la commande :
        // un jeu dont le nom porte deux espaces — « Jeu  (USA).chd », que les
        // jeux de ROMs produisent réellement — verrait sinon son chemin
        // réécrit, et l'émulateur ne trouverait pas le fichier.
        string commande = Valeur(p, "launch")
            .Replace("{render}", rendu)
            .Replace("  ", " ")
            .Trim()
            .Replace("{rom}", rom);

        Noter(cle + " | mode " + effectif + " (" + motif + ") | "
            + largeur + "x" + hauteur + " | " + emulateur + " " + commande);

        var psi = new ProcessStartInfo(emulateur, commande);
        psi.WorkingDirectory = Valeur(p, "workdir");
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        using (var jeu = Process.Start(psi))
        {
            // Attendre : sans cela, le lanceur rendrait la main immédiatement
            // et Steam croirait la partie terminée dès son démarrage — durée
            // de jeu à zéro, et le bouton « Jouer » de retour pendant la
            // partie.
            jeu.WaitForExit();
            return jeu.ExitCode;
        }
    }

    static string ApresExecutable(string ligne)
    {
        if (ligne.StartsWith("\""))
        {
            int fin = ligne.IndexOf('"', 1);
            return fin < 0 ? "" : ligne.Substring(fin + 1);
        }
        int espace = ligne.IndexOf(' ');
        return espace < 0 ? "" : ligne.Substring(espace + 1);
    }

    static Dictionary<string, string> LirePlan(string chemin)
    {
        var table = new Dictionary<string, string>();
        foreach (string ligne in File.ReadAllLines(chemin, Encoding.UTF8))
        {
            if (ligne.Length == 0 || ligne.StartsWith("#")) continue;
            int egal = ligne.IndexOf('=');
            if (egal > 0) table[ligne.Substring(0, egal)] = ligne.Substring(egal + 1);
        }
        return table;
    }

    // Une clé absente est une faute du plan, pas une valeur vide : la traiter
    // comme vide ferait lancer une commande tronquée d'apparence normale.
    static string Valeur(Dictionary<string, string> p, string cle)
    {
        string v;
        if (!p.TryGetValue(cle, out v))
            throw new Exception("Le plan de lancement n'a pas de champ « "
                + cle + " ». Relancer « retro sync ».");
        return v;
    }

    static string ModeChoisi()
    {
        try
        {
            string m = File.ReadAllText(Path.Combine(dossier, "mode.txt"),
                                        Encoding.UTF8).Trim();
            if (m == "native" || m == "auto" || m == "full") return m;
        }
        catch (Exception) { }
        return "auto";
    }

    static string ClasserMachine(Dictionary<string, string> p, int vram, int coeurs)
    {
        // Du plus exigeant au moins exigeant, avec les seuils du plan — jamais
        // des seuils écrits ici, qui auraient divergé de ceux de la politique.
        foreach (string nom in new string[] { "solide", "moyenne" })
        {
            string[] seuil = Valeur(p, "threshold_" + nom).Split(',');
            if (vram >= int.Parse(seuil[0], CultureInfo.InvariantCulture)
                && coeurs >= int.Parse(seuil[1], CultureInfo.InvariantCulture))
                return nom;
        }
        return "modeste";
    }

    static string Substituer(string gabarit, Dictionary<string, string> p,
                             int largeur, int hauteur)
    {
        if (gabarit.Length == 0) return "";
        int natif = int.Parse(Valeur(p, "native_height"), CultureInfo.InvariantCulture);
        int maxi = int.Parse(Valeur(p, "max_scale"), CultureInfo.InvariantCulture);
        string echelle = "1";
        if (gabarit.Contains("{scale}"))
        {
            if (natif <= 0 || maxi <= 0)
                throw new Exception(
                    "Le plan emploie {scale} sans hauteur d'origine ni échelle "
                    + "maximale. Relancer « retro sync ».");
            int e = hauteur / natif;
            if (e < 1) e = 1;
            if (e > maxi) e = maxi;
            echelle = e.ToString(CultureInfo.InvariantCulture);
        }
        if ((gabarit.Contains("{width}") || gabarit.Contains("{height}"))
            && (largeur <= 0 || hauteur <= 0))
            throw new Exception(
                "La résolution de la session n'a pas pu être mesurée. Zéro "
                + "n'est pas une résolution : l'émulateur refuserait de "
                + "démarrer, ou démarrerait dans une taille absurde.");
        return gabarit
            .Replace("{width}", largeur.ToString(CultureInfo.InvariantCulture))
            .Replace("{height}", hauteur.ToString(CultureInfo.InvariantCulture))
            .Replace("{scale}", echelle);
    }

    // La VRAM, en mégaoctets. Le registre porte la valeur réelle sur 64 bits ;
    // Win32_VideoController.AdapterRAM est un entier 32 bits qui plafonne à
    // 4 Go et annoncerait une carte de 8 Go comme une carte de 4.
    static int VramMo()
    {
        try
        {
            using (var classe = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(
                @"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"))
            {
                if (classe == null) return 0;
                long meilleure = 0;
                foreach (string nom in classe.GetSubKeyNames())
                {
                    using (var carte = classe.OpenSubKey(nom))
                    {
                        if (carte == null) continue;
                        object v = carte.GetValue("HardwareInformation.qwMemorySize");
                        if (v is long && (long)v > meilleure) meilleure = (long)v;
                    }
                }
                return (int)(meilleure / (1024 * 1024));
            }
        }
        catch (Exception)
        {
            // Une VRAM inconnue vaut zéro, et zéro n'est pas une petite carte :
            // c'est une mesure qui n'a pas eu lieu. Le mode `auto` retombe
            // alors sur « modeste », le seul choix qui ne promet rien.
            return 0;
        }
    }
}
