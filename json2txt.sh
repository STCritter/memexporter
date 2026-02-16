#!/bin/bash
cd "$(dirname "$0")"

if [ -z "$1" ]; then
    echo "Drag and drop your memories.json file onto this script!"
    echo "Or run: python3 json2txt.py memories.json"
    echo
    read -p "Press Enter to close..."
    exit 1
fi

python3 json2txt.py "$1"
echo
read -p "Press Enter to close..."
