@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Read this project's private .env instead of old terminal overrides.
set "AI_MODE="
set "AI_BASE_URL="
set "AI_API_KEY="
set "AI_MODEL="
set "AI_TIMEOUT_SECONDS="

rem Prefer a repaired environment before the original project environment.
set "STUDYBUDDY_PYTHON=%~dp0.venv-repair\Scripts\python.exe"
if not exist "%STUDYBUDDY_PYTHON%" set "STUDYBUDDY_PYTHON=%USERPROFILE%\.venv-repair\Scripts\python.exe"
if not exist "%STUDYBUDDY_PYTHON%" set "STUDYBUDDY_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%STUDYBUDDY_PYTHON%" (
    echo StudyBuddy's Python environment was not found.
    echo Open the project folder and follow the Windows setup steps in README.md.
    pause
    exit /b 1
)

"%STUDYBUDDY_PYTHON%" "%~dp0main.py"
set "STUDYBUDDY_EXIT_CODE=%ERRORLEVEL%"
if not "%STUDYBUDDY_EXIT_CODE%"=="0" (
    echo StudyBuddy stopped with an error. Read the message above.
    pause
)
exit /b %STUDYBUDDY_EXIT_CODE%
