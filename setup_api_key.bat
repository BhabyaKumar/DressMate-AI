@echo off
REM Quick setup script for Gemini API key

echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║  DressMate AI Stylist - API Key Setup                     ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

echo Your current API key status:
python -c "exec(\"import os; f=open('.env');api=[l for l in f if l.startswith('GEMINI_API_KEY')]; print('Set' if api and 'YOUR_GEMINI' not in api[0] else 'NOT SET (placeholder)')\") 2>nul || echo "Status: unknown"

echo.
echo To get your API key:
echo 1. Go to: https://ai.google.dev/
echo 2. Click "Get API Key" button
echo 3. Copy the key
echo.

set /p key="Paste your API key here: "

if "%key%"=="" (
    echo Error: No key provided
    pause
    exit /b 1
)

REM Update .env file
(
    echo # Gemini Configuration
    echo GEMINI_API_KEY=%key%
) > .env.tmp

REM Add other settings from original .env if they exist
type .env | find /v "GEMINI_API_KEY" >> .env.tmp 2>nul

move /y .env.tmp .env

echo.
echo Updated! Restarting backend server...
echo.
pause
