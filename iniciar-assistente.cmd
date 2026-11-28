@echo off
rem Liga o Assistente da Live Rodikil em segundo plano (chat sempre pronto + clipes para Shorts).
rem Para ligar junto com o Windows: Win+R, digite shell:startup e coloque um ATALHO deste arquivo nessa pasta.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" "scripts\assistente_live.py"
echo Assistente da Live ligado (log em logs\assistente.log).
timeout /t 3 >nul
