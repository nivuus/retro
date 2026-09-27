// retro-eeprom — the console language inside an Xbox EEPROM image.
//
// xemu reads the language games see from its EEPROM (sys.files.eeprom_path,
// eeprom.bin next to xemu.toml), never from xemu.toml: an Xbox game asks
// the kernel, and the kernel reads the EEPROM. xemu generates that file
// itself at first start, with this console's serial number, MAC address
// and hard-disk key — so retro never POSES one, it changes one value in it.
//
// The layout is xemu's (hw/xbox/eeprom_generation.h, revision fc24584):
// a 256-byte image whose user section starts at 0x64, 0x5C bytes long,
// guarded by user_checksum at 0x60; the language is the little-endian u32
// at user_section + 0x2C = 0x90. The checksum is xbox_eeprom_crc from the
// same file, transcribed below. Nothing outside 0x60-0x63 and 0x90-0x93 is
// ever written: the factory and security sections hold the keys that
// unlock the hard disk, and a byte changed there would lock the saves.
//
// The fragment is text, "language = <n>", with <n> an XC_LANGUAGE code
// (1 English ... 9 Portuguese); retro/dialectes.py (`valider_eeprom`)
// refuses any other key or value before a plan is ever written.
using System;
using System.Globalization;
using System.IO;

static class EepromXbox
{
    const int TAILLE = 256;
    const int SOMME_UTILISATEUR = 0x60;
    const int SECTION_UTILISATEUR = 0x64;
    const int LONGUEUR_UTILISATEUR = 0x5C;
    const int LANGUE = 0x90;

    // The image with `fragment`'s language, or null when it already holds
    // it. Throws on anything that is not an intact Xbox EEPROM: a checksum
    // that does not match means the file is not what the plan believes, and
    // rewriting it would hand the kernel a user section it rejects.
    public static byte[] Poser(byte[] image, string fragment, string cible,
                               out int avant, out int apres)
    {
        if (image.Length != TAILLE)
            throw new Exception(
                "The Xbox EEPROM is " + image.Length.ToString(
                    CultureInfo.InvariantCulture)
                + " bytes, not " + TAILLE.ToString(CultureInfo.InvariantCulture)
                + ":\n\n" + cible + "\n\nNothing was written. Delete it to let "
                + "xemu generate a new one, or point the profile elsewhere.");
        uint stockee = BitConverter.ToUInt32(image, SOMME_UTILISATEUR);
        uint calculee = Somme(image, SECTION_UTILISATEUR, LONGUEUR_UTILISATEUR);
        if (stockee != calculee)
            throw new Exception(
                "The Xbox EEPROM's user checksum does not match its content:"
                + "\n\n" + cible + "\n\nNothing was written: this file is not "
                + "an intact EEPROM, and patching it would not make it one.");

        apres = Langue(fragment);
        avant = (int)BitConverter.ToUInt32(image, LANGUE);
        if (avant == apres) return null;

        var sortie = (byte[])image.Clone();
        Array.Copy(BitConverter.GetBytes((uint)apres), 0, sortie, LANGUE, 4);
        Array.Copy(BitConverter.GetBytes(
                       Somme(sortie, SECTION_UTILISATEUR, LONGUEUR_UTILISATEUR)),
                   0, sortie, SOMME_UTILISATEUR, 4);
        return sortie;
    }

    // xbox_eeprom_crc: the 32-bit words summed with an end-around carry,
    // complemented. BitConverter is little-endian on every Windows the
    // launcher runs on, as the file is.
    static uint Somme(byte[] donnees, int debut, int longueur)
    {
        uint haut = 0, bas = 0;
        for (int i = 0; i < longueur / 4; i++)
        {
            uint val = BitConverter.ToUInt32(donnees, debut + 4 * i);
            ulong somme = ((ulong)haut << 32) | bas;
            haut = (uint)((somme + val) >> 32);
            bas += val;
        }
        return ~(haut + bas);
    }

    static int Langue(string fragment)
    {
        foreach (string ligne in fragment.Replace("\r\n", "\n").Split('\n'))
        {
            string nue = ligne.Trim();
            if (nue.Length == 0 || nue[0] == ';' || nue[0] == '#') continue;
            int egal = nue.IndexOf('=');
            int valeur;
            if (egal > 0 && nue.Substring(0, egal).Trim() == "language"
                && int.TryParse(nue.Substring(egal + 1).Trim(),
                                NumberStyles.None, CultureInfo.InvariantCulture,
                                out valeur)
                && valeur >= 1 && valeur <= 9)
                return valeur;
        }
        throw new Exception(
            "The EEPROM language fragment carries no \"language = <1-9>\" "
            + "line. Run « retro scan » from the host to rewrite the plans.");
    }
}

static partial class RetroLaunch
{
    // The language step of AmorcerUne for an Xbox EEPROM target: the same
    // backup, atomic write and journal as FusionnerFragment, on bytes.
    // Returns true when the image was written.
    //
    // AN ABSENT IMAGE IS NOT AN ERROR, AND NOTHING IS CREATED. xemu writes it
    // at its first start with this console's own serial and keys; an image
    // made here would carry none of them. The game of that first start runs
    // in the language xemu generates (English), and the journal says so; the
    // next launch finds the image and patches it.
    static bool PoserLangueEeprom(string cible, string fragment, string profil,
                                  string etiquette)
    {
        if (!File.Exists(fragment))
            throw new Exception(
                "Le fichier de langue est introuvable :\n\n" + fragment
                + "\n\nRelancer « retro scan » depuis l'hôte.");
        if (!File.Exists(cible))
        {
            Noter(etiquette + " : " + cible + " absent — xemu le cree a son "
                  + "premier demarrage, la langue sera posee au lancement "
                  + "suivant");
            return false;
        }
        bool bom;
        string texte = LireTexte(fragment, out bom);
        int avant, apres;
        byte[] image = EepromXbox.Poser(File.ReadAllBytes(cible), texte, cible,
                                        out avant, out apres);
        if (image == null)
        {
            Noter(etiquette + " : " + cible + " deja conforme — aucune "
                  + "sauvegarde, aucune reecriture (eeprom)");
            return false;
        }
        Sauvegarder(cible);
        EcrireOctetsAtomique(cible, image);
        Noter(etiquette + " : " + profil + " -> " + cible + " (eeprom, langue "
              + avant.ToString(CultureInfo.InvariantCulture) + " -> "
              + apres.ToString(CultureInfo.InvariantCulture) + ")");
        return true;
    }
}
