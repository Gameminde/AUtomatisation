@echo off
REM ============================================
REM Content Factory - Windows Task Scheduler Setup
REM ============================================
REM Ce script crée une tâche planifiée pour exécuter
REM le pipeline automatiquement toutes les 4 heures.
REM 
REM Usage: Exécuter en tant qu'administrateur
REM ============================================

echo ===== Content Factory Task Scheduler Setup =====

REM Configuration
set PYTHON_PATH="C:\Users\youcef cheriet\AppData\Local\Programs\Python\Python312\python.exe"
set SCRIPT_PATH="C:\Users\youcefcheriet\agen-automatisation\auto_runner.py"
set TASK_NAME="ContentFactory_AutoRun"
set LOG_PATH="C:\Users\youcefcheriet\agen-automatisation\logs"

REM Créer le dossier logs s'il n'existe pas
if not exist %LOG_PATH% mkdir %LOG_PATH%

REM Supprimer la tâche existante si elle existe
schtasks /Delete /TN %TASK_NAME% /F 2>nul

REM Créer la nouvelle tâche (toutes les 4 heures)
schtasks /Create ^
    /TN %TASK_NAME% ^
    /TR "%PYTHON_PATH% %SCRIPT_PATH% --limit 10 --publish-limit 3" ^
    /SC HOURLY ^
    /MO 4 ^
    /ST 08:00 ^
    /F

echo.
echo ===== Task Created Successfully! =====
echo.
echo Task Name: %TASK_NAME%
echo Schedule: Every 4 hours starting at 08:00
echo.
echo To view the task: taskschd.msc
echo To run manually: schtasks /Run /TN %TASK_NAME%
echo To delete: schtasks /Delete /TN %TASK_NAME%
echo.

pause
