@echo off
setlocal
cd /d "%~dp0"
where gh >nul 2>&1
if errorlevel 1 (
  echo GitHub CLI not found. Install it from https://cli.github.com/
  pause
  exit /b 1
)
gh auth status >nul 2>&1
if errorlevel 1 (
  echo Please authenticate GitHub CLI using: gh auth login
  pause
  exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.11+ and retry.
  pause
  exit /b 1
)
echo Opening private editorial inbox at http://127.0.0.1:8765/
echo Copy that address into your browser. Press Ctrl+C to stop.
py -3 -m newsbot.editorial_inbox --repo varadachiru/x-news-automation
if errorlevel 1 pause
endlocal
