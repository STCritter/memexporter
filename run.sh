#!/bin/bash
cd "$(dirname "$0")"

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo
        echo "ERROR: Could not create virtual environment."
        echo "Make sure python3-venv is installed: sudo apt install python3-venv"
        read -p "Press Enter to close..."
        exit 1
    fi
fi

# Activate venv
source venv/bin/activate

# Install deps on first run
if [ ! -f ".installed" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo
        echo "ERROR: Failed to install dependencies."
        read -p "Press Enter to close..."
        exit 1
    fi
    playwright install chromium firefox
    touch .installed
    echo
fi

python3 memexporter.py "$@"
echo
echo "Exports are saved in: $(pwd)/exports/"
echo
read -p "Press Enter to close..."
