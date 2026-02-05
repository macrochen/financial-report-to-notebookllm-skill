#!/bin/bash

# Financial Report to NotebookLM - Installation Script

set -e

echo "🚀 Installing Financial Report to NotebookLM Skill..."

# Get the directory where the script is located
SKILL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SKILL_DIR"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 could not be found."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

echo "📦 Installing dependencies from requirements.txt..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install httpx[socks] httpx[http2] pymupdf pymupdf4llm notebooklm-py html2text lxml

echo "🌐 Installing Chromium for Playwright..."
.venv/bin/playwright install chromium

echo "✅ Installation complete!"
echo ""
echo "👉 NEXT STEP: Authenticate with NotebookLM if you haven't already:"
echo "   $SKILL_DIR/.venv/bin/notebooklm login"
echo ""
echo "📊 To analyze a stock, run:"
echo "   $SKILL_DIR/scripts/run.py <stock_code_or_name>"
