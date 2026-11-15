@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Sincronizando a pasta NAM do MX5 com os presets do Anxiety OD...
echo (MX5 ligado no USB, na tela normal, e MX-Edit fechado)
echo.
uv run --python 3.12 --no-project python "%~dp0nam_presets.py" %*
echo.
pause
