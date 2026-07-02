# Termux AI Agent v4.0 ⚡

**AI assistant that controls your Android phone via Termux.**  
Uses **DeepSeek V4 Flash** (free, opencode.ai) + **termuxgpt/termux-mcp** (103 REST API tools).

```
You ──> DeepSeek V4 Flash ──> REST API ──> termuxgpt/termux-mcp ──> Android
         (free / SSE streaming)  (port 8080)   (103 tools via HTTP)
```

## ✨ Features

- **103 Tools** — File system, shell, SMS, calls, camera, sensors, WiFi, GitHub, media, UI, network, and more
- **SSE Streaming** — See AI reasoning in real-time
- **Reasoning Display** — Watch the model "think" (dimmed text)
- **Smart Loop Detection** — Prevents infinite tool-calling (3 rounds max)
- **Long Text** — 65K token context for poems, code, analysis
- **Multiline Input** — `"""..."""` for pasting large text
- **File Input** — `@/path/to/file` to read from a file

## 🚀 Quick Start

```bash
git clone https://github.com/tundefund0-gif/termux-ai-agent
cd termux-ai-agent
python3 agent.py
```

First run auto-clones [termuxgpt/termux-mcp](https://github.com/termuxgpt/termux-mcp) and starts the server.

## 📋 Commands

| Command | Description |
|---|---|
| `/clear` | Clear chat history |
| `/bye` or `exit` | Exit |
| `/help` | Show help |
| `"""..."""` | Multiline input |
| `@file` | Read from file |

## 🛠 103 Tools

shell, file system, SMS, calls, camera, sensors, WiFi, Bluetooth, clipboard, notifications, media, GitHub, device info, battery, location, apps, UI, network, and more.

## 🌐 API (free, no key)

- **Endpoint**: `https://opencode.ai/zen/v1/chat/completions`
- **Model**: `deepseek-v4-flash-free`
- Config at `~/.termux-agent.json`
