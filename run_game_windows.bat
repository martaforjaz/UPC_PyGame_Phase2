@echo off
REM Dieses Skript startet die UPC_PyGame-Simulation, indem es den Server und die Agents startet.

REM Setze den PYTHONPATH auf den Projektstamm
set PYTHONPATH=%cd%

REM Starte main.py in einem neuen Fenster
echo Starting game (main.py)...
start "Game" python main.py

REM Warte 5 Sekunden, damit der Server Zeit zum Starten hat
timeout /t 5 /nobreak

REM Liste alle Agent-Skripte im Ordner "agents" auf
set "AGENTS_DIR=%cd%\agents"
echo Automatically detecting agents in %AGENTS_DIR%...
for %%F in ("%AGENTS_DIR%\*.py") do (
    echo Detected agent: %%~nxF
)

REM Starte alle gefundenen Agents
for %%F in ("%AGENTS_DIR%\*.py") do (
    echo Starting %%~nxF...
    REM Hier wird per -m der Modulpfad verwendet: "agents.AGENTNAME"
    start "Agent" pythonw -m agents.%%~nF
)

REM Warten bis main.py (Spiel) beendet wird (optional)
echo Waiting for main process (main.py) to finish...
timeout /t 5 /nobreak
exit