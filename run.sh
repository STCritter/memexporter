#!/bin/bash
cd "$(dirname "$0")"

if [ ! -f ".installed" ]; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
    playwright install chromium
    touch .installed
    echo
fi

python3 memexporter.py "$@"
