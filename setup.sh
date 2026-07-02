#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  Termux AI Agent — Setup                    │"
echo "  └─────────────────────────────────────────────┘"
echo ""

# Install mcp package
echo "  ⟳ Installing Python deps..."
pip3 install mcp 2>&1 | tail -3

# Symlink
ln -sf "$DIR/agent.py" "$HOME/termux-ai"
echo "  ✓ Symlink: ~/termux-ai → $DIR/agent.py"

echo ""
echo "  ─────────────────────────────────────────────"
echo "  ✅ Setup complete!"
echo "  Run: python3 ~/termux-ai"
echo "  ─────────────────────────────────────────────"
