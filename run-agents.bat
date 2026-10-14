@echo off
REM Agentes autónomos: ejecutan las tareas del panel. Pausa desde el panel o creando board\STOP.
cd /d "%~dp0"
where claude >nul 2>nul || (
  echo [!] Claude Code no esta instalado. En PowerShell: irm https://claude.ai/install.ps1 ^| iex
  echo     y despues "claude" una vez para iniciar sesion.
  pause & exit /b 1
)
where git >nul 2>nul || echo [i] Sin git: no habra historial para deshacer cambios de los agentes.
python board\runner.py %*
pause
