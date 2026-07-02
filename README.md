# Termux AI Agent v3.0 ⚡

**AI assistant that controls your Android phone via Termux.**  
Uses **DeepSeek V4 Flash** (free, opencode.ai) + **wujie272/termux-mcp** (80 MCP tools).

```
You ──> DeepSeek V4 Flash ──> MCP JSON-RPC ──> wujie272/termux-mcp ──> Android
         (free / SSE streaming)   (stdio pipe)     (80 tools via FastMCP)
```

## ✨ Features

- **SSE Streaming** — See AI responses appear in real-time as they're generated
- **Reasoning Display** — Watch the model "think" before answering (dimmed text)
- **Long Text Generation** — Full 65K token context for poems, code, analysis
- **Long Text Input** — Multiline mode (`"""..."""`) and file input (`@file.txt`)
- **80 MCP Tools** — Shell, file system, UI automation, ADB/Shizuku, apps, SMS, GitHub, sensors, media
- **Auto-Installer** — First run clones wujie272/termux-mcp automatically
- **GitHub Tools** — Search repos, list issues, browse files, get languages
- **Futuristic UI** — Colored terminal with borders, spinners, and tool call display

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/tundefund0-gif/termux-ai-agent
cd termux-ai-agent

# Run (auto-installs MCP server on first launch)
python3 agent.py
```

Or use the launcher:
```bash
./start-agent.sh
```

## 📋 Available Commands

| Command | Description |
|---|---|
| `/clear` | Clear conversation history |
| `/bye` or `exit` or `quit` | Exit the agent |
| `/help` | Show help |
| `"""..."""` | Multiline text input |
| `@/path/to/file` | Read input from a file |

## 🔧 Requirements

- Termux from F-Droid
- Python 3.10+
- Internet connection
- `git` (`pkg install git`)
- `requests` (`pip install requests`)

### Optional: Termux:API

Install `Termux:API` from F-Droid for:
- Battery status
- GPS location
- Camera
- SMS
- Notifications
- TTS (text-to-speech)
- Sensors

### Optional: GitHub Tools

Set `GITHUB_TOKEN` environment variable:
```bash
export GITHUB_TOKEN="your_github_token"
```

## 🛠 Architecture

```
agent.py
├── LLM class → DeepSeek V4 Flash (SSE streaming, opencode.ai)
├── MCP class → wujie272/termux-mcp (JSON-RPC 2.0 over stdio)
│   └── 80 tools:
│       ├── device_info   — battery, storage, WiFi, sensors, display
│       ├── execute       — shell commands (execute_command)
│       ├── file_system   — read, write, edit, search, copy, move, delete
│       ├── ui_smart      — click, swipe, type, find elements, screenshot
│       ├── app_management — list, launch, uninstall, app stats
│       ├── communication  — SMS, clipboard, contacts, notifications
│       ├── system_control — volume, brightness, torch, vibrate, restart
│       ├── adb           — ADB connection and device management
│       ├── shizuku_window — Shizuku service management
│       └── github        — repos, issues, files, search, languages
└── Chat loop with history trimming
```

## 💡 How It Works

1. **You type a command** — The agent sends it to DeepSeek V4 Flash
2. **DeepSeek decides** — Either responds with text OR calls a tool
3. **If tool call** — Agent executes the tool via MCP protocol and feeds result back
4. **Streaming response** — Text responses stream character-by-character via SSE
5. **Reasoning shown** — The model's "thinking" process is displayed in dim text

## 🌐 API Configuration

Default (free, no key needed):
- **Endpoint**: `https://opencode.ai/zen/v1/chat/completions`
- **Model**: `deepseek-v4-flash-free`
- **Max Tokens**: 65,536

Custom config file: `~/.termux-agent.json`
```json
{
  "api_key": "your-key",
  "base_url": "https://opencode.ai/zen/v1",
  "model": "deepseek-v4-flash-free",
  "max_tokens": 65536,
  "temperature": 0.7,
  "top_p": 0.95
}
```
