#!/bin/bash
# Termux AI Agent — Setup
# Installs termux-mcp server + the AI agent

set -e

echo "  ┌─────────────────────────────────────────────┐"
echo "  │  Termux AI Agent — Setup                    │"
echo "  └─────────────────────────────────────────────┘"
echo ""

# Check termux-mcp
if [ -d "$HOME/termux-mcp" ]; then
    echo "  ✓ termux-mcp already installed"
else
    echo "  ⟳ Installing termux-mcp..."
    cd "$HOME"
    git clone --depth 1 https://github.com/termuxgpt/termux-mcp.git
    echo "  ✓ termux-mcp installed"
fi

# Create symlink
ln -sf "$(pwd)/agent.py" "$HOME/termux-ai"
echo "  ✓ Symlink created: ~/termux-ai"

# Install deps
echo "  ⟳ Checking Python dependencies..."
python3 -c "import requests" 2>/dev/null && echo "  ✓ requests already installed" || {
    pip3 install requests && echo "  ✓ requests installed"
}

echo ""
echo "  ─────────────────────────────────────────────"
echo "  ✅ Setup complete!"
echo ""
echo "  Run the agent:"
echo "    python3 ~/termux-ai"
echo ""
echo "  Or from this folder:"
echo "    python3 agent.py"
echo "  ─────────────────────────────────────────────"
