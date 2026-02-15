#!/bin/bash

echo ""
echo "========================================"
echo "  🚀 Content Factory v2.0"
echo "  Gumroad Edition"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 not found!"
    echo ""
    echo "Please install Python 3.10+ from:"
    echo "https://www.python.org/downloads/"
    exit 1
fi

PYVER=$(python3 --version)
echo "✅ $PYVER found"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 First run - installing dependencies..."
    echo ""
    
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    
    echo ""
    echo "✅ Dependencies installed!"
else
    source venv/bin/activate
fi

# Create .env from example if not exists
if [ ! -f ".env" ]; then
    if [ -f "env.example" ]; then
        cp env.example .env
        echo "📝 Created .env file"
    elif [ -f ".env.example" ]; then
        cp .env.example .env
        echo "📝 Created .env file"
    fi
fi

echo ""
echo "🌐 Starting server..."
echo ""

# Run the launcher
python3 launcher.py

echo ""
echo "👋 Content Factory stopped"
