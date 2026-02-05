#!/bin/bash

# Financial Report to NotebookLM - Installation Script

set -e

echo "🚀 Installing Financial Report to NotebookLM Skill..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 could not be found."
    exit 1
fi

echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo "🌐 Installing Chromium for Playwright..."
playwright install chromium

echo "✅ Installation complete!"
echo ""
echo "👉 NEXT STEP: Authenticate with NotebookLM if you haven't already:"
echo "   notebooklm login"
echo ""
echo "📊 To analyze a stock, run:"
echo "   python3 scripts/run.py <stock_code_or_name>"
