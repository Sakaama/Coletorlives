@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto erro
)
.venv\Scripts\python.exe -c "import flask,waitress,yt_dlp,faster_whisper,numpy,yt_dlp_ejs" >nul 2>nul
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto erro
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo FFmpeg nao encontrado. Adicione a pasta bin do FFmpeg ao PATH.
  goto erro
)
.venv\Scripts\python.exe app.py
if errorlevel 1 goto erro
exit /b 0
:erro
echo Nao foi possivel iniciar. Consulte README.md ou logs\miner.log.
pause
exit /b 1
