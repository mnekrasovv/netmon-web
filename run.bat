@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "EMBED_MARKER=%SCRIPT_DIR%.python-path"
set "PYTHON_SCRIPT=%SCRIPT_DIR%server.py"

:: Если есть маркер embedded Python — используем его без venv
if exist "%EMBED_MARKER%" (
    set /p PY_EXE=<"%EMBED_MARKER%"
    if exist "!PY_EXE!" (
        echo Using portable Python: !PY_EXE!
        "!PY_EXE!" -c "import fastapi, uvicorn" >nul 2>&1
        if errorlevel 1 (
            echo Installing dependencies into embedded Python...
            "!PY_EXE!" -m pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
        )
        "!PY_EXE!" "%PYTHON_SCRIPT%" %*
        if errorlevel 1 (
            echo.
            echo Server exited with error.
            pause
        )
        exit /b 0
    )
)

:: Иначе — стандартный путь через системный Python + venv
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+ from python.org
    echo         Make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.8+ required.
    python --version
    pause
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate venv.
    pause
    exit /b 1
)

python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

python "%PYTHON_SCRIPT%" %*

if errorlevel 1 (
    echo.
    echo Server exited with error code %errorlevel%.
    pause
)
endlocal
