@echo off
REM Install Claude Code skills from project to user directory
REM Usage: .claude\install-skills.bat

setlocal

set "SCRIPT_DIR=%~dp0"
set "USER_SKILLS_DIR=%USERPROFILE%\.claude\skills"

echo Installing Claude Code skills...

REM Create user skills directory if not exists
if not exist "%USER_SKILLS_DIR%" mkdir "%USER_SKILLS_DIR%"

REM Copy each skill
for /D %%i in ("%SCRIPT_DIR%skills\*") do (
    echo   Installing: %%~nxi
    xcopy "%%i" "%USER_SKILLS_DIR%\%%~nxi\" /E /I /Y >nul
)

echo.
echo Done! Skills installed to: %USER_SKILLS_DIR%
echo Restart Claude Code to use the new skills.

pause
