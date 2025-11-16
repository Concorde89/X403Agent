#!/bin/bash
# Run bot with virtual environment activated

cd "$(dirname "$0")"
source venv/bin/activate
cd bot
python3 bot.py

