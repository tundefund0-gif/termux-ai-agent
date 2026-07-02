# Termux AI Agent

AI assistant that controls your Android phone via Termux. Uses **DeepSeek V4 Flash** (free) + **[wujie272/termux-mcp](https://github.com/wujie272/termux-mcp)** (MCP protocol, 72 tools).

## What it does

One command → AI has full control of your device via MCP protocol:
- **Shell** — execute commands, manage files
- **Device** — sensors, battery, display, WiFi, clipboard
- **UI Automation** — click by text/ID/class, swipe, type, screenshot
- **Apps** — list, launch, uninstall, usage stats
- **Communication** — SMS, calls, clipboard, TTS
- **System** — ADB/Shizuku, GitHub, job management
- **Media** — camera, screen record, vibration, torch

## Quick start

```bash
git clone https://github.com/tundefund0-gif/termux-ai-agent
cd termux-ai-agent
python3 agent.py
```

The first run will automatically:
1. Clone [wujie272/termux-mcp](https://github.com/wujie272/termux-mcp) (~72 tools)
2. Install Python dependencies (`mcp` package)
3. Start the MCP server and connect

## Architecture

```
You ──> DeepSeek V4 Flash ──> MCP JSON-RPC ──> wujie272/termux-mcp ──> Android
         (free OpenCode)       (stdio pipe)      (72 tools via FastMCP)
```

- **API**: `opencode.ai/zen/v1` — free, no key needed
- **Model**: `deepseek-v4-flash-free`
- **Protocol**: MCP (Model Context Protocol) — JSON-RPC 2.0 over stdio
- **Server**: [wujie272/termux-mcp](https://github.com/wujie272/termux-mcp) — built on FastMCP

## Requirements

- Termux from F-Droid
- Python 3.10+
- Internet connection
- `git` (`pkg install git`)
