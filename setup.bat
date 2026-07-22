@echo off
chcp 65001 >nul
REM ==========================================================================
REM  compy-ui setup (Windows) - self-contained.
REM  Creates a virtual env, installs deps, downloads the local TTS models,
REM  and checks ffmpeg + ComfyUI. Run this once before run.bat.
REM  ComfyUI itself is NOT installed here - you run ComfyUI separately and
REM  this app connects to it (default http://127.0.0.1:8188).
REM ==========================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (echo [error] Install Python 3.11-3.13 first. & pause & exit /b 1)

echo [setup] Creating virtual environment (.venv)
if not exist ".venv\Scripts\python.exe" python -m venv .venv || (pause & exit /b 1)

echo [setup] Installing dependencies
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)

echo [setup] Checking ffmpeg
where ffmpeg >nul 2>nul || echo [warn] ffmpeg not on PATH. Install: winget install Gyan.FFmpeg

echo [setup] Checking Supertonic-3 TTS models (assets_supertonic\onnx)
if exist "assets_supertonic\onnx\vocoder.onnx" (
  echo   models already present - skip.
) else (
  echo   models not found. Downloading Supertonic-3 from HuggingFace ^(~800MB, needs git-lfs^).
  powershell -ExecutionPolicy Bypass -File "scripts\setup_assets.ps1"
)

echo [setup] Preparing .env
if not exist ".env" (
  if exist ".env.example" ( copy /y ".env.example" ".env" >nul & echo   created .env from .env.example )
) else (
  echo   .env already present - keep.
)

echo [setup] Checking ComfyUI connection (optional)
".venv\Scripts\python.exe" -m comfy.check
echo   ^(If ComfyUI is not running yet, start it and re-run: .venv\Scripts\python -m comfy.check^)

echo.
echo [setup] Done. Start ComfyUI, then double-click run.bat (the browser opens automatically).
pause
endlocal
