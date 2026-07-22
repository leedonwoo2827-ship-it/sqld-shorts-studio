@echo off
chcp 65001 >nul
REM ==========================================================================
REM  compy-ui web app launcher. Run setup.bat first. Browser opens automatically.
REM  Make sure ComfyUI is running (default http://127.0.0.1:8188) before you
REM  generate images. --reload restarts the server when code changes.
REM ==========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [setup] Virtual environment not found. Run setup.bat first.
  pause
  exit /b 1
)

REM Web app port. Change this one value if the port is in use.
set "PORT=8831"

set "PYTHONPATH=%~dp0;%PYTHONPATH%"
echo [run] Open http://localhost:%PORT% in your browser  (close this window to stop)
echo [run] SQLD 말하는-아바타 쇼츠: http://localhost:%PORT%/shorts  (ComfyUI 'shorts' 인스턴스 먼저 실행)

start "" http://localhost:%PORT%

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --reload --reload-dir app --reload-dir comfy --reload-dir services --reload-dir voicewright --reload-dir mp4maker
endlocal
