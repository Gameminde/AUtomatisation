@echo off
chcp 65001 > nul
title Content Factory v2.0

echo.
echo ========================================
echo   🚀 Content Factory v2.0
echo   Gumroad Edition
echo ========================================
echo.

REM Check if Python is installed
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ خطأ: Python غير مثبت!
    echo.
    echo الرجاء تثبيت Python 3.10+ من:
    echo https://www.python.org/downloads/
    echo.
    echo تأكد من تحديد "Add Python to PATH" عند التثبيت
    echo.
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version') do set PYVER=%%i
echo ✅ Python %PYVER% موجود

REM Install dependencies if needed (first run)
if not exist "venv" (
    echo.
    echo 📦 أول تشغيل - جاري تثبيت المتطلبات...
    echo قد يستغرق هذا دقيقة أو دقيقتين...
    echo.
    
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet
    
    echo.
    echo ✅ تم تثبيت المتطلبات!
) else (
    call venv\Scripts\activate.bat
)

REM Create .env from example if not exists
if not exist ".env" (
    if exist "env.example" (
        copy env.example .env > nul
        echo 📝 تم إنشاء ملف .env
    )
    if exist ".env.example" (
        copy .env.example .env > nul
        echo 📝 تم إنشاء ملف .env
    )
)

echo.
echo 🌐 جاري تشغيل الخادم...
echo.

REM Run the launcher
python launcher.py

REM If launcher exits, pause
echo.
echo 👋 تم إيقاف Content Factory
pause
