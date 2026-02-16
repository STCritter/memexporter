#!/bin/bash
cd "$(dirname "$0")"

if [ ! -f ".installed" ]; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo
        echo "ERROR: Failed to install dependencies. Make sure Python 3 is installed."
        read -p "Press Enter to close..."
        exit 1
    fi
    playwright install chromium
    touch .installed
    echo
fi

python3 memexporter.py "$@"
echo
echo "Exports are saved in: $(pwd)/exports/"
echo
read -p "Press Enter to close..."
