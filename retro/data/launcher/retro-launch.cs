// retro-launch — le lanceur commun de la console rétro.
//
// Steam fige les options de lancement au moment de la synchronisation. Ce
// qu'il faut savoir pour rendre un jeu — la résolution de la session, ce que
// la machine offre — n'est connu qu'ICI, au lancement : un flux Apollo change
// de résolution selon le client qui se connecte.
//
// Ce programme NE DÉCIDE RIEN. Tout l'arbitrage est calculé en Python, où il
// est testé, et écrit par `retro scan` dans le plan que ce fichier se
// contente de lire. Le classement de la machine se fait ici parce que la machine est
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
using System.Threading;

static class RetroLaunch
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int MessageBoxW(IntPtr h, string texte, string titre, uint type);
    [DllImport("user32.dll")]
    static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll")]
    static extern bool SetProcessDPIAware();
    // Un programme /target:winexe n'a PAS de console : sans cet appel,
    // Console.Out ecrit dans le vide et « --explain » ne rendrait rien, ce qui
    // ressemblerait exactement a un lanceur muet. La sortie est de toute facon
    // ecrite aussi dans un fichier, seul canal sur lequel on puisse compter.
    [DllImport("kernel32.dll")]
    static extern bool AttachConsole(int pid);
    const int ATTACH_PARENT_PROCESS = -1;

    const int SM_CXSCREEN = 0, SM_CYSCREEN = 1;

    // Steam n'arrete que le processus QU'IL a lance — celui-ci. L'emulateur,
    // lui, est un enfant : il survivait a son parent, et le bouton « Arreter »
    // de Steam ne fermait rien du tout. Mesure le 2026-08-27 sur un emulateur
    // reste sur son assistant de premier lancement : ni Steam ni la manette ne
    // pouvaient en sortir, et la bibliotheque restait « en jeu » indefiniment.
    //
    // Un job object avec KILL_ON_JOB_CLOSE lie les deux vies : quand ce
    // processus meurt, de sa belle mort ou tue par Steam, Windows ferme le
    // job, et l'emulateur meurt avec lui. Le handle reste donc ouvert
    // volontairement jusqu'a la fin.
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr CreateJobObjectW(IntPtr attrs, string nom);
    [DllImport("kernel32.dll")]
    static extern bool SetInformationJobObject(IntPtr job, int classe,
                                               IntPtr info, uint taille);
    [DllImport("kernel32.dll")]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr processus);

    // L'ENUMERATION DES MANETTES, PAR WINMM.
    //
    // POURQUOI winmm et pas System.Management, ni SDL, ni XInput : winmm est
    // dans mscorlib au sens ou il ne demande AUCUNE reference d'assemblage
    // supplementaire. System.Management en exigerait une, donc une ligne de
    // plus dans compiler.cmd — dont l'encodage cp850 est garde par un test
    // parce qu'une seule ligne coupee rend le lanceur non compilable sur la
    // console. Le cout d'une reference est ici plus grand qu'il n'en a l'air.
    //
    // CE QUE CE TEMOIN N'EST PAS, ET IL FAUT LE LIRE AVANT DE S'EN SERVIR :
    // l'identifiant winmm d'une manette N'EST PAS l'index SDL. Les vingt-sept
    // liaisons de DuckStation visent « SDL-0 », c'est-a-dire la premiere
    // manette QUE SDL enumere ; rien ne garantit que les deux numerotations
    // coincident. Elles coincident quand il n'y a qu'une manette, qui est le
    // cas normal de cette console — et c'est justement le NOMBRE que ce
    // temoin sert d'abord a constater. Le compte, lui, ne depend d'aucune
    // numerotation.
    [DllImport("winmm.dll")]
    static extern uint joyGetNumDevs();
    [DllImport("winmm.dll", CharSet = CharSet.Unicode)]
    static extern uint joyGetDevCapsW(UIntPtr id, ref JOYCAPSW caps, uint taille);
    [DllImport("winmm.dll")]
    static extern uint joyGetPosEx(uint id, ref JOYINFOEX info);

    const uint JOYERR_NOERROR = 0;
    // Ce que joyGetPosEx rend d'un identifiant que le pilote connait mais dont
    // aucune manette n'est branchee. C'est LA distinction qui compte :
    // joyGetNumDevs rend le nombre d'identifiants SUPPORTES — 16 sur une
    // machine ou rien n'est branche — et non le nombre de manettes presentes.
    // Compter sans ce filtre annoncerait seize manettes sur une console qui
    // n'en a aucune, ce qui leverait le probleme « plus d'une manette » a
    // chaque lancement et apprendrait au proprietaire a l'ignorer.
    const uint JOYERR_UNPLUGGED = 167;
    const uint JOY_RETURNCENTERED = 0x00000400;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct JOYCAPSW
    {
        public ushort wMid;          // le fabricant : le VID
        public ushort wPid;          // le produit  : le PID
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string szPname;       // le nom lisible
        public uint wXmin, wXmax, wYmin, wYmax, wZmin, wZmax;
        public uint wNumButtons;
        public uint wPeriodMin, wPeriodMax;
        public uint wRmin, wRmax, wUmin, wUmax, wVmin, wVmax;
        public uint wCaps;
        public uint wMaxAxes, wNumAxes, wMaxButtons;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string szRegKey;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string szOEMVxD;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOYINFOEX
    {
        public uint dwSize;
        public uint dwFlags;
        public uint dwXpos, dwYpos, dwZpos;
        public uint dwRpos, dwUpos, dwVpos;
        public uint dwButtons, dwButtonNumber;
        public uint dwPOV;
        public uint dwReserved1, dwReserved2;
    }

    const int JobObjectExtendedLimitInformation = 9;
    const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct IO_COUNTERS
    {
        public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
        public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }

    // Rend le job, ou IntPtr.Zero si le systeme l'a refuse. Un echec ici ne
    // doit PAS empecher le jeu de demarrer : il rend seulement l'arret depuis
    // Steam moins sur, et le journal le dit.
    static IntPtr CreerJob()
    {
        try
        {
            IntPtr job = CreateJobObjectW(IntPtr.Zero, null);
            if (job == IntPtr.Zero) return IntPtr.Zero;
            var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            int taille = Marshal.SizeOf(info);
            IntPtr bloc = Marshal.AllocHGlobal(taille);
            try
            {
                Marshal.StructureToPtr(info, bloc, false);
                if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                             bloc, (uint)taille))
                    return IntPtr.Zero;
            }
            finally { Marshal.FreeHGlobal(bloc); }
            return job;
        }
        catch (Exception) { return IntPtr.Zero; }
    }

    static string dossier;
    static string journal;
    const string SI_ABSENT = "si-absent";
    // La seconde strategie d'ecriture. « si-absent » pose un fichier absent
    // et n'y revient jamais ; « fusion » rouvre un fichier QUI EXISTE pour y
    // porter les seules cles que retro apporte. Le proprietaire l'a
    // explicitement autorisee — a MODIFIER, jamais a ECRASER.
    const string FUSION = "fusion";
    // La ligne qui distingue, DANS LE FICHIER, ce que retro a pose de ce que
    // le proprietaire a pose. Sans elle, quelqu'un qui rouvre son settings.ini
    // six mois plus tard ne peut pas savoir quelle valeur il a choisie
    // lui-meme et laquelle lui a ete posee — et corrigerait la mauvaise.
    //
    // ELLE N'EST POSEE QUE DANS UN INI, jamais dans un YAML, et pour deux
    // raisons dont chacune suffirait :
    //
    //   · elle commence par « ; », qui est un commentaire INI mais N'EN EST
    //     PAS UN en YAML — la marque corromprait le fichier ;
    //   · Vita3K REGENERE son config.yml a chaque lancement (serialize_config,
    //     appelee par init_config, vita3k/config/src/config.cpp) et yaml-cpp
    //     n'emet aucun commentaire. La marque disparaitrait a chaque partie,
    //     la fusion la reposerait, et chaque lancement deposerait une
    //     sauvegarde de plus — l'inverse exact de ce que l'idempotence
    //     garantit. En YAML, l'idempotence se juge sur la seule VALEUR.
    const string MARQUE_FUSION = "; posé par « retro » — cette ligne est réécrite à chaque lancement";

    // LES EXTENSIONS DONT LE CONTENU EST UN YAML PLAT. Le miroir exact de
    // `_YAML` dans retro/profiles.py : le dialecte se deduit de l'EXTENSION de
    // la cible, pas d'un champ declare — un champ pourrait contredire ce que
    // le fragment contient, une extension non.
    static bool EstYaml(string cible)
    {
        string ext = Path.GetExtension(cible);
        if (ext == null) return false;
        ext = ext.ToLowerInvariant();
        return ext == ".yml" || ext == ".yaml";
    }

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

    // Un avertissement A L'ECRAN qui ne retient PAS le lanceur.
    //
    // MessageBoxW est MODALE : appelee sur le fil principal, elle bloquerait
    // le lancement jusqu'a ce que quelqu'un clique — et une console de salon
    // pilotee a la seule manette n'a personne pour le faire. Le jeu ne
    // demarrerait alors JAMAIS et Steam resterait « en jeu » indefiniment :
    // exactement l'aller sans retour que l'en-tete de ce fichier decrit comme
    // le pire etat possible. Sur un thread d'arriere-plan, l'appelant se
    // poursuit tout de suite ; IsBackground fait mourir ce thread avec le
    // processus, donc il ne peut jamais retenir le lanceur apres la fin du
    // jeu, et STA est ce qu'exige une boite de dialogue Win32.
    //
    // Factorisee parce que DEUX chemins en ont besoin — un amorcage qui
    // echoue, un ordre de reamorcage qui n'a pas pu etre consomme — et qu'un
    // second exemplaire finirait par perdre l'un de ces trois reglages.
    static void AvertirEnFond(string titre, string message)
    {
        try
        {
            var boite = new Thread(() => MessageBoxW(IntPtr.Zero, message,
                                                     titre, 0x30));
            boite.IsBackground = true;
            boite.SetApartmentState(ApartmentState.STA);
            boite.Start();
        }
        catch (Exception e)
        {
            // Un thread qui ne demarre pas ne doit pas, lui non plus,
            // empecher le jeu de demarrer : l'appelant a deja ecrit la trace
            // complete au journal AVANT d'appeler cette methode.
            Noter("boite de dialogue non affichee (" + titre + ") : "
                + e.Message);
        }
    }

    // L'INDICE D'UNE ENTREE, EN CHIFFRES INVARIANTS.
    //
    // « "bootstrap_target." + n » passe par int.ToString() DE LA CULTURE : sous
    // une culture a chiffres natifs, la cle composee ne serait plus celle que
    // « retro scan » a ecrite. Cote plan, Valeur() protesterait — une cle
    // absente est une faute du plan. Cote rapport --explain, en revanche, rien
    // ne protesterait : l'hote decoupe « cle=valeur » ligne a ligne et ne
    // reconnaitrait tout simplement plus « amorcage_cible.1 ». Meme precaution
    // que l'horodatage du temoin, et pour la meme raison.
    static string Indice(string prefixe, int n)
    {
        return prefixe + n.ToString(CultureInfo.InvariantCulture);
    }

    // L'amorçage : poser la configuration d'un émulateur qui n'en a jamais eu.
    //
    // Mesuré le 2026-08-28 : sans son settings.ini, DuckStation tient
    // SetupWizardIncomplete pour vrai et ouvre son assistant AVANT d'honorer
    // sa ligne de commande. Aucun de ses dix-sept arguments ne le saute, et
    // comme personne ne termine un assistant depuis un canapé, rien n'est
    // jamais ecrit : le lancement suivant recommence a l'identique.
    //
    // PLUSIEURS CIBLES PAR PROFIL. Le plan porte « bootstrap_count » puis des
    // lignes indicees de 1 a N : RPCS3 a deux fichiers a recevoir — ses modales
    // dans un INI, son gestionnaire de manette dans un YAML — et une seule
    // cible par profil rendait le second inexprimable. Le lanceur boucle et
    // n'invente rien : ce qui est pose, et quand, est decide par « retro scan ».
    static void Amorcer(Dictionary<string, string> p, string profil)
    {
        int nombre = int.Parse(Valeur(p, "bootstrap_count"),
                               CultureInfo.InvariantCulture);
        if (nombre == 0)
        {
            // Cet emulateur n'a rien a recevoir — mais un ordre de
            // reamorcage a pu etre pose AVANT que le bloc [[bootstrap]]
            // disparaisse du profil. Sortir sans le consommer le laisserait
            // dans reamorcer.txt pour toujours : invisible tant que le bloc
            // manque, et surprenant le jour ou il revient — ce jour-la, un
            // ordre que personne ne se rappelle avoir donne ferait sauvegarder
            // puis ecraser la configuration du proprietaire.
            if (OrdreDeReamorcage(profil))
            {
                Noter("ordre de reamorcage sans objet pour " + profil
                    + " : ce profil ne porte plus de configuration a poser ; "
                    + "l'ordre est retire sans rien ecrire.");
                ConsommerOrdre(profil, false);
            }
            return;
        }

        // L'ordre de reamorcage vaut pour TOUTES les entrees du profil, et il
        // est lu UNE FOIS, avant la boucle. Le relire a chaque tour serait sans
        // effet aujourd'hui ; le CONSOMMER dans la boucle, en revanche, ne
        // reposerait que la premiere cible et laisserait les suivantes intactes
        // — un « --reamorcer » a moitie execute, sans un mot.
        bool force = OrdreDeReamorcage(profil);
        bool quelqueChosePose = false;

        for (int n = 1; n <= nombre; n++)
        {
            if (AmorcerUne(p, profil, n, force)) quelqueChosePose = true;
        }

        if (force) ConsommerOrdre(profil, quelqueChosePose);
    }

    // UNE entree du plan, les deux regimes dans l'ordre. Rend vrai si quelque
    // chose a ete ecrit — c'est ce qui decide d'inscrire le temoin.
    static bool AmorcerUne(Dictionary<string, string> p, string profil,
                           int n, bool force)
    {
        string cible = Valeur(p, Indice("bootstrap_target.", n));

        // LE JETON NON SUBSTITUE. « retro scan » resout {install_dir} a
        // l'ecriture du plan ; s'il en reste un ici, c'est que le plan a ete
        // ecrit par une version qui ne connaissait pas ce jeton, ou que la
        // substitution a rate. Sans ce garde, Windows creerait un dossier
        // portant LITTERALEMENT « {install_dir} », le fichier y serait pose, et
        // l'emulateur n'y lirait jamais rien : une panne parfaitement muette,
        // qui ressemble a un reglage qui « ne prend pas ».
        //
        // Il leve plutot que d'ecrire a cote : ecrire au mauvais endroit est la
        // seule issue dont personne ne se remet sans savoir ou regarder.
        if (cible.IndexOf('{') >= 0)
            throw new Exception(
                "La cible d'amorçage n°"
                + n.ToString(CultureInfo.InvariantCulture)
                + " porte encore un jeton non "
                + "substitué :\n\n" + cible + "\n\nAucun fichier n'a été "
                + "écrit : un dossier portant littéralement ce nom serait créé, "
                + "et l'émulateur n'y lirait jamais rien.\n\n"
                + "Relancer « retro scan » depuis l'hôte pour réécrire les "
                + "plans.");

        // « bootstrap_when » ne gouverne QUE le fichier « posé une fois ». Le
        // second regime, celui des cles imposees, se reconnait a la presence
        // de « bootstrap_enforced » : le profil le distingue par STRUCTURE,
        // pas par un mode qu'on pourrait mettre en contradiction avec ce
        // qu'il contient.
        string quand = Valeur(p, Indice("bootstrap_when.", n));
        if (quand.Length > 0 && quand != SI_ABSENT)
            throw new Exception(
                "Le plan demande une stratégie d'amorçage inconnue : « " + quand
                + " ». Ce lanceur ne connaît que « " + SI_ABSENT + " » pour le "
                + "fichier posé une fois, et « " + FUSION + " » pour les clés "
                + "imposées, qu'il reconnaît à « bootstrap_enforced ».\n\n"
                + "Recompiler le lanceur (compiler.cmd), ou relancer "
                + "« retro scan ».");

        cible = Environment.ExpandEnvironmentVariables(cible);
        string impose = Valeur(p, Indice("bootstrap_enforced.", n));

        // GetDirectoryName rend null pour une racine ("C:\"): tester
        // parent.Length sans ce garde leverait une NullReferenceException,
        // dont le message « Object reference not set to an instance of an
        // object » ne nomme rien — la politique de ce depot l'interdit. Une
        // cible sans dossier parent est de toute facon une erreur du plan :
        // aucune configuration d'emulateur ne se pose a la racine d'un disque.
        string parent = Path.GetDirectoryName(cible);
        if (parent == null)
            throw new Exception(
                "La cible d'amorçage n'a pas de dossier parent valide :\n\n"
                + cible + "\n\nRelancer « retro scan ».");
        if (parent.Length > 0 && !Directory.Exists(parent))
            Directory.CreateDirectory(parent);

        // LES DEUX REGIMES, DANS CET ORDRE, SUR LA MEME CIBLE.
        //
        // 1. poser le fichier s'il est absent — les preferences, que le
        //    proprietaire pourra ensuite changer pour de bon ;
        // 2. y refondre les cles que la console impose.
        //
        // L'ordre n'est pas indifferent : sur une console neuve, la seconde
        // etape doit trouver le fichier que la premiere vient de poser. A
        // l'envers, la fusion aurait cree un fichier ne portant QUE les cles
        // imposees, et « si-absent » n'aurait plus jamais pose les
        // preferences — la cible existant desormais.
        bool ecrit = false;

        if (!File.Exists(cible) || force)
        {
            string source = Valeur(p, Indice("bootstrap_source.", n));
            if (source.Length > 0)
            {
                if (!File.Exists(source))
                    throw new Exception(
                        "Le fichier de configuration à poser est introuvable :"
                        + "\n\n" + source + "\n\nRelancer « retro scan » "
                        + "depuis l'hôte.");
                bool bomSource;
                string contenu = LireTexte(source, out bomSource);
                Sauvegarder(cible);
                EcrireAtomique(cible, contenu, bomSource);
                Noter("amorcage : " + profil + " -> " + cible + " (" + SI_ABSENT
                      + ")" + (force ? " (ordre de reamorcage)" : ""));
                ecrit = true;
            }
        }

        if (impose.Length > 0)
        {
            if (!File.Exists(impose))
                throw new Exception(
                    "Le fichier des clés imposées est introuvable :\n\n"
                    + impose + "\n\nRelancer « retro scan » depuis l'hôte.");
            bool bomImpose;
            string apporte = LireTexte(impose, out bomImpose);
            if (File.Exists(cible))
            {
                bool bomCible;
                string existant = LireTexte(cible, out bomCible);
                int posees;
                string fusionne = Fusionner(cible, existant, apporte,
                                            out posees);
                // Un fichier deja conforme n'est NI sauvegarde NI reecrit.
                // Sans ce test, chaque lancement deposerait une sauvegarde de
                // plus et retoucherait un fichier qui n'avait rien a changer
                // — le contraire exact de ce que le proprietaire a autorise.
                //
                // La conformite se juge SUR LES CLES, marques retirees des
                // deux cotes. Voir SansMarques : la marque est un
                // commentaire, et l'interface de l'emulateur les efface.
                if (SansMarques(fusionne) == SansMarques(existant))
                {
                    Noter("amorcage : " + cible + " deja conforme — aucune "
                          + "sauvegarde, aucune reecriture (" + FUSION + ")");
                }
                else
                {
                    Sauvegarder(cible);
                    // Le BOM rendu est celui de la CIBLE : le fichier
                    // appartient au proprietaire, et le lui changer au
                    // passage serait une modification qu'il n'a pas
                    // autorisee.
                    EcrireAtomique(cible, fusionne, bomCible);
                    Noter("amorcage : " + profil + " -> " + cible + " ("
                          + FUSION + ", " + posees + " cle(s) imposee(s))");
                    ecrit = true;
                }
            }
            else
            {
                // Aucune cible : le profil n'a pas de fichier « posé une
                // fois », ou il est vide. Les cles imposees suffisent a le
                // creer — sans elles l'emulateur rouvrirait son assistant.
                EcrireAtomique(cible, apporte, bomImpose);
                Noter("amorcage : " + profil + " -> " + cible + " (" + FUSION
                      + ", fichier cree)");
                ecrit = true;
            }
        }

        // Le temoin porte la CIBLE, pas seulement le profil : un profil a deux
        // cibles en ecrit deux lignes, et l'hote les relit toutes.
        if (ecrit) InscrireTemoin(profil, cible);
        return ecrit;
    }

    // Une copie horodatee de la cible, avant toute ecriture. Rien n'ecrase
    // une configuration sans sauvegarde : la convention est celle de
    // shortcuts.vdf.bak-*, deja en usage cote synchronisation.
    static void Sauvegarder(string cible)
    {
        if (!File.Exists(cible)) return;
        // L'horodatage a une resolution d'une seconde : deux lancements du
        // meme profil dans la meme seconde visent le meme nom, et
        // File.Copy(..., false) refuse a bon droit de l'ecraser — mais il
        // faut alors essayer un AUTRE nom plutot que de faire echouer
        // l'amorcage. Meme parade que sauvegarder() cote synchronisation
        // (retro/steam/writer.py) : un suffixe « -N » croissant, borne pour
        // ne jamais boucler indefiniment.
        string based = cible + ".bak-" + DateTime.Now.ToString(
            "yyyyMMdd-HHmmss", CultureInfo.InvariantCulture);
        string sauvegarde = based;
        bool copiee = false;
        for (int n = 0; n < 1000 && !copiee; n++)
        {
            sauvegarde = n == 0 ? based : based + "-" + n;
            try
            {
                File.Copy(cible, sauvegarde, false);
                copiee = true;
            }
            catch (IOException)
            {
                // Un filtre d'exception (« catch (...) when ») serait du
                // C# 6 ; compiler.cmd appelle le csc.exe du .NET Framework
                // 4.0.30319, dont rien ne garantit la version de langage sur
                // la machine du proprietaire. Le test est donc fait EN CLAIR,
                // dans le catch : si ce nom est deja pris, essayer le
                // suivant ; toute autre IOException (disque plein,
                // permission) n'est pas une collision de nom et remonte telle
                // quelle.
                if (!File.Exists(sauvegarde)) throw;
            }
        }
        if (!copiee)
            throw new Exception(
                "Impossible de sauvegarder " + cible + " : 1000 noms de "
                + "sauvegarde sont déjà pris.");
        Noter("amorcage : " + cible + " sauvegarde en " + sauvegarde);
    }

    // ECRITURE ATOMIQUE, comme retro/steam/writer.py (os.replace) : c'est la
    // politique du depot, et elle vaut ici plus qu'ailleurs. Une ecriture
    // interrompue — disque plein, machine eteinte, antivirus — laisserait une
    // cible qui EXISTE, a moitie ecrite : « si-absent » ne la reparerait plus
    // JAMAIS, et l'emulateur rouvrirait son assistant pour de bon. On ecrit
    // donc a cote, puis on bascule d'un coup : a tout instant, la cible est
    // soit l'ancienne, soit la nouvelle, jamais une moitie des deux.
    //
    // Deux appels et non un : File.Move refuse d'ecraser (l'option
    // « overwrite » n'existe pas sur le .NET Framework) et File.Replace exige
    // au contraire une cible existante.
    static void EcrireAtomique(string cible, string contenu, bool bom)
    {
        string temporaire = cible + ".retro-tmp";
        try
        {
            File.WriteAllText(temporaire, contenu, new UTF8Encoding(bom));
            if (File.Exists(cible)) File.Replace(temporaire, cible, null);
            else File.Move(temporaire, cible);
        }
        catch (Exception)
        {
            // Ne rien laisser derriere : ce dossier appartient au
            // proprietaire, et un « .retro-tmp » a moitie ecrit y serait un
            // debris que personne ne saurait relier a quoi que ce soit.
            try { if (File.Exists(temporaire)) File.Delete(temporaire); }
            catch (Exception) { }
            throw;
        }
    }

    // Ce qu'une fusion FERAIT, sans rien ecrire. C'est la seule facon de
    // verifier a distance qu'elle ne va pas abimer le fichier du
    // proprietaire : on lit, on melange en memoire, on compare, on rend le
    // compte — et on ne touche a rien.
    //
    // Toute exception est RATTRAPEE et rendue en clair : --explain est appele
    // par WinRM en session 0, ou une boite de dialogue pendrait jusqu'a
    // l'expiration du delai. Meme raison que pour la lecture de reamorcer.txt.
    static string FusionAPoser(string cible, string impose)
    {
        try
        {
            cible = Environment.ExpandEnvironmentVariables(cible);
            if (!File.Exists(impose))
                return "inconnu (le fichier des cles imposees est "
                       + "introuvable : " + impose + ")";
            bool bomCible, bomImpose;
            string apporte = LireTexte(impose, out bomImpose);
            if (!File.Exists(cible))
                return "oui (" + FUSION + " : la cible n'existe pas encore)";
            string existant = LireTexte(cible, out bomCible);
            int posees;
            string fusionne = Fusionner(cible, existant, apporte, out posees);
            // Le MEME juge que le chemin d'ecriture, et pas une seconde
            // formule qui lui ressemble : --explain est la seule facon de
            // verifier a distance ce que la fusion ferait, et deux juges
            // divergents rendraient « rien ne sera reecrit » a un
            // proprietaire dont le fichier est reecrit a chaque clic.
            if (SansMarques(fusionne) == SansMarques(existant))
                return "non (" + FUSION + " : la cible porte deja les cles "
                       + "imposees, rien ne sera reecrit)";
            return "oui (" + FUSION + " : " + posees + " cle(s) imposee(s) ; "
                   + "la cible sera sauvegardee, le reste de son contenu est "
                   + "preserve)";
        }
        catch (Exception e)
        {
            return "inconnu (fusion illisible : "
                   + e.Message.Replace("\r", " ").Replace("\n", " ") + ")";
        }
    }

    // --- la fusion d'un fichier INI -------------------------------------
    //
    // Le proprietaire a autorise retro a MODIFIER un settings.ini qui existe.
    // Modifier, jamais ecraser : tout ce que cette methode ne connait pas est
    // recopie tel quel — cles inconnues, commentaires, lignes vides, ordre.
    // Le [BIOS] SearchDirectory que le proprietaire a ajoute a la main
    // survit ; c'est le cas d'usage qui a fait ecrire cette methode ainsi.
    //
    // Ce qu'elle apporte, et rien d'autre : les cles du fichier source. Pour
    // chacune, dans sa section :
    //   - la cle existe deja  -> sa VALEUR est remplacee, a sa place ;
    //   - la section existe   -> la cle est ajoutee a la fin de la section ;
    //   - rien n'existe       -> la section est creee a la fin du fichier.
    //
    // IDEMPOTENTE : les marques de retro presentes sont retirees a la lecture
    // et reposees a l'ecriture, donc fusionner deux fois rend exactement le
    // meme texte. C'est ce qui permet a l'appelant de comparer et de NE RIEN
    // ECRIRE quand le fichier est deja conforme — pas de sauvegarde inutile,
    // pas de section empilee, pas de fichier retouche pour rien.
    //
    // LIMITE ASSUMEE : les COMMENTAIRES du fichier source ne sont pas
    // reportes, seules ses cles le sont. Les reporter demanderait de savoir
    // les reconnaitre pour ne pas les empiler a chaque passage, et un
    // commentaire duplique a chaque lancement serait exactement la panne que
    // l'idempotence existe pour fermer. Les explications vivent dans le
    // profil et dans le fichier source depose a cote des plans ; ici, la
    // marque dit qui a pose la ligne, ce qui est ce dont on a besoin devant
    // un fichier qu'on relit six mois plus tard.
    static string SectionDe(string ligne, bool yaml)
    {
        // Un YAML PLAT n'a pas de sections : tout vit au premier niveau. Rendre
        // une section sur « [a, b] », qui est une sequence en ligne, ferait
        // basculer la fusion dans une section imaginaire et deplacerait la cle
        // imposee hors de portee de son lecteur.
        if (yaml) return null;
        string s = ligne.Trim();
        if (s.Length >= 2 && s[0] == '[' && s[s.Length - 1] == ']')
            return s.Substring(1, s.Length - 2).Trim();
        return null;
    }

    // Le nom de cle d'une ligne « cle = valeur », ou null. Les commentaires
    // n'en sont pas : une ligne « ; Scaling = ... » ne doit pas passer pour
    // le reglage qu'elle explique, sans quoi la fusion irait ecrire dans un
    // commentaire et la vraie cle resterait a sa valeur d'avant.
    static string CleDe(string ligne, bool yaml)
    {
        string s = ligne.Trim();
        if (s.Length == 0) return null;
        if (yaml)
        {
            // Le miroir exact de `cles_yaml` (retro/profiles.py). Seul le
            // PREMIER NIVEAU compte : une ligne indentee appartient a la cle du
            // dessus, une ligne « - x » est un element de sequence. Les prendre
            // pour des cles ferait ecrire notre valeur au milieu d'une
            // structure, que le lecteur de l'emulateur refuserait.
            if (char.IsWhiteSpace(ligne[0])) return null;
            // « # » est le commentaire YAML ; « ; » n'en est PAS un.
            if (s[0] == '#' || s[0] == '-') return null;
            int deuxPoints = s.IndexOf(':');
            if (deuxPoints <= 0) return null;
            string cleY = s.Substring(0, deuxPoints).Trim();
            return cleY.Length > 0 ? cleY : null;
        }
        if (s[0] == ';' || s[0] == '#' || s[0] == '[')
            return null;
        int eq = s.IndexOf('=');
        if (eq <= 0) return null;
        string cle = s.Substring(0, eq).Trim();
        return cle.Length > 0 ? cle : null;
    }

    static string Cle(string section, string cle, bool yaml)
    {
        // En YAML les cles SONT sensibles a la casse — yaml-cpp les compare
        // octet par octet. Rapprocher « Pref-Path » de « pref-path » ferait
        // ecrire notre valeur sur une cle que l'emulateur ne lit pas, ce qui
        // se comporte exactement comme si rien n'avait ete pose.
        if (yaml) return cle;
        // Les sections et les cles d'un INI ne sont pas sensibles a la casse
        // chez la plupart des lecteurs. Comparer telles quelles ferait poser
        // une SECONDE cle « scaling » a cote de « Scaling », dont l'emulateur
        // ne lirait qu'une — et pas forcement la notre.
        return section.ToLowerInvariant() + " " + cle.ToLowerInvariant();
    }

    // Le texte SANS les marques de retro, et sans ses fins de ligne : c'est
    // sur cette forme que se juge « deja conforme ».
    //
    // POURQUOI, et c'est une MESURE, pas une precaution : l'emulateur reecrit
    // son fichier de reglages a une fermeture propre depuis son interface, et
    // il en EFFACE TOUS LES COMMENTAIRES — 2187 octets devenus 985, mesure du
    // 2026-08-29. Les cles survivent ; les marques, qui SONT des commentaires,
    // non. Comparer le texte brut faisait donc differer le fusionne de
    // l'existant a TOUS les coups des lors que le proprietaire avait ouvert
    // son interface une fois : une sauvegarde horodatee et une reecriture
    // complete a chaque lancement, alors que pas une cle n'avait bouge.
    //
    // Ce que ce choix concede, et il faut le dire : les marques ne reviennent
    // alors PAS d'elles-memes. Elles sont reposees quand une cle est
    // reellement (re)posee, et pas avant. C'est delibere — les rendre
    // permanentes demanderait de reecrire le fichier a chaque cycle, qui est
    // exactement la panne qu'on ferme ici. Une marque est un CONFORT de
    // lecture ; l'idempotence est une promesse faite au proprietaire.
    //
    // Ce qu'on n'a PAS fait, et pourquoi : poser la marque sous forme de CLE
    // — que l'emulateur conserverait, puisqu'il preserve ce qu'il ne
    // comprend pas. Le proprietaire a autorise a ecrire « seulement les cles
    // que la console doit imposer » ; une cle de comptabilite que son
    // emulateur ne reconnait pas sort de cette autorisation.
    static string SansMarques(string texte)
    {
        var gardees = new List<string>();
        foreach (string ligne in texte.Replace("\r\n", "\n").Split('\n'))
            if (ligne.Trim() != MARQUE_FUSION) gardees.Add(ligne);
        return string.Join("\n", gardees.ToArray());
    }

    static string Fusionner(string cible, string existant, string apporte,
                            out int posees)
    {
        bool yaml = EstYaml(cible);
        // Ce que la source apporte, dans l'ordre : (section, cle) -> ligne.
        var ordre = new List<string>();
        var lignesApportees = new Dictionary<string, string>();
        var sectionDe = new Dictionary<string, string>();
        string courante = "";
        foreach (string ligne in apporte.Replace("\r\n", "\n").Split('\n'))
        {
            string sec = SectionDe(ligne, yaml);
            if (sec != null) { courante = sec; continue; }
            string cle = CleDe(ligne, yaml);
            if (cle == null) continue;
            string id = Cle(courante, cle, yaml);
            if (!lignesApportees.ContainsKey(id)) ordre.Add(id);
            lignesApportees[id] = ligne.Trim();
            sectionDe[id] = courante;
        }

        var reste = new List<string>(ordre);
        var sortie = new List<string>();
        courante = "";
        posees = 0;

        var lignes = new List<string>(existant.Replace("\r\n", "\n").Split('\n'));
        for (int i = 0; i < lignes.Count; i++)
        {
            string ligne = lignes[i];
            // Les marques d'un passage anterieur sont retirees ici et
            // reposees plus bas : c'est ce qui rend la fusion idempotente.
            if (ligne.Trim() == MARQUE_FUSION) continue;

            string sec = SectionDe(ligne, yaml);
            if (sec != null)
            {
                Completer(sortie, reste, lignesApportees, sectionDe, courante,
                          yaml, ref posees);
                courante = sec;
                sortie.Add(ligne);
                continue;
            }
            string cle = CleDe(ligne, yaml);
            string id = cle == null ? null : Cle(courante, cle, yaml);
            if (id != null && lignesApportees.ContainsKey(id)
                && reste.Contains(id))
            {
                if (!yaml) sortie.Add(MARQUE_FUSION);
                sortie.Add(lignesApportees[id]);
                reste.Remove(id);
                posees++;
                continue;
            }
            sortie.Add(ligne);
        }
        Completer(sortie, reste, lignesApportees, sectionDe, courante,
                  yaml, ref posees);

        // Ce qui reste appartient a des sections que le fichier n'a pas. En
        // YAML, toutes les cles vivent sous la section vide, que `Completer`
        // vient de traiter : cette boucle ne s'y execute jamais, et ecrire
        // « [] » dans un YAML n'a donc pas lieu.
        while (reste.Count > 0)
        {
            string section = sectionDe[reste[0]];
            if (sortie.Count > 0 && sortie[sortie.Count - 1].Trim().Length > 0)
                sortie.Add("");
            sortie.Add("[" + section + "]");
            for (int i = 0; i < reste.Count; i++)
            {
                if (sectionDe[reste[i]] != section) continue;
                if (!yaml) sortie.Add(MARQUE_FUSION);
                sortie.Add(lignesApportees[reste[i]]);
                posees++;
                reste.RemoveAt(i);
                i--;
            }
        }
        return string.Join("\r\n", sortie.ToArray());
    }

    // Les cles de CETTE section que le fichier ne portait pas, ajoutees a sa
    // fin. Rien si la section n'est pas concernee.
    static void Completer(List<string> sortie, List<string> reste,
                          Dictionary<string, string> lignesApportees,
                          Dictionary<string, string> sectionDe,
                          string section, bool yaml, ref int posees)
    {
        if (section == null) return;
        // Reculer avant les lignes vides de fin de section : la cle se pose
        // apres le dernier reglage, pas apres le blanc qui suit — sans quoi
        // elle glisserait d'une section a l'autre au passage suivant, et
        // l'idempotence tomberait.
        int fin = sortie.Count;
        while (fin > 0 && sortie[fin - 1].Trim().Length == 0) fin--;
        var ajouts = new List<string>();
        for (int i = 0; i < reste.Count; i++)
        {
            if (!string.Equals(sectionDe[reste[i]], section,
                               StringComparison.OrdinalIgnoreCase)) continue;
            if (!yaml) ajouts.Add(MARQUE_FUSION);
            ajouts.Add(lignesApportees[reste[i]]);
            posees++;
            reste.RemoveAt(i);
            i--;
        }
        if (ajouts.Count > 0) sortie.InsertRange(fin, ajouts);
    }

    // Le texte d'un fichier, et si on lui a trouve une marque d'octets. Le
    // BOM se PRESERVE : le fichier appartient au proprietaire, et le lui
    // retirer au passage serait une modification qu'il n'a pas autorisee.
    static string LireTexte(string chemin, out bool bom)
    {
        byte[] octets = File.ReadAllBytes(chemin);
        bom = octets.Length >= 3 && octets[0] == 0xEF && octets[1] == 0xBB
              && octets[2] == 0xBF;
        return new UTF8Encoding(false).GetString(
            octets, bom ? 3 : 0, octets.Length - (bom ? 3 : 0));
    }

    // Le propriétaire a-t-il demande de reposer la configuration de ce profil ?
    static bool OrdreDeReamorcage(string profil)
    {
        string fichier = Path.Combine(dossier, "reamorcer.txt");
        if (!File.Exists(fichier)) return false;
        foreach (string ligne in File.ReadAllLines(fichier, Encoding.UTF8))
            if (ligne.Trim() == profil) return true;
        return false;
    }

    // Un ordre ne vaut qu'un passage : le laisser ferait une sauvegarde et une
    // reecriture a chaque lancement, et le propriétaire ne pourrait plus jamais
    // regler son emulateur lui-meme.
    //
    // Protegee comme InscrireTemoin : reamorcer.txt est aussi ecrit depuis
    // l'hote a travers un partage reseau, et un verrou ou un attribut lecture
    // seule y ferait lever une exception ALORS QUE la configuration a deja
    // ete posee — sur le chemin nominal, Amorcer() n'appelle cette methode
    // qu'apres avoir copie le fichier avec succes. Une exception non rattrapee ferait donc annoncer
    // « ECHEC de l'amorcage » pour un amorcage reussi, et laisserait surtout
    // l'ordre en place : chaque lancement suivant reposerait la configuration
    // et ajouterait une sauvegarde de plus — precisement ce que cette methode
    // existe pour empecher.
    //
    // « configurationPosee » ne sert qu'au message : le meme echec n'a pas la
    // meme suite selon qu'une configuration vient d'etre ecrite (elle le sera
    // de nouveau a chaque lancement) ou que l'ordre etait devenu sans objet
    // (rien n'a ete ecrit, mais l'ordre attendra le retour du bloc). Dire
    // « la configuration a bien ete posee » dans le second cas serait faux.
    static void ConsommerOrdre(string profil, bool configurationPosee)
    {
        string fichier = Path.Combine(dossier, "reamorcer.txt");
        try
        {
            var restants = new List<string>();
            foreach (string ligne in File.ReadAllLines(fichier, Encoding.UTF8))
                if (ligne.Trim().Length > 0 && ligne.Trim() != profil)
                    restants.Add(ligne.Trim());
            if (restants.Count == 0) File.Delete(fichier);
            else File.WriteAllLines(fichier, restants, new UTF8Encoding(false));
        }
        catch (Exception e)
        {
            // Le proprietaire doit lire la consequence, pas seulement
            // l'echec : sans cela rien ne dit que sa configuration sera
            // reposee au prochain lancement, ni ce qu'il faut faire pour
            // l'empecher.
            //
            // ET A L'ECRAN, pas seulement au journal : c'est le seul chemin
            // de l'amorcage qui abime les donnees du proprietaire de facon
            // REPETEE — l'ordre restant en place, chaque lancement suivant
            // sauvegarde puis ecrase, indefiniment. Un journal ne se lit pas
            // depuis un canape.
            string consequence = configurationPosee
                ? "La configuration a bien été posée, mais elle sera reposée "
                  + "(avec une sauvegarde de plus) à CHAQUE lancement tant que "
                  + "« " + profil + " » restera dans " + fichier
                  + " — retirer cette ligne, ou supprimer ce fichier, pour "
                  + "l'empêcher."
                : "Rien n'a été écrit : ce profil ne porte plus de "
                  + "configuration à poser. L'ordre, lui, reste dans "
                  + fichier + ", et il s'appliquera le jour où ce profil en "
                  + "portera une de nouveau — retirer cette ligne, ou "
                  + "supprimer ce fichier.";
            Noter("ordre de reamorcage non consomme pour " + profil + " : "
                + e.Message + ". " + consequence);
            AvertirEnFond("Console rétro — ordre de ré-amorçage non consommé",
                "L'ordre de ré-amorçage de « " + profil + " » n'a pas pu être "
                + "retiré :\n\n" + e.Message + "\n\n" + consequence);
        }
    }

    // Le temoin : « retro status » tourne sur l'hote, qui n'atteint ni
    // C:\Users ni %APPDATA%. Il ne peut donc pas CONSTATER qu'un emulateur est
    // amorce — seulement lire ce que le lanceur a ecrit la ou l'hote regarde.
    // C'est une trace, jamais une source de verite : Amorcer() consulte la
    // cible, jamais ce fichier.
    static void InscrireTemoin(string profil, string cible)
    {
        try
        {
            string fichier = Path.Combine(dossier, "bootstrap.txt");
            var lignes = new List<string>();
            // La ligne REMPLACEE est celle qui porte le profil ET la cible.
            // Dedupliquer sur le seul profil effacerait la premiere cible
            // chaque fois que la seconde est posee : le rapport n'en montrerait
            // jamais qu'une, et la disparue passerait pour « pas encore
            // amorcee » alors qu'elle est en place.
            string prefixe = profil + "\t";
            string suffixe = "\t" + cible;
            if (File.Exists(fichier))
                foreach (string l in File.ReadAllLines(fichier, Encoding.UTF8))
                    if (l.Length > 0
                        && !(l.StartsWith(prefixe) && l.EndsWith(suffixe)))
                        lignes.Add(l);
            // InvariantCulture : dans un format personnalise, « : » est le
            // separateur d'heure DE LA CULTURE (pas un litteral) et l'annee
            // suit son calendrier. Ce temoin est un contrat relu par
            // retro/launcher.py::lire_amorcages, qui attend exactement
            // « yyyy-MM-dd HH:mm:ss » : une culture exotique sur la console
            // casserait cette lecture en silence.
            lignes.Add(profil + "\t" + DateTime.Now.ToString(
                "yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture)
                + "\t" + cible);
            lignes.Sort();
            File.WriteAllLines(fichier, lignes, new UTF8Encoding(false));
        }
        catch (Exception e)
        {
            // Un temoin illisible ne doit pas priver le propriétaire de son jeu :
            // la configuration, elle, est posee.
            Noter("temoin d'amorcage non ecrit : " + e.Message);
        }
    }

    // LE TEMOIN DES MANETTES. Meme partage des roles que bootstrap.txt : le
    // lanceur ecrit ici, retro/launcher.py::lire_pads lit la-bas, et l'hote
    // n'a AUCUN autre moyen de savoir combien de manettes la console voit ni
    // lesquelles. Sans lui, un pad d'un autre type — ou un pad de plus, qui
    // decale l'index sur lequel DuckStation repose entierement — ne se
    // constate qu'en s'asseyant devant la television avec une manette muette.
    //
    // UN INSTANTANE, reecrit en entier, et non un journal fusionne comme
    // bootstrap.txt : ce qui compte est l'etat de la DERNIERE session.
    //
    // ZERO MANETTE N'EST PAS UNE ERREUR, et le fichier le DIT plutot que de
    // ne pas etre ecrit. Un fichier absent veut dire « le lanceur n'a jamais
    // regarde » ; un fichier a zero veut dire « il a regarde et n'a rien
    // vu ». Ce sont deux constats differents, et les confondre effacerait le
    // seul des deux qui dise quelque chose de la console.
    static void InscrireTemoinPads()
    {
        try
        {
            var lignes = new List<string>();
            uint supportes = joyGetNumDevs();
            for (uint id = 0; id < supportes; id++)
            {
                // joyGetNumDevs rend le nombre d'identifiants que le PILOTE
                // supporte, pas le nombre de manettes branchees. Chaque
                // identifiant est donc verifie deux fois : ses capacites se
                // lisent-elles, et une manette repond-elle vraiment dessus.
                var caps = new JOYCAPSW();
                if (joyGetDevCapsW((UIntPtr)id, ref caps,
                                   (uint)Marshal.SizeOf(typeof(JOYCAPSW)))
                    != JOYERR_NOERROR)
                    continue;
                var info = new JOYINFOEX();
                info.dwSize = (uint)Marshal.SizeOf(typeof(JOYINFOEX));
                info.dwFlags = JOY_RETURNCENTERED;
                uint etat = joyGetPosEx(id, ref info);
                if (etat != JOYERR_NOERROR)
                {
                    // « Debranche » est le cas NORMAL et reste muet : sur une
                    // console qui porte une manette, quinze des seize
                    // identifiants supportes le sont, et les noter noierait le
                    // journal. Tout autre code est anormal et se DIT — sans
                    // quoi un pilote en panne rendrait « aucune manette », qui
                    // est un constat, alors que ce n'en est pas un.
                    if (etat != JOYERR_UNPLUGGED)
                        Noter("manette " + id.ToString(
                                  CultureInfo.InvariantCulture)
                            + " : joyGetPosEx rend " + etat.ToString(
                                  CultureInfo.InvariantCulture));
                    continue;
                }
                // vid:pid en hexadecimal MINUSCULE sur quatre chiffres, la
                // forme exacte que la table de retro/profiles.py compare.
                // « x4 » sur un ushort, en culture invariante comme la date.
                string vidPid =
                    caps.wMid.ToString("x4", CultureInfo.InvariantCulture)
                    + ":"
                    + caps.wPid.ToString("x4", CultureInfo.InvariantCulture);
                // Le nom est le DERNIER champ de la ligne et lire_pads le
                // prend en entier : une tabulation qu'il contiendrait ne le
                // tronquerait pas. Les retours a la ligne, eux, casseraient
                // le decoupage en lignes, et sont donc retires.
                string nom = (caps.szPname ?? "")
                    .Replace("\r", " ").Replace("\n", " ").Trim();
                lignes.Add(id.ToString(CultureInfo.InvariantCulture)
                    + "\t" + vidPid + "\t" + nom);
            }
            // InvariantCulture : dans un format personnalise, « : » est le
            // separateur d'heure DE LA CULTURE (pas un litteral) et l'annee
            // suit son calendrier. Ce temoin est un contrat relu par
            // retro/launcher.py::lire_pads, qui attend exactement
            // « yyyy-MM-dd HH:mm:ss » — exactement comme bootstrap.txt.
            var tout = new List<string>();
            tout.Add(DateTime.Now.ToString(
                "yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture)
                + "\t" + lignes.Count.ToString(CultureInfo.InvariantCulture));
            tout.AddRange(lignes);
            File.WriteAllLines(Path.Combine(dossier, "pads.txt"), tout,
                               new UTF8Encoding(false));
            Noter("manettes vues : " + lignes.Count.ToString(
                CultureInfo.InvariantCulture));
        }
        catch (Exception e)
        {
            // Rien de ce qui sert a OBSERVER ne doit pouvoir priver le
            // proprietaire de son jeu : le modele exact d'InscrireTemoin. Et
            // l'echec est NOTE plutot qu'avale — un temoin non ecrit se
            // lirait sinon comme « aucune manette », qui est un constat,
            // alors que « on n'a pas pu regarder » n'en est pas un.
            Noter("temoin des manettes non ecrit : " + e.Message);
        }
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

        // « --explain <systeme> <rom> » compose et REND COMPTE sans lancer.
        // C'est ce qui rend ce fichier verifiable : la substitution des
        // variables et le calcul de l'echelle n'existent qu'ici, la hauteur de
        // la session n'etant connue qu'au lancement. Les tenir aussi en Python
        // pour les tester aurait fait deux exemplaires dont un seul tourne.
        bool expliquer = false;
        if (reste.StartsWith("--explain "))
        {
            expliquer = true;
            reste = reste.Substring("--explain ".Length).Trim();
            espace = reste.IndexOf(' ');
            if (espace < 0)
                throw new Exception("--explain attend <systeme> \"<rom>\"");
        }

        string cle = reste.Substring(0, espace);
        string rom = reste.Substring(espace + 1).Trim().Trim('"');

        // « cle » est « <profil>.<systeme> » (system_key, cote Python). La
        // coupe se fait au PREMIER point : c'est l'identifiant de PROFIL qui
        // est garanti sans point — profiles.py refuse a la lecture du profil
        // tout identifiant hors [a-z0-9_-], parce que cet identifiant nomme
        // un fichier et se decoupe a trois endroits. Rien de tel n'est exige
        // d'un identifiant de SYSTEME : couper au dernier point ferait, sur
        // un systeme nomme « ps.x », chercher un profil qui n'existe pas, et
        // l'ordre de reamorcage du proprietaire ne serait jamais vu.
        int premierPoint = cle.IndexOf('.');
        string profilCle = premierPoint < 0 ? cle : cle.Substring(0, premierPoint);

        string plan = Path.Combine(Path.Combine(dossier, "systems"), cle + ".ini");
        if (!File.Exists(plan))
            throw new Exception(
                "Aucun plan de lancement pour « " + cle + " ».\n\n"
                + "Attendu ici : " + plan + "\n\n"
                + "Relancer « retro scan » depuis l'hôte : c'est lui qui écrit "
                + "les plans.");

        var p = LirePlan(plan);
        // UN JEU N'EST PAS TOUJOURS UN FICHIER. Sur PS Vita, PS4 et PS5, une
        // application installée est un DOSSIER — « ux0:app\PCSE00123\ »,
        // « CUSA07410\ », « PPSA01474\ » — et c'est exactement ce que le
        // profil déclare par son `app_dir_marker`. `File.Exists` rend FAUX sur
        // un dossier : le lanceur refusait donc TOUS ces jeux avec « La ROM
        // est introuvable », en désignant un chemin parfaitement présent.
        //
        // Mesuré le 2026-08-29 sur Ratchet & Clank (PPSA01474) : le dossier
        // existait, la synchronisation l'avait inventorié, Steam affichait son
        // entrée, et le lanceur envoyait chercher un partage qui était monté.
        if (!expliquer && !File.Exists(rom) && !Directory.Exists(rom))
            throw new Exception("La ROM est introuvable :\n\n" + rom
                + "\n\nLe partage des ROMs est-il monté ?");
        string emulateur = Valeur(p, "emulator");
        if (!expliquer && !File.Exists(emulateur))
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
            // {rom_id} : le NOM du jeu, sans son chemin ni son extension.
            //
            // Il existe pour les émulateurs qui ne se lancent PAS sur un
            // chemin. Vita3K en est un, et l'apprendre a coûté cher : son
            // argument positionnel signifie « installer ET lancer », si bien
            // que lui passer le dossier d'une application DÉJÀ installée la
            // réinstalle par-dessus elle-même. Mesuré le 2026-08-30 sur
            // Uncharted: Golden Abyss — après ce lancement, l'application
            // avait perdu son eboot.bin et son param.sfo, son titre était
            // retombé sur son identifiant, et elle ne démarrait plus. Un
            // lancement qui DÉTRUIT ce qu'il devait lancer.
            //
            // Sa vraie commande est « -r <identifiant de titre> », et cet
            // identifiant est le nom du dossier sous ux0\app\ — donc, dans
            // une bibliothèque qui suit la même convention, le nom du dossier
            // inventorié. C'est ce que ce jeton rend.
            .Replace("{rom_id}", Path.GetFileNameWithoutExtension(
                rom.TrimEnd('\\', '/')))
            .Replace("{rom}", rom);

        Noter(cle + " | mode " + effectif + " (" + motif + ") | "
            + largeur + "x" + hauteur + " | " + emulateur + " " + commande);

        if (expliquer)
        {
            AttachConsole(ATTACH_PARENT_PROCESS);
            var rapport = new StringBuilder();
            rapport.AppendLine("systeme=" + cle);
            // Sur stdout, pas dans une boite de dialogue : --explain est fait
            // pour etre lu par la machine qui pilote, a travers WinRM.
            rapport.AppendLine("mode_demande=" + demande);
            rapport.AppendLine("mode_effectif=" + effectif);
            rapport.AppendLine("motif=" + motif);
            rapport.AppendLine("classe=" + classe);
            rapport.AppendLine("vram_mo=" + vram);
            rapport.AppendLine("coeurs=" + coeurs);
            rapport.AppendLine("resolution=" + largeur + "x" + hauteur);
            rapport.AppendLine("emulateur=" + emulateur);
            rapport.AppendLine("commande=" + commande);
            // UN ORDRE DE REAMORCAGE EST LU UNE FOIS, POUR TOUT LE PROFIL.
            //
            // Un ordre en attente CHANGE la reponse, et le taire faisait
            // mentir le seul controle verifiable a distance : --explain
            // rendait « non (la cible existe) » alors que le lancement
            // suivant allait justement sauvegarder cette cible et la
            // reecrire. Lire reamorcer.txt ne modifie rien — --explain doit
            // rester sans effet de bord.
            //
            // La lecture est RATTRAPEE ICI, et nulle part ailleurs. Ce
            // fichier est ecrit par l'hote a travers un partage reseau : il
            // peut etre verrouille ou illisible au moment ou on le lit. Une
            // exception remonterait a Main(), qui appelle Echouer(), qui
            // affiche une MessageBoxW SYNCHRONE sur le fil principal — or
            // --explain est appele par WinRM, en session 0, ou personne ne
            // peut cliquer : l'appel pendrait jusqu'a son delai
            // d'expiration, et c'est justement le canal par lequel ce
            // lanceur se verifie a distance. Sur le chemin de LANCEMENT, au
            // contraire, la meme exception doit rester bruyante : le jeu
            // demarre quand meme et la boite s'affiche en arriere-plan,
            // devant quelqu'un qui peut la lire.
            //
            // Et on le DIT : repondre « aucun » sans avoir pu lire mentirait
            // par omission sur le point meme qu'on vient d'ajouter. Le
            // message de l'exception est mis a plat, une ligne du rapport
            // etant un « cle=valeur » que l'hote decoupe ligne a ligne.
            bool ordre = false;
            string ordreIllisible = "";
            try
            {
                ordre = OrdreDeReamorcage(profilCle);
            }
            catch (Exception e)
            {
                ordreIllisible = e.Message.Replace("\r", " ").Replace("\n", " ");
            }
            if (ordreIllisible.Length > 0)
                rapport.AppendLine("amorcage_ordre=illisible : " + ordreIllisible);
            else
                rapport.AppendLine("amorcage_ordre="
                    + (ordre ? "en attente" : "aucun"));

            // UNE LIGNE PAR ENTREE, indicee comme le plan. Une seule ligne
            // pour un profil a deux cibles ferait disparaitre la seconde du
            // seul controle lisible sans rien lancer.
            int compte = int.Parse(Valeur(p, "bootstrap_count"),
                                   CultureInfo.InvariantCulture);
            rapport.AppendLine("amorcage_count="
                + compte.ToString(CultureInfo.InvariantCulture));
            for (int n = 1; n <= compte; n++)
            {
                string cibleAmorcage = Valeur(p, Indice("bootstrap_target.", n));
                rapport.AppendLine(Indice("amorcage_cible.", n) + "=" + cibleAmorcage);
                // Combien de cles la console impose dans ce fichier, et non
                // seulement qu'elle en impose : « 3 cles » et « tout le
                // fichier » n'appellent pas la meme reaction.
                string imposeN = Valeur(p, Indice("bootstrap_enforced.", n));
                rapport.AppendLine(Indice("amorcage_impose.", n) + "="
                    + (imposeN.Length > 0 ? "oui" : "non"));
                string aPoser;
                if (cibleAmorcage.IndexOf('{') >= 0)
                    // Le garde d'Amorcer(), rendu SANS lever : --explain doit
                    // rester lisible en session 0, et c'est justement le
                    // controle qui doit montrer ce plan-la avant qu'un jeu ne
                    // le rencontre.
                    aPoser = "non (jeton non substitue dans la cible : "
                        + "relancer « retro scan »)";
                else if (ordreIllisible.Length > 0)
                    // Ni « oui » ni « non » : avec un ordre qu'on n'a pas pu
                    // lire, on ne sait pas si la cible sera reecrite. Trancher
                    // ici rendrait faux le seul controle a distance.
                    aPoser = "inconnu (l'ordre de reamorcage n'a pas pu etre lu)";
                else if (ordre)
                    aPoser = "oui (ordre de reamorcage : la cible sera "
                        + "sauvegardee puis reecrite)";
                else if (File.Exists(Environment.ExpandEnvironmentVariables(
                             cibleAmorcage)))
                    // « si-absent » s'arrete la ; les cles IMPOSEES, elles,
                    // rouvrent ce fichier a chaque lancement. Repondre « non
                    // (la cible existe) » quand il y en a mentirait sur le seul
                    // controle verifiable a distance — et c'est precisement le
                    // fichier du proprietaire qui est en jeu.
                    aPoser = imposeN.Length > 0
                        ? FusionAPoser(cibleAmorcage, imposeN)
                        : "non (la cible existe)";
                else
                    aPoser = "oui";
                rapport.AppendLine(Indice("amorcage_a_poser.", n) + "=" + aPoser);
            }
            if (compte == 0)
                rapport.AppendLine("amorcage_a_poser=" + (ordre
                    ? "rien (ordre sans objet : il sera retire au prochain "
                      + "lancement)"
                    : "rien"));
            Console.Out.Write(rapport.ToString());
            Console.Out.Flush();
            File.WriteAllText(Path.Combine(dossier, "explain.txt"),
                              rapport.ToString(), new UTF8Encoding(false));
            return 0;
        }

        // AVANT de demarrer l'emulateur : une fois le processus lance, ce
        // lanceur peut etre en train de rendre la main, et le temoin
        // decrirait alors une session deja finie.
        InscrireTemoinPads();

        // Avant de lancer : poser la configuration si l'emulateur n'en a
        // aucune. Un echec n'empeche PAS le jeu de demarrer — il ouvrira son
        // assistant, mais le propriétaire aura lu pourquoi. Abandonner ici
        // rendrait la main a Steam, ce qui ressemble exactement a un jeu
        // qu'on vient de quitter.
        try
        {
            Amorcer(p, profilCle);
        }
        catch (Exception e)
        {
            // Le journal garde la trace complete, synchrone, AVANT tout le
            // reste : meme si la boite ne s'affiche jamais, rien n'est perdu.
            Noter("ECHEC de l'amorcage : " + e.Message);
            AvertirEnFond("Console rétro — configuration non posée",
                e.Message + "\n\nLe jeu va tout de même démarrer : "
                + "l'émulateur ouvrira peut-être son assistant de "
                + "configuration.");
        }

        IntPtr job = CreerJob();
        if (job == IntPtr.Zero)
            Noter("ATTENTION : job object indisponible — arreter le jeu depuis "
                + "Steam pourrait laisser l'emulateur ouvert.");

        var psi = new ProcessStartInfo(emulateur, commande);
        psi.WorkingDirectory = Valeur(p, "workdir");
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        // Steam pose SDL_GAMECONTROLLER_IGNORE_DEVICES dans l'environnement de
        // ce qu'il lance : la liste des manettes qu'il prend en charge, et
        // 0x045e/0x028e — la Xbox 360 — en fait partie. C'est precisement ce
        // que la manette virtuelle d'Apollo se declare etre. SDL la masque
        // donc a l'emulateur, et Steam ne fournit AUCUN peripherique virtuel
        // en echange tant que Steam Input n'est pas actif sur le raccourci :
        // l'emulateur ne voit plus aucune manette du tout.
        //
        // Mesure sur la machine le 2026-08-28 : le meme outil SDL, dans la
        // meme session, voit UNE manette sans cette variable et ZERO avec.
        // l'emulateur repondait « No matching controllers found » a chaque
        // lancement, sans qu'aucun message ne nomme la cause.
        //
        // La retirer ICI, et pas dans les reglages de Steam : le masquage est
        // repose par le client a chaque lancement, un reglage par raccourci
        // serait a refaire a chaque synchronisation, et ce lanceur est deja le
        // seul passage oblige entre Steam et les emulateurs. Le retrait vaut
        // donc pour les neuf d'un coup.
        psi.EnvironmentVariables.Remove("SDL_GAMECONTROLLER_IGNORE_DEVICES");
        psi.EnvironmentVariables.Remove("SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT");
        // Steam a un SECOND mecanisme, et celui-la ne se neutralise PAS d'ici.
        // Il injecte gameoverlayrenderer64.dll dans tout ce qu'il lance, et
        // cette DLL pose son propre hook sur XInput pour le compte de Steam
        // Input, en dialoguant avec le client par IPC. Priver l'emulateur des
        // variables Steam a bien ete essaye le 2026-08-28 — verifie sur le
        // processus vivant : SteamAppId, SteamGameId et le reste absents,
        // SteamNoOverlayUIDrawing pose — et la manette restait masquee. Le
        // code a ete retire : il ne servait a rien, et il privait au passage
        // le jeu de l'overlay Steam, que le bouton Xbox n'ouvrait plus.
        //
        // La seule parade est un REGLAGE STEAM, hors d'atteinte d'ici :
        // « Desactiver Steam Input » sur le raccourci. Voir le plan du
        // sous-projet E, section « Ce dont la console depend et que le code
        // ne garantit pas ».
        using (var jeu = Process.Start(psi))
        {
            // Avant WaitForExit : entre le demarrage et l'affectation, un
            // arret de Steam laisserait l'emulateur orphelin.
            if (job != IntPtr.Zero && !AssignProcessToJobObject(job, jeu.Handle))
                Noter("ATTENTION : l'emulateur n'a pas pu etre rattache au job "
                    + "— l'arreter depuis Steam pourrait le laisser ouvert.");
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
                + cle + " ». Relancer « retro scan », qui écrit les plans "
                + "— ce message est celui d'un plan écrit par une version "
                + "antérieure de retro.");
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
                    + "maximale. Relancer « retro scan ».");
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
                    // Chaque carte dans son propre try : cette arborescence
                    // contient des sous-cles dont l'ACL refuse la lecture
                    // (« Configuration », entre autres). Une seule d'entre
                    // elles faisait perdre TOUT le calcul, et une RTX 4070 de
                    // 12 Go se retrouvait annoncee a zero — mesure le
                    // 2026-08-27 : « SecurityException : Requested registry
                    // access is not allowed », et la machine classee modeste.
                    try
                    {
                        using (var carte = classe.OpenSubKey(nom))
                        {
                            if (carte == null) continue;
                            object v = carte.GetValue(
                                "HardwareInformation.qwMemorySize");
                            if (v is long && (long)v > meilleure)
                                meilleure = (long)v;
                            else if (v is int && (int)v > meilleure)
                                meilleure = (int)v;
                        }
                    }
                    catch (Exception) { continue; }
                }
                if (meilleure == 0)
                    Noter("VRAM : aucune carte ne publie "
                        + "HardwareInformation.qwMemorySize sous "
                        + "HKLM\\SYSTEM\\...\\Class\\{4d36e968-...}.");
                return (int)(meilleure / (1024 * 1024));
            }
        }
        catch (Exception e)
        {
            // Une VRAM inconnue vaut zéro, et zéro n'est pas une petite carte :
            // c'est une mesure qui n'a pas eu lieu. Le mode `auto` retombe
            // alors sur « modeste », le seul choix qui ne promet rien — mais
            // il faut pouvoir SAVOIR que la mesure a échoué, sinon une machine
            // à 12 Go se voit classer modeste sans que rien ne l'explique.
            Noter("VRAM illisible : " + e.GetType().Name + " : " + e.Message);
            return 0;
        }
    }
}
