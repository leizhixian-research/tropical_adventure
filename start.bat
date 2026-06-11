@echo off
setlocal

cd /d "%~dp0"

echo Tropical Adventure
echo.

:ask_host
set "HOST="
set /p "HOST=Server IP or host [127.0.0.1]: "
if "%HOST%"=="" set "HOST=127.0.0.1"

set "PORT="
set /p "PORT=Port [12222]: "
if "%PORT%"=="" set "PORT=12222"

:ask_name
set "PLAYER_NAME="
set /p "PLAYER_NAME=Player name: "
if "%PLAYER_NAME%"=="" (
    echo Player name is required.
    goto ask_name
)

:ask_lang
set "LANG="
set /p "LANG=Language en/zh [zh]: "
if "%LANG%"=="" set "LANG=zh"
if /I not "%LANG%"=="en" if /I not "%LANG%"=="zh" (
    echo Language must be en or zh.
    goto ask_lang
)

set "INVITE="
set /p "INVITE=Invite code, blank if none: "

echo.
echo Connecting...
echo.

if "%INVITE%"=="" (
    uv run python -m tropical_adventure.client --host "%HOST%" --port "%PORT%" --name "%PLAYER_NAME%" --lang "%LANG%"
) else (
    uv run python -m tropical_adventure.client --host "%HOST%" --port "%PORT%" --name "%PLAYER_NAME%" --lang "%LANG%" --invite "%INVITE%"
)

if errorlevel 1 (
    echo.
    echo The client exited with an error. Check uv, the server IP, port, invite code, and Python dependencies.
    pause
)
