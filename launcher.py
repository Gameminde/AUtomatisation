#!/usr/bin/env python3
"""
Content Factory v2.0 - One-Click Launcher

This script:
1. Checks Python dependencies
2. Starts the Flask dashboard
3. Opens the browser automatically
4. Shows a system tray icon (optional)

Double-click to run!
"""

import os
import sys
import time
import webbrowser
import subprocess
import threading
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass
    # Also set environment variable for subprocess
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Get the directory where this script is located
BASE_DIR = Path(__file__).parent.resolve()
os.chdir(BASE_DIR)

# Add base dir to Python path
sys.path.insert(0, str(BASE_DIR))

# Configuration
PORT = int(os.getenv("DASHBOARD_PORT", 5000))
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"


def safe_print(text):
    """Print text, stripping emojis if console doesn't support them."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Remove emojis and try again
        import re
        clean_text = re.sub(r'[^\x00-\x7F]+', '', text)
        print(clean_text)


def print_banner():
    """Print startup banner."""
    safe_print("\n" + "=" * 60)
    safe_print("[+] Content Factory v2.0 - Gumroad Edition")
    safe_print("=" * 60)
    safe_print(f"[>] Starting at: {URL}")
    safe_print("=" * 60 + "\n")


def check_dependencies():
    """Check if required packages are installed."""
    required = ['flask', 'requests', 'dotenv', 'PIL']
    missing = []
    
    for pkg in required:
        try:
            if pkg == 'dotenv':
                import dotenv
            elif pkg == 'PIL':
                import PIL
            else:
                __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        safe_print(f"[!] Missing packages: {missing}")
        safe_print("Installing dependencies...")
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', 
            str(BASE_DIR / 'requirements.txt')
        ], check=False)
        safe_print("[OK] Dependencies installed!")
    
    return True


def create_env_if_missing():
    """Create .env file from example if missing."""
    env_file = BASE_DIR / '.env'
    env_example = BASE_DIR / '.env.example'
    env_example2 = BASE_DIR / 'env.example'
    
    if not env_file.exists():
        safe_print("[>] Creating .env file...")
        
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
        elif env_example2.exists():
            import shutil
            shutil.copy(env_example2, env_file)
        else:
            # Create minimal .env
            env_content = """# Content Factory v2.0 Configuration
# =================================

# AI API (Gemini recommended - FREE!)
# Get key: https://makersuite.google.com/app/apikey
GEMINI_API_KEY=

# Facebook OAuth (configured via dashboard)
# FB_APP_ID=
# FB_APP_SECRET=

# Images (optional - works without it)
# PEXELS_API_KEY=

# Database (SQLite by default, Supabase optional)
# DB_MODE=sqlite
"""
            env_file.write_text(env_content)
        
        safe_print(f"[OK] Created {env_file}")
        safe_print("[!] Please configure your API keys in the setup wizard!")


def open_browser_delayed():
    """Open browser after a short delay."""
    time.sleep(2)
    safe_print(f"[>] Opening browser: {URL}")
    webbrowser.open(URL + "/setup")


def run_dashboard():
    """Run the Flask dashboard."""
    try:
        # Import and run dashboard
        from dashboard_app import app, create_tables_if_not_exist
        
        # Ensure database is ready
        create_tables_if_not_exist()
        
        # Open browser in background thread
        browser_thread = threading.Thread(target=open_browser_delayed, daemon=True)
        browser_thread.start()
        
        safe_print(f"[OK] Server running at {URL}")
        safe_print("[>] Opening setup wizard in browser...")
        safe_print("\n[!] Press Ctrl+C to stop the server\n")
        
        # Run Flask (blocking)
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
        
    except KeyboardInterrupt:
        safe_print("\n\n[>] Shutting down Content Factory...")
        safe_print("[OK] Goodbye!")
    except Exception as e:
        safe_print(f"\n[X] Error: {e}")
        safe_print("\n[?] Troubleshooting:")
        safe_print("1. Make sure port 5000 is not in use")
        safe_print("2. Try: pip install -r requirements.txt")
        safe_print("3. Check .env file for errors")
        input("\nPress Enter to exit...")


def main():
    """Main entry point."""
    print_banner()
    
    # Pre-flight checks
    safe_print("[>] Checking environment...")
    check_dependencies()
    create_env_if_missing()
    
    # License validation
    safe_print("[>] Checking license...")
    try:
        from license_validator import require_license
        require_license()
    except SystemExit:
        safe_print("\n[X] License activation failed. Exiting.")
        sys.exit(1)
    except ImportError:
        safe_print("[!] License module not found — skipping validation")
    except Exception as e:
        safe_print(f"[!] License check error: {e} — continuing anyway")
    
    # Run the dashboard
    run_dashboard()


if __name__ == "__main__":
    main()
