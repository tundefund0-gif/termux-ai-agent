# Termux AI Agent

AI assistant that controls your Android phone via Termux. Uses **DeepSeek V4 Flash** (free) + **termux-mcp** server.

## What it does

One command → AI has full control of your device:
- **Shell** — run commands, manage files, processes
- **Sensors** — battery, GPS, WiFi, camera, fingerprint
- **Communication** — SMS, calls, notifications, TTS
- **System** — git, cron, SSH, packages, backup
- **Media** — photos, screen recording, QR codes, OCR

## Quick start

```bash
git clone https://github.com/tundefund0-gif/termux-ai-agent
cd termux-ai-agent
bash setup.sh
python3 agent.py
```

Or from anywhere after setup:

```bash
python3 ~/termux-ai
```

## Architecture

```
You ──> DeepSeek V4 Flash (free API) ──> termux-mcp ──> Android/ Termux
              │                                │
              │  103 tools                     │  90+ HTTP endpoints
              │  (auto-discovered)             │  (shell, sensors, SMS…)
```

- **API**: `opencode.ai/zen/v1` — free, no key needed
- **Model**: `deepseek-v4-flash-free`
- **Server**: [termux-mcp](https://github.com/termuxgpt/termux-mcp) — auto-starts if not running

## Files

| File | Purpose |
|---|---|
| `agent.py` | The AI agent (339 lines) |
| `setup.sh` | Installs termux-mcp + dependencies |
| `start-agent.sh` | Quick launcher |

## Requirements

- Termux from F-Droid
- Python 3.10+
- Internet connection
