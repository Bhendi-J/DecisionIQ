@echo off
setlocal

cd /d "%~dp0"

echo ===================================================
echo     Promoting Accounts to Admin & Rebuilding UI
echo ===================================================

echo.
echo [1/2] Updating database to grant Administrator access...
if exist "data\dashboard.sqlite3" (
    python -c "import sqlite3; con=sqlite3.connect('data/dashboard.sqlite3'); cur=con.cursor(); cur.execute('UPDATE users SET is_admin=1'); con.commit(); print(f'Success: Granted Administrator access to {cur.rowcount} user(s).')" 2>nul
    if errorlevel 1 (
        uv run python -c "import sqlite3; con=sqlite3.connect('data/dashboard.sqlite3'); cur=con.cursor(); cur.execute('UPDATE users SET is_admin=1'); con.commit(); print(f'Success: Granted Administrator access to {cur.rowcount} user(s).')" 2>nul
    )
) else (
    echo Note: Database not found yet. Register an account first, then run this.
)

echo.
echo [2/2] Rebuilding frontend with latest changes from git pull...
call npm --prefix frontend run build

echo.
echo ===================================================
echo Done! Please refresh your browser (Ctrl + F5).
echo You will now see 'Model Lab' in the sidebar under EXPLORE.
echo ===================================================
pause

