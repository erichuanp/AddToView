@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   AddToView - Windows launcher
echo   backend  http://0.0.0.0:2232 (LAN-reachable; use http://localhost:2232 locally)
echo   frontend http://0.0.0.0:2233 (LAN-reachable; use http://localhost:2233 locally)
echo ========================================
echo.

REM --- backend ---
if not exist "backend\.venv\Scripts\python.exe" (
  echo [setup] creating backend venv...
  pushd backend
  python -m venv .venv || goto :err
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt || goto :err
  popd
)

if not exist "backend\.env" (
  echo [setup] backend\.env missing -- copying from .env.example
  copy /Y "backend\.env.example" "backend\.env" >nul
)

start "AddToView backend" cmd /k "cd /d %CD%\backend && .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 2232 --reload"

REM --- frontend ---
if not exist "frontend\node_modules" (
  echo [setup] installing frontend deps...
  pushd frontend
  call npm install || goto :err
  popd
)

start "AddToView frontend" cmd /k "cd /d %CD%\frontend && npm run dev"

REM give them a moment, then open browser
timeout /t 4 /nobreak >nul
start "" http://localhost:2233

exit /b 0

:err
echo.
echo [error] setup failed. see messages above.
popd
exit /b 1
