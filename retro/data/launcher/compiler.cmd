@echo off
chcp 65001 >nul
setlocal

rem Compile le lanceur commun de la console rétro.
rem
rem csc.exe du .NET Framework est présent sur toute installation de Windows
rem depuis la 4.x : aucun outil à télécharger, aucune empreinte à épingler,
rem et le binaire se reconstruit à l'identique depuis la source versionnée.
rem
rem /target:winexe est TOUTE la raison d'être de ce lanceur côté fenêtre : un
rem programme console fait ouvrir une console noire par Windows. Le sous-système
rem se choisit à la compilation ; le corriger après coup dans l'en-tête PE d'un
rem exécutable .NET déjà lié l'empêche de démarrer.

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
