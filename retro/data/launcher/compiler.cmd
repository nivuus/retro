@echo off
setlocal

rem CE FICHIER EST ENCODE EN CP850, PAS EN UTF-8, ET CE N'EST PAS UN OUBLI.
rem
rem cmd.exe lit un .cmd ligne par ligne dans la page de code OEM active. Un
rem caractere accentue encode en UTF-8 y occupe DEUX octets, dont cmd coupe la
rem ligne : mesure le 2026-08-27, ce script a compile correctement tout en
rem crachant huit "'ucun' is not recognized as an internal or external
rem command" venus de ses propres commentaires. Une reussite qui a l'air d'un
rem echec est aussi mauvaise que l'inverse.
rem
rem En page de code 8 bits, chaque caractere tient sur un octet : le parsing
rem est sur, et "chcp 65001" devient inutile - il ne reparait rien, puisque
rem cmd a deja lu la ligne.

rem Compile le lanceur commun de la console r‚tro.
rem
rem csc.exe du .NET Framework est pr‚sent sur toute installation de Windows
rem depuis la 4.x : aucun outil … t‚l‚charger, aucune empreinte … ‚pingler,
rem et le binaire se reconstruit … l'identique depuis la source versionn‚e.
rem
rem /target:winexe est TOUTE la raison d'ˆtre de ce lanceur c“t‚ fenˆtre : un
rem programme console fait ouvrir une console noire par Windows. Le sous-systŠme
rem se choisit … la compilation ; le corriger aprŠs coup dans l'en-tˆte PE d'un
rem ex‚cutable .NET d‚j… li‚ l'empˆche de d‚marrer.

set "SOURCE=%~dp0retro-launch.cs"
set "SORTIE=%~dp0retro-launch.exe"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if not exist "%CSC%" (
    echo ECHEC : csc.exe introuvable a l'emplacement attendu :
    echo     %CSC%
    echo Le .NET Framework 4.x est-il installe ?
    exit /b 1
)
if not exist "%SOURCE%" (
    echo ECHEC : source introuvable : %SOURCE%
    exit /b 1
)

"%CSC%" /nologo /target:winexe /optimize+ /utf8output ^
        /out:"%SORTIE%" "%SOURCE%"
if errorlevel 1 (
    echo ECHEC : la compilation du lanceur a echoue.
    exit /b 1
)
if not exist "%SORTIE%" (
    echo ECHEC : la compilation n'a signale aucune erreur mais n'a rien produit.
    exit /b 1
)
echo OK : %SORTIE%
exit /b 0
