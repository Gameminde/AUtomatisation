#!/usr/bin/env python3
"""
Build Content Factory .exe with PyInstaller

Run: python build_exe.py

This creates a standalone .exe that:
- Includes all dependencies
- Works without Python installed
- Can be distributed via Gumroad
"""

import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()


def build_exe():
    """Build the .exe using PyInstaller."""
    print("🔨 Building Content Factory .exe...")
    print("=" * 50)
    
    # Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
    
    # PyInstaller command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', 'ContentFactory',
        '--onefile',  # Single .exe file
        '--windowed',  # No console window (optional)
        '--icon', str(BASE_DIR / 'static' / 'icon.ico') if (BASE_DIR / 'static' / 'icon.ico').exists() else '',
        '--add-data', f'{BASE_DIR / "templates"};templates',
        '--add-data', f'{BASE_DIR / "static"};static',
        '--add-data', f'{BASE_DIR / "fonts"};fonts' if (BASE_DIR / 'fonts').exists() else '',
        '--hidden-import', 'flask',
        '--hidden-import', 'flask_cors',
        '--hidden-import', 'PIL',
        '--hidden-import', 'arabic_reshaper',
        '--hidden-import', 'bidi.algorithm',
        '--hidden-import', 'feedparser',
        '--hidden-import', 'requests',
        '--hidden-import', 'dotenv',
        '--hidden-import', 'supabase',
        '--hidden-import', 'cryptography',
        '--collect-all', 'flask',
        '--collect-all', 'PIL',
        str(BASE_DIR / 'launcher.py'),
    ]
    
    # Remove empty arguments
    cmd = [c for c in cmd if c]
    
    print(f"Running: {' '.join(cmd[:5])}...")
    
    try:
        subprocess.run(cmd, check=True, cwd=str(BASE_DIR))
        
        # Success message
        exe_path = BASE_DIR / 'dist' / 'ContentFactory.exe'
        if exe_path.exists():
            print("\n" + "=" * 50)
            print("✅ Build successful!")
            print(f"📁 .exe location: {exe_path}")
            print(f"📊 Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
            print("=" * 50)
            print("\n📦 To create Gumroad package:")
            print("1. Copy 'dist/ContentFactory.exe' to a new folder")
            print("2. Add: .env.example, README.md, templates/, static/")
            print("3. Add: video guides (Loom links)")
            print("4. Zip everything")
            print("5. Upload to Gumroad!")
        else:
            print("❌ .exe not found in dist/")
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. pip install pyinstaller")
        print("2. Check for import errors")
        print("3. Try: pyinstaller --debug launcher.py")


def create_simple_batch():
    """Create a simple batch file as backup."""
    batch_content = """@echo off
title Content Factory v2.0
echo.
echo ========================================
echo   Content Factory v2.0 - Starting...
echo ========================================
echo.

REM Check Python
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\\Scripts\\activate
    pip install -r requirements.txt
) else (
    call venv\\Scripts\\activate
)

REM Run launcher
python launcher.py

pause
"""
    
    batch_file = BASE_DIR / 'start.bat'
    batch_file.write_text(batch_content)
    print(f"✅ Created {batch_file}")


if __name__ == "__main__":
    print("🚀 Content Factory Build Tool")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--batch':
        create_simple_batch()
    else:
        build_exe()
        create_simple_batch()
