#!/bin/bash
set -e
echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║   Termux AI Agent v3.0 — Setup                  ║"
echo "  ║   DeepSeek V4 Flash × wujie272 MCP (80 tools)   ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""

# Install Python deps
echo "  ⟳ Installing Python packages..."
pip3 install requests mcp 2>&1 | tail -3 || true
pip3 install requests mcp --break-system-packages 2>&1 | tail -3 || true

# Make agent executable
chmod +x "$(dirname "$0")/agent.py" 2>/dev/null || true

# Create symlink
ln -sf "$(dirname "$0")/agent.py" "$HOME/termux-ai"
echo "  ✓ Symlink: ~/termux-ai → $(dirname "$0")/agent.py"
echo ""
echo "  ─────────────────────────────────────────────────"
echo "  ✅ Setup complete!"
echo "  Run:  cd $(dirname "$0") && python3 agent.py"
echo "  Or:   ~/termux-ai"
echo "  ─────────────────────────────────────────────────"
