@echo off
title DEMO PROSPECTION INFOSOLUCES
color 0E
echo ============================================================
echo   🚀 DEMO PROSPECTION INFOSOLUCES
echo   5 cas concrets : Developpement, Cybersecurite, ERP,
echo                    Reseau, Infogerance
echo ============================================================
echo.
echo Generation de 5 emails personnalises via DeepSeek...
echo (cette etape prend environ 2-3 minutes)
echo.
echo Lancement en cours...
echo.

set PYTHONIOENCODING=utf-8
python A:\Projets\scrapp-infosoluces\demo_prospection.py

echo.
echo ============================================================
echo   DEMO TERMINEE
echo.
echo   Appuie sur une touche pour ouvrir TOUS les fichiers HTML
echo   dans ton navigateur...
echo ============================================================
pause >nul

start "" "A:\Projets\scrapp-infosoluces\demo_prospection_1.html"
start "" "A:\Projets\scrapp-infosoluces\demo_prospection_2.html"
start "" "A:\Projets\scrapp-infosoluces\demo_prospection_3.html"
start "" "A:\Projets\scrapp-infosoluces\demo_prospection_4.html"
start "" "A:\Projets\scrapp-infosoluces\demo_prospection_5.html"

echo.
echo  ✅ 5 fichiers ouverts dans le navigateur !
echo  Appuie sur une touche pour fermer...
pause >nul
